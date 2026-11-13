"""HMO Performance System: claims analytics."""
import argparse
import csv
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

import llm

Z_THRESHOLD = 1.5
DUP_DAYS = 7


def load(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    for r in rows:
        r["amount"] = float(r["amount"])
        r["sub"] = date.fromisoformat(r["submitted"])
        r["dec"] = date.fromisoformat(r["decided"]) if r["decided"] else None
    return rows


def provider_kpis(rows):
    by = defaultdict(list)
    for r in rows:
        by[r["provider"]].append(r)
    out = {}
    for p, rs in by.items():
        decided = [r for r in rs if r["dec"]]
        out[p] = {"claims": len(rs), "cost": sum(r["amount"] for r in rs),
                  "avg_cost": statistics.mean(r["amount"] for r in rs),
                  "approval_rate": sum(r["status"] == "approved" for r in decided) / len(decided) if decided else 0,
                  "turnaround": statistics.mean((r["dec"] - r["sub"]).days for r in decided) if decided else None}
    return out


def outliers(kpis):
    costs = [k["avg_cost"] for k in kpis.values()]
    mu, sd = statistics.mean(costs), statistics.pstdev(costs) or 1
    return {p: round((k["avg_cost"] - mu) / sd, 2) for p, k in kpis.items() if (k["avg_cost"] - mu) / sd > Z_THRESHOLD}


def duplicates(rows):
    found, seen = [], {}
    for r in sorted(rows, key=lambda r: r["sub"]):
        key = (r["enrollee"], r["provider"], r["diagnosis"], r["amount"])
        if key in seen and (r["sub"] - seen[key]["sub"]).days <= DUP_DAYS:
            found.append((seen[key]["claim_id"], r["claim_id"]))
        seen[key] = r
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", default="sample_claims.csv")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    rows = load(a.input)
    k = provider_kpis(rows)
    out, dups = outliers(k), duplicates(rows)
    enrollees = len({r["enrollee"] for r in rows})
    total = sum(r["amount"] for r in rows)
    decided = [r for r in rows if r["dec"]]
    lines = ["# HMO weekly performance summary", "",
             f"- Claims: {len(rows)} from {len(k)} providers, {enrollees} enrollees",
             f"- Total claimed: NGN {total:,.0f} (NGN {total / enrollees:,.0f} per enrollee)",
             f"- Approval rate: {sum(r['status'] == 'approved' for r in decided) / len(decided):.0%}",
             f"- Average turnaround: {statistics.mean((r['dec'] - r['sub']).days for r in decided):.1f} days",
             f"- Pending: {sum(not r['dec'] for r in rows)}", "", "## Actions", ""]
    lines += [f"- Review {p}: cost per claim is {z} SD above network average" for p, z in out.items()]
    lines += [f"- Possible duplicate: {a1} and {a2}" for a1, a2 in dups]
    print(f"{'Provider':<24}{'Claims':>7}{'Avg cost':>12}{'Approve':>9}{'TAT days':>10}")
    for p, v in sorted(k.items(), key=lambda x: -x[1]["cost"]):
        tat = f"{v['turnaround']:.1f}" if v["turnaround"] is not None else "-"
        print(f"{p:<24}{v['claims']:>7}{v['avg_cost']:>12,.0f}{v['approval_rate']:>9.0%}{tat:>10}")
    print()
    print("\n".join(lines))
    ai = llm.complete("Write a 3-sentence summary for an HMO medical director:\n" + "\n".join(lines))
    if ai:
        lines += ["", "## Narrative", "", ai]
    Path("output").mkdir(exist_ok=True)
    Path("output/hmo_summary.md").write_text("\n".join(lines))
    print("\nSaved output/hmo_summary.md")


if __name__ == "__main__":
    main()
