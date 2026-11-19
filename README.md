# review-bakeoff

Open benchmark: AI code reviewer comparison — raw results published.

## What this is

A reproducible benchmark of AI-powered code review tools against a dataset of
100 open-source pull requests with **known, confirmed bugs**. Results are
published raw with no post-processing — every true positive, false positive, and
latency measurement is in the repo.

## Dataset

`data/pr-corpus.csv` — 100 OSS PRs drawn from popular Python/TypeScript projects.
Each row contains the PR reference, the merge SHA, and a brief description of the
confirmed bug that was fixed by the PR.

Seed rows are provided. Run `make bakeoff` to validate them and collect results.

## Reviewers benchmarked

| Reviewer | Integration |
|---|---|
| Argus (TrustModel) | REST API via `ARGUS_API_BASE` env var |
| CodeRabbit | REST API via `CODERABBIT_API_KEY` env var |
| GitHub Copilot | Manual — see `scripts/run_reviewers.py` for instructions |

## Metrics

| Metric | Definition |
|---|---|
| TP rate | % of known bugs surfaced by the reviewer |
| FP/PR | Average false-positive comments per pull request |
| Latency (p50/p95) | Wall-clock seconds from API call to first comment |

## Running the benchmark

```bash
# Install deps
pip install -r requirements.txt

# Set credentials
export ARGUS_API_BASE=https://...
export ARGUS_API_KEY=...
export CODERABBIT_API_KEY=...
export GITHUB_TOKEN=...

# Full pipeline
make bakeoff

# Regenerate report from existing scores
make report

# Remove collected results (keeps corpus)
make clean
```

## Output

- `data/results/{reviewer}/` — raw JSON responses per PR
- `data/scores.csv` — TP/FP/latency per PR per reviewer
- `report.md` — summary table + per-reviewer breakdown

## Contributing

Fill in `[FILL]` placeholders in `data/pr-corpus.csv` with real PR references.
PRs must meet the bar: merged, confirmed bug in description, fix clearly scoped
to the PR. Open an issue before adding a batch of PRs.

## License

MIT — see `LICENSE`.
