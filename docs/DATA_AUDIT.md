# Data source audit and validation checklist

## LSC monthly court filings

Source: https://civilcourtdata.lsc.gov/data/eviction/ (Monthly County Data). Direct public CSV currently linked from the source: https://civilcourtdata.lsc.gov/downloads/monthly_county_data_download.csv

- Confirm a downloaded CSV actually contains observed case **filing counts**, not filing *rates*, judgments or default orders.
- Inspect `lsc_manifest.json` (checksum and retrieval time) in the Action artifact or local `data/raw`.
- Check whether jurisdiction rows represent counties, cities, municipalities or duplicates. Parser discards unmatched rows and refuses to aggregate duplicated county-month rows without source verification.
- Compare a sample of state-by-month totals to LSC's source maps or official court reports. Do not claim the full county-level series is complete simply because it downloaded.
- Observe state-specific court coverage, court procedure, reporting lags, automated sealing or revisions. LSC states that case classifications and definitions vary. A filing is not a completed eviction.
- Two most recent months are excluded by default, but the appropriate reporting lag can differ across states. A stronger future model would store historical source snapshots and evaluate revision-aware forecast accuracy.
- No empty missing county-month is imputed to zero.

## ACS county data

Source: https://api.census.gov/data/2024/acs/acs5 and earlier ACS five-year vintages. Exact variable IDs, universes and derived metrics in `VARIABLES.md`.

- ACS uses five-year survey windows. Month-to-month changes in Evict-AI forecasts come from court filing history, not from pretending ACS is observed each month.
- Current historical rule: vintage *Y* may enter only from **January of Y+2**, as a deliberately conservative release timing proxy, not a precise official release calendar.
- Median and share values with ACS suppression sentinels become missing, never zero. Small counties can have large margins of error; these are not yet modeled explicitly.
- Rate denominator: ACS renter-occupied households, not individual renters or number of people at risk.
- 'Rent burdened' share excludes B25070 "Not computed" from the percentage denominator; see `VARIABLES.md`.

## Map boundaries

Public geometry: https://github.com/plotly/datasets/blob/master/geojson-counties-fips.json . Some county-equivalents and historical FIPS may not match. If no polygon is found, the county still appears in the sortable table. Gray indicates absence of *mapped forecast*, not zero risk.

## Modeling

- One- and three-month **direct forecast horizons** and assumed two-month court reporting lag.
- Four model predictions compared on the exact same future testing months.
- WAPE: total absolute filing count error divided by total observed filings; MAE: average absolute count error per county-month.
- Rising-filing alert definition is **at least 5 predicted filings AND at least 25% above recent 12-month average**. This is provisional and must be assessed for false positives, missed rises and consequences of warnings.
- No causal identification, calibrated prediction intervals, individual risk assessment or fair-intervention certification.
