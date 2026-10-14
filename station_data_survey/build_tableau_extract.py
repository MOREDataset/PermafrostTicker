"""Build Tableau-ready CSVs from the downloaded TOA5 files.

Usage: python -I build_tableau_extract.py <survey_dir>
Writes <survey_dir>/tableau/stations.csv and hourly_long.csv.
Only physically meaningful channels are kept (air T, RH, dew point,
live soil T, battery); open channels (< -100 C) and NAN become blank.
"""
import csv
import sys
from pathlib import Path

STATIONS = {
    # id: (name, region, lat, lon, elev_ft)
    "DYTF20": ("Permafrost Station DYTF20", "Yukon Tanana Uplands", 65.8259, -149.5346, 1924),
    # DBSF10 lat/lon: median GPS of 19 geotagged photos (spread < 5 m), fieldwork data/
    # UND_Alaska_DOT_Dalton_District_2026/Dalton_District_Chandalar_to_Fairbanks_20260524_mrl/
    # Dalton_UND_Site10_20260524_mrl. Elevation: USGS 3DEP (EPQS) at that point, not surveyed.
    "DBSF10": ("Permafrost Station #10", "Southern Foothills, Brooks Range", 66.138185, -150.173455, 811),
    "DBNF22": ("Permafrost Station DBNF22", "Northern Foothills, Brooks Range", 68.628139, -149.592644, 2392),
    "DBNF23": ("Permafrost Station DBNF23", "Northern Foothills, Brooks Range", 68.640056, -149.515086, 2967),
    "DBNF26": ("Permafrost Station DBNF26", "Northern Foothills, Brooks Range (Atigun Pass)", 68.108451, -149.532086, 3541),
    "DBSF27": ("Permafrost Station DBSF27", "Southern Foothills, Brooks Range", 67.684157, -149.726958, 1466),
}
DATA_COLS = ["AirT_Primary_C_Avg", "AirT_Secondary_C_Avg", "RH_Avg", "DewPoint_C_Avg",
             "SoilT_1_C_Avg", "SoilT_2_C_Avg", "SoilT_3_C_Avg", "SoilT_4_C_Avg"]
DIAG_COLS = ["Batt_V_Avg", "PanelT_C_Avg", "ISolar_A_Avg", "ILoad_A_Avg"]


def read_toa5(path):
    with path.open(encoding="utf-8", errors="replace", newline="") as f:
        r = csv.reader(f)
        next(r)
        fields = next(r)
        units = next(r)
        next(r)
        return fields, units, [dict(zip(fields, row)) for row in r]


def clean(v):
    try:
        x = float(v)
    except ValueError:
        return ""
    return "" if x < -100 else v


def main(root):
    out = root / "tableau"
    out.mkdir(exist_ok=True)
    with (out / "stations.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["station", "name", "region", "lat", "lon", "elev_ft"])
        for sid, (name, region, lat, lon, elev) in STATIONS.items():
            w.writerow([sid, name, region, lat or "", lon or "", elev or ""])

    with (out / "hourly_long.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["station", "timestamp_local", "variable", "unit", "value"])
        n = 0
        for sid in STATIONS:
            for table, cols in (("HrlyData", DATA_COLS), ("HrlyDiag", DIAG_COLS)):
                path = next((root / sid).glob(f"*_{table}.dat"))
                fields, units, rows = read_toa5(path)
                unit = dict(zip(fields, units))
                seen = set()
                for row in rows:
                    ts = row["TIMESTAMP"]
                    if ts in seen:  # DBSF27 has a duplicated 2026-10-11 01:00 row
                        continue
                    seen.add(ts)
                    for c in cols:
                        if c in row:
                            w.writerow([sid, ts, c, unit[c], clean(row[c])])
                            n += 1
        print("hourly_long rows:", n)


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
