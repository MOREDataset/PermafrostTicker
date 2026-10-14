"""Folium map of the stations with one optional reference layer."""
import json

import folium
import streamlit as st

import config as C

HEALTH_COLOUR = {"green": "#2e9e44", "orange": "#e69500", "red": "#d62728"}

# stem -> (menu label, property, colours or None/"maat", one-line explanation, source line)
J08 = "Jorgenson et al. (2008), Permafrost Characteristics of Alaska, UAF/INE; 1:250,000 terrain units, 1–3 km positional error."
LAYERS = {
    "jorgenson_permafrost_extent": (
        "Permafrost extent", "pf_extent", {
            "Continuous (>90%)": "#2b4c8c", "Discontinuous (50-90%)": "#5b8fd6", "Sporadic (10-50%)": "#a8c8f0",
            "Isolated (>0-10%)": "#dcebfa", "Unfrozen": "#f2e6c9", "Glacier": "#ffffff",
            "Large waterbodies (unfrozen below)": "#9ecae1"},
        "Share of the ground area that is underlain by permafrost.", J08),
    "jorgenson_ground_ice": (
        "Ground ice content", "ICECLOWASS", {
            "High": "#08306b", "Moderate": "#4292c6", "Low": "#c6dbef", "Variable": "#9e9ac8",
            "Unfrozen": "#f2e6c9", "Glacier": "#ffffff"},
        "Volume of excess ice in the upper permafrost; high-ice ground is prone to thaw settlement.", J08),
    "jorgenson_soil_texture": (
        "Soil texture", "TEXTURE", {
            "Silty": "#c49a6c", "Sandy": "#f0d78c", "Rocky": "#8c8c8c", "Ice": "#ffffff", "Water": "#9ecae1"},
        "Dominant texture of the surficial deposit.", J08),
    "jorgenson_surficial_deposits": (
        "Surficial deposits", "AGGRDEPOS", None,
        "Type of surface geology (glacial, fluvial, eolian, bedrock, ...).", J08),
    "jorgenson_mean_annual_air_temp": (
        "Mapped mean annual air temperature (°C)", "MAAT_NUMB", "maat",
        "Climate class used to assign permafrost extent (1961–1990 normals).", J08),
    "brown_ipa_permafrost_ground_ice": (
        "IPA permafrost & ground ice (circum-Arctic)", "ipa_class", None,
        "Extent and ice content; ice thresholds differ for thick-sediment lowlands and thin-overburden mountains.",
        "Brown et al. (2002), Circum-Arctic Map of Permafrost and Ground-Ice Conditions v2, NSIDC GGD318; 1:10,000,000."),
    "jorgenson_ecoregions": (
        "Ecoregions (detailed)", "ECOREGION", None,
        "Ecoregions of Alaska as attributed in the permafrost map.", "Nowacki et al. (2001) ecoregions, via " + J08),
    "ecoregions_level2": (
        "Ecoregions (level 2)", "LEVEL_2", None, "Broad ecological regions (boreal, tundra, ...).",
        "Nowacki et al. (2001), Unified Ecoregions of Alaska, USGS OFR 2002-297 (simplified)."),
}
ALT_KEY = "alt_model"
ALT_INFO = ("Modeled active-layer thickness (Dalton corridor)",
            "Modeled late-summer thaw depth; covers the Dalton Highway corridor model domain only.",
            "HighwayStability project, baseline v3 (precip), 1 km grid; internal model output, not field-validated.")
PALETTE = ["#1b9e77", "#d95f02", "#7570b3", "#e7298a", "#66a61e", "#e6ab02", "#a6761d", "#666666",
           "#1f78b4", "#b2df8a", "#fb9a99", "#fdbf6f", "#cab2d6", "#ffff99", "#8dd3c7", "#bebada",
           "#80b1d3", "#fccde5", "#bc80bd", "#ccebc5", "#ffed6f", "#fb8072", "#b3de69", "#d9d9d9"]
LABEL_LEFT = {"DBNF22"}
VIRIDIS = ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"]


def _geojson(stem):
    path = C.LAYERS_DIR / f"{stem}.geojson"
    return _load_geojson(str(path), path.stat().st_mtime)


@st.cache_data(show_spinner=False)
def _load_geojson(path, mtime_key):  # mtime_key (no underscore) so Streamlit hashes it
    return json.loads(open(path, encoding="utf-8").read())


def colours(stem):
    _, prop, spec, *_ = LAYERS[stem]
    classes = sorted({f["properties"][prop] for f in _geojson(stem)["features"]}, key=str)
    if spec == "maat":  # blue (cold) -> red (warm)
        lo, hi = min(classes), max(classes)
        def ramp(v):
            t = (v - lo) / (hi - lo or 1)
            return "#%02x%02x%02x" % (int(40 + 200 * t), int(90 + 60 * (1 - abs(t - .5) * 2)), int(230 - 200 * t))
        return {c: ramp(c) for c in classes}
    if spec:
        return {c: spec.get(c, "#cccccc") for c in classes}
    return {c: PALETTE[i % len(PALETTE)] for i, c in enumerate(classes)}


