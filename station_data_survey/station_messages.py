"""Build one transmission message per station from profile_report.json.

Usage: python -I station_messages.py <survey_dir> <out_dir> STATION [STATION ...]
Header lines that are byte-identical to the DBNF22 file of the same table
are referenced instead of repeated. In Public rows/stats the 120/120/12/12
gust and sin/cos arrays are summarized as ranges; all other values verbatim.
"""
import csv
import json
import sys
from pathlib import Path

ARRAY_PREFIXES = ("GustSpeedArray(", "GustDirArray(", "SinArray(", "CosArray(")


def g(x):
    return f"{x:.5g}"


def table_of(fname):
    return fname.split("_CR1000X")[-1].removesuffix(".dat").lstrip("e_")


def summarize_row(row_text, fields):
    vals = next(csv.reader([row_text]))
    out, i = [], 0
    while i < len(vals):
        name = fields[i] if i < len(fields) else ""
        prefix = next((p for p in ARRAY_PREFIXES if name.startswith(p)), None)
        if prefix is None:
            out.append(row_text_value(vals[i], i, row_text))
            i += 1
            continue
        j = i
        while j < len(fields) and fields[j].startswith(prefix):
            j += 1
        nums = [float(v) for v in vals[i:j] if v not in ("NAN", "")]
        rng = f"{g(min(nums))}..{g(max(nums))}" if nums else "NAN"
        out.append(f"[{prefix[:-1]} x{j - i} {rng}]")
        i = j
    return ",".join(out)


def row_text_value(v, i, row_text):
    # Re-quote strings the way TOA5 does (numbers bare, text quoted).
    try:
        float(v)
        return v
    except ValueError:
        return f'"{v}"'


def stats(cols, skip_constant):
    parts, skipped, i = [], 0, 1
    while i < len(cols):
        c = cols[i]
        prefix = next((p for p in ARRAY_PREFIXES if c["name"].startswith(p)), None)
        if prefix:
            j = i
            while j < len(cols) and cols[j]["name"].startswith(prefix):
                j += 1
            los = [x["min_7d"] for x in cols[i:j] if x["min_7d"] is not None]
            his = [x["max_7d"] for x in cols[i:j] if x["max_7d"] is not None]
            nan = sum(x["nan_count"] for x in cols[i:j])
            s = f"{prefix[:-1]}(1..{j - i})"
            s += f" within [{g(min(los))}..{g(max(his))}]" if los else ""
            s += f" NAN{nan}" if nan else ""
            parts.append(s)
            i = j
            continue
        lo, hi = c["min_7d"], c["max_7d"]
        if skip_constant and lo is not None and lo == hi and not c["nan_count"]:
            skipped += 1
            i += 1
            continue
        s = c["name"]
        if lo is not None:
            s += f"={g(lo)}" if lo == hi else f"[{g(lo)}..{g(hi)}]"
        elif c["non_numeric_7d"]:
            s += "(text)"
        elif not c["nan_count"]:
            s += "(no 7d data)"
        if c["nan_count"]:
            s += f" NAN{c['nan_count']}"
        parts.append(s)
        i += 1
    if skipped:
        parts.append(f"({skipped} constant non-NAN columns omitted)")
    return "; ".join(parts)


def main(root, outdir, stations):
    rep = json.loads((root / "profile_report.json").read_text(encoding="utf-8"))
    ref = {table_of(p["file"]): p for p in rep["DBNF22"]}
    for st in stations:
        md = [f"## {st} ({len(rep[st])} files)", ""]
        for p in rep[st]:
            t = table_of(p["file"])
            fields = next(csv.reader([p["field_names"]]))
            md.append(f"### {p['file']}")
            md.append(f"size {p['size_bytes']} B; rows {p['n_rows']}; fields {p['n_fields']}; "
                      f"first {p['first_ts']}; last {p['last_ts']}; median step {p['median_spacing_s']} s; "
                      f"non-monotonic steps {p['non_monotonic_steps']}; bad-width rows {p['rows_with_wrong_width']}")
            md.append("L1: " + p["line1"])
            r = ref.get(t)
            for tag, key in (("L2", "field_names"), ("L3", "units"), ("L4", "processing")):
                if r and r[key] == p[key]:
                    md.append(f"{tag} = DBNF22/{t}")
                else:
                    md.append(f"{tag}: " + p[key])
            for row in p["last_rows"]:
                md.append("last: " + (summarize_row(row, fields) if t == "Public" else row))
            if t.endswith("US") or t == "DataTableInfo":
                md.append("stats: omitted (US twin / logger config)")
            else:
                md.append("stats: " + stats(p["columns"], skip_constant=t in ("Public", "Status")))
            md.append("")
        (outdir / f"{st}.md").write_text("\n".join(md), encoding="utf-8")
        print(st, len("\n".join(md).encode()))


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), sys.argv[3:])
