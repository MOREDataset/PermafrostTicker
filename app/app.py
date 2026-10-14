"""UND Alaska Permafrost Network - live station dashboard.

Run:  streamlit run app/app.py   (or double-click start_dashboard.cmd)
Data: ../station_data_survey/<STATION>/*.dat, refreshed hourly by the
      "PermafrostTicker Hourly Refresh" scheduled task. Without those files (e.g. on
      Streamlit Community Cloud) the app downloads them itself; see config.DATA_MODE.
"""
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from streamlit_folium import st_folium

import config as C
import data as D
import map_view as MV

st.set_page_config(page_title="Alaska Permafrost Stations", page_icon="🧊", layout="wide")

WINDOWS = {"7 d": 7, "30 d": 30, "90 d": 90, "All": None}
DOT = {"green": "🟢", "orange": "🟠", "red": "🔴"}
fmt = MV.fmt

meta = D.stations_meta()
meta_i = meta.set_index("station")
latest = {s: D.latest(s) for s in C.STATIONS}


def station_name(s):
    lat = meta_i.loc[s, "lat"]
    return f"{s} ({lat:.2f}° N)" if pd.notna(lat) else f"{s} (location unknown)"


SOUTH_TO_NORTH = list(meta.sort_values("lat", na_position="last")["station"])


def window_picker(key, default="30 d"):
    choice = st.segmented_control("Time window", list(WINDOWS), default=default, key=key,
                                  help="How far back from the latest record to show.")
    return WINDOWS[choice or default], (choice or default)


def provisional_badge():
    st.badge("provisional – less than one full season of record", icon="⏳", color="orange")


# ---------------------------------------------------------------- sidebar (minimal)
with st.sidebar:
    st.title("🧊 Permafrost stations")
    st.caption("UND Alaska Permafrost Network · Brooks Range & Yukon–Tanana Uplands")
    newest = max(D.file_mtime(s, "QtrHrly") for s in C.STATIONS)
    st.caption(f"Data last downloaded {datetime.fromtimestamp(newest, C.LOGGER_TZ):%Y-%m-%d %H:%M} AKST; "
               f"refreshes hourly.")
    if st.button("Reload data now", help="Re-read the station files without waiting for the cache."):
        D.reload_remote()
        st.cache_data.clear()
        st.rerun()
    st.caption(f"All times are logger time, **AKST (UTC−9, no daylight saving)**. "
               f"Now {D.now_logger():%Y-%m-%d %H:%M} AKST.")

tab_over, tab_station, tab_layers, tab_health, tab_about = st.tabs(
    ["Overview", "Station", "Map layers", "Station health", "About & methods"])


# ---------------------------------------------------------------- Overview
def ticker_card(x):
    s = x["station"]
    soil = x.get("soil", {})
    shallow = min(soil) if soil else None
    deep = max(soil) if soil else None
    age = x.get("age_min")
    row = lambda k, v: (f"<div style='display:flex;justify-content:space-between'>"
                        f"<span style='opacity:.75'>{k}</span><b>{v}</b></div>")
    flag = " <span title='depth unverified' style='opacity:.7'>⚠</span>" if s in C.DEPTH_UNVERIFIED else ""
    return (f"<div style='border-left:6px solid {C.STATION_COLOURS[s]};padding:6px 10px;border-radius:6px;"
            f"background:rgba(128,128,128,.08);font-size:14px' title='{x['health_reason']}'>"
            f"<div style='font-weight:700;font-size:15px'>{DOT[x['health']]} {s}</div>"
            + row("Air", f"{fmt(x.get('air'))} °C")
            + (row(f"Soil {shallow} cm{flag}", f"{fmt(soil.get(shallow))} °C") if soil else "")
            + (row(f"Soil {deep} cm{flag}", f"{fmt(soil.get(deep))} °C") if soil and deep != shallow else "")
            + row("Battery", f"{fmt(x.get('batt'), 2)} V")
            + f"<div style='opacity:.6;font-size:12px'>{'no data' if age is None else f'{age:.0f} min ago'}</div></div>")


