"""Load, quality-control and summarise the Campbell TOA5 station files.

Conventions (see REVIEW.md):
* Time stamps are logger time, AKST (UTC-9), labelled as such everywhere.
* Quarter-hour series are put on a regular 15-min grid so missing records are NaN
  and plot as gaps (never interpolated).
* Daily means need >= 80 % quarter-hour coverage; days that fail are NaN and counted.
* Degree-days accumulate from 1 July (season start) over valid days only.
"""
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

import config as C

SOIL_COL = "SoilT_{}_C"


# ---------------------------------------------------------------- file access
def _local_file(station, table):
    hits = sorted((C.RAW_DIR / station).glob(f"{station}_*_{table}.dat"))
    return hits[0] if hits else None


@st.cache_data(ttl=C.REMOTE_REFRESH_S, show_spinner=False)
def _remote_names(station):
    """Data file names in the station's Apache directory listing (backups skipped)."""
    html = urllib.request.urlopen(C.REMOTE_BASE.format(station), timeout=60).read().decode("utf-8", "replace")
    return sorted({urllib.parse.unquote(h) for h in re.findall(r'href="([^"?/][^"/]*\.dat)"', html)
                   if urllib.parse.unquote(h).startswith(f"{station}_")})


_locks = {}
_locks_guard = threading.Lock()


def _remote_file(station, table, max_age=C.REMOTE_REFRESH_S):
    """Cached copy of one station file, re-downloaded when older than max_age seconds.
    A failed download keeps serving the previous copy (the health check then shows it stale)."""
    with _locks_guard:
        lock = _locks.setdefault((station, table), threading.Lock())
    with lock:
        hits = sorted((C.REMOTE_CACHE_DIR / station).glob(f"{station}_*_{table}.dat"))
        f = hits[0] if hits else None
        if f is not None and time.time() - f.stat().st_mtime < max_age:
            return f
        try:
            name = next((n for n in _remote_names(station) if n.endswith(f"_{table}.dat")), None)
            if name is None:
                return f
            data = urllib.request.urlopen(C.REMOTE_BASE.format(station) + urllib.parse.quote(name),
                                          timeout=120).read()
            out = C.REMOTE_CACHE_DIR / station / name
            out.parent.mkdir(parents=True, exist_ok=True)
            tmp = out.with_suffix(".part")
            tmp.write_bytes(data)
            tmp.replace(out)  # atomic swap so a failed download never leaves a truncated file
            return out
        except Exception:
            return f


def reload_remote():
    """Force the next read to re-download, unless the copies are under REMOTE_MIN_RELOAD_S old."""
    if C.DATA_MODE != "remote":
        return
    _remote_names.clear()
    old = time.time() - C.REMOTE_REFRESH_S - 1
    for f in C.REMOTE_CACHE_DIR.glob("*/*.dat"):
        if time.time() - f.stat().st_mtime >= C.REMOTE_MIN_RELOAD_S:
            os.utime(f, (old, old))  # mark stale; the old copy stays if the download fails


def _file(station, table):
    return _local_file(station, table) if C.DATA_MODE == "local" else _remote_file(station, table)


def file_mtime(station, table):
    f = _file(station, table)
    return f.stat().st_mtime if f else 0.0


@st.cache_data(show_spinner=False)
def _read_raw(station, table, mtime):
    """Read one TOA5 table as-is (mtime is only a cache key)."""
    f = _file(station, table)
    if f is None:
        return pd.DataFrame()
    df = pd.read_csv(f, skiprows=[0, 2, 3], na_values=["NAN"], low_memory=False)
    df["TIMESTAMP"] = pd.to_datetime(df["TIMESTAMP"], format="mixed")
    return df


