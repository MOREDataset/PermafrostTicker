"""Profile Campbell Scientific TOA5 station files.

Usage: python -I profile.py <survey_dir>
Writes <survey_dir>/profile_report.md and profile_report.json.

The 7-day min/max window is relative to each file's LAST timestamp,
not to today's date, so stale files still get meaningful stats.
"""
import csv
import json
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path

STATIONS = ["DBNF22", "DBNF23", "DBNF26", "DBSF10", "DBSF27", "DYTF20"]


def parse_ts(s):
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def to_float(s):
    try:
        return float(s)
    except ValueError:
        return None


def fmt_num(x):
    return "" if x is None else f"{x:.6g}"


def profile_file(path):
    raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    header = raw_lines[:4]
    fields = next(csv.reader([raw_lines[1]])) if len(raw_lines) > 1 else []
    data_lines = [ln for ln in raw_lines[4:] if ln.strip()]
    rows = list(csv.reader(data_lines))

    timestamps = [parse_ts(r[0]) for r in rows if r]
    valid_ts = [t for t in timestamps if t]
    first_ts = valid_ts[0] if valid_ts else None
    last_ts = valid_ts[-1] if valid_ts else None
    diffs = [(b - a).total_seconds() for a, b in zip(valid_ts, valid_ts[1:])]
    median_spacing = statistics.median(diffs) if diffs else None
    non_monotonic = sum(1 for d in diffs if d <= 0)
    bad_width = sum(1 for r in rows if len(r) != len(fields))

    cutoff = last_ts - timedelta(days=7) if last_ts else None
    cols = []
    for i, name in enumerate(fields):
        nan = 0
        lo = hi = None
        non_numeric = 0
        for r, t in zip(rows, timestamps):
            if i >= len(r):
                continue
            v = r[i]
            if v == "NAN":
                nan += 1
                continue
            if i == 0:
                continue
            if cutoff is None or t is None or t < cutoff:
                continue
            f = to_float(v)
            if f is None:
                non_numeric += 1
                continue
            lo = f if lo is None or f < lo else lo
            hi = f if hi is None or f > hi else hi
        cols.append({"name": name, "nan_count": nan, "min_7d": lo, "max_7d": hi,
                     "non_numeric_7d": non_numeric})

    return {
        "file": path.name,
        "size_bytes": path.stat().st_size,
        "line1": header[0] if header else "",
        "field_names": header[1] if len(header) > 1 else "",
        "units": header[2] if len(header) > 2 else "",
        "processing": header[3] if len(header) > 3 else "",
        "n_fields": len(fields),
        "n_rows": len(rows),
        "first_ts": first_ts.isoformat(sep=" ") if first_ts else None,
        "last_ts": last_ts.isoformat(sep=" ") if last_ts else None,
        "median_spacing_s": median_spacing,
        "non_monotonic_steps": non_monotonic,
        "rows_with_wrong_width": bad_width,
        "last_rows": data_lines[-2:],
        "columns": cols,
    }


def md_for_file(p):
    out = [f"### {p['file']}",
           f"- size: {p['size_bytes']} bytes; rows: {p['n_rows']}; fields: {p['n_fields']}",
           f"- first: {p['first_ts']}; last: {p['last_ts']}; median spacing: {p['median_spacing_s']} s"
           f"; non-monotonic steps: {p['non_monotonic_steps']}; rows w/ wrong width: {p['rows_with_wrong_width']}",
           "- line1: `" + p["line1"] + "`",
           "- fields: `" + p["field_names"] + "`",
           "- units: `" + p["units"] + "`",
           "- processing: `" + p["processing"] + "`",
           "- last 2 rows:"]
    out += ["  - `" + r + "`" for r in p["last_rows"]]
    stats = []
    for c in p["columns"][1:]:
        s = c["name"]
        if c["nan_count"]:
            s += f" nan={c['nan_count']}"
        if c["min_7d"] is not None:
            s += f" [{fmt_num(c['min_7d'])}..{fmt_num(c['max_7d'])}]"
        elif c["non_numeric_7d"]:
            s += " [text]"
        stats.append(s)
    out.append("- col stats (NAN count over whole file; [min..max] over last 7 days of file): "
               + "; ".join(stats))
    return "\n".join(out)


def main(root):
    report = {}
    md = ["# Station data profile",
          "Source: https://gwscientific.com/remote/UND_DOT_RWIS/<STATION>/data/ (excluding *.backup).",
          "7-day window is relative to each file's last timestamp.", ""]
    for st in STATIONS:
        d = root / st
        files = sorted(d.glob("*.dat"))
        report[st] = [profile_file(f) for f in files]
        md.append(f"## {st} ({len(files)} files)")
        md.append("")
        for p in report[st]:
            md.append(md_for_file(p))
            md.append("")
    (root / "profile_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    (root / "profile_report.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
