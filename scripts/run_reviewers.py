#!/usr/bin/env python3
"""
run_reviewers.py

Fetches the diff for each PR in data/pr-corpus.csv and submits it to each
configured reviewer API. Raw responses are saved to data/results/{reviewer}/.

Supported reviewers
-------------------
argus       REST API — requires ARGUS_API_BASE and ARGUS_API_KEY env vars.
            POST {ARGUS_API_BASE}/v1/review  body: {diff, pr_url, pr_number}
            Response: {comments: [{line, body, severity}], latency_ms: int}

coderabbit  REST API — requires CODERABBIT_API_KEY env var.
            POST https://api.coderabbit.ai/v1/review
            body: {diff, pull_request_url}
            Response: {comments: [{path, line, body}]}

copilot     GitHub Copilot does not expose a public review API as of 2026-11.
            To include Copilot results, trigger a review manually on the PR and
            export the comments via:
              gh api repos/{owner}/{repo}/pulls/{number}/comments
            Save the JSON to data/results/copilot/{owner}__{repo}__{number}.json
            and re-run score_results.py.

Required env:
    GITHUB_TOKEN    — public_repo read (for fetching diffs)
    ARGUS_API_BASE  — e.g. https://argus.trustmodel.ai  (optional, skipped if absent)
    ARGUS_API_KEY   — (optional, skipped if absent)
    CODERABBIT_API_KEY — (optional, skipped if absent)
"""

import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

CORPUS_PATH = Path(__file__).parent.parent / "data" / "pr-corpus.csv"
RESULTS_DIR = Path(__file__).parent.parent / "data" / "results"

ARGUS_API_BASE = os.environ.get("ARGUS_API_BASE", "").rstrip("/")
ARGUS_API_KEY = os.environ.get("ARGUS_API_KEY", "")
CODERABBIT_API_KEY = os.environ.get("CODERABBIT_API_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")


def fetch_diff(owner: str, repo: str, pr_number: str) -> str:
    """Fetch the unified diff for a PR via the GitHub API."""
    result = subprocess.run(
        [
            "gh", "api",
            f"repos/{owner}/{repo}/pulls/{pr_number}",
            "--header", "Accept: application/vnd.github.v3.diff",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to fetch diff for {owner}/{repo}#{pr_number}: {result.stderr.strip()}")
    return result.stdout


def call_argus(diff: str, pr_url: str, pr_number: str) -> tuple[dict, float]:
    """Submit diff to Argus. Returns (response_dict, latency_seconds)."""
    import urllib.request
    import urllib.error

    payload = json.dumps({"diff": diff, "pr_url": pr_url, "pr_number": pr_number}).encode()
    req = urllib.request.Request(
        f"{ARGUS_API_BASE}/v1/review",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ARGUS_API_KEY}",
        },
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            latency = time.time() - t0
            body = resp.read().decode()
            return json.loads(body), latency
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Argus API error {exc.code}: {exc.read().decode()}") from exc


def call_coderabbit(diff: str, pr_url: str) -> tuple[dict, float]:
    """Submit diff to CodeRabbit. Returns (response_dict, latency_seconds)."""
    import urllib.request
    import urllib.error

    payload = json.dumps({"diff": diff, "pull_request_url": pr_url}).encode()
    req = urllib.request.Request(
        "https://api.coderabbit.ai/v1/review",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {CODERABBIT_API_KEY}",
        },
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            latency = time.time() - t0
            body = resp.read().decode()
            return json.loads(body), latency
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"CodeRabbit API error {exc.code}: {exc.read().decode()}") from exc


def save_result(reviewer: str, owner: str, repo: str, pr_number: str, data: dict) -> Path:
    out_dir = RESULTS_DIR / reviewer
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{owner}__{repo}__{pr_number}.json"
    with out_file.open("w") as fh:
        json.dump(data, fh, indent=2)
    return out_file


def main() -> None:
    with CORPUS_PATH.open(newline="") as fh:
        rows = [
            r for r in csv.DictReader(fh)
            if "[FILL]" not in r.get("pr_number", "") and "[FILL]" not in r.get("merge_sha", "")
        ]

    if not rows:
        print("No runnable rows in corpus. Run collect_prs.py first to validate.")
        sys.exit(0)

    reviewers_enabled = []
    if ARGUS_API_BASE and ARGUS_API_KEY:
        reviewers_enabled.append("argus")
    else:
        print("ARGUS_API_BASE / ARGUS_API_KEY not set — skipping Argus")

    if CODERABBIT_API_KEY:
        reviewers_enabled.append("coderabbit")
    else:
        print("CODERABBIT_API_KEY not set — skipping CodeRabbit")

    print("Copilot: manual mode. See module docstring for instructions.")

    if not reviewers_enabled:
        print("No reviewers configured. Set at least one API key.")
        sys.exit(1)

    print(f"\nRunning {len(reviewers_enabled)} reviewer(s) over {len(rows)} PRs...")

    for row in rows:
        owner = row["owner"]
        repo = row["repo"]
        pr_number = row["pr_number"]
        pr_url = f"https://github.com/{owner}/{repo}/pull/{pr_number}"

        print(f"\n  PR: {pr_url}")

        try:
            diff = fetch_diff(owner, repo, pr_number)
        except RuntimeError as exc:
            print(f"    SKIP (diff fetch failed): {exc}")
            continue

        if "argus" in reviewers_enabled:
            try:
                response, latency = call_argus(diff, pr_url, pr_number)
                envelope = {"pr_url": pr_url, "latency_seconds": latency, "response": response}
                out = save_result("argus", owner, repo, pr_number, envelope)
                n_comments = len(response.get("comments", []))
                print(f"    argus: {n_comments} comment(s), {latency:.2f}s → {out.name}")
            except RuntimeError as exc:
                print(f"    argus ERROR: {exc}")
                save_result("argus", owner, repo, pr_number, {"error": str(exc), "pr_url": pr_url})

        if "coderabbit" in reviewers_enabled:
            try:
                response, latency = call_coderabbit(diff, pr_url)
                envelope = {"pr_url": pr_url, "latency_seconds": latency, "response": response}
                out = save_result("coderabbit", owner, repo, pr_number, envelope)
                n_comments = len(response.get("comments", []))
                print(f"    coderabbit: {n_comments} comment(s), {latency:.2f}s → {out.name}")
            except RuntimeError as exc:
                print(f"    coderabbit ERROR: {exc}")
                save_result("coderabbit", owner, repo, pr_number, {"error": str(exc), "pr_url": pr_url})

    print("\nDone. Run score_results.py next.")


if __name__ == "__main__":
    main()