def qc_limits(station):
    """Plausible ranges from the logger's own Const_Table, else config defaults."""
    lim = dict(C.QC_DEFAULTS)
    ct = _read_raw(station, "Const_Table", file_mtime(station, "Const_Table"))
    if not ct.empty:
        r = ct.iloc[-1]
        try:
            lim["air"] = (float(r["QC_TA_MIN"]), float(r["QC_TA_MAX"]))
            lim["soil"] = (float(r["QC_TS_MIN"]), float(r["QC_TS_MAX"]))
            lim["rh"] = (float(r["QC_HR_MIN"]), float(r["QC_HR_MAX"]))
            lim["batt_v"] = (float(r["Batt_Volt_Min"]) / 1000, float(r["Batt_Volt_Max"]) / 1000)
        except (KeyError, ValueError):
            pass
    return lim


@st.cache_data(show_spinner=False)
def _clean(station, table, mtime):
    """Apply QC; returns (cleaned frame, dict of how many values each rule removed)."""
    df = _read_raw(station, table, mtime).copy()
    log = {}
    if df.empty:
        return df, log
    n0 = len(df)
    df = df.drop_duplicates("TIMESTAMP", keep="last").sort_values("TIMESTAMP")
    log["duplicate time stamps dropped"] = n0 - len(df)
    cutoff = C.INSTALL_CUTOFF.get(station)
    if cutoff:
        n1 = len(df)
        df = df[df["TIMESTAMP"] >= pd.Timestamp(cutoff)]
        log[f"installation rows before {cutoff[:10]} dropped"] = n1 - len(df)
    lim = qc_limits(station)

    def mask(cols, lo, hi, label):
        n = 0
        for c in cols:
            if c in df and pd.api.types.is_numeric_dtype(df[c]):
                bad = (df[c] < lo) | (df[c] > hi)
                n += int(bad.sum())
                df.loc[bad, c] = np.nan
        if n:
            log[label] = n

    num = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    mask([c for c in num if c.startswith(("AirT", "DewPoint", "WindChill")) and "_F" not in c],
         *lim["air"], f"air/dew-point values outside {lim['air']} C")
    mask([c for c in num if c.startswith("SoilT") and "_F" not in c],
         *lim["soil"], f"soil values outside {lim['soil']} C (open sensor channels)")
    mask([c for c in num if c.startswith("Batt_V")], *lim["batt_v"], f"battery values outside {lim['batt_v']} V")
    mask([c for c in num if c.startswith(("IBatt", "ISolar", "ILoad"))],
         -C.MAX_CURRENT_A, C.MAX_CURRENT_A, f"current spikes beyond +/-{C.MAX_CURRENT_A} A")
    if "RH" in df:  # RH = 0 only occurs as a dead-sensor reading
        rh_cols = [c for c in ("RH", "RH_Avg", "RH_Max", "RH_Min") if c in df]
        bad = (df["RH"] <= lim["rh"][0]) | (df["RH"] > lim["rh"][1])
        if bad.any():
            df.loc[bad, rh_cols + [c for c in df if c.startswith("DewPoint") or c.startswith("VaporPressure")]] = np.nan
            log["RH = 0 / >100 % rows blanked"] = int(bad.sum())
    for c in num:
        if c.startswith("ess"):
            bad = df[c].isin([1001, 3001])
            df.loc[bad, c] = np.nan
    return df.reset_index(drop=True), log


def table(station, name):
    return _clean(station, name, file_mtime(station, name))[0]


def qc_log(station, name):
    return _clean(station, name, file_mtime(station, name))[1]


def regular(df, minutes=C.RECORD_MINUTES):
    """Re-index onto a regular grid so missing records become NaN (plotted as gaps)."""
    if df.empty:
        return df
    grid = pd.date_range(df["TIMESTAMP"].min(), df["TIMESTAMP"].max(), freq=f"{minutes}min")
    return df.set_index("TIMESTAMP").reindex(grid).rename_axis("TIMESTAMP").reset_index()


def window(df, days):
    if df.empty or days is None:
        return df
    return df[df["TIMESTAMP"] >= df["TIMESTAMP"].max() - pd.Timedelta(days=days)]


# ---------------------------------------------------------------- metadata & latest
@st.cache_data(show_spinner=False)
def stations_meta(mtime_key=None):
    meta = pd.read_csv(C.STATIONS_CSV)
    site = C.LAYERS_DIR / "station_site_attributes.csv"
    if site.exists():
        meta = meta.merge(pd.read_csv(site), on="station", how="left")
    meta["has_location"] = meta["lat"].notna()
    return meta.set_index("station").loc[C.STATIONS].reset_index()


