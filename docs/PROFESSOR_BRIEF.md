# Research brief for faculty discussion

## Working title

**Evict-AI: Can Early Warning Models Forecast Local Eviction Filing Surges Before They Appear in Structural Housing Risk Maps?**

**Study status:** code prototype with local synthetic-fixture tests. No empirical forecast accuracy or superiority is claimed until an authenticated real-data run succeeds and source quality is independently verified.

## Motivation

The UC Berkeley / Eviction Research Network HPRM 2.0 provides tract-level estimated eviction and displacement risk using BART and observed housing and demographic predictors. It already uses machine learning, holdout-based diagnostics and historical eviction data. It should not be characterized as a purely descriptive map. The proposed study complements that work by testing operational **lead-time performance**: which county-months will show unusually large filing counts in the next 1 or 3 months?

## Research questions

1. Can historical eviction filings forecast future filings at one- and three-month lead times?
2. Do *historically available* ACS housing and economic conditions improve genuine out-of-time forecast errors and emerging-risk detection relative to using filing history alone?
3. For a fixed number of counties that a housing organization could investigate, how many future filing surges would each approach detect early, and how many false alerts would it generate?

## Observed outcome

- **Actual number of court eviction filings** recorded by the Legal Services Corporation (LSC) in county-months that can be reliably mapped to a Census county FIPS, *not a modeled eviction-risk score*.
- `filings / renter-occupied households × 1000` is a contextual intensity measure, not households evicted and not a probability.
- Counties without uniquely verifiable identifiers, unrecorded months, ambiguous duplicate records, and a recent reporting-lag window are not silently filled or aggregated.

## Candidate models

- Last-observed-month filing count baseline.
- Same-month-prior-year (seasonal-naive) baseline.
- Gradient boosting using only historical monthly filings + seasonality.
- Gradient boosting adding a parsimonious group of ACS housing, rent burden, poverty, unemployment, SNAP and heating-fuel composition variables.

## Honest validation

At every held-out future target month `t`, retrain using only outcomes available at the forecast-origin month `t-h` **after applying a conservative two-month case reporting delay**. Outcomes used for training end by `t-h-2`; lagged input counts also end by `t-h-2`. ACS vintage `Y` is allowed after January `Y+2`; for three-month forecasts the ACS vintage is evaluated at `t-3`, not `t`. No random shuffle of county-month observations. Compare mean absolute error and WAPE; additionally evaluate recall and false positives on historical **observed** filing surges. Stratify errors by filing intensity and county size for bias audit.

## What would distinguish this project

- Tests actual advance warning rather than only structural vulnerability (a complementary goal; not inherently better).
- Direct model **ablation** reveals whether annual housing conditions add incremental predictive value after filing history.
- Horizon- and coverage-aware evaluation with a specified reporting lag and strict publication-time boundaries.
- Auditable provenance: public raw-source URLs, checksum, ACS vintage, county FIPS, rejected units and source quality report.
- A research dashboard that presents out-of-time performance alongside forecasts and explicitly labels uncertainty and data gaps.

## Non-negotiable conditions before claiming an advantage

1. Verify LSC exported column meanings, jurisdiction coverage and any national duplicate records; compare selected sampled county-month counts against official court/LSC pages.
2. Secure a meaningful number of clean county-month observations, with at least 24 months of training history per evaluation period, and a pre-specified test window.
3. Show that the ACS-augmented model improves a policy-relevant metric versus both the historical model and seasonal-naive baseline; if it does not, publish the negative finding.
4. If comparing against **HPRM directly**, acquire its EER outputs and align geography, target, period and evaluation protocol. A county-level model's performance alone does **not** establish that it is better than HPRM's census-tract risk model.
5. Assess local court filing definitions, incomplete/late counts, nonrandom coverage, fairness, uncertainty intervals and intervention implications with housing partners.

## Concrete outputs from the supplied code

`data/processed/county_month.csv`: matched observed LSC counts, county name, and observed filing rate. Historical ACS predictors are merged during training and are not distributed in raw form.  
`data/processed/data_quality.json`: coverage and rejection statistics.  
`data/processed/rolling_backtests.csv`: month-by-month predictions made without future outcomes.  
`data/processed/model_metrics.csv`: baseline-versus-model tests and alert precision/recall.  
`data/processed/county_forecasts.csv`: experimental future county-month counts and rates.  
`app.py`: live dashboard once official inputs are accessible in the GitHub workflow.

**Practical note:** No actual LSC/ACS CSV bytes could be retrieved into the authoring runtime. Unit tests use artificial inputs **only inside tests**. The real-data pipeline first needs successful execution on GitHub Actions with a Census API key; inspection of its first report is a required research step, not an optional footnote.