def network_chart(days):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=("Air temperature at 2 m", "Soil temperature at 15 cm (nominal)"))
    for s in SOUTH_TO_NORTH:
        h = D.hourly(s, ["AirT_Primary_C", "SoilT_2_C"], days)
        if h.empty:
            continue
        kw = dict(name=station_name(s), legendgroup=s, line=dict(color=C.STATION_COLOURS[s], width=1.6),
                  connectgaps=False, hovertemplate="%{y:.1f} °C")
        fig.add_trace(go.Scatter(x=h["TIMESTAMP"], y=h["AirT_Primary_C"], **kw), row=1, col=1)
        fig.add_trace(go.Scatter(x=h["TIMESTAMP"], y=h["SoilT_2_C"], showlegend=False, **kw), row=2, col=1)
    for r in (1, 2):
        fig.add_hline(y=0, line_dash="dot", line_color="grey", row=r, col=1)
        fig.update_yaxes(title_text="°C", row=r, col=1)
    fig.update_xaxes(title_text="Logger time (AKST)", row=2, col=1)
    fig.update_layout(height=480, hovermode="x unified", legend_title_text="South → North",
                      margin=dict(t=40, b=10, l=10, r=10))
    return fig


with tab_over:
    n_ok = sum(latest[s]["health"] == "green" for s in C.STATIONS)
    newest_rec = max(latest[s].get("time") for s in C.STATIONS if latest[s].get("time") is not None)
    st.markdown(f"**{n_ok} of {len(C.STATIONS)} stations reporting normally** · newest record "
                f"{newest_rec:%Y-%m-%d %H:%M} AKST")
    st.markdown("<div style='display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:8px'>"
                + "".join(ticker_card(latest[s]) for s in C.STATIONS) + "</div>", unsafe_allow_html=True)
    st.caption("Card colour bar = station colour used in every chart. Dot: 🟢 OK · 🟠 battery < "
               f"{C.BATTERY_WARN_V} V · 🔴 overdue (no record for the station's call-in interval + 1 h) or "
               f"battery < {C.BATTERY_LOW_V} V. ⚠ = sensor depth not yet verified. Hover a card for the reason.")

    c_map, c_chart = st.columns([2, 3], gap="medium")
    with c_map:
        st.markdown("##### Where the stations are")
        st_folium(MV.build_map(meta, latest, layer=None, height_zoom=5), height=480,
                  use_container_width=True, returned_objects=[], key="overview_map")
        unknown = meta.loc[~meta["has_location"], "station"].tolist()
        if unknown:
            st.caption(f"Not on the map (location unknown): {', '.join(unknown)}. Click a marker for latest values.")
        for s, note in C.LOCATION_NOTES.items():
            st.caption(f"{s} location is {note}.")
    with c_chart:
        st.markdown("##### Air vs shallow soil, all stations")
        days, _ = window_picker("over_win")
        st.plotly_chart(network_chart(days), width="stretch")
        st.caption("Hourly means (an hour needs ≥ 3 of its 4 records); breaks in a line are missing data, "
                   "not zero. Soil lags and damps air-temperature swings; shallow soil holding near 0 °C "
                   "while air is below freezing is the freeze-back 'zero curtain'.")


