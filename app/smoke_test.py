"""Headless check: run the app for every station x time window and every map layer.

Usage (from the app folder): python smoke_test.py
"""
from streamlit.testing.v1 import AppTest

import config as C
import map_view as MV

failures = 0


def check(label, at):
    global failures
    errs = [e.value for e in at.exception]
    failures += bool(errs)
    print(f"{label}: {'FAIL ' + str(errs)[:400] if errs else 'ok'}")


for window in ["7 d", "30 d", "90 d", "All"]:
    for station in C.STATIONS:
        at = AppTest.from_file("app.py", default_timeout=180).run()
        at.segmented_control(key="over_win").set_value(window).run()
        at.segmented_control(key="station_win").set_value(window).run()
        at.segmented_control(key="health_win").set_value(window).run()
        at.selectbox[0].set_value(station).run()
        at.selectbox(key="health_station").set_value(station).run()
        check(f"{window:5} {station}", at)

at = AppTest.from_file("app.py", default_timeout=300).run()
for layer in list(MV.LAYERS) + [MV.ALT_KEY]:
    at.selectbox[1].set_value(layer).run()
    check(f"layer {layer}", at)
raise SystemExit(1 if failures else 0)
