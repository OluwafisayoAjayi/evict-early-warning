"""LSC observed county-month filing counts + historically eligible ACS 5-year covariates.

Conservative by design: no unmatched county, date or outcome is invented; no duplicate
jurisdiction-month is summed; no gap is filled with zero; matching uses unique FIPS.
"""
import argparse, json, re
from pathlib import Path
import numpy as np
import pandas as pd
from .config import RAW, OUT, ACS_VARS

STATES={'alabama':'01','alaska':'02','arizona':'04','arkansas':'05','california':'06','colorado':'08','connecticut':'09',
 'delaware':'10','district of columbia':'11','florida':'12','georgia':'13','hawaii':'15','idaho':'16','illinois':'17',
 'indiana':'18','iowa':'19','kansas':'20','kentucky':'21','louisiana':'22','maine':'23','maryland':'24',
 'massachusetts':'25','michigan':'26','minnesota':'27','mississippi':'28','missouri':'29','montana':'30',
 'nebraska':'31','nevada':'32','new hampshire':'33','new jersey':'34','new mexico':'35','new york':'36',
 'north carolina':'37','north dakota':'38','ohio':'39','oklahoma':'40','oregon':'41','pennsylvania':'42',
 'rhode island':'44','south carolina':'45','south dakota':'46','tennessee':'47','texas':'48','utah':'49',
 'vermont':'50','virginia':'51','washington':'53','west virginia':'54','wisconsin':'55','wyoming':'56',
 'puerto rico':'72'}

# Cover all US state abbreviations, not only the first 11 Eviction Lab states.
USPS_CODES = 'AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY PR'.split()
assert len(USPS_CODES) == len(STATES)
ABBREVIATIONS = {a:STATES[n] for a,n in zip(USPS_CODES,STATES)}


def norm(x): return re.sub(r'[^a-z0-9]+','_',str(x).lower()).strip('_')

def pick(d, options):
    cols={norm(c):c for c in d.columns}
    return next((cols[o] for o in options if o in cols),None)

def canonical_county(x):
    s=str(x).split(',')[0].strip().lower().replace('saint ','st ')
    s=re.sub(r'\b(county|parish|borough|municipality|census area|city and borough)\b','',s)
    return re.sub(r'[^a-z0-9]','',s)

def parse_month(d):
    date=pick(d,['month_date','month_start','month_start_date','filing_month','filings_month','date','month_year','year_month','month'])
    year=pick(d,['year','filing_year'])
    month=pick(d,['month_number','month_num','month'])
    if date:
        raw=d[date].astype(str)
        # For numeric month 1..12 coupled with separate year, use separate columns.
        if year is not None and raw.str.fullmatch(r'\d{1,2}(?:\.0)?').fillna(False).mean()>.95:
            v=pd.to_datetime({'year':pd.to_numeric(d[year],errors='coerce'),
                'month':pd.to_numeric(d[date],errors='coerce'),'day':1},errors='coerce')
        else:
            v=pd.to_datetime(raw,errors='coerce')
    elif year and month:
        v=pd.to_datetime({'year':pd.to_numeric(d[year],errors='coerce'),
            'month':pd.to_numeric(d[month],errors='coerce'),'day':1},errors='coerce')
    else: raise ValueError(f'Cannot identify month in LSC CSV; available columns={list(d.columns)}')
    if v.notna().mean()<.99: raise ValueError('Unparseable LSC filing dates; see source schema')
    return v.dt.to_period('M').dt.to_timestamp()