# ---------------------------------------------------------------- Station
with tab_station:
    c1, c2 = st.columns([1, 2])
    with c1:
        station = st.selectbox("Station", C.STATIONS, format_func=lambda s: f"{s} – {meta_i.loc[s, 'region']}")
    with c2:
        days, win_label = window_picker("station_win")
    x = latest[station]

    if station in C.DEPTH_UNVERIFIED:
        st.warning(f"**Depth unverified at {station}:** soil sensors are shown at nominal depths "
                   f"0/15/30/50 cm, but {C.DEPTH_UNVERIFIED[station]}. Interpret depth-dependent results with care.",
                   icon="⚠️")

    with st.container(horizontal=True):
        st.metric("Air (2 m)", f"{fmt(x.get('air'))} °C", border=True)
        for d, v in x.get("soil", {}).items():
            st.metric(f"Soil {d} cm", f"{fmt(v)} °C", border=True)
        st.metric("Relative humidity", f"{fmt(x.get('rh'), 0)} %", border=True)
    st.caption(f"Latest 15-min record: {x.get('time', '?')} AKST.")

    s = D.series(station, days)
    if s.empty or s.drop(columns="TIMESTAMP").isna().all().all():
        st.info("No data in this window.")
    else:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=s["TIMESTAMP"], y=s["AirT_Primary_C"], name="Air (2 m)", connectgaps=False,
                                 line=dict(color=C.DEPTH_COLOURS["Air"], width=1)))
        for i in C.wired_soil(station):
            d = C.soil_depth(i)
            fig.add_trace(go.Scatter(x=s["TIMESTAMP"], y=s[D.SOIL_COL.format(i)], name=f"Soil {d} cm",
                                     connectgaps=False, line=dict(color=C.DEPTH_COLOURS[d], width=1.8)))
        fig.add_hline(y=0, line_dash="dot", line_color="grey")
        fig.update_layout(height=420, hovermode="x unified", margin=dict(t=40, b=10),
                          title=f"{station}: air and soil temperature, 15-min records ({win_label})",
                          xaxis_title="Logger time (AKST)", yaxis_title="Temperature (°C)",
                          legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig, width="stretch")
        st.caption("Breaks in a line are missing records. Deeper soil responds later and less strongly than air.")

    st.markdown("##### Soil thermal state this season")
    st.dataframe(D.soil_state(station), width="stretch", hide_index=True)
    st.caption(f"From daily means (a day needs ≥ {C.DAILY_MIN_COVERAGE:.0%} of its 15-min records) since "
               f"{D.season_start(pd.Timestamp.now()):%d %b %Y}. *Frozen* < −{C.ZERO_CURTAIN_C} °C, *thawed* > "
               f"+{C.ZERO_CURTAIN_C} °C. A *zero-curtain period* is ≥ {C.ZERO_CURTAIN_MIN_DAYS} consecutive days "
               f"within ±{C.ZERO_CURTAIN_C} °C, when latent heat of freezing holds the soil near 0 °C.")

    dd, info = D.degree_days(station)
    st.markdown("##### Freezing and thawing degree-days")
    if info.get("provisional"):
        provisional_badge()
    if not dd.empty:
        fig = go.Figure()
        styles = {"FDD air": ("#4575b4", "solid"), "FDD soil 0 cm": ("#4575b4", "dash"),
                  "TDD air": ("#d73027", "solid"), "TDD soil 0 cm": ("#d73027", "dash")}
        for col, (colour, dash) in styles.items():
            fig.add_trace(go.Scatter(x=dd["date"], y=dd[col], name=col, line=dict(color=colour, dash=dash)))
        fig.update_layout(height=320, margin=dict(t=10, b=10), hovermode="x unified",
                          xaxis_title="Day (AKST)", yaxis_title="Cumulative °C·days",
                          legend=dict(orientation="h", y=-0.25))
        st.plotly_chart(fig, width="stretch")
        nf = info.get("n_factor_freezing")
        cols = st.columns(3)
        cols[0].metric("FDD air", f"{dd['FDD air'].iloc[-1]:.0f} °C·d", border=True,
                       help="Freezing degree-days: sum of daily mean temperatures below 0 °C (as positive numbers).")
        cols[1].metric("TDD air", f"{dd['TDD air'].iloc[-1]:.0f} °C·d", border=True,
                       help="Thawing degree-days: sum of daily mean temperatures above 0 °C.")
        cols[2].metric("Freezing n-factor (0 cm / air)", "–" if nf is None else f"{nf:.2f}", border=True,
                       help="FDD at the ground surface divided by FDD of air over the same days. "
                            "Values < 1 mean snow/vegetation insulate the ground. Meaningful only over a "
                            "full freezing season.")
        st.caption(f"Accumulated from {info['season_start']:%d %b %Y} (season start, 1 July convention) or the start "
                   f"of record ({info['record_start']:%d %b %Y}), over {info['valid_days']} valid days; "
                   f"{info['failed_days']} day(s) skipped for incomplete data.")

    with st.expander("Advanced: depth–time plot, temperature envelope, data quality and download"):
        soil_cols = [D.SOIL_COL.format(i) for i in C.wired_soil(station)]
        h = D.hourly(station, soil_cols, days)
        depths = [C.soil_depth(i) for i in C.wired_soil(station)]
        a1, a2 = st.columns([3, 2])
        with a1:
            if not h.empty and h[soil_cols].notna().any().any():
                z = h[soil_cols].T.values
                lim = max(float(abs(pd.DataFrame(z).min().min())), float(abs(pd.DataFrame(z).max().max())), 1.0)
                if len(depths) >= 3:
                    trace = go.Contour(x=h["TIMESTAMP"], y=depths, z=z, zmid=0, zmin=-lim, zmax=lim,
                                       colorscale="RdBu_r", connectgaps=False, colorbar=dict(title="°C"),
                                       contours=dict(coloring="heatmap", showlines=True, start=0, end=0, size=1))
                    note = ("Colours are linearly interpolated between sensor depths (no extrapolation below "
                            f"{max(depths)} cm); the black line is the 0 °C isotherm. Gaps stay blank.")
                else:
                    trace = go.Heatmap(x=h["TIMESTAMP"], y=depths, z=z, zmid=0, zmin=-lim, zmax=lim,
                                       colorscale="RdBu_r", colorbar=dict(title="°C"))
                    note = "Only two sensor depths: each band is one sensor, no interpolation between them."
                fig = go.Figure(trace)
                fig.update_yaxes(autorange="reversed", title="Depth (cm)", tickvals=depths)
                fig.update_layout(height=330, margin=dict(t=30, b=10), title="Soil temperature by depth and time (hourly)",
                                  xaxis_title="Logger time (AKST)")
                st.plotly_chart(fig, width="stretch")
                st.caption(note)
        with a2:
            ss = D.series(station, days, regular_grid=False)
            if not ss.empty:
                prof = pd.DataFrame({"depth": depths,
                                     "min": [ss[c].min() for c in soil_cols],
                                     "mean": [ss[c].mean() for c in soil_cols],
                                     "max": [ss[c].max() for c in soil_cols]})
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=prof["max"], y=prof["depth"], name="max", line=dict(color="#d73027")))
                fig.add_trace(go.Scatter(x=prof["min"], y=prof["depth"], name="min", line=dict(color="#4575b4"),
                                         fill="tonextx", fillcolor="rgba(150,150,150,0.15)"))
                fig.add_trace(go.Scatter(x=prof["mean"], y=prof["depth"], name="mean",
                                         line=dict(color="#555", dash="dot")))
                fig.add_vline(x=0, line_dash="dot", line_color="grey")
                fig.update_yaxes(autorange="reversed", title="Depth (cm)", tickvals=depths)
                fig.update_layout(height=330, margin=dict(t=30, b=10), xaxis_title="Temperature (°C)",
                                  title=f"Temperature envelope ({win_label})", legend=dict(orientation="h", y=-0.3))
                st.plotly_chart(fig, width="stretch")
                st.caption("Min/mean/max of 15-min records at each sensor depth (the 'trumpet curve'). "
                           "A true trumpet curve and active-layer depth need a full year of record.")
                provisional_badge()

        st.markdown("**Quality control applied to this station's 15-min table**")
        log = D.qc_log(station, "QtrHrly")
        lim = D.qc_limits(station)
        st.caption(f"Plausible ranges from the logger's Const_Table: air {lim['air']} °C, soil {lim['soil']} °C, "
                   f"RH {lim['rh']} %, battery {lim['batt_v']} V.")
        st.dataframe(pd.DataFrame({"Rule": list(log), "Values removed": list(log.values())}),
                     hide_index=True, width="stretch")

        raw = D.series(station, days, regular_grid=False).rename(
            columns={"TIMESTAMP": "timestamp_akst", "AirT_Primary_C": "air_2m_C",
                     **{D.SOIL_COL.format(i): f"soil_{C.soil_depth(i)}cm_C" for i in C.wired_soil(station)}})
        st.download_button(f"Download cleaned 15-min data ({station}, {win_label}) as CSV",
                           raw.to_csv(index=False).encode(), file_name=f"{station}_15min_clean_{win_label.replace(' ', '')}.csv",
                           mime="text/csv")


