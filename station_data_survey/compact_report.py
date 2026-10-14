"""Render a compact transmission copy of profile_report.json.

Usage: python -I compact_report.py <survey_dir>
Writes <survey_dir>/profile_report_compact.md. Nothing is truncated:
a header triple (fields/units/processing) is printed in full the first time it
appears and referenced afterwards. Column stats are omitted for *US tables
(unit-converted twins of the metric tables) and DataTableInfo (logger config).
"""
import json
import sys
from pathlib import Path


def g(x):
    return f"{x:.5g}"


def stats_line(cols, skip_constant=False):
    parts = []
    skipped = 0
    for c in cols[1:]:
        s = c["name"]
        lo, hi = c["min_7d"], c["max_7d"]
        if skip_constant and lo is not None and lo == hi and not c["nan_count"]:
            skipped += 1
            continue
        if lo is not None:
            s += f"={g(lo)}" if lo == hi else f"[{g(lo)}..{g(hi)}]"
        elif c["non_numeric_7d"]:
            s += "(text)"
        elif not c["nan_count"]:
            s += "(no 7d data)"
        if c["nan_count"]:
            s += f" NAN{c['nan_count']}"
        parts.append(s)
    if skipped:
        parts.append(f"({skipped} constant non-NAN columns omitted)")
    return "; ".join(parts)


def main(root):
    rep = json.loads((root / "profile_report.json").read_text(encoding="utf-8"))
    seen = {}
    md = ["# Station data profile (compact transmission copy)",
          "Full version: station_data_survey/profile_report.md. Each fields/units/processing triple is printed "
          "in full the first time it appears; later files with byte-identical header lines say 'headers = <first file>'. "
          "Stats: name[min..max] or name=value over the last 7 days of each file (relative to that file's last "
          "timestamp); NANn = NAN count over the whole file; (text) = non-numeric.", ""]
    for st, files in rep.items():
        md += [f"## {st} ({len(files)} files)", ""]
        for p in files:
            table = p["file"].split("_CR1000X")[-1].removesuffix(".dat").lstrip("e_")
            key = (p["field_names"], p["units"], p["processing"])
            md.append(f"### {p['file']}")
            md.append(f"size {p['size_bytes']} B; rows {p['n_rows']}; fields {p['n_fields']}; "
                      f"first {p['first_ts']}; last {p['last_ts']}; median step {p['median_spacing_s']} s; "
                      f"non-monotonic steps {p['non_monotonic_steps']}; bad-width rows {p['rows_with_wrong_width']}")
            md.append("L1: " + p["line1"])
            if key in seen:
                md.append(f"headers = {seen[key]}")
            else:
                seen[key] = f"{st}/{table}"
                md += ["L2: " + p["field_names"], "L3: " + p["units"], "L4: " + p["processing"]]
            md += ["last: " + r for r in p["last_rows"]]
            if table.endswith("US") or table == "DataTableInfo":
                md.append("stats: omitted (US twin / logger config table; see full report)")
            else:
                md.append("stats: " + stats_line(p["columns"], skip_constant=table == "Public"))
            md.append("")
    (root / "profile_report_compact.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
