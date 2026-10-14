# Dashboard review (2026-10-13)

Scope: data handling, derived permafrost metrics, map layers and the user interface of the
Streamlit dashboard. The previous version is preserved in `app_v1_backup/`.

## 1. Data

| Check | Finding | Action |
|---|---|---|
| Units | All temperatures °C (metric tables), RH %, battery V, currents A. US-unit twin tables are not used. | Units now on every axis and metric. |
| Time zone | Logger clocks are AKST (UTC−9) all year; verified from server `Last-Modified` vs last record. | All times labelled "AKST"; now-time computed in AKST. |
| QC thresholds | v1 used a hard-coded −100 °C cut-off for open channels. The loggers' own `Const_Table` defines the limits (air −55…70 °C, soil −50…70 °C, RH 0…100 %, battery 10.5…15 V). | **Fixed:** limits now read from each logger's Const_Table (fallback to the same values). A per-station QC log (values removed per rule) is shown under *Advanced*. |
| Sentinels | NTCIP 1001/3001 error codes, RH = 0 dead-sensor rows, 135.6 A current spike at DBNF26. | Masked (unchanged), RH = 0 also blanks dew point and vapour pressure. |
| Duplicates / install rows | DBSF27: 4 duplicated time stamps and 71 installation-day rows (bench readings, RH 0). | Dropped (unchanged), now reported in the QC log. |
| Gaps | v1 drew straight lines across missing records (longest gap 12.8 h at DBSF10, 6.5 h at DBNF26). | **Fixed:** 15-min series re-indexed to a regular grid; gaps plot as breaks. Hourly means need ≥ 3 of 4 records. Nothing is interpolated or gap-filled. |
| Daily aggregation | v1 used the logger's Daily table with no coverage check (first/partial days included). | **Fixed:** daily means computed from 15-min data and only kept if ≥ 80 % of the 96 records exist; the current day is never used. DBSF10 has 2–3 failing days, most stations 1 (installation day). |
| Air sensors | Secondary air sensor reads 0.2–1.1 °C warmer than primary (1.1 °C at DBSF27). | Primary sensor used throughout; note for field QC (shield/aspiration of secondary). |

## 2. Science / derived metrics

| Metric | v1 | Now |
|---|---|---|
| Degree-days | Cumulated over whatever time window was selected, from the logger Daily table. | **Fixed:** FDD = Σ max(0, −T̄), TDD = Σ max(0, T̄) over valid daily means, accumulated from **1 July** (season start) or start of record. Independent of the chart window. Skipped days are counted and shown. |
| n-factor | Shown as a plain number from a few weeks of record. | Freezing n-factor = FDD(0 cm) / FDD(air) over the same valid days, labelled **provisional** with a one-line explanation. It is not meaningful until a full freezing season is recorded (spring 2027). |
| Zero curtain | Count of days with |daily mean| < 0.5 °C, no minimum duration; 0 °C crossings counted on noisy 15-min data (hundreds of spurious crossings near 0 °C). | **Fixed:** a zero-curtain *period* = ≥ 3 consecutive valid days with |T̄| ≤ 0.5 °C; periods listed with dates. Last 0 °C crossing from daily means. Current state = frozen / near 0 °C / thawed. |
| Depth–time plot | Contour plot interpolating between depths for every station, including 2-sensor sites. | Contour (linear interpolation between sensors, no extrapolation, gaps blank) only where ≥ 3 depths exist; 2-depth stations get a plain heat-map. Interpolation is stated in the caption. |
| Trumpet curve | Presented as a trumpet curve. | Labelled "temperature envelope", **provisional**; a true trumpet curve / active-layer depth needs ≥ 1 year. |
| Sensor depths | Nominal 0/15/30/50 cm. Daily-swing analysis suggests the order is not as nominal at DYTF20 (15 cm swings 3.3 °C/day vs 0.24 °C at 0 cm), DBNF26 (0 and 15 cm both ~9 °C/day) and DBNF23 (all < 0.1 °C/day). | Depths **kept nominal**; a visible "depth unverified" warning on those stations' soil views and ⚠ on the ticker. **Needs field confirmation.** |

## 3. Geodata

| Check | Finding | Action |
|---|---|---|
| CRS | Sources: Jorgenson 2008 and ecoregions in Alaska Albers (EPSG:3338); Brown/IPA in a spherical Lambert azimuthal equal-area; ALT raster in EPSG:3338. All processing (dissolve, simplify, point sampling) done in EPSG:3338, output GeoJSON in WGS84. | OK. |
| **Antimeridian** | Brown and ecoregion polygons crossing 180° (western Aleutians) wrapped around the globe when written to WGS84, so the simplified Brown display layer showed the **wrong class at 3 stations and nothing at 2**. | **Fixed:** all layers clipped to 179.9° W–129° W before reprojection. A QA step now samples the simplified display layers at each station and compares with the original polygons: all match. |
| **ALT raster overlay** | PNG was warped to EPSG:4326 but Leaflet stretches overlays linearly in Web Mercator, misplacing the 65–70° N model domain by kilometres. No value legend. | **Fixed:** warped to EPSG:3857 with lat/lon bounds; colour-bar legend with cm values added. |
| Simplification | 1 km Douglas–Peucker + 0.001° coordinate precision. Jorgenson source is 1:250,000 with 1–3 km positional error; Brown is 1:10,000,000. | Appropriate for zoom ≤ 8; stated in captions. |
| Site values | Sampled from the **original** (unsimplified) polygons/raster at station coordinates. | OK; caption warns these are regional context (1–3 km / ~10 km uncertainty). |
| Class names | Jorgenson names now taken verbatim from the layer metadata ("Isolated (>0-10%)", "Large waterbodies (unfrozen below)"). Brown ground-ice classes were labelled with lowland thresholds everywhere. | **Fixed:** Brown classes now combine extent, ice content and landform (f = thick overburden: >20 / 10–20 / 0–10 %; r = thin overburden/bedrock: >10 / 0–10 %), per NSIDC GGD318. |
| Citations | Only in the About tab. | Source line under every layer on the Map layers tab; full citations in About & methods. |