def now_logger():
    """Current time on the logger clock (AKST), naive, comparable to TIMESTAMP."""
    return datetime.now(C.LOGGER_TZ).replace(tzinfo=None)


def stale_after(station):
    """Minutes without a new record before a station is flagged: its longest scheduled
    call-in interval (ControlVariables) + 60 min, never less than STALE_MINUTES."""
    cv = table(station, "ControlVariables")
    cols = ["CommsAutoDayInterval_Min", "CommsAutoNightInterval_Min"]
    if cv.empty or not set(cols) <= set(cv.columns):
        return C.STALE_MINUTES
    return max(C.STALE_MINUTES, int(cv[cols].iloc[-1].max()) + 60)


def latest(station):
    q = table(station, "QtrHrly")
    d = table(station, "HrlyDiag")
    p = table(station, "Public")
    out = {"station": station, "stale_after_min": stale_after(station)}
    if not q.empty:
        row = q.iloc[-1]
        out["time"] = row["TIMESTAMP"]
        out["age_min"] = (now_logger() - row["TIMESTAMP"]).total_seconds() / 60
        out["air"] = row.get("AirT_Primary_C")
        out["rh"] = row.get("RH")
        wired = C.wired_soil(station)
        out["soil"] = {C.soil_depth(i): row.get(SOIL_COL.format(i)) for i in wired}
    if not d.empty:
        out["batt"] = d["Batt_V"].iloc[-1]
    if not p.empty and "BattRemainingpct" in p:
        out["soc"] = p["BattRemainingpct"].iloc[-1] * 100
        out["soc_time"] = p["TIMESTAMP"].iloc[-1]
    out["health"], out["health_reason"] = health(out)
    return out


def health(x):
    age, batt, limit = x.get("age_min"), x.get("batt"), x["stale_after_min"]
    if age is None:
        return "red", "no data"
    if age > limit:
        return "red", f"no new record for {age / 60:.1f} h (expected every {limit - 60} min)"
    if batt is not None and batt < C.BATTERY_LOW_V:
        return "red", f"battery low ({batt:.2f} V)"
    if batt is not None and batt < C.BATTERY_WARN_V:
        return "orange", f"battery getting low ({batt:.2f} V)"
    return "green", "reporting normally"


# ---------------------------------------------------------------- series for charts
def series(station, days, regular_grid=True):
    """Air + wired soil temperatures (15-min) for one station, wide, gaps kept as NaN."""
    q = table(station, "QtrHrly")
    if q.empty:
        return q
    cols = ["AirT_Primary_C"] + [SOIL_COL.format(i) for i in C.wired_soil(station)]
    q = q[["TIMESTAMP", *[c for c in cols if c in q]]]
    if regular_grid:
        q = regular(q)
    return window(q, days)


def hourly(station, cols, days):
    """Hourly means on a regular grid; an hour needs >= 3 of its 4 records."""
    q = table(station, "QtrHrly")
    if q.empty:
        return q
    q = q.set_index("TIMESTAMP")[[c for c in cols if c in q]]
    h = q.resample("1h").mean().where(q.resample("1h").count() >= 3)
    return window(h.reset_index(), days)


@st.cache_data(show_spinner=False)
def _daily(station, mtime):
    """Daily means from quarter-hour data with the coverage rule. Returns (means, coverage)."""
    q = table(station, "QtrHrly")
    if q.empty:
        return pd.DataFrame(), pd.DataFrame()
    cols = ["AirT_Primary_C"] + [SOIL_COL.format(i) for i in C.wired_soil(station)]
    g = q.set_index("TIMESTAMP")[cols].resample("D")
    per_day = 24 * 60 // C.RECORD_MINUTES
    cov = g.count() / per_day
    mean = g.mean().where(cov >= C.DAILY_MIN_COVERAGE)
    # the current (incomplete) day is never a valid daily mean
    last_day = q["TIMESTAMP"].max().normalize()
    mean.loc[mean.index >= last_day] = np.nan
    return mean, cov


