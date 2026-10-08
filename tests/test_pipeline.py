"""Synthetic, clearly artificial test-only fixtures; dashboard NEVER displays these."""
import numpy as np
import pandas as pd
import pytest
from src.config import ACS_VARS
from src.prepare_panel import normalize_lsc, merge_acs_asof, enrich

@pytest.fixture(autouse=True)
def isolate_diagnostic_outputs(monkeypatch,tmp_path):
    import src.prepare_panel as prep
    monkeypatch.setattr(prep, "OUT", tmp_path)
from src.forecast import make_lags, backtest, upcoming


def example_acs():
    d={v:200. for v in ACS_VARS}
    d.update({'B25003_001E':1000.,'B25003_003E':400.,
              'B25070_001E':400.,'B25070_007E':30.,'B25070_008E':20.,
              'B25070_009E':20.,'B25070_010E':50.,'B25070_011E':40.,
              'B25002_001E':1200.,'B25002_003E':200.,'B25058_001E':1200.,
              'B19013_001E':45000.,'B17001_001E':1000.,'B17001_002E':100.,
              'B23025_003E':600.,'B23025_005E':60.,'B22003_001E':1000.,
              'B22003_002E':200.,'B25040_001E':1000.,'B25040_002E':400.,
              'B25040_003E':50.,'B25040_004E':300.,'B25040_005E':100.})
    return d


def mock_panel(nmonths=45):
    dates=pd.date_range('2022-01-01',periods=nmonths,freq='MS')
    counties=['09001','09003','09005','09007']
    records=[];avs=[]
    for j,f in enumerate(counties):
        for i,t in enumerate(dates):
            records.append({'fips':f,'month':t,'filings':int(15+j*7+(i%12)*2+(i%5))})
        for y in range(2019,2025):
            avs.append({'fips':f,'NAME':f'Test County {j}, Connecticut','acs_year':y,
                        **example_acs()})
    return pd.DataFrame(records),pd.DataFrame(avs)


def test_lsc_observed_count_schema_and_geographic_key():
    acs=pd.DataFrame([{'fips':'09001','NAME':'Fairfield County, Connecticut'}])
    raw=pd.DataFrame({'county_fips':['09001'],'month_date':['2025-06-01'],'filings':['21']})
    x,log=normalize_lsc(raw,acs)
    assert x.loc[0,'filings']==21
    assert x.loc[0,'fips']=='09001'
    assert log['accepted_records']==1


def test_unmatched_rows_not_fabricated_or_assigned_to_county():
    acs=pd.DataFrame([{'fips':'09001','NAME':'Fairfield County, Connecticut'}])
    raw=pd.DataFrame({'county_fips':['99999'],'month_date':['2025-06-01'],'filings':['5']})
    with pytest.raises(ValueError,match='No LSC jurisdiction'):
        normalize_lsc(raw,acs)


def test_duplicate_county_month_fails_closed():
    acs=pd.DataFrame([{'fips':'09001','NAME':'Fairfield County, Connecticut'}])
    raw=pd.DataFrame({'county_fips':['09001','09001'],'month_date':['2025-06-01','2025-06-01'],'filings':['21','21']})
    with pytest.raises(ValueError,match='Duplicate county-month'):
        normalize_lsc(raw,acs)


def test_acs_rentburden_uses_computed_denominator():
    x=pd.DataFrame([{'fips':'09001','month':pd.Timestamp('2025-06-01'),'filings':10,
                      'acs_year':2023,'NAME':'test',**example_acs()}])
    z=enrich(x)
    assert z.rent_burden_30_share.iloc[0]==pytest.approx(120/360)
    assert z.severe_rent_burden_50_share.iloc[0]==pytest.approx(50/360)
    assert z.filings_per_1000_renter_households.iloc[0]==25


def test_acs_vintage_cannot_peek_into_future():
    panel=pd.DataFrame({'fips':['09001']*3,'month':pd.to_datetime(['2025-01-01','2026-01-01','2026-02-01']),'filings':[20,22,25]})
    acs=pd.DataFrame([{'fips':'09001','acs_year':2022,'NAME':'a',**example_acs()},
                      {'fips':'09001','acs_year':2023,'NAME':'a',**example_acs()},
                      {'fips':'09001','acs_year':2024,'NAME':'a',**example_acs()}])
    h1=merge_acs_asof(panel,acs,1)
    assert h1.acs_year.tolist()==[2022,2023,2024]
    h3=merge_acs_asof(panel,acs,3)
    assert h3.acs_year.tolist()==[2022,2023,2023]


def test_monthly_gap_not_silently_treated_as_zero():
    d=pd.DataFrame({'fips':['09001','09001'],'month':pd.to_datetime(['2025-01-01','2025-03-01']),'filings':[7,11]})
    z=make_lags(d,1).set_index('month')
    assert pd.isna(z.loc[pd.Timestamp('2025-02-01'),'filings'])
    assert pd.isna(z.loc[pd.Timestamp('2025-03-01'),'lag_last'])


def test_three_month_horizon_uses_only_counts_known_at_origin():
    d=pd.DataFrame({'fips':['09001']*15,'month':pd.date_range('2024-01-01',periods=15,freq='MS'),'filings':list(range(15))})
    z=make_lags(d,3).set_index('month')
    # At Apr 2025, origin Jan 2025; cannot use February/March 2025 outcomes.
    assert z.loc[pd.Timestamp('2025-03-01'),'lag_last']==9
    assert z.loc[pd.Timestamp('2025-03-01'),'origin_month']==pd.Timestamp('2024-12-01')


def test_rolling_origin_and_forward_predictions_smoke():
    p,a=mock_panel()
    b,m=backtest(p,a,horizon=3,months=2,min_train_months=18)
    assert len(b)>0
    assert (b.origin_month==b.month-pd.DateOffset(months=3)).all()
    assert {'model_history_acs','baseline_last','baseline_seasonal'}.issubset(m.model)
    fc=upcoming(p,a,3)
    assert len(fc)==4
    assert (fc.month==fc.last_observed_month+pd.DateOffset(months=5)).all()
    assert (fc.forecast_issue_month==fc.last_observed_month+pd.DateOffset(months=2)).all()
    assert fc.predicted_filings.ge(0).all()


def test_state_abbreviation_and_three_digit_county_fips():
    acs=pd.DataFrame([{'fips':'42071','NAME':'Lancaster County, Pennsylvania'}])
    raw=pd.DataFrame({'state':['PA'],'county_fips':['071'],'month':['2025-06-01'],'filings':['10']})
    d,_=normalize_lsc(raw,acs)
    assert d.fips.iloc[0]=='42071'
