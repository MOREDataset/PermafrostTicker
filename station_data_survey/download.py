"""Download all station data files from the gwscientific Apache listings."""
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://gwscientific.com/remote/UND_DOT_RWIS/{}/data/"
STATIONS = ["DBNF22", "DBNF23", "DBNF26", "DBSF10", "DBSF27", "DYTF20"]
OUT = Path(__file__).resolve().parent

failures = []
for st in STATIONS:
    url = BASE.format(st)
    try:
        html = urllib.request.urlopen(url, timeout=60).read().decode("utf-8", "replace")
    except Exception as e:
        failures.append((url, repr(e)))
        print("LIST FAIL", url, e)
        continue
    names = []
    for href in re.findall(r'href="([^"]+)"', html):
        if href.startswith(("?", "/", "http")) or href.endswith("/"):
            continue
        name = urllib.parse.unquote(href)
        if name.endswith(".backup") or "/" in name or "\\" in name:
            continue
        names.append((href, name))
    d = OUT / st
    d.mkdir(exist_ok=True)
    for href, name in names:
        try:
            data = urllib.request.urlopen(url + href, timeout=300).read()
            tmp = d / (name + ".part")
            tmp.write_bytes(data)
            tmp.replace(d / name)  # atomic swap so a failed download never leaves a truncated file
            print(f"{st}/{name}: {len(data)} bytes")
        except Exception as e:
            failures.append((url + href, repr(e)))
            print("FAIL", url + href, e)

print("FAILURES:", failures)
sys.exit(0)
