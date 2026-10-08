"""Source URLs and stable, documented ACS county-level variable IDs."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw'
OUT = ROOT / 'data' / 'processed'
LSC_CSV = 'https://civilcourtdata.lsc.gov/downloads/monthly_county_data_download.csv'
LSC_PAGE = 'https://civilcourtdata.lsc.gov/data/eviction/'
ACS_URL = 'https://api.census.gov/data/{year}/acs/acs5'
# ACS 5-year estimates: public county-level variables. Each variable has an exact source label in docs/VARIABLES.md.
ACS_VARS = [
    'B25003_001E','B25003_003E', # occupied households, renter-occupied households
    'B25070_001E','B25070_007E','B25070_008E','B25070_009E','B25070_010E','B25070_011E',
    'B25002_001E','B25002_003E',
    'B25058_001E', # median contract rent
    'B19013_001E', # median household income
    'B17001_001E','B17001_002E',
    'B23025_003E','B23025_005E',
    'B22003_001E','B22003_002E',
    'B25040_001E','B25040_002E','B25040_003E','B25040_004E','B25040_005E',
]
# ACS 2024 five-year released Dec 2025; conservative operational rule:
# ACS vintage Y first eligible from January Y+2 (origin month, NOT outcome month).
ACS_FIRST, ACS_LAST = 2018, 2024
