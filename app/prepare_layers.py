"""One-off: build the static map layers and per-station site attributes.

Usage: python -I app/prepare_layers.py [SOURCE_ROOT]
SOURCE_ROOT defaults to Desktop/HighwayStability, where the past-project
GIS files live. Writes app/layers/*.geojson, app/layers/alt_overlay.png(+json)
and app/layers/station_site_attributes.csv. Re-run only if sources change.
"""
import json
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import shapely
from matplotlib import colormaps
from PIL import Image
from pyproj import Transformer
from rasterio.warp import Resampling, calculate_default_transform, reproject
from shapely.geometry import box

warnings.filterwarnings("ignore")

APP = Path(__file__).resolve().parent
LAYERS = APP / "layers"
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else APP.parents[1] / "HighwayStability"

JORGENSON = SRC / "review/ground_ice/shp/233-permafrost-characteristics-of-alaska-2008-sha/Permafrost_AK_2008_AlbAK83.shp"
BROWN = SRC / "data/raw/ggd318_map_circumarctic/permaice.shp"
ECOREG = SRC / "data/raw/ecoregions_simplified/ecoregions_simplified.shp"
ALT = SRC / "modeling/outputs_v3_precip/baseline_v3_precip_alt_baseline_cm.tif"

AK_ALBERS = "EPSG:3338"
SIMPLIFY_M = 1000  # simplification tolerance in metres (keeps each file ~1 MB)

# Class names exactly as in the layer metadata (Permafrost_AK_2008_AlbAK83.shp.xml).
PF_EXTENT = {"C": "Continuous (>90%)", "D": "Discontinuous (50-90%)", "S": "Sporadic (10-50%)",
             "I": "Isolated (>0-10%)", "U": "Unfrozen", "G": "Glacier",
             "W": "Large waterbodies (unfrozen below)"}
# Brown et al. (2002) legend (NSIDC GGD318): extent + ground-ice content, where the ice
# thresholds depend on landform: f = lowlands/highlands with thick overburden (>5-10 m),
# r = mountains/plateaus with thin overburden and exposed bedrock.
BROWN_EXTENT = {"C": "Continuous (90-100%)", "D": "Discontinuous (50-90%)", "S": "Sporadic (10-50%)",
                "I": "Isolated (0-10%)"}
BROWN_ICE = {("h", "f"): "high ice (>20%)", ("m", "f"): "medium ice (10-20%)", ("l", "f"): "low ice (0-10%)",
             ("h", "r"): "high ice (>10%)", ("l", "r"): "low ice (0-10%)"}
BROWN_LANDFORM = {"f": "thick overburden", "r": "thin overburden / bedrock"}


def _clip_window():
    """Alaska east of the antimeridian (179.9 W - 129 W, 50-72 N), densified and
    projected to EPSG:3338. Clipping before reprojecting stops polygons that cross
    180 deg (western Aleutians) from wrapping around the globe in WGS84."""
    ll = shapely.segmentize(box(-179.9, 50, -129, 72), 0.25)
    return gpd.GeoSeries([ll], crs=4326).to_crs(AK_ALBERS).iloc[0]


def write(gdf, name, cols):
    gdf = gdf[cols + ["geometry"]].copy()
    gdf["geometry"] = gdf.geometry.intersection(_clip_window())
    gdf["geometry"] = gdf.geometry.simplify(SIMPLIFY_M, preserve_topology=True)
    gdf = gdf[~gdf.geometry.is_empty].to_crs(4326)
    geom = shapely.make_valid(np.asarray(gdf.geometry.values))
    geom = shapely.make_valid(shapely.set_precision(geom, 0.001))  # ~100 m, shrinks GeoJSON text
    gdf["geometry"] = [_polygons_only(g) for g in geom]  # drop slivers make_valid turns into lines/points
    gdf = gdf[~gdf.geometry.is_empty]
    path = LAYERS / f"{name}.geojson"
    path.write_text(gdf.to_json(drop_id=True, to_wgs84=True), encoding="utf-8")
    print(f"{name}: {len(gdf)} features, {path.stat().st_size / 1e6:.1f} MB")


def _polygons_only(g):
    parts = [p for p in shapely.get_parts(g) if p.geom_type in ("Polygon", "MultiPolygon")]
    return shapely.MultiPolygon([q for p in parts for q in shapely.get_parts(p)]) if parts else shapely.Polygon()


def dissolve(gdf, col):
    out = gdf[[col, "geometry"]].dissolve(by=col).reset_index()
    out["geometry"] = out.geometry.buffer(0)
    return out


