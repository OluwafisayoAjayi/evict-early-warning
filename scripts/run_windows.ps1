# Run in PowerShell from the extracted project folder.
# Set $env:CENSUS_API_KEY before executing this file.
$ErrorActionPreference = 'Stop'
if (-not $env:CENSUS_API_KEY) { throw 'Set CENSUS_API_KEY first.' }
python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'pip install failed' }
python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Unit tests failed' }
python -m src.download_lsc
if ($LASTEXITCODE -ne 0) { throw 'LSC download failed' }
python -m src.download_acs
if ($LASTEXITCODE -ne 0) { throw 'ACS download failed' }
python -m src.prepare_panel --reporting-lag 2
if ($LASTEXITCODE -ne 0) { throw 'Panel creation failed' }
python -m src.forecast --horizons 1 3 --test-months 9
if ($LASTEXITCODE -ne 0) { throw 'Forecast run failed' }
streamlit run app.py
