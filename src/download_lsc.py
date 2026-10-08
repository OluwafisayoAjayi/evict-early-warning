"""Download original public LSC monthly COUNTY export with provenance; never use invented data."""
import argparse, datetime, hashlib, json
from pathlib import Path
import requests
from .config import LSC_CSV, LSC_PAGE, RAW


def download(url=LSC_CSV, output=None):
    path = Path(output) if output else RAW / 'lsc_county_month.csv'
    path.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, timeout=240, headers={'User-Agent':'EvictAI-Research/0.2 (academic, public CSV)'})
    r.raise_for_status()
    b = r.content
    if len(b) < 100 or b'<' in b[:10] or b',' not in b[:10000]:
        raise ValueError('LSC response is not a nonempty CSV; did not overwrite local data')
    path.write_bytes(b)
    meta = {'url':url,'source_information':LSC_PAGE,'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
    (path.parent / 'lsc_manifest.json').write_text(json.dumps(meta,indent=2))
    print(f'LSC raw CSV: {path} ({len(b):,} bytes, sha256={meta["sha256"][:12]}...)')
    return path

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--url',default=LSC_CSV); p.add_argument('--output')
    a=p.parse_args(); download(a.url,a.output)
