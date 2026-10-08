# ACS predictor dictionary — exact table concepts

All are **ACS five-year estimates** from the US Census API (`/data/{year}/acs/acs5`), using `for=county:*&in=state:*`. Annual data vintage **is not a monthly measurement**. Negative Census sentinel estimates are treated as missing. Counts, percentages and income variables come from published estimates, not administrative receipts.

| Variable | Exact ACS detailed-table label / concept | Role in project |
|---|---|---|
| B25003_001E | Occupied housing units — total (TENURE) | denominator for renter share |
| B25003_003E | Occupied housing units — renter-occupied | exposure: renter-occupied households |
| B25070_001E | Renter-occupied housing units paying cash rent — gross rent as a percentage of household income, total | denominator before excluding not computed |
| B25070_007E | Gross rent 30.0 to 34.9 percent of household income | numerator for 30%+ burden |
| B25070_008E | Gross rent 35.0 to 39.9 percent | numerator |
| B25070_009E | Gross rent 40.0 to 49.9 percent | numerator |
| B25070_010E | Gross rent 50.0 percent or more | severe rent burden |
| B25070_011E | Gross rent as share of income — not computed | excluded from burden denominator |
| B25002_001E | Occupancy status, housing units total | denominator |
| B25002_003E | Vacant housing units | vacancy share |
| B25058_001E | Median contract rent, renter-occupied housing units paying cash rent | housing price level, not gross rent |
| B19013_001E | Median household income in past 12 months (vintage-adjusted dollars) | local income |
| B17001_001E | Population for whom poverty status is determined — total | poverty denominator |
| B17001_002E | Population whose income in past 12 months is below poverty level | poverty share |
| B23025_003E | Civilian labor force, population 16 years or older | denominator |
| B23025_005E | Unemployed civilian labor force, population 16 years or older | estimated unemployment share; NOT BLS county unemployment |
| B22003_001E | Households by SNAP and poverty status, total | denominator |
| B22003_002E | Household received SNAP benefits in past 12 months | SNAP receipt share |
| B25040_001E | Occupied housing units by house heating fuel, total | denominator |
| B25040_002E | House heating fuel: utility gas | heating composition, NOT bills |
| B25040_003E | House heating fuel: bottled, tank, or LP gas | heating composition, NOT bills |
| B25040_004E | House heating fuel: electricity | heating composition, NOT bills |
| B25040_005E | House heating fuel: fuel oil, kerosene, etc. | heating composition, NOT bills |

## Constructed metrics

- `rent_burden_30_share` = (`B25070_007E` + `B25070_008E` + `B25070_009E` + `B25070_010E`) / (`B25070_001E` − `B25070_011E`). This is conditional on the burden being computed.
- `severe_rent_burden_50_share` = `B25070_010E` / (`B25070_001E` − `B25070_011E`).
- `filings_per_1000_renter_households` = **monthly observed LSC filing count** × 1,000 / **ACS five-year renter-occupied households**. Do not interpret as probability of a renter receiving an eviction filing; repeat filings and court heterogeneity matter.
- `acs_unemployment_share` = `B23025_005E` / `B23025_003E`.
- Shares of housing heating fuel have denominator `B25040_001E`, whose population is all occupied housing units, **not specifically renter households**. This is a local-area contextual indicator only; do not call it renters' fuel exposure.

## Avoid two research mistakes

1. **Not every ACS variable is useful**. Hundreds of predictors could make the model unstable and harder to interpret. The full model compares a pre-specified subset of theoretically relevant ACS fields against a historical-filings-only version.
2. **A five-year ACS estimate is not observed in each of those five years separately.** ACS year `Y` becomes eligible only in January of `Y+2` in this code, a conservative approximation to normal late-year publication timing. Release-vintage and revision audits should precede journal submission.

## Source variable documentation

- [ACS B25070 gross rent as a percentage of income](https://api.census.gov/data/2024/acs/acs5/groups/B25070.html)
- [ACS B25040 house heating fuel](https://api.census.gov/data/2024/acs/acs5/groups/B25040.html)
- [ACS B23025 employment status](https://api.census.gov/data/2024/acs/acs5/groups/B23025.html)
- [ACS B22003 SNAP](https://api.census.gov/data/2024/acs/acs5/groups/B22003.html)