# ---------------------------------------------------------------- Map layers
with tab_layers:
    options = list(MV.LAYERS) + [MV.ALT_KEY]
    label_of = lambda k: MV.ALT_INFO[0] if k == MV.ALT_KEY else MV.LAYERS[k][0]
    layer = st.selectbox("Reference layer", options, format_func=label_of,
                         help="One layer at a time. Values at each station are listed in the table below.")
    expl, src = (MV.ALT_INFO[1], MV.ALT_INFO[2]) if layer == MV.ALT_KEY else MV.LAYERS[layer][3:5]
    st.caption(f"{expl} **Source:** {src}")
    st_folium(MV.build_map(meta, latest, layer=layer), height=560, use_container_width=True,
              returned_objects=[], key="layer_map")
    st.markdown(MV.legend_html(layer), unsafe_allow_html=True)

    st.markdown("##### What the reference maps say at each station")
    site = meta.set_index("station").drop(columns=["lat", "lon", "has_location", "name"], errors="ignore")
    site["elev_ft"] = site["elev_ft"].map(lambda v: f"{v:,.0f}" if pd.notna(v) else "unknown")
    site = site.rename(columns={"region": "Region", "elev_ft": "Elevation (ft)"})
    st.dataframe(site.T.astype(str).replace({"nan": "–"}), width="stretch")
    st.caption("Values are read from the original (unsimplified) polygons and raster at each station's "
               "coordinates. Statewide maps have 1–3 km (Jorgenson) to ~10 km (Brown) positional uncertainty, "
               "so treat them as regional context, not site measurements.")


