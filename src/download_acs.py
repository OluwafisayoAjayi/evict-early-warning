"""Fetch ACS 5-year COUNTY values by vintage, preserving year and ACS geography.

Requires CENSUS_API_KEY environment variable. Requests fail loudly, no zero-filling.
"""
import argparse, hashlib, json, os, time
from pathlib import Path
import pandas as pd
import requests
from .config import ACS_URL, ACS_VARS, ACS_FIRST, ACS_LAST, RAW


def read_json_table(payload,year):
    if not isinstance(payload,list) or len(payload)<2: raise ValueError(f'{year}: unexpected Census API response')
    d=pd.DataFrame(payload[1:],columns=payload[0])
    if not {'state','county','NAME'}.issubset(d): raise ValueError(f'{year}: missing geography fields: {d.columns.tolist()}')
    if set(ACS_VARS)-set(d): raise ValueError(f'{year}: missing requested ACS variables: {set(ACS_VARS)-set(d)}')
    d['fips']=d['state'].str.zfill(2)+d['county'].str.zfill(3)
    d['acs_year']=year
    # Census returns negative sentinel values for suppressed/invalid estimates; never mistake them for actual data.
    for v in ACS_VARS:
        d[v]=pd.to_numeric(d[v],errors='coerce').mask(lambda s:s<0)
    if d['fips'].duplicated().any(): raise ValueError('Duplicate ACS county FIPS')
    return d[['fips','NAME','acs_year']+ACS_VARS]


def download(years=range(ACS_FIRST,ACS_LAST+1),output=None):
    key=os.environ.get('CENSUS_API_KEY')
    if not key: raise RuntimeError('CENSUS_API_KEY is required. Add it to GitHub repository Settings > Secrets and variables > Actions.')
    chunks=[]
    for y in years:
        params={'get':','.join(['NAME']+ACS_VARS),'for':'county:*','in':'state:*','key':key}
        r=requests.get(ACS_URL.format(year=y),params=params,timeout=120)
        if not r.ok: raise RuntimeError(f'ACS {y} failed ({r.status_code}): {r.text[:250]}')
        rows=read_json_table(r.json(),y)
        chunks.append(rows)
        print(f'ACS {y}: {len(rows)} county records',flush=True)
        time.sleep(.15)
    data=pd.concat(chunks,ignore_index=True)
    if data.duplicated(['fips','acs_year']).any(): raise AssertionError('duplicate ACS key')
    path=Path(output) if output else RAW/'acs_county_vintages.csv'
    path.parent.mkdir(parents=True,exist_ok=True); data.to_csv(path,index=False)
    manifest={'source':ACS_URL,'vintages':list(years),'variables':ACS_VARS,'records':len(data),
              'sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'note':'5-year estimates; vintage Y first eligible in January Y+2'}
    (path.parent/'acs_manifest.json').write_text(json.dumps(manifest,indent=2))
    print(f'ACS file: {path}')
    return data

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--start',type=int,default=ACS_FIRST);p.add_argument('--end',type=int,default=ACS_LAST); a=p.parse_args()
    download(range(a.start,a.end+1))