def normalize_lsc(raw, acs):
    raw=raw.copy()
    count=pick(raw,['filings','filing_count','filings_count','eviction_filings','eviction_filing_count','n_filings','case_filings','cases_filed','filings_total','total_filings','evictions','n_cases','cases','count'])
    if count is None: raise ValueError('Cannot find OBSERVED EVICTION FILING COUNT. Got columns: '+repr(raw.columns.tolist())+
                                    '. Edit src/prepare_panel.py after confirming the published export schema.')
    observed=pd.to_numeric(raw[count],errors='coerce')
    if observed.isna().any() or (observed<0).any() or (~np.isfinite(observed)).any() or (observed%1!=0).any():
        raise ValueError(f'LSC {count} contains missing, invalid, negative or fractional counts; inspect official data.')
    months=parse_month(raw)
    # Numerical 5-digit FIPS wins. Do NOT truncate arbitrary noncounty or ZIP identifiers.
    fips_col=pick(raw,['county_geoid','county_fips','county_fips_code','fips','geoid','geo_id','county_id'])
    fips=pd.Series([None]*len(raw),index=raw.index,dtype='object')
    if fips_col:
        candidate=raw[fips_col].astype(str).str.strip().str.replace(r'\.0$','',regex=True)
        valid=candidate.str.fullmatch(r'\d{5}')
        fips.loc[valid]=candidate.loc[valid]
    state_col=pick(raw,['state','state_name','state_abbreviation','state_fips','state_code'])
    county_col=pick(raw,['county','county_name','jurisdiction','jurisdiction_name'])
    state_id=pd.Series([None]*len(raw),index=raw.index,dtype='object')
    if state_col:
        v=raw[state_col].astype('string').str.lower().str.strip()
        state_id=v.map(STATES).astype('string')
        state_id=state_id.fillna(v.where(v.str.fullmatch(r'\d{2}')))
        state_id=state_id.fillna(v.str.upper().map(ABBREVIATIONS))
    # Three-digit county codes are valid only WITH an independently identified two-digit state.
    if fips_col and state_col:
        shortened=raw[fips_col].astype(str).str.strip().str.replace(r'\.0$','',regex=True)
        shortened=shortened.where(shortened.str.fullmatch(r'\d{1,3}'))
        composite=state_id.str.cat(shortened.str.zfill(3),na_rep='')
        verified=composite.isin(acs.fips) & fips.isna()
        fips.loc[verified]=composite.loc[verified]
    if county_col and state_col:
        amap=acs[['fips','NAME']].drop_duplicates('fips').copy()
        amap['state']=amap.fips.str[:2]
        amap['county_normal']=amap.NAME.map(canonical_county)
        if amap.duplicated(['state','county_normal']).any():
            # Unusual ambiguous jurisdiction names; only direct FIPS assignment allowed.
            amap=amap.loc[~amap.duplicated(['state','county_normal'],keep=False)]
        lookup=amap.set_index(['state','county_normal'])['fips'].to_dict()
        lookup2=[lookup.get((s,canonical_county(c))) for s,c in zip(state_id,raw[county_col])]
        fips=fips.fillna(pd.Series(lookup2,index=raw.index))
    d=pd.DataFrame({'fips':fips,'month':months,'filings':observed})
    accepted=set(acs.fips.unique())
    missing=d.fips.isna() | ~d.fips.isin(accepted)
    # NOTE: Source may contain municipalities. Those must never be implicitly treated as counties.
    report={'source_records':len(d),'accepted_records':int((~missing).sum()),
            'unmatched_or_noncounty_records':int(missing.sum()),'count_column':count,
            'date_min':str(d.month.min().date()),'date_max':str(d.month.max().date()),
            'original_columns':list(raw.columns)}
    OUT.mkdir(parents=True,exist_ok=True)
    if missing.any():
        pd.concat([raw.loc[missing].head(1000),d.loc[missing,['fips','month']].add_prefix('_parsed_')],axis=1).to_csv(
            OUT/'unmatched_lsc_rows.csv',index=False)
    d=d.loc[~missing].copy()
    if d.empty: raise ValueError('No LSC jurisdiction could be linked to a unique county FIPS. See unmatched_lsc_rows.csv')
    dupe=d.duplicated(['fips','month'],keep=False)
    if dupe.any():
        d.loc[dupe].to_csv(OUT/'duplicate_lsc_rows.csv',index=False)
        raise ValueError('Duplicate county-month rows in LSC export! Do not sum: inspect duplicate_lsc_rows.csv')
    d['filings']=d.filings.astype(int)
    return d.sort_values(['fips','month']).reset_index(drop=True),report


def add_acs(d,acs):
    d=d.copy(); d['month']=pd.to_datetime(d['month']); acs=acs.copy()
    # At target t, horizon h, latest data available at origin t-h. This function
    # attaches ACS for h=1; forecast(h=3) separately remaps older vintage below.
    return merge_acs_asof(d,acs,horizon=1)


def merge_acs_asof(d,acs,horizon):
    d=d.copy(); acs=acs.copy()
    d['month']=pd.to_datetime(d['month'])
    origin=d['month']-pd.DateOffset(months=horizon)
    year=origin.dt.year-2
    maxyear=int(acs.acs_year.max())
    d['acs_year']=year.clip(upper=maxyear)
    acs['fips']=acs.fips.astype(str).str.zfill(5)
    # Use last available vintage no later than eligibility year; do not use contemporaneous data.
    v=sorted(int(a) for a in acs.acs_year.unique())
    d['acs_year']=d['acs_year'].apply(lambda y:max((z for z in v if z<=y),default=-1)).astype(int)
    merge=d.merge(acs,on=['fips','acs_year'],how='left',validate='many_to_one',indicator=True)
    if merge['_merge'].eq('left_only').any():
        # Early dates lacking historical ACS removed, never assigned an artificially current vintage.
        merge=merge.loc[merge['_merge'].eq('both')].copy()
    merge=merge.drop(columns='_merge')
    return merge