# ---------------------------------------------------------------- Station health
with tab_health:
    rows = []
    for s in C.STATIONS:
        x = latest[s]
        rows.append({"": DOT[x["health"]], "Station": s, "Status": x["health_reason"],
                     "Last record (AKST)": x.get("time"),
                     "Minutes ago": round(x["age_min"]) if x.get("age_min") is not None else None,
                     "Expected every (min)": x["stale_after_min"] - 60,
                     "Battery (V)": x.get("batt"), "State of charge (%)": x.get("soc"),
                     "Charge reading from (AKST)": x.get("soc_time")})
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True,
                 column_config={"Battery (V)": st.column_config.NumberColumn(format="%.2f"),
                                "State of charge (%)": st.column_config.NumberColumn(format="%.1f")})
    st.caption("State of charge comes from the logger's Public table, written only when the station calls in; "
               "at DYTF20 it has not updated since 2026-09-29.")

    days_h, _ = window_picker("health_win")
    fig = go.Figure()
    for s in C.STATIONS:
        d = D.window(D.table(s, "HrlyDiag"), days_h)
        if not d.empty:
            fig.add_trace(go.Scatter(x=d["TIMESTAMP"], y=d["Batt_V_Avg"], name=s,
                                     line=dict(color=C.STATION_COLOURS[s], width=1.5)))
    fig.add_hline(y=C.BATTERY_LOW_V, line_dash="dash", line_color="red",
                  annotation_text=f"low ({C.BATTERY_LOW_V} V)", annotation_position="bottom right")
    fig.update_layout(height=360, hovermode="x unified", title="Battery voltage (hourly mean)",
                      xaxis_title="Logger time (AKST)", yaxis_title="Volts", margin=dict(t=40, b=10))
    st.plotly_chart(fig, width="stretch")
    st.caption("A healthy solar-charged battery rises during the day and settles above ~12.5 V at night.")

    with st.expander("Power budget per station: solar input vs load"):
        hs = st.selectbox("Station", C.STATIONS, key="health_station")
        d = D.window(D.table(hs, "HrlyDiag"), days_h)
        if not d.empty:
            f2 = go.Figure()
            f2.add_trace(go.Scatter(x=d["TIMESTAMP"], y=d["ISolar_A_Avg"], name="Solar input", fill="tozeroy",
                                    line=dict(color="#f2b701")))
            f2.add_trace(go.Scatter(x=d["TIMESTAMP"], y=d["ILoad_A_Avg"], name="Load", line=dict(color="#444")))
            f2.update_layout(height=300, hovermode="x unified", xaxis_title="Logger time (AKST)",
                             yaxis_title="Current (A, hourly mean)", margin=dict(t=10, b=10))
            st.plotly_chart(f2, width="stretch")
            dd2 = D.window(D.table(hs, "DailyDiag"), days_h)
            if not dd2.empty:
                bal = dd2.assign(net=dd2["IBatt_A_Avg"] * 24)
                f3 = go.Figure(go.Bar(x=bal["TIMESTAMP"] - pd.Timedelta(days=1), y=bal["net"],
                                      marker_color=["#2e9e44" if v >= 0 else "#d62728" for v in bal["net"]]))
                f3.update_layout(height=240, xaxis_title="Day (AKST)", yaxis_title="Net charge (Ah/day)",
                                 margin=dict(t=10, b=10))
                st.plotly_chart(f3, width="stretch")
                st.caption("Green = battery gained charge that day, red = net drain. Persistent red days in winter "
                           "mean the station will eventually run flat.")


