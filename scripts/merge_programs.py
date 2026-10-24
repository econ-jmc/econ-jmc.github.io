#!/usr/bin/env python3
"""
Add candidates collected from job market pages (one JSON per program) to the directory CSVs.

Usage:  python scripts/merge_programs.py <folder> <cycle>
        e.g. python scripts/merge_programs.py cache/expand/out/bschool 2026-2027

Each JSON: {"school", "kind": "econ|agecon|bschool", "url", "status": "posted|not_posted|no_program", "status_by_db": {...},
            "candidates": [{name, jmp, fields, website, education, placement, db}]}
kind econ -> data/global/<cycle>.csv, agecon -> data/agecon/<cycle>.csv, bschool -> data/<db>/<cycle>.csv per candidate
(db = finance | accounting | marketing). Rank and country come from data/<dir>/programs.csv. Rows already in a CSV are
kept as they are (they may have been edited by hand); only candidates not yet listed for that school are added.
Department status per program goes to data/<dir>/<cycle>_sources.json.
"""
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COLS = ["name", "school", "country", "school_rank", "jmp", "fields", "website", "placement", "education"]
NON_DEGREE = re.compile(r"\s*(exchange|visiting|study abroad)", re.I)
DIRS = {"econ": "global", "agecon": "agecon", "finance": "finance", "accounting": "accounting", "marketing": "marketing"}


def norm(name: str) -> str:
    return re.sub(r"[^a-z]", "", re.sub(r"\([^)]*\)", "", name.lower()))


def main() -> int:
    src, cycle = Path(sys.argv[1]), sys.argv[2]
    known = {}
    for db, d in DIRS.items():
        known[db] = json.loads((ROOT / "data" / "dbs.json").read_text(encoding="utf-8"))["dbs"][db].get("fields")
    known["econ"] = list(json.loads((ROOT / "data" / "fields.json").read_text(encoding="utf-8"))["categories"])
    new: dict[str, list[dict]] = {}
    status: dict[str, list[dict]] = {}
    for f in sorted(src.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        kind = d.get("kind") or src.name
        dbs = ["finance", "accounting", "marketing"] if kind == "bschool" else [kind]
        for db in dbs:
            st = (d.get("status_by_db") or {}).get(db) or d.get("status") or "not_posted"
            cands = [c for c in d.get("candidates") or [] if kind != "bschool" or c.get("db") == db]
            if cands and st != "posted":
                st = "posted"
            status.setdefault(db, []).append({"school": d["school"], "status": st, "url": d.get("url", ""), "n": len(cands),
                                              "note": d.get("note", ""), "checked": date.today().isoformat()})
            for c in cands:
                degrees = [e for e in c.get("education") or [] if not NON_DEGREE.match(e.get("degree") or "")]
                edu = "; ".join(" | ".join(str(e.get(k) or "").strip().replace(";", ",").replace("|", "/")
                                           for k in ("degree", "institution", "year")) for e in degrees)
                fields = [x for x in c.get("fields") or [] if x in known[db]]
                new.setdefault(db, []).append({"name": c["name"].strip(), "school": d["school"], "jmp": (c.get("jmp") or "").strip(),
                                               "fields": "; ".join(fields), "website": (c.get("website") or "").strip(),
                                               "placement": (c.get("placement") or "").strip(), "education": edu})
    for db in sorted(set(new) | set(status)):
        folder = ROOT / "data" / DIRS[db]
        with (folder / "programs.csv").open(encoding="utf-8-sig", newline="") as fh:
            progs = {r["school"]: (i, r) for i, r in enumerate(csv.DictReader(fh))}
        out = folder / f"{cycle}.csv"
        rows = []
        if out.exists():
            with out.open(encoding="utf-8-sig", newline="") as fh:
                rows = list(csv.DictReader(fh))
        have = {(r["school"], norm(r["name"])) for r in rows}
        added = 0
        for r in new.get(db, []):
            if r["school"] not in progs:
                print(f"!! {db}: {r['school']!r} is not in {folder.name}/programs.csv", file=sys.stderr)
                continue
            if (r["school"], norm(r["name"])) in have:
                continue
            p = progs[r["school"]][1]
            rows.append({**r, "country": p["country"], "school_rank": p["rank"]})
            have.add((r["school"], norm(r["name"])))
            added += 1
        order = lambda r: (progs.get(r["school"], (9999,))[0], r["name"].split()[-1].lower() if r["name"].split() else "")
        rows.sort(key=order)
        with out.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=COLS, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        sp = folder / f"{cycle}_sources.json"
        srcs = {s["school"]: s for s in json.loads(sp.read_text(encoding="utf-8"))} if sp.exists() else {}
        for s in status.get(db, []):
            if s["status"] == "posted" or srcs.get(s["school"], {}).get("status") != "posted":
                srcs[s["school"]] = {k: v for k, v in s.items() if v != "" or k == "url"}
        srcs_l = sorted(srcs.values(), key=lambda s: progs.get(s["school"], (9999,))[0])
        sp.write_text(json.dumps(srcs_l, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        n_posted = sum(1 for s in srcs_l if s["status"] == "posted")
        print(f"{db:10s} +{added:4d} candidates -> {out.relative_to(ROOT)} ({len(rows)} rows); {n_posted}/{len(progs)} programs posted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
