#!/usr/bin/env python3
"""
generate_report.py

Reads data/scores.csv and writes report.md with:
  - A summary table (TP rate, FP/PR, latency p50/p95) per reviewer
  - Raw per-PR data for every reviewer

Output: report.md
"""

import csv
import statistics
import sys
from datetime import date
from pathlib import Path

SCORES_PATH = Path(__file__).parent.parent / "data" / "scores.csv"
REPORT_PATH = Path(__file__).parent.parent / "report.md"


def percentile(data, pct):
    """Return the pct-th percentile of a sorted list."""
    if not data:
        return None
    sorted_data = sorted(data)
    idx = (pct / 100) * (len(sorted_data) - 1)
    lo = int(idx)
    hi = lo + 1
    if hi >= len(sorted_data):
        return sorted_data[-1]
    frac = idx - lo
    return sorted_data[lo] + frac * (sorted_data[hi] - sorted_data[lo])


def fmt(val, fmt_str):
    return fmt_str.format(val) if val is not None else "n/a"


def main():
    if not SCORES_PATH.exists():
        print(f"ERROR: {SCORES_PATH} not found. Run score_results.py first.")
        sys.exit(1)

    with SCORES_PATH.open(newline="") as fh:
        rows = list(csv.DictReader(fh))

    if not rows:
        print("scores.csv is empty.")
        sys.exit(1)

    reviewers = sorted({r["reviewer"] for r in rows})

    # Build summary stats per reviewer
    summary = {}
    for reviewer in reviewers:
        rrows = [r for r in rows if r["reviewer"] == reviewer]
        scored = [r for r in rrows if r["error"] == "0"]
        tps = [int(r["true_positive"]) for r in scored]
        fps = [int(r["false_positives"]) for r in scored]
        latencies = [float(r["latency_seconds"]) for r in scored if r["latency_seconds"] not in ("", "None", None)]

        summary[reviewer] = {
            "n": len(rrows),
            "n_scored": len(scored),
            "tp_rate": statistics.mean(tps) if tps else None,
            "fp_per_pr": statistics.mean(fps) if fps else None,
            "lat_p50": percentile(latencies, 50),
            "lat_p95": percentile(latencies, 95),
            "errors": len(rrows) - len(scored),
        }

    lines = []
    lines.append(f"# review-bakeoff Results")
    lines.append(f"")
    lines.append(f"Generated: {date.today()}")
    lines.append(f"")
    lines.append(f"## Summary")
    lines.append(f"")
    lines.append(f"| Reviewer | PRs | TP Rate | FP/PR | Latency p50 | Latency p95 | Errors |")
    lines.append(f"|---|---|---|---|---|---|---|")
    for reviewer in reviewers:
        s = summary[reviewer]
        lines.append(
            f"| {reviewer}"
            f" | {s['n']}"
            f" | {fmt(s['tp_rate'], '{:.0%}')}"
            f" | {fmt(s['fp_per_pr'], '{:.1f}')}"
            f" | {fmt(s['lat_p50'], '{:.1f}s')}"
            f" | {fmt(s['lat_p95'], '{:.1f}s')}"
            f" | {s['errors']} |"
        )

    lines.append(f"")
    lines.append(f"> TP Rate: fraction of PRs where reviewer surfaced the known bug.")
    lines.append(f"> FP/PR: average comments per PR not matching the known bug (upper bound).")
    lines.append(f"> Latency: wall-clock seconds from API call to first response.")
    lines.append(f"")
    lines.append(f"## Raw Data")
    lines.append(f"")
    lines.append(f"| Reviewer | Owner | Repo | PR | Bug | TP | FP | Latency | Error |")
    lines.append(f"|---|---|---|---|---|---|---|---|---|")
    for row in rows:
        lat = row["latency_seconds"]
        lat_str = f"{float(lat):.1f}s" if lat not in ("", "None", None) else "n/a"
        lines.append(
            f"| {row['reviewer']}"
            f" | {row['owner']}"
            f" | {row['repo']}"
            f" | #{row['pr_number']}"
            f" | {row['bug_description'][:60]}"
            f" | {row['true_positive']}"
            f" | {row['false_positives']}"
            f" | {lat_str}"
            f" | {row['error']} |"
        )

    report_text = "\n".join(lines) + "\n"
    REPORT_PATH.write_text(report_text)
    print(f"Wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