def daily(station):
    return _daily(station, file_mtime(station, "QtrHrly"))


def season_start(ts):
    m, d = C.SEASON_START
    year = ts.year if (ts.month, ts.day) >= (m, d) else ts.year - 1
    return pd.Timestamp(year, m, d)


def degree_days(station):
    """Freezing / thawing degree-days of air and 0 cm soil since the season start.

    FDD = sum over valid days of max(0, -Tmean); TDD = sum of max(0, Tmean).
    Days failing the coverage rule are skipped and counted.
    """
    mean, cov = daily(station)
    if mean.empty:
        return pd.DataFrame(), {}
    start = season_start(mean.index.max())
    mean = mean[mean.index >= start]
    cov = cov[cov.index >= start]
    surf = SOIL_COL.format(C.wired_soil(station)[0])
    out = pd.DataFrame(index=mean.index)
    for col, name in [("AirT_Primary_C", "air"), (surf, "soil 0 cm")]:
        t = mean[col]
        out[f"FDD {name}"] = (-t).clip(lower=0).fillna(0).cumsum().where(t.notna().cumsum() > 0)
        out[f"TDD {name}"] = t.clip(lower=0).fillna(0).cumsum().where(t.notna().cumsum() > 0)
    out = out.iloc[:-1] if len(out) and mean.iloc[-1].isna().all() else out  # drop today's empty row
    both = mean[["AirT_Primary_C", surf]].dropna()
    fdd_air = (-both["AirT_Primary_C"]).clip(lower=0).sum()
    fdd_soil = (-both[surf]).clip(lower=0).sum()
    record_days = int(mean["AirT_Primary_C"].notna().sum())
    info = {
        "season_start": start.date(),
        "record_start": mean.index.min().date(),
        "valid_days": record_days,
        "failed_days": int(((cov["AirT_Primary_C"] < C.DAILY_MIN_COVERAGE) &
                            (cov.index < mean.index.max())).sum()),
        "n_factor_freezing": fdd_soil / fdd_air if fdd_air > 0 else None,
        "fdd_air_paired": fdd_air,
        "provisional": record_days < C.FULL_SEASON_DAYS,
    }
    return out.reset_index(names="date"), info


def soil_state(station):
    """Per depth: current thermal state, last 0 C crossing and zero-curtain periods,
    from valid daily means since the season start."""
    mean, _ = daily(station)
    if mean.empty:
        return pd.DataFrame()
    mean = mean[mean.index >= season_start(mean.index.max())]
    rows = []
    for i in C.wired_soil(station):
        s = mean[SOIL_COL.format(i)].dropna()
        if s.empty:
            continue
        last = s.iloc[-1]
        state = "frozen" if last < -C.ZERO_CURTAIN_C else "thawed" if last > C.ZERO_CURTAIN_C else "near 0 °C (zero curtain)"
        sign = np.sign(s.where(s.abs() > 1e-9))
        cross = s.index[1:][(sign.values[1:] * sign.values[:-1]) < 0]
        zc = (s.abs() <= C.ZERO_CURTAIN_C).astype(int)
        runs = (zc.diff() != 0).cumsum()
        periods = [(g.index[0].date(), g.index[-1].date(), len(g)) for _, g in s[zc == 1].groupby(runs[zc == 1])
                   if len(g) >= C.ZERO_CURTAIN_MIN_DAYS]
        rows.append({
            "Depth": C.soil_label(i),
            "Latest daily mean (°C)": round(last, 2),
            "State": state,
            "Last 0 °C crossing (daily mean)": str(cross[-1].date()) if len(cross) else "none",
            f"Zero-curtain periods (≥{C.ZERO_CURTAIN_MIN_DAYS} d)": "; ".join(
                f"{a:%b %d}–{b:%b %d} ({n} d)" for a, b, n in periods) or "none",
            "Zero-curtain days": int(sum(p[2] for p in periods)),
        })
    return pd.DataFrame(rows)
