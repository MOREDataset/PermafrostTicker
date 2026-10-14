# Alaska permafrost station dashboard

Streamlit dashboard for the UND Alaska Permafrost Network stations (Brooks Range and
Yukon–Tanana Uplands): live air and soil temperatures, degree-days, station health and
reference permafrost map layers.

## Run locally (Windows)

Double-click `start_dashboard.cmd`, or:

```
pip install -r app/requirements.txt
streamlit run app/app.py
```

## Where the data comes from

The station loggers' Campbell Scientific TOA5 files are published at
`https://gwscientific.com/remote/UND_DOT_RWIS/<STATION>/data/`.

* **On the field PC**, the scheduled task "PermafrostTicker Hourly Refresh" runs `refresh.cmd`,
  which downloads them into `station_data_survey/<STATION>/` and rebuilds the Tableau CSVs.
  The app reads those files.
* **Anywhere else** (e.g. Streamlit Community Cloud), those files are absent, so the app
  downloads the tables it needs itself and re-downloads each one when it is over an hour old.

Set `PERMAFROST_DATA=local` or `remote` to force either mode (see `app/config.py`).

## Deploy on Streamlit Community Cloud

Repository: this repo · Branch: `main` · Main file path: `app/app.py`. No secrets are needed.

## Not in this repository

Field photos and slides, raw `.dat` downloads, the derived `hourly_long.csv`, the profiling
reports, the v1 app backup and logs. Map layer sources and citations: `app/layers/SOURCES.md`.
Methods and review notes: `app/REVIEW.md`.