def main():
    LAYERS.mkdir(exist_ok=True)
    stations = pd.read_csv(APP.parent / "station_data_survey/tableau/stations.csv")
    known = stations.dropna(subset=["lat", "lon"])
    pts = gpd.GeoDataFrame(known, geometry=gpd.points_from_xy(known.lon, known.lat), crs=4326).to_crs(AK_ALBERS)
    attrs = known[["station"]].copy()

    # Jorgenson et al. 2008 - one layer per theme, dissolved by class.
    jg = gpd.read_file(JORGENSON).to_crs(AK_ALBERS)
    jg["pf_extent"] = jg["PF_EXTENT"].map(PF_EXTENT)
    jg["ThrmoKarst"] = jg["ThrmoKarst"].replace({"Thaw Stable: Ice-poor": "Thaw Stable, Ice-poor"})
    for name, col in [("jorgenson_permafrost_extent", "pf_extent"), ("jorgenson_ground_ice", "ICECLOWASS"),
                      ("jorgenson_soil_texture", "TEXTURE"), ("jorgenson_surficial_deposits", "AGGRDEPOS"),
                      ("jorgenson_ecoregions", "ECOREGION"), ("jorgenson_mean_annual_air_temp", "MAAT_NUMB")]:
        write(dissolve(jg, col), name, [col])
    hit = gpd.sjoin(pts, jg, how="left", predicate="within")
    for col, label in [("pf_extent", "Permafrost extent (Jorgenson 2008)"), ("ICECLOWASS", "Ground ice (Jorgenson 2008)"),
                       ("TEXTURE", "Soil texture"), ("AGGRDEPOS", "Surficial deposit"),
                       ("ThrmoKarst", "Thermokarst landforms"), ("MAAT_NUMB", "Mapped MAAT (C)"),
                       ("ECOREGION", "Ecoregion")]:
        attrs[label] = hit[col].values

    # Brown et al. (IPA) circum-Arctic map, clipped to Alaska.
    br = gpd.read_file(BROWN).to_crs(AK_ALBERS)
    ak = box(-2_300_000, 300_000, 1_600_000, 2_500_000)
    br = br[br.intersects(ak)].copy()
    br = br[br["EXTENT"].isin(BROWN_EXTENT)]
    br["ipa_class"] = [f"{BROWN_EXTENT[e]}, {BROWN_ICE.get((c, l), 'ice n/a')}, {BROWN_LANDFORM.get(l, '?')}"
                       for e, c, l in zip(br["EXTENT"], br["CONTENT"], br["LANDFORM"])]
    write(dissolve(br, "ipa_class"), "brown_ipa_permafrost_ground_ice", ["ipa_class"])
    attrs["IPA permafrost / ground ice (Brown et al.)"] = gpd.sjoin(pts, br, how="left", predicate="within")["ipa_class"].values

    # Unified Ecoregions of Alaska (level 2, simplified).
    er = gpd.read_file(ECOREG).to_crs(AK_ALBERS)
    write(er, "ecoregions_level2", ["LEVEL_2"])
    attrs["Ecoregion (level 2)"] = gpd.sjoin(pts, er, how="left", predicate="within")["LEVEL_2"].values

    # Modeled active-layer thickness (HighwayStability baseline v3). Leaflet stretches an
    # ImageOverlay linearly in Web Mercator, so the PNG must be warped to EPSG:3857
    # (warping to EPSG:4326 misplaces it by kilometres over 65-70 N).
    with rasterio.open(ALT) as src:
        dst_tf, w, h = calculate_default_transform(src.crs, "EPSG:3857", src.width, src.height, *src.bounds)
        arr = np.full((h, w), np.nan, dtype="float32")
        reproject(rasterio.band(src, 1), arr, dst_transform=dst_tf, dst_crs="EPSG:3857",
                  resampling=Resampling.nearest, dst_nodata=np.nan)
        nodata = src.nodata
        xs, ys = pts.geometry.x.values, pts.geometry.y.values
        vals = [v[0] for v in src.sample(zip(xs, ys))]
    if nodata is not None:
        arr[arr == nodata] = np.nan
    vmin, vmax = np.nanpercentile(arr, [2, 98])
    rgba = colormaps["viridis"]((arr - vmin) / (vmax - vmin))
    rgba[..., 3] = np.where(np.isnan(arr), 0, 0.75)
    Image.fromarray((rgba * 255).astype("uint8")).save(LAYERS / "alt_overlay.png")
    x0, y1 = dst_tf * (0, 0)
    x1, y0 = dst_tf * (w, h)
    (west, east), (south, north) = Transformer.from_crs(3857, 4326, always_xy=True).transform([x0, x1], [y0, y1])
    (LAYERS / "alt_overlay.json").write_text(json.dumps(
        {"bounds": [[south, west], [north, east]], "vmin": float(vmin), "vmax": float(vmax), "units": "cm",
         "colormap": "viridis", "crs_of_png": "EPSG:3857"}))
    attrs["Modeled active layer (cm)"] = [None if (nodata is not None and v == nodata) or np.isnan(v) else round(float(v))
                                          for v in vals]
    print("alt overlay:", w, "x", h, "range", round(vmin), "-", round(vmax), "cm")

    attrs.to_csv(LAYERS / "station_site_attributes.csv", index=False)
    print(attrs.to_string())

    # QA: site values above come from the ORIGINAL polygons; check the simplified
    # display layers give the same class at each station.
    pts84 = pts.to_crs(4326)
    for stem, col, label in [("jorgenson_permafrost_extent", "pf_extent", "Permafrost extent (Jorgenson 2008)"),
                             ("jorgenson_ground_ice", "ICECLOWASS", "Ground ice (Jorgenson 2008)"),
                             ("jorgenson_soil_texture", "TEXTURE", "Soil texture"),
                             ("brown_ipa_permafrost_ground_ice", "ipa_class", "IPA permafrost / ground ice (Brown et al.)")]:
        simp = gpd.read_file(LAYERS / f"{stem}.geojson")
        got = gpd.sjoin(pts84, simp, how="left", predicate="within").drop_duplicates("station")[col].values
        bad = [f"{s}: {a!r} vs {b!r}" for s, a, b in zip(attrs.station, attrs[label], got) if str(a) != str(b)]
        print(f"QA {stem}: {'all stations match' if not bad else 'MISMATCH ' + '; '.join(bad)}")


if __name__ == "__main__":
    main()
