"""Before/after comparison of the replays: per candidate path, decisions, learned labels."""
import json, sys
from collections import Counter
from pathlib import Path

D = Path(sys.argv[1])
names = sorted({p.stem.rsplit("_", 1)[0] for p in D.glob("*_before.json")})
tot = Counter()
for name in names:
    b = json.loads((D / f"{name}_before.json").read_text(encoding="utf-8"))
    a = json.loads((D / f"{name}_after.json").read_text(encoding="utf-8"))
    runs_b, runs_a = b["runs"] if "runs" in b else b, a["runs"] if "runs" in a else a
    print(f"## {name}: {len(runs_b)} run(s)")
    for ri, (rb, ra) in enumerate(zip(runs_b, runs_a)):
        rb = rb["results"] if isinstance(rb, dict) else rb
        ra = ra["results"] if isinstance(ra, dict) else ra
        for cb, ca in zip(rb, ra):
            assert cb["id"] == ca["id"]
            for side, c in (("before", cb), ("after", ca)):
                for i in c["learned"]:
                    tot[(side, i["kind"], i["label"])] += 1
                for t in c["traps"]:
                    tot[(side, "trap_hit")] += t["hit"]
                for f in c["facts"]:
                    tot[(side, "fact_learned")] += bool(f["learned"])
                    tot[(side, "facts")] += 1
                for d in c["decisions"]:
                    tot[(side, "decision", d)] += 1
            fb = [tuple(map(str, f)) for f in cb["funnel"]]
            fa = [tuple(map(str, f)) for f in ca["funnel"]]
            for x, y in zip(fb, fa):
                if x != y:
                    print(f"  r{ri} {cb['id']}: {x[0]}.{x[1]}={x[2][:50]!r} {x[3]}/{x[4]}/{x[5]} -> {y[3]}/{y[4]}/{y[5]}")
                    tot["memory_changed"] += 1
            if len(fb) != len(fa):
                print(f"  r{ri} {cb['id']}: funnel length {len(fb)} -> {len(fa)}")
            if cb["decisions"] != ca["decisions"]:
                raw = json.loads(cb["raw_text"] or "{}").get("decision_candidates", [])
                print(f"  r{ri} {cb['id']}: decisions {cb['decisions']} -> {ca['decisions']}")
                for d in raw:
                    print(f"      raw: {d.get('decision_text','')[:70]!r} | quote {d.get('raw_quote','')[:80]!r}")
                tot["decision_cases_changed"] += 1
            lb = Counter((i["kind"], i["label"]) for i in cb["learned"])
            la = Counter((i["kind"], i["label"]) for i in ca["learned"])
            if lb != la:
                print(f"  r{ri} {cb['id']}: learned {dict(lb)} -> {dict(la)}")
print("\n## totals")
for k in sorted(tot, key=str):
    print(" ", k, tot[k])
