.PHONY: bakeoff report clean
bakeoff:
	python scripts/collect_prs.py
	python scripts/run_reviewers.py
	python scripts/score_results.py
	python scripts/generate_report.py
report:
	python scripts/generate_report.py
clean:
	rm -f data/results/*.json
