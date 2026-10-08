# Evict-AI | County-level eviction early warning

**Status: research prototype — code completed; real-data execution and empirical evaluation pending.**

Evict-AI is a US county-level **court filing forecasting** and housing vulnerability dashboard built with Python, Streamlit and Plotly. It downloads public monthly county eviction filing *counts* from the Legal Services Corporation (LSC), combines them with historical ACS county-level housing and socioeconomic indicators, tests one- and three-month-ahead forecasts against earlier historical benchmarks, and shows the results on an interactive county map.

**This repository intentionally contains no fabricated filing counts, forecasts or reported accuracy scores.** After a successful GitHub Actions run, outputs populate `data/processed` and become visible in the Streamlit app.

## What users see

1. **County map:** orange = experimental predicted increase in filings, red = highest quartile of predicted filing rates among tracked counties, teal = other tracked counties, gray = no mapped forecast (not zero risk). Categories are not validated risk probabilities.
2. **County details:** actual month-by-month filings, historical mean, and a separately identified future forecast marker; exportable CSV.
3. **Housing indicators:** ACS rent burden, poverty, income, renter share, housing vacancy, SNAP and heating fuel composition; charts are descriptive.
4. **Forecast accuracy:** out-of-time model comparisons (historical, seasonal-naive, history-only machine learning, and history-plus-ACS machine learning), WAPE/MAE and experimental alert precision/recall.
5. **Coverage and methods:** unmatched geography and missing-month diagnostics, methodological limitations and source links.

## Upload to GitHub — follow these steps exactly

**You do not need to run Python on your own computer if you use GitHub Actions and Streamlit Cloud.**

1. Download `evict-ai-complete-github.zip` and **extract** it. You should see files such as `app.py`, `README.md`, `requirements.txt`, plus folders `.github`, `.streamlit`, `src`, `docs`, `data`, and `tests`.
2. Sign in to [GitHub](https://github.com) and select **+ → New repository**. Name it `evict-ai-early-warning`. Set **Public** if you plan to deploy on the free public Streamlit service and are comfortable publicly sharing the *aggregate outputs*. Do not add another README, license or gitignore on creation: they are already included.
3. Within the new repository choose **Add file → Upload files**, then drag in all the files/folders **inside** the extracted folder (not the ZIP itself). Check that `.github/workflows/update-data.yml` appears in GitHub after upload. Finish with **Commit changes**. If the GitHub browser does not retain nested directories, upload the directory structure with GitHub Desktop or git (instructions below).
4. Ask Census for a [free Census API key](https://api.census.gov/data/key_signup.html). Open your repository **Settings → Secrets and variables → Actions → New repository secret**. Enter name `CENSUS_API_KEY`, put the private key in the value, save. **Never put the key in README or upload it as a file.**
5. Open **Actions → Update eviction forecast data → Run workflow** (select main/default branch). Wait for all steps. GitHub downloads the official records, checks the data, constructs county-month panels, fits and evaluates models, and commits processed aggregate tables. The **Actions** log indicates any download/schema/quality failure. A failure is not a result and must be corrected before proceeding.
6. Confirm that `data/processed/county_forecasts.csv`, `county_month.csv`, `rolling_backtests.csv`, `model_metrics.csv` and `data_quality.json` are present in your repository. If not, don't deploy as if forecasts exist; check failed Actions step first.
7. Visit [Streamlit Community Cloud](https://share.streamlit.io), connect your GitHub account, select the repository and branch, use main file path **`app.py`**, and select **Deploy**. The public URL is your dashboard for your professor.

Your repository's **Actions → Check research code** automatically tests logic on pushes and pull requests. **Update eviction forecast data** also runs automatically around the 15th of every month, though the source may not be fully updated at that time.

### GitHub Desktop alternative

Choose **File → Clone repository**, copy all extracted project files into the new local clone, commit and push with GitHub Desktop. Keep the hidden `.github` and `.streamlit` folders intact.

## Run on your own computer (optional)

```bash
python -m pip install -r requirements.txt
python -m pytest -q
# Use a private environment variable CENSUS_API_KEY (never commit it)
python -m src.download_lsc
python -m src.download_acs
python -m src.prepare_panel --reporting-lag 2
python -m src.forecast --horizons 1 3 --test-months 9
streamlit run app.py
```

Windows PowerShell users can run `scripts/run_windows.ps1` **after** setting `$env:CENSUS_API_KEY`. Mac/Linux users have `scripts/run_local.sh`.

### CSV schema changes / first-run problems

The official LSC county CSV is here: <https://civilcourtdata.lsc.gov/downloads/monthly_county_data_download.csv>. The data schema could change. The parser intentionally **fails** on unknown count/date columns, ambiguous repeated county-months or impossible counts rather than silently guessing. Inspect the `Prepare observed county-month and ACS panel` GitHub Actions failure, and the `evict-ai-results-and-diagnostics` Actions artifact for unmatched rows or duplicate diagnostics. Do not manually set missing filings to zero.

ACS historical vintages: **2018–2024**. If your key is unavailable, verify `CENSUS_API_KEY` was entered under **repository secrets** exactly. Only public aggregate data gets committed; raw official CSVs are ignored by git.

## Files

```text
.github/workflows/update-data.yml  Monthly official-source download, quality checks, forecasts and output commit
.github/workflows/tests.yml        Tests on every code update
.streamlit/config.toml             Dashboard layout / colors
app.py                             Interactive US county map + five dashboard tabs
src/config.py                      Official source endpoints and ACS source variable IDs
src/download_lsc.py                Court filing CSV downloader and checksum manifest
src/download_acs.py                ACS vintage downloader
src/prepare_panel.py               Validate/count/link data with missing-data safeguards
src/forecast.py                    County forecasting and rolling historical evaluation
src/visuals.py                     Map categories and test-statistic helpers
scripts/                          Optional command-line runners
tests/                            Synthetic fixtures used for code tests only
docs/VARIABLES.md                 Exact ACS field meanings and rate formulas
docs/PROFESSOR_BRIEF.md           Methodology and research contribution
docs/DASHBOARD_GUIDE.md          Explain the map / walk through professor demo
docs/DATA_AUDIT.md                Data limitations and things to validate
```

## Data and research notes

- LSC: https://civilcourtdata.lsc.gov/data/eviction/ — public monthly county export, limited jurisdiction coverage, potential revisions and recording differences.
- ACS: https://api.census.gov/data/2024/acs/acs5 — 5-year *county* estimates for renters, rent burden, poverty and more. We conservatively make vintage **Y** eligible for forecast origins starting January **Y+2**. ACS is **not a monthly dataset**.
- A filing count records a **court case**, not an eviction judgment, unique household evicted or individual-level probability. The filing rate denominator is ACS renter-occupied households (per 1,000); multiple cases per household are possible.
- Heating fuel type captures the *fuel used*, not what households pay, heating expenses, energy burden, or the price of fuel.
- Only uniquely matched counties with adequate consecutive history support the model; gray counties should never be interpreted as safe or having zero filings.
- Historical comparisons test error in observed monthly counts; prediction intervals are **not** yet calibrated, and the dashboard is **not** a clinically or legally validated decision system.
- A comparison claiming Evict-AI *outperforms* UC Berkeley's HPRM would require the **same outcome, spatial geography and held-out periods**. This repository does **not** establish that claim.

Credit LSC / Civil Court Data Initiative and Census ACS in presentations and any papers. County GeoJSON is accessed from [Plotly's public datasets repository](https://github.com/plotly/datasets) (MIT license); updated boundaries may differ from those historical shapes.
