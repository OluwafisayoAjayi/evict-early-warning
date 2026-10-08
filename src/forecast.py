"""Pooled county-month direct-horizon forecasts with true rolling-origin backtesting.

The training outcome date must be <= the forecast origin date (target - horizon).
Therefore the 3-month-ahead backtest does NOT train using months that were
unavailable when the forecast would have been issued.
"""
import argparse, json
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error
from .config import RAW, OUT
from .prepare_panel import merge_acs_asof, enrich

BASE_FEATURES=['lag_last','lag_2','lag_3','lag_6','lag_12','roll_3','roll_12','month_sin','month_cos']
ACS_FEATURES=['renter_households','renter_share','rent_burden_30_share','severe_rent_burden_50_share',
              'housing_vacancy_share','median_contract_rent','median_household_income',
              'poverty_share','acs_unemployment_share','snap_household_share',
              'heat_utility_gas_share','heat_bottled_gas_share','heat_electricity_share','heat_fuel_oil_share']


def make_lags(counts, horizon, reporting_lag=2):
    if horizon<1: raise ValueError('Forecast horizon must be positive')
    effective_lag=horizon+reporting_lag
    parts=[]
    for fips,g in counts.groupby('fips',sort=False):
        g=g.copy();g['month']=pd.to_datetime(g.month)
        # Month-indexed lags: missing observations stay missing, never become zeros.
        g=g.set_index('month').sort_index().asfreq('MS')
        g['fips']=fips
        for k,n in [('lag_last',effective_lag),('lag_2',effective_lag+1),('lag_3',effective_lag+2),
                    ('lag_6',effective_lag+5),('lag_12',12)]:
            # For h > 12, seasonal feature cannot be observed in origin; restrict to 1 or 3.
            g[k]=g['filings'].shift(n)
        g['roll_3']=g['filings'].shift(effective_lag).rolling(3,min_periods=3).mean()
        g['roll_12']=g['filings'].shift(effective_lag).rolling(12,min_periods=12).mean()
        g['month_sin']=np.sin(2*np.pi*g.index.month/12)
        g['month_cos']=np.cos(2*np.pi*g.index.month/12)
        g['origin_month']=g.index-pd.DateOffset(months=horizon)
        parts.append(g.reset_index())
    return pd.concat(parts,ignore_index=True)


def design(counts,acs,horizon,reporting_lag=2):
    lg=make_lags(counts,horizon,reporting_lag)
    lg=merge_acs_asof(lg,acs,horizon)
    lg=enrich(lg)
    lg['state_fips']=lg.fips.str[:2]
    # Only a very small number of ACS fields are necessary for the outcome denominator.
    lg=lg.loc[lg.renter_households.gt(0)].copy()
    for c in BASE_FEATURES+ACS_FEATURES:
        lg[c]=pd.to_numeric(lg[c],errors='coerce')
    lg=lg.dropna(subset=BASE_FEATURES).copy()
    return lg


def feature_matrix(df,acs_enabled,states=None):
    cols=BASE_FEATURES+(ACS_FEATURES if acs_enabled else [])
    x=df[cols].copy()
    # State is geographic context, not an ordinal numeric ranking.
    d=pd.get_dummies(df.state_fips,prefix='state',dtype=int)
    x=pd.concat([x,d],axis=1)
    if states is not None: x=x.reindex(columns=states,fill_value=0)
    return x.replace([np.inf,-np.inf],np.nan)


def fit_predict(train,test,acs_enabled):
    x=feature_matrix(train,acs_enabled)
    xt=feature_matrix(test,acs_enabled,states=x.columns)
    model=HistGradientBoostingRegressor(loss='poisson',max_iter=95,learning_rate=.055,
                  max_leaf_nodes=15,l2_regularization=5,min_samples_leaf=30,random_state=42)
    model.fit(x,train.filings)
    return np.maximum(0,model.predict(xt))


