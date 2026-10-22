# Project instructions

- Project: IPL analytics; Python 3.14 + pandas pipeline; static dashboard in `site/`, deployed on ChatGPT Sites.
- Commands: tests: `.venv/bin/python -m unittest discover -s tests`; pipeline: `.venv/bin/python scripts/run_pipeline.py`; preview: serve `site/` over local HTTP.
- Never read or write `all_matches.csv`; never modify anything in `data/raw/`.
- Every metric needs a test. Wides and no-balls are not legal balls. Exclude super-over innings (`innings > 2`) from delivery metrics.
- Keep all team-name aliases and sample thresholds only in `scripts/config.py`.
- Add no Python dependencies beyond pandas; use no chart library in the dashboard.
- Deploy only after tests pass. Do not touch files outside this project folder.

The build plan is in docs/PLAN.md.