# ---------------------------------------------------------------- About & methods
with tab_about:
    st.markdown(f"""
#### Station data
* Source: `https://gwscientific.com/remote/UND_DOT_RWIS/<STATION>/data/` (Campbell Scientific TOA5 files),
  downloaded hourly ({"by the PC's scheduled refresh task" if C.DATA_MODE == "local" else "by the app itself"}).
* Tables used: **QtrHrly** (15-min air, soil, RH — all temperature analyses), **HrlyDiag / DailyDiag**
  (battery and power), **Public** (state of charge), **ControlVariables** (call-in schedule),
  **Const_Table** (the logger's own plausible ranges used for QC).
* Times are logger time **AKST (UTC−9)** year-round.
* Soil sensors: SoilT_1–4 at nominal **0, 15, 30, 50 cm**; DBNF26 and DBSF27 have only 0 and 15 cm wired.
  Depths at {", ".join(C.DEPTH_UNVERIFIED)} are **unverified** (sensor responses do not follow the nominal order).
* Hidden until installed: wind, snow depth, rain, soil moisture/conductivity (`SHOW_FUTURE_SENSORS` in `app/config.py`).

#### Processing and metric definitions
* **Quality control:** values outside the logger's Const_Table ranges are removed (this removes the open soil
  channels reading about −110 °C), as are current spikes > {C.MAX_CURRENT_A} A, RH = 0 rows, NTCIP error codes
  1001/3001, duplicated time stamps and DBSF27 installation data before 2026-10-11. Nothing is gap-filled.
* **Gaps:** 15-min series are placed on a regular grid; missing records show as breaks in the lines.
* **Daily mean:** mean of a calendar day's 15-min records, only if ≥ {C.DAILY_MIN_COVERAGE:.0%} of the 96 are present.
* **Degree-days:** FDD = Σ max(0, −T̄day), TDD = Σ max(0, T̄day), accumulated from **1 July** (season start)
  over valid days. **Freezing n-factor** = FDD(0 cm soil) / FDD(air) over the same days.
* **Zero curtain:** ≥ {C.ZERO_CURTAIN_MIN_DAYS} consecutive days with |daily mean| ≤ {C.ZERO_CURTAIN_C} °C.
* **Provisional:** degree-days, n-factor and the temperature envelope are marked provisional until
  {C.FULL_SEASON_DAYS} days of record exist — the network started in Aug–Oct 2026.
""")
    st.divider()
    st.markdown((C.LAYERS_DIR / "SOURCES.md").read_text(encoding="utf-8"))
