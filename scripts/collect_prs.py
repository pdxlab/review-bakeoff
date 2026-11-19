#!/usr/bin/env python3
"""
collect_prs.py

Reads data/pr-corpus.csv, validates that each PR exists via the GitHub API,
and prints a summary. Does not clone repositories.

Required env:
    GITHUB_TOKEN — a token with public_repo read access
"""

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

CORPUS_PATH = Path(__file__).parent.parent / "data" / "pr-corpus.csv"

REQUIRED_COLUMNS = {"owner", "repo", "pr_number", "merge_sha", "bug_description", "bug_fixed_in_pr"}


def gh_api(path: str) -> dict:
    """Call gh api <path> and return parsed JSON. Raises on non-zero exit."""
    result = subprocess.run(
        ["gh", "api", path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh api {path} failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def validate_corpus(rows: list[dict]) -> list[str]:
    errors = []
    for i, row in enumerate(rows, start=2):  # row 1 = header
        for col in REQUIRED_COLUMNS:
            if col not in row or not row[col].strip():
                errors.append(f"Row {i}: missing or empty column '{col}'")
        if "[FILL]" in row.get("pr_number", ""):
            errors.append(f"Row {i}: pr_number is a placeholder — fill it before running")
        if "[FILL]" in row.get("merge_sha", ""):
            errors.append(f"Row {i}: merge_sha is a placeholder — fill it before running")
    return errors


def check_pr_exists(owner: str, repo: str, pr_number: str) -> tuple[bool, str]:
    """Return (ok, message)."""
    try:
        data = gh_api(f"repos/{owner}/{repo}/pulls/{pr_number}")
        state = data.get("state", "unknown")
        return True, f"state={state}"
    except RuntimeError as exc:
        return False, str(exc)


def main() -> None:
    if not CORPUS_PATH.exists():
        print(f"ERROR: corpus not found at {CORPUS_PATH}", file=sys.stderr)
        sys.exit(1)

    with CORPUS_PATH.open(newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    print(f"Loaded {len(rows)} rows from {CORPUS_PATH}")

    errors = validate_corpus(rows)
    if errors:
        print("\nValidation errors (fix before running full bakeoff):")
        for err in errors:
            print(f"  {err}")
        # Non-zero exit only if ALL rows are placeholders — partial corpus is ok for dev
        placeholder_rows = [r for r in rows if "[FILL]" in r.get("pr_number", "")]
        if len(placeholder_rows) == len(rows):
            print("\nAll rows are placeholders. Populate pr-corpus.csv first.")
            sys.exit(1)

    # Only validate rows that look complete (no [FILL])
    runnable = [
        r for r in rows
        if "[FILL]" not in r.get("pr_number", "") and "[FILL]" not in r.get("merge_sha", "")
    ]

    if not runnable:
        print("No runnable rows — all PRs are placeholders. Exiting.")
        sys.exit(0)

    print(f"\nValidating {len(runnable)} runnable PRs via GitHub API...")
    ok_count = 0
    fail_count = 0
    for row in runnable:
        owner = row["owner"]
        repo = row["repo"]
        pr_number = row["pr_number"]
        ok, msg = check_pr_exists(owner, repo, pr_number)
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {owner}/{repo}#{pr_number} — {msg}")
        if ok:
            ok_count += 1
        else:
            fail_count += 1

    print(f"\nSummary: {ok_count} valid, {fail_count} unreachable, "
          f"{len(rows) - len(runnable)} placeholders remaining")

    if fail_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
