#!/usr/bin/env python3
"""
Merge per-school JSON files collected from department job market pages into data/global/<cycle>.csv.

Usage:  python scripts/merge_global.py cache/global_2026 2026-2027
Each JSON: {"school", "url", "status": "posted|not_posted", "candidates": [{name, jmp, fields, website, education, placement}]}.
School rank and country come from the China JMC school list in data/<cycle>.md (via site/data.json).
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NON_DEGREE = re.compile(r"\s*(exchange|visiting|study abroad)", re.I)  # exchange terms etc. are not degrees
COLS = ["name", "school", "country", "school_rank", "jmp", "fields", "website", "placement", "education"]


def main() -> int:
    src, cycle = Path(sys.argv[1]), sys.argv[2]
    data = json.loads((ROOT / "site" / "data.json").read_text(encoding="utf-8"))
    schools = {s["name"]: s for s in data["schools"] if s["cycle"] == cycle}
    rows, report = [], []
    for f in sorted(src.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        s = schools.get(d["school"])
        if s is None:
            print(f"!! {f.name}: school {d['school']!r} is not in data/{cycle}.md", file=sys.stderr)
            continue
        cands = d.get("candidates") or []
        n_edu = sum(1 for c in cands if c.get("education"))
        report.append((s["order"], d["school"], d.get("status"), len(cands), n_edu, d.get("url", "")))
        for c in cands:
            degrees = [e for e in c.get("education") or [] if not NON_DEGREE.match(e.get("degree") or "")]
            edu = "; ".join(" | ".join(str(e.get(k) or "").strip().replace(";", ",").replace("|", "/")
                                       for k in ("degree", "institution", "year")) for e in degrees)
            rows.append({
                "name": c["name"].strip(), "school": d["school"], "country": "Canada" if s["region"] == "加拿大区域" else "United States",
                "school_rank": s["rank"] or "", "jmp": (c.get("jmp") or "").strip(), "fields": "; ".join(c.get("fields") or []),
                "website": (c.get("website") or "").strip(), "placement": (c.get("placement") or "").strip(), "education": edu,
                "_order": s["order"],
            })
    rows.sort(key=lambda r: (r["_order"], r["name"].split()[-1].lower() if r["name"] else ""))
    out = ROOT / "data" / "global" / f"{cycle}.csv"
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    for _, name, status, n, ne, url in sorted(report):
        print(f"{name:45s} {status:10s} {n:3d} candidates, {ne:3d} with education  {url}")
    print(f"\nWrote {out}: {len(rows)} candidates from {sum(1 for r in report if r[2] == 'posted')} posted schools ({len(report)} checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