def enrich(d):
    x=d.copy(); g=lambda key:x[key]
    def share(n,den):
        return (n/den.replace(0,np.nan)).where(den>0)
    x['renter_households']=g('B25003_003E')
    x['renter_share']=share(g('B25003_003E'),g('B25003_001E'))
    rentbase=g('B25070_001E')-g('B25070_011E')
    rentburden=x[['B25070_007E','B25070_008E','B25070_009E','B25070_010E']].sum(axis=1,min_count=4)
    x['rent_burden_30_share']=share(rentburden,rentbase)
    x['severe_rent_burden_50_share']=share(g('B25070_010E'),rentbase)
    x['housing_vacancy_share']=share(g('B25002_003E'),g('B25002_001E'))
    x['median_contract_rent']=g('B25058_001E')
    x['median_household_income']=g('B19013_001E')
    x['poverty_share']=share(g('B17001_002E'),g('B17001_001E'))
    x['acs_unemployment_share']=share(g('B23025_005E'),g('B23025_003E'))
    x['snap_household_share']=share(g('B22003_002E'),g('B22003_001E'))
    for label,code in [('heat_utility_gas_share','B25040_002E'),('heat_bottled_gas_share','B25040_003E'),
                       ('heat_electricity_share','B25040_004E'),('heat_fuel_oil_share','B25040_005E')]:
        x[label]=share(g(code),g('B25040_001E'))
    rate=(1000*x.filings/x.renter_households.replace(0,np.nan))
    x['filings_per_1000_renter_households']=rate
    for c in [k for k in x if k.endswith('_share')]:
        # Values >1 indicate invalid ACS combinations or a numerator/denominator mismatch.
        x.loc[~x[c].between(0,1),c]=np.nan
    return x


def build(lsc_path=None,acs_path=None,reporting_lag=2):
    lsc_path=Path(lsc_path) if lsc_path else RAW/'lsc_county_month.csv'
    acs_path=Path(acs_path) if acs_path else RAW/'acs_county_vintages.csv'
    if not lsc_path.exists() or not acs_path.exists(): raise FileNotFoundError('Download official LSC and ACS inputs first; no fake demo inputs are substituted')
    acs=pd.read_csv(acs_path,dtype={'fips':'string'})
    if set(ACS_VARS)-set(acs): raise ValueError('ACS download does not have the required detailed tables')
    acs['fips']=acs.fips.str.zfill(5)
    lsc=pd.read_csv(lsc_path,dtype='string',low_memory=False)
    d,report=normalize_lsc(lsc,acs)
    # Drop the latest N observed months from the entire source: conservative reporting lag.
    max_date=d.month.max()
    cutoff=max_date-pd.DateOffset(months=reporting_lag)
    d=d[d.month<=cutoff].copy()
    observed_gaps=[]
    for fips, grp in d.groupby('fips'):
        expected=len(pd.date_range(grp.month.min(),grp.month.max(),freq='MS'))
        missing=expected-len(grp)
        if missing: observed_gaps.append({'fips':fips,'missing_months_within_recorded_span':missing})
    report['counties_with_month_gaps']=len(observed_gaps)
    report['missing_county_month_observations_within_spans']=sum(z['missing_months_within_recorded_span'] for z in observed_gaps)
    report['missing_months_sample']=observed_gaps[:20]
    report.update({'reporting_lag_months':reporting_lag,'max_download_month':str(max_date.date()),
                   'last_included_month':str(cutoff.date()),'included_counties':int(d.fips.nunique()),
                   'included_months':int(d.month.nunique()),'included_states':int(d.fips.str[:2].nunique())})
    # All years of ACS maintained; horizon-dependent merge occurs in forecast step.
    panel=add_acs(d,acs); panel=enrich(panel)
    if not len(panel): raise RuntimeError('No observations with eligible historical ACS; check vintages and filings dates')
    OUT.mkdir(parents=True,exist_ok=True)
    # Keep publishable data small: forecasting uses the original counts and remerges
    # dated ACS vintages from the private temporary download at model runtime.
    keep=['fips','month','filings','NAME','filings_per_1000_renter_households']
    panel[keep].to_csv(OUT/'county_month.csv',index=False)
    (OUT/'data_quality.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    return panel

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--lsc');p.add_argument('--acs');p.add_argument('--reporting-lag',type=int,default=2)
    a=p.parse_args();build(a.lsc,a.acs,a.reporting_lag)
