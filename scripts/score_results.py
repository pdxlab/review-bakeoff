#!/usr/bin/env python3
"""
score_results.py

Scores reviewer outputs against the known-bug ground truth in pr-corpus.csv.

Scoring rules
-------------
true_positive   1 if any comment's body contains a keyword from bug_description
                (case-insensitive, unigram overlap >= 1 content word), else 0.
false_positives count of comments that do NOT match the known bug (proxy metric).
latency_seconds wall-clock seconds recorded by run_reviewers.py.
error           1 if the result file contains an "error" key.

Output: data/scores.csv
"""

import csv
import json
import re
import sys
from pathlib import Path

CORPUS_PATH = Path(__file__).parent.parent / "data" / "pr-corpus.csv"
RESULTS_DIR = Path(__file__).parent.parent / "data" / "results"
SCORES_PATH = Path(__file__).parent.parent / "data" / "scores.csv"

STOPWORDS = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "and", "or",
    "is", "are", "was", "were", "be", "been", "has", "have", "had",
    "it", "its", "this", "that", "with", "by", "from", "as", "bug",
}


def keywords(text):
    tokens = re.findall(r"[a-z0-9_]+", text.lower())
    return {t for t in tokens if t not in STOPWORDS and len(t) > 2}


def comment_text(comment):
    return comment.get("body", "") + " " + comment.get("message", "")


def score_result(result_data, bug_description):
    if "error" in result_data:
        return {
            "true_positive": 0,
            "false_positives": 0,
            "latency_seconds": None,
            "error": 1,
        }

    bug_kws = keywords(bug_description)
    latency = result_data.get("latency_seconds")
    comments = result_data.get("response", {}).get("comments", [])

    tp = 0
    fp_count = 0
    for comment in comments:
        text = comment_text(comment)
        comment_kws = keywords(text)
        overlap = bug_kws & comment_kws
        if overlap:
            tp = 1
        else:
            fp_count += 1

    return {
        "true_positive": tp,
        "false_positives": fp_count,
        "latency_seconds": round(latency, 3) if latency is not None else None,
        "error": 0,
    }


def main():
    with CORPUS_PATH.open(newline="") as fh:
        corpus = {
            f"{r['owner']}__{r['repo']}__{r['pr_number']}": r
            for r in csv.DictReader(fh)
            if "[FILL]" not in r.get("pr_number", "")
        }

    if not corpus:
        print("No runnable rows in corpus.")
        sys.exit(0)

    reviewers = [d.name for d in RESULTS_DIR.iterdir() if d.is_dir()]
    if not reviewers:
        print("No result directories found. Run run_reviewers.py first.")
        sys.exit(1)

    rows = []
    for reviewer in sorted(reviewers):
        reviewer_dir = RESULTS_DIR / reviewer
        for result_file in sorted(reviewer_dir.glob("*.json")):
            stem = result_file.stem
            corpus_row = corpus.get(stem)
            if corpus_row is None:
                print(f"  WARN: {result_file.name} has no matching corpus row -- skipping")
                continue

            with result_file.open() as fh:
                result_data = json.load(fh)

            scores = score_result(result_data, corpus_row["bug_description"])
            rows.append({
                "reviewer": reviewer,
                "owner": corpus_row["owner"],
                "repo": corpus_row["repo"],
                "pr_number": corpus_row["pr_number"],
                "bug_description": corpus_row["bug_description"],
                **scores,
            })

    if not rows:
        print("No scoreable results found.")
        sys.exit(1)

    fieldnames = [
        "reviewer", "owner", "repo", "pr_number",
        "bug_description", "true_positive", "false_positives",
        "latency_seconds", "error",
    ]
    with SCORES_PATH.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} score rows to {SCORES_PATH}")
    for reviewer in sorted(reviewers):
        reviewer_rows = [r for r in rows if r["reviewer"] == reviewer]
        if not reviewer_rows:
            continue
        scored = [r for r in reviewer_rows if not r["error"]]
        tp_rate = sum(r["true_positive"] for r in scored) / len(scored) if scored else 0
        avg_fp = sum(r["false_positives"] for r in scored) / len(scored) if scored else 0
        latencies = [r["latency_seconds"] for r in scored if r["latency_seconds"] is not None]
        avg_lat = sum(latencies) / len(latencies) if latencies else None
        print(
            f"  {reviewer}: TP={tp_rate:.0%}  FP/PR={avg_fp:.1f}"
            + (f"  latency={avg_lat:.1f}s" if avg_lat else "")
        )


if __name__ == "__main__":
    main()
