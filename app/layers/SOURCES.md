### Map layer sources

All reference layers were built by `app/prepare_layers.py` from GIS files already used in the
HighwayStability project (`Desktop/HighwayStability`): processed in Alaska Albers (EPSG:3338),
dissolved by class, clipped to 179.9° W–129° W (avoids antimeridian wrap), simplified (~1 km) and
written as WGS84 GeoJSON. The active-layer raster is warped to Web Mercator (EPSG:3857) for display.
Station site values are sampled from the original, unsimplified data; the script checks that the
simplified display layers give the same class at every station. Replace a source file and re-run
the script to swap in a different map.

| Layer(s) in the app | Source file | Citation / origin |
|---|---|---|
| Permafrost extent, ground ice, soil texture, surficial deposits, mapped MAAT, ecoregions (32 classes) | `review/ground_ice/shp/233-permafrost-characteristics-of-alaska-2008-sha/Permafrost_AK_2008_AlbAK83.shp` | Jorgenson, T., Yoshikawa, K., Kanevskiy, M., Shur, Y., Romanovsky, V., Marchenko, S., Grosse, G., Brown, J., Jones, B. (2008). *Permafrost Characteristics of Alaska*. Institute of Northern Engineering, University of Alaska Fairbanks. Extended abstract & map, Ninth International Conference on Permafrost. Ecoregion attribute follows Nowacki et al. (2001). |
| IPA circum-Arctic permafrost & ground ice | `data/raw/ggd318_map_circumarctic/permaice.shp` | Brown, J., Ferrians, O., Heginbottom, J. A., Melnikov, E. (2002). *Circum-Arctic Map of Permafrost and Ground-Ice Conditions*, Version 2. NSIDC dataset GGD318, https://nsidc.org/data/ggd318 |
| Unified ecoregions, level 2 | `data/raw/ecoregions_simplified/ecoregions_simplified.shp` | Nowacki, G., Spencer, P., Fleming, M., Brock, T., Jorgenson, T. (2001). *Unified Ecoregions of Alaska*. USGS Open-File Report 2002-297 (simplified level-2 version from the HighwayStability project). |
| Modeled active-layer thickness | `modeling/outputs_v3_precip/baseline_v3_precip_alt_baseline_cm.tif` | HighwayStability project model output (baseline v3 with precipitation), 1 km grid, Dalton Highway corridor only. Internal product, not peer-reviewed. |

Not included (no local file found): a dedicated soils map (e.g. NRCS STATSGO2) and Obu et al. (2019)
ground-temperature / permafrost-zone rasters. Soil information shown comes from the texture and
surficial-deposit attributes of Jorgenson et al. (2008).

Basemaps: Esri World Topographic Map, Esri World Imagery, OpenStreetMap.