## 4. Controls (v1 → now)

| v1 widget | Needed? | Now |
|---|---|---|
| Sidebar time-window radio (applied to all tabs) | Yes, but global coupling confused degree-days | Per-section segmented control (Overview chart, Station, Health), default 30 d |
| 8 sidebar layer checkboxes + ALT checkbox | Too many; layers overlapped | One "Reference layer" select on the Map layers tab |
| Station select (Station detail) | Yes | Kept |
| Station select (Health solar vs load) | Occasionally | Moved into a collapsed "Power budget" expander |
| Reload data button | Rarely | Kept in sidebar |
| Map LayerControl (basemaps) | Occasionally | Kept, collapsed |
| — | Researchers want the data | **New:** CSV download of cleaned 15-min data (Station → Advanced) |

## 5. UI changes

* Landing view (**Overview**): status line, compact ticker, station map and one headline chart (air vs 15 cm soil, all stations, south→north).
* Tabs reduced to **Overview · Station · Map layers · Station health · About & methods** (Network tab merged into Overview).
* One colour per station everywhere (colour-blind-safe Okabe–Ito); warm→cool colour ramp for depth; units on every axis; one-sentence captions/tooltips for each metric.
* Researcher detail (depth–time plot, envelope, QC log, CSV) in an *Advanced* expander.
* Health status now states the reason (overdue vs low battery) and the station's expected call-in interval.

## 6. Needs the user's input

1. Confirm soil sensor depths/order at **DYTF20, DBNF26, DBNF23**. (Field photos 2026 do not show depth labels for these three; still open.)
2. Season convention for degree-days (1 July used; change `SEASON_START` in `config.py` if the group uses another). (Not in the field data; still open.)
3. ~~DBSF10 coordinates and elevation~~: see section 7.

## 7. Checked against fieldwork data (2026-10-14)

Source folder: `fieldwork data/UND_Alaska_DOT_Dalton_District_2026` (1,098 photos, 913 geotagged by the Nikon W300 GPS; one slide deck; one storage list).
The camera GPS agrees with the given DBNF22 coordinates to 10–20 m (Toolik photos), so it is usable for locating sites to a few tens of metres.

| Item | Field evidence | Action |
|---|---|---|
| DBSF10 location | `Dalton_District_Chandalar_to_Fairbanks_20260524_mrl/Dalton_UND_Site10_20260524_mrl`: 19 photos, median 66.138185° N, 150.173455° W, spread < 5 m. Placement matches the DBSF10 slide in `UND_AK_Perm_Network_Pre_and_Post_2026Aug_20261001a.pptx` (slide 10), between DBSF03 (UND Site 3) and DYTF07 (UND Site 7). The photos show the pre-upgrade station; no photos of the August CR1000X install exist, so the new mast may be offset. | **Applied** in `station_data_survey/build_tableau_extract.py`. Elevation 811 ft from USGS 3DEP (EPQS) at that point; 3DEP reproduces the other given elevations within 15–50 ft. Flagged as approximate in the map popup and Overview caption (`LOCATION_NOTES` in `config.py`). Site attributes re-sampled with `prepare_layers.py`; other stations unchanged. |
| DBSF10 region label | Every reference layer puts the point in the Ray Mountains / Intermontane Boreal, south of the Brooks Range. | Label "Southern Foothills, Brooks Range" **kept**; needs the user's call. |
| DBNF23 logger calls itself DBNF09 | `DBNF23_20260924` photos: logger SN 84807 (= the DBNF23 data files' serial), cellular modem labelled "SM-DBNF09" (DSCN7134, 7140, 7151). The deck shows DBNF09 as a separate site (slide 20). | The data does come from the DBNF23 site; the DBNF09 name is the reused program file (`DBNF09_20260819.cr1x`) and modem. No change. |
| DYTF20 hardware | `DYTF20_20260921`: logger SN 84869 (matches the data files), modem labelled "SM-DYTF05" (DSCN6980). | Same reuse pattern; no change. |
| DBNF26 coordinates | `DBNF26_20261004` and `_20261005`: 63 photos at 68.17793° N, 149.42887° W (spread < 12 m), 8.8 km NE of the given 68.108451, −149.532086. Modem "SM-DBNF26" visible (DSCN7272). | **Not changed**: reported to the user. |
| DBSF27 coordinates | `DBSF27_20261005/10/11`: photos at 67.69440° N, 149.73215° W, 1.2 km NNW of the given 67.684157, −149.726958. | **Not changed**: reported to the user. |
| DBSF27 install | Logbook pages in `DBSF27_20261011` (DSCN7444–7445): soil sensors installed and comms tested on 11 Oct; soil pit about 40 cm deep (DSCN7400–7402). | Confirms `INSTALL_CUTOFF` of 11 Oct. |
| Slide deck | The pptx is truncated (49 MB of a ~52 MB file; 3 of 21 slide images missing). Remaining slides are Google Earth maps without coordinates. | Recovered by reading the zip entries directly. |