def backtest(panel,acs,horizon=1,months=9,min_train_months=24,reporting_lag=2):
    design_df=design(panel[['fips','month','filings']],acs,horizon,reporting_lag)
    eligible=design_df.dropna(subset=['filings']).copy()
    all_months=sorted(eligible.month.unique())
    # All counties evaluated in the exact same future months; avoid choosing dates based on outcome quality.
    test_months=all_months[-months:]
    rows=[]
    for t in test_months:
        origin=pd.Timestamp(t)-pd.DateOffset(months=horizon)
        train=eligible.loc[eligible.month<=origin-pd.DateOffset(months=reporting_lag)].copy()
        test=eligible.loc[eligible.month==t].copy()
        nmonths=train.month.nunique()
        if nmonths<min_train_months or len(test)<3 or train.fips.nunique()<3:
            print(f'Skip target {pd.Timestamp(t).date()}, horizon {horizon}: too little training/evaluation data')
            continue
        if train.filings.min()<0: raise ValueError('Negative observed outcome')
        pa=fit_predict(train,test,False)
        pf=fit_predict(train,test,True)
        test=test.copy()
        test['training_cutoff_month']=origin-pd.DateOffset(months=reporting_lag)
        test['baseline_last']=test.lag_last
        test['baseline_seasonal']=test.lag_12
        test['model_history']=pa
        test['model_history_acs']=pf
        rows.append(test[['fips','month','origin_month','training_cutoff_month','filings','renter_households','lag_last','roll_12',
                          'baseline_last','baseline_seasonal','model_history','model_history_acs']])
        print(f'h={horizon}, target={pd.Timestamp(t).strftime("%Y-%m")}, test counties={len(test)}, train={len(train)}',flush=True)
    if not rows: raise RuntimeError('Not enough observed county-month data for honest out-of-time validation')
    b=pd.concat(rows,ignore_index=True)
    b['horizon']=horizon
    b['actual_filings_per_1000_renters']=1000*b.filings/b.renter_households
    # Forecast errors in counts; pooled and county-specific summaries calculated below.
    metrics=[]
    for field in ['baseline_last','baseline_seasonal','model_history','model_history_acs']:
        x=b[[field,'filings']].dropna()
        mae=mean_absolute_error(x.filings,x[field])
        wape=100*np.abs(x.filings-x[field]).sum()/max(x.filings.sum(),1)
        metrics.append({'horizon':horizon,'model':field,'mae_count':round(mae,3),
                        'wape_pct':round(wape,2),'test_county_months':len(x),
                        'test_months':b.month.nunique(),'test_counties':b.fips.nunique()})
    # Emerging hotspot: true future filings >=25% above preceding year average,
    # requiring at least 5 monthly counts to avoid dividing small numbers.
    b['hotspot_truth']=(b.filings>=5)&(b.filings>=1.25*b.roll_12)&(b.roll_12>0)
    for field in ['baseline_seasonal','model_history_acs']:
        alert=(b[field]>=5)&(b[field]>=1.25*b.roll_12)&(b.roll_12>0)
        tp=int((alert&b.hotspot_truth).sum());fp=int((alert&~b.hotspot_truth).sum())
        fn=int((~alert&b.hotspot_truth).sum())
        metrics.append({'horizon':horizon,'model':f'{field}_hotspot_alert',
                        'precision':round(tp/(tp+fp),3) if tp+fp else np.nan,
                        'recall':round(tp/(tp+fn),3) if tp+fn else np.nan,
                        'true_positives':tp,'false_positives':fp,'false_negatives':fn,
                        'test_county_months':len(b),'test_months':b.month.nunique(),'test_counties':b.fips.nunique()})
    return b,pd.DataFrame(metrics)


