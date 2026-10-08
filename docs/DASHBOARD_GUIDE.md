# Dashboard guide for a professor meeting

**One sentence:** "Evict-AI uses recorded monthly county court filing counts and historically eligible Census housing data to test how early we can forecast increases in eviction filings."

## Suggested 5-minute walkthrough

1. Open the **County map** tab. Show orange (predicted increase) and red (top-quartile forecast rate) counties. Explain that *gray means no mapped estimate*, not a zero rate. Choose a state in the sidebar. Distinguish relative filing *rates* from counts and explain that the thresholds are exploratory.
2. Switch to **County details**. Pick one county. Explain the observed historical filings as opposed to the future predicted marker. Explain the 1 vs 3 month horizon and the assumed two-month reporting delay.
3. Switch to **Housing indicators**. Show rent burden and local predicted filing rates; clarify that correlations are not causal effects. Household heating fuel is a share of occupied units, **not energy burden**.
4. Switch to **Forecast accuracy**. Ask: does the history+ACS model beat the history-only model and the naive benchmarks on months it did not train on? If it does not, acknowledge that directly and revise the research design.
5. Switch to **Coverage and methods**. Explain which jurisdictions and historical months are observed, where missing data occur, and what is still necessary for credible real-time warnings.

## Strongest defensible innovation

The research question is whether *prospectively evaluated changes in filing risk* can be detected at useful lead times. Berkeley's HPRM already predicts structural eviction vulnerability at census-tract level, so claiming "we are first to predict eviction risk" would be wrong. Our current county-level design does not replace their tract-level displacement model.

## What not to say yet

- "Our model is more accurate than Berkeley's." No common-sample head-to-head evaluation has been conducted.
- "We predicted who would be evicted." No personal-level data or probabilities are used.
- "Our model proves energy burden causes eviction." The dataset includes heating fuel shares, not energy bills; the forecasts are predictive, not causal.
- "The system is nationally complete." LSC covers only selected counties and municipalities.
- "The alerts are suitable for distributing assistance." Alert precision, recall, geographic fairness and local coverage must be validated first.

## Before showing results

- Run GitHub Actions and confirm outputs exist.
- Review failures or `data/processed/data_quality.json` rather than hiding them.
- Compare the top three counties' filing counts against the official LSC jurisdiction pages or other official court tabulations.
- Inspect whether ACS improves WAPE/MAE and whether the positive signal is robust across states and years.
