#!/usr/bin/env bash
set -euo pipefail
python -m pytest -q
python -m src.download_lsc
python -m src.download_acs
python -m src.prepare_panel --reporting-lag 2
python -m src.forecast --horizons 1 3 --test-months 9
printf '\nOfficial-source processed outputs saved under data/processed.\n'
