"""Static configuration for the permafrost station dashboard."""
import os
import tempfile
from datetime import timedelta, timezone
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
PROJECT_DIR = APP_DIR.parent
LOCAL_RAW_DIR = PROJECT_DIR / "station_data_survey"    # kept current by the hourly refresh task (this PC)
STATIONS_CSV = LOCAL_RAW_DIR / "tableau" / "stations.csv"
LAYERS_DIR = APP_DIR / "layers"

# Data source. "local" reads the files the hourly refresh task downloads; "remote" downloads
# them itself (used on Streamlit Community Cloud, where those files do not exist).
# Default: local if the downloaded files are present, else remote. Override with PERMAFROST_DATA.
REMOTE_BASE = "https://gwscientific.com/remote/UND_DOT_RWIS/{}/data/"
REMOTE_CACHE_DIR = Path(tempfile.gettempdir()) / "permafrost_ticker"
REMOTE_REFRESH_S = 3600        # re-download a station file when the cached copy is older than this
REMOTE_MIN_RELOAD_S = 300      # "Reload data now" never re-downloads more often than this
DATA_MODE = os.environ.get("PERMAFROST_DATA") or (
    "local" if any(LOCAL_RAW_DIR.glob("*/*_QtrHrly.dat")) else "remote")
RAW_DIR = LOCAL_RAW_DIR if DATA_MODE == "local" else REMOTE_CACHE_DIR

# Logger clocks run on Alaska Standard Time all year (no DST): the server's
# Last-Modified (UTC) is 9 h ahead of the last record timestamp.
LOGGER_TZ = timezone(timedelta(hours=-9), "AKST")

STATIONS = ["DYTF20", "DBSF10", "DBSF27", "DBNF26", "DBNF22", "DBNF23"]

# One colour per station, used in every chart and on the map (Okabe-Ito, colour-blind safe).
STATION_COLOURS = {"DYTF20": "#E69F00", "DBSF10": "#56B4E9", "DBSF27": "#009E73",
                   "DBNF26": "#CC79A7", "DBNF22": "#0072B2", "DBNF23": "#D55E00"}

# Soil thermistor depths (cm), nominal. SoilT_5/6 are not connected anywhere.
SOIL_DEPTH_CM = {1: 0, 2: 15, 3: 30, 4: 50}
SOIL_WIRED = {"DBNF26": [1, 2], "DBSF27": [1, 2]}       # others: all four
DEFAULT_WIRED = [1, 2, 3, 4]
# Stations whose sensor responses do not match the nominal depth order; depths are kept
# at nominal values but flagged "depth unverified" until confirmed in the field.
DEPTH_UNVERIFIED = {
    "DYTF20": "the 15 cm sensor has a much larger daily swing than the 0 cm sensor",
    "DBNF26": "the 0 cm and 15 cm sensors have almost the same large daily swing",
    "DBNF23": "all sensors have a very small daily swing (< 0.1 C)",
}
# Station locations that are approximate (not from a survey); shown with the coordinates.
LOCATION_NOTES = {
    "DBSF10": "approximate: camera GPS of the pre-upgrade UND Site 10 (photos 24 May 2026); the August 2026 "
              "mast may be offset; elevation from USGS 3DEP",
}
# Depth colours: warm (surface) to cool (deep); air in dark grey.
DEPTH_COLOURS = {"Air": "#444444", 0: "#d7301f", 15: "#fc8d59", 30: "#74add1", 50: "#313695"}

# Sensors to be installed later. Flip to True to show them in the UI.
SHOW_FUTURE_SENSORS = {"wind": False, "snow": False, "rain": False, "soil_water": False}

# ---- Data cleaning -----------------------------------------------------------
# Plausible ranges are read from each logger's Const_Table (QC_TA_*, QC_TS_*, QC_HR_*,
# Batt_Volt_*); these are the fallbacks if that table is missing.
QC_DEFAULTS = {"air": (-55, 70), "soil": (-50, 70), "rh": (0, 100), "batt_v": (10.5, 15.0)}
MAX_CURRENT_A = 20             # current spikes above this are glitches (e.g. 135.6 A at DBNF26)
INSTALL_CUTOFF = {"DBSF27": "2026-10-11 00:00:00"}  # drop install/bench data before this
RECORD_MINUTES = 15            # QtrHrly interval; gaps longer than this are shown as gaps

# ---- Derived metrics ---------------------------------------------------------
DAILY_MIN_COVERAGE = 0.8       # a daily mean needs >= 80 % of the 96 quarter-hour records
SEASON_START = (7, 1)          # degree-days accumulate from 1 July (freezing season convention)
ZERO_CURTAIN_C = 0.5           # |daily mean T| <= this ...
ZERO_CURTAIN_MIN_DAYS = 3      # ... for at least this many consecutive days = zero-curtain period
FULL_SEASON_DAYS = 300         # metrics based on less record than this are "provisional"

# ---- Health ------------------------------------------------------------------
STALE_MINUTES = 120            # minimum; per station: call-in interval + 60 min
BATTERY_LOW_V = 12.2
BATTERY_WARN_V = 12.4


def wired_soil(station):
    return SOIL_WIRED.get(station, DEFAULT_WIRED)


def soil_depth(i):
    return SOIL_DEPTH_CM[i]


def soil_label(i):
    return f"{SOIL_DEPTH_CM[i]} cm"