def legend_html(stem):
    if stem == ALT_KEY:
        info = json.loads((C.LAYERS_DIR / "alt_overlay.json").read_text())
        bar = "linear-gradient(to right," + ",".join(VIRIDIS) + ")"
        return (f"<div style='font-size:13px'><span>{info['vmin']:.0f} cm</span>"
                f"<span style='display:inline-block;width:220px;height:12px;margin:0 8px;vertical-align:middle;"
                f"background:{bar}'></span><span>{info['vmax']:.0f} cm</span>"
                f" &nbsp;<span style='opacity:.7'>(2nd–98th percentile stretch)</span></div>")
    items = "".join(f"<span style='white-space:nowrap;margin-right:12px'><span style='display:inline-block;"
                    f"width:12px;height:12px;background:{col};border:1px solid #555;margin-right:4px;"
                    f"vertical-align:middle'></span>{cls}</span> "
                    for cls, col in colours(stem).items())
    return f"<div style='font-size:13px;line-height:1.9'>{items}</div>"


def build_map(meta, latest_by_station, layer=None, height_zoom=6):
    m = folium.Map(location=[67.3, -149.6], zoom_start=height_zoom, tiles=None, control_scale=True)
    # Leaflet shows the last-added base layer, so the default (Topographic) goes last.
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap", show=False).add_to(m)
    folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                     attr="Esri World Imagery", name="Satellite", show=False).add_to(m)
    folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
                     attr="Esri World Topo", name="Topographic", show=True).add_to(m)

    if layer in LAYERS:
        label, prop, *_ = LAYERS[layer]
        cmap = colours(layer)
        folium.GeoJson(
            _geojson(layer), name=label,
            style_function=lambda f, p=prop, c=cmap: {"fillColor": c.get(f["properties"][p], "#ccc"),
                                                      "color": "#555", "weight": 0.3, "fillOpacity": 0.55},
            tooltip=folium.GeoJsonTooltip(fields=[prop], aliases=[label + ":"]),
        ).add_to(m)
    elif layer == ALT_KEY:
        info = json.loads((C.LAYERS_DIR / "alt_overlay.json").read_text())
        folium.raster_layers.ImageOverlay(str(C.LAYERS_DIR / "alt_overlay.png"), bounds=info["bounds"],
                                          name=ALT_INFO[0], opacity=0.8).add_to(m)

    group = folium.FeatureGroup(name="Stations").add_to(m)
    for _, r in meta[meta["has_location"]].iterrows():
        s = r["station"]
        x = latest_by_station.get(s, {})
        soil = x.get("soil", {})
        soil_txt = " · ".join(f"{d} cm {fmt(v)}" for d, v in soil.items())
        loc_note = f"<br><span style='color:#666'>Location {C.LOCATION_NOTES[s]}</span>" if s in C.LOCATION_NOTES else ""
        popup = f"""<div style='font-family:sans-serif;font-size:12px;min-width:230px'>
            <b>{s}</b> – {r['region']}<br>{r['lat']:.4f}° N, {abs(r['lon']):.4f}° W · {int(r['elev_ft']):,} ft{loc_note}
            <hr style='margin:4px 0'>Air {fmt(x.get('air'))} °C · RH {fmt(x.get('rh'), 0)} %<br>
            Soil (°C): {soil_txt}<br>Battery {fmt(x.get('batt'), 2)} V<br>
            <span style='color:#666'>Status: {x.get('health_reason', '?')}<br>
            Last record {x.get('time', '?')} AKST</span></div>"""
        folium.CircleMarker([r["lat"], r["lon"]], radius=9, color=HEALTH_COLOUR[x.get("health", "red")], weight=4,
                            fill=True, fill_color=C.STATION_COLOURS[s], fill_opacity=1,
                            popup=folium.Popup(popup, max_width=320),
                            tooltip=f"{s}: air {fmt(x.get('air'))} °C").add_to(group)
        left = s in LABEL_LEFT  # DBNF22/DBNF23 are ~4 km apart: put one label on each side
        folium.map.Marker([r["lat"], r["lon"]], icon=folium.DivIcon(
            icon_size=(70, 16), icon_anchor=(82, 8) if left else (-12, 8),
            html=f"<div style='font-size:12px;font-weight:700;color:#111;text-align:{'right' if left else 'left'};"
                 f"text-shadow:0 0 3px #fff,0 0 3px #fff'>{s}</div>"),
        ).add_to(group)

    folium.LayerControl(collapsed=True).add_to(m)
    return m


def fmt(v, nd=1):
    try:
        v = float(v)
        return "–" if v != v else f"{v:.{nd}f}"
    except (TypeError, ValueError):
        return "–"