def upcoming(panel,acs,horizon, reporting_lag=2,reporting_stale_months=0):
    parts=[]
    for fips,g in panel.groupby('fips'):
        g=g[['fips','month','filings']].sort_values('month').copy()
        last=pd.Timestamp(g.month.max())
        # Only forecast counties that have recent actual observed months.
        latest=pd.Timestamp(panel.month.max())
        if last<latest-pd.DateOffset(months=reporting_stale_months):continue
        future=pd.date_range(last+pd.DateOffset(months=1),periods=horizon+reporting_lag,freq='MS')
        parts.append(pd.concat([g,pd.DataFrame({'fips':fips,'month':future,'filings':np.nan})],ignore_index=True))
    if not parts: raise RuntimeError('No continuously covered counties for forecasts')
    panel_full=pd.concat(parts,ignore_index=True)
    dd=design(panel_full,acs,horizon,reporting_lag)
    train=dd.loc[dd.filings.notna()].copy()
    future=dd.loc[dd.filings.isna()].copy()
    future=future.loc[future.month==future.origin_month+pd.DateOffset(months=horizon)].copy()
    # Only choose the horizon-th month after the latest OBSERVED month in each county.
    last_obs=panel.groupby('fips').month.max().rename('last_observed_month')
    future=future.merge(last_obs,on='fips',how='left',validate='many_to_one')
    future=future.loc[future.month==future.last_observed_month+pd.DateOffset(months=horizon+reporting_lag)].copy()
    if future.empty: raise RuntimeError('No valid future rows; check missing lagged months or ACS vintages')
    base=fit_predict(train,future,False)
    full=fit_predict(train,future,True)
    future['baseline_last']=future.lag_last
    future['baseline_seasonal']=future.lag_12
    future['predicted_filings']=full
    future['predicted_filings_history_only']=base
    future['predicted_rate_per_1000_renter_households']=1000*future.predicted_filings/future.renter_households
    future['hotspot_alert']=(future.predicted_filings>=5)&(future.predicted_filings>=1.25*future.roll_12)&future.roll_12.gt(0)
    future['county_name']=future['NAME']
    future['horizon']=horizon
    future['acs_asof_year']=future.acs_year
    future['last_observed_filings']=future.lag_last
    future['reporting_lag_months']=reporting_lag
    future['forecast_issue_month']=future.month-pd.DateOffset(months=horizon)
    return future[['fips','county_name','state_fips','month','last_observed_month','forecast_issue_month','reporting_lag_months','horizon',
                  'predicted_filings','predicted_rate_per_1000_renter_households',
                  'predicted_filings_history_only','baseline_last','baseline_seasonal','last_observed_filings',
                  'renter_households','rent_burden_30_share','severe_rent_burden_50_share','poverty_share',
                  'acs_unemployment_share','heat_electricity_share','heat_fuel_oil_share',
                  'roll_12','acs_asof_year','hotspot_alert']]


def run(horizons=(1,3),test_months=9,reporting_lag=2):
    panel=pd.read_csv(OUT/'county_month.csv',dtype={'fips':'string'},parse_dates=['month'])
    acs=pd.read_csv(RAW/'acs_county_vintages.csv',dtype={'fips':'string'})
    panel.fips=panel.fips.str.zfill(5);acs.fips=acs.fips.str.zfill(5)
    bts=[];scores=[];preds=[]
    for h in horizons:
        bt,mt=backtest(panel,acs,h,months=test_months,reporting_lag=reporting_lag)
        preds.append(upcoming(panel,acs,h,reporting_lag=reporting_lag))
        bts.append(bt);scores.append(mt)
    OUT.mkdir(parents=True,exist_ok=True)
    pd.concat(bts).to_csv(OUT/'rolling_backtests.csv',index=False)
    pd.concat(scores).to_csv(OUT/'model_metrics.csv',index=False)
    pd.concat(preds).to_csv(OUT/'county_forecasts.csv',index=False)
    print(f'Saved empirical backtests, comparisons, and {sum(len(t) for t in preds)} experimental forecasts')
    return pd.concat(scores)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--horizons',nargs='+',type=int,default=[1,3]);p.add_argument('--test-months',type=int,default=9);p.add_argument('--reporting-lag',type=int,default=2)
    a=p.parse_args(); print(run(a.horizons,a.test_months,a.reporting_lag).to_string(index=False))
