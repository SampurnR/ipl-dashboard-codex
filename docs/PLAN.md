# IPL Data Pipeline and Dashboard

## Summary

Build a reproducible, read-only pipeline from per-match Cricsheet files to cleaned tables, metric summaries, and a static dashboard. Keep `data/raw/` immutable; include playoffs and all seasons. The intended audience is people exploring IPL team and player statistics.

## Numbered build plan

1. **Centralize rules — `scripts/config.py`.** Define the four team aliases in one mapping, the legal-ball sample thresholds (60 for All seasons, 30 for a selected season), and shared paths and field names. Treat unmapped team names as unchanged. Select only numeric `<match_id>.csv` files and their `<match_id>_info.csv` companions.

2. **Clean the source — `scripts/clean.py`.** Read those per-match files only; never read `all_matches.csv` or write under `data/raw/`. Preserve the source season as `source_season`, derive integer `season_year` from `start_date`, and canonicalize team names in delivery and match metadata. Write:
   - `data/clean/deliveries.csv`: all innings, with derived `season_year`, `legal_ball`, `is_super_over`, team runs, bowler runs conceded, and over number.
   - `data/clean/matches.csv`: one row per match with canonical teams, winner, result status, `season_year`, and `super_over_winner` parsed from the `eliminator` metadata line. Super-over matches have `outcome,tie`, so team W/L/T records count them as ties while `super_over_winner` separately records the eliminator team.

   Treat blank extras as zero. Fail with match/file context on invalid dates, missing required columns, or inconsistent match IDs. Retain super-over rows in clean data for traceability; exclude them from delivery-based metrics.

3. **Compute metrics — `scripts/metrics.py`.** Read the clean tables and write five metric CSVs under `data/clean/`. Use these definitions:
   - Team run rate: `(runs_off_bat + extras) / legal balls × 6`; include no-result matches and playoffs.
   - Bowler economy: `(runs_off_bat + wides + noballs) / legal balls × 6`; do not charge byes or leg byes.
   - Batter boundary percentage: boundary runs divided by total `runs_off_bat`, ×100. Boundary runs are `runs_off_bat` values of 4 or 6 only when `non_boundary` is not `"true"`; 29 deliveries are marked `non_boundary=true`, including four-run outcomes that were run rather than hit to the boundary.
   - Death-over economy: the bowler economy formula for overs 16–20. Since Cricsheet labels the first over `0.x`, use ball-label prefixes 15–19.
   - Team records: derive wins, losses, and ties from match metadata; exclude no-results, count tied super-over matches as ties, and retain their eliminator team in `super_over_winner` without using it to convert the tie into a win/loss.

   For all delivery metrics, wides and no-balls are not legal balls; other extras do not make a delivery illegal. Apply a 60 legal-ball minimum to bowler economy, death-over economy, and batter boundary percentage when All seasons is selected, and a 30 legal-ball minimum when one season is selected. Apply the threshold within the selected season/team scope. Exclude undefined batter percentages where batter runs are zero.

4. **Export for the site — `scripts/export.py`.** Bundle the metric tables into one versioned JSON file at `site/data/ipl_metrics.json`. Include seasons, canonical teams, metric definitions, metric values, and the run/ball totals needed to aggregate after filtering.

5. **Build the static dashboard.** Create `site/index.html`, `site/styles.css`, and `site/app.js` using vanilla JavaScript and SVG charts; use no backend or chart-library dependency. Load the relative JSON file with `fetch`. Provide single-select season and team filters, both defaulting to All. Render three charts—run rate by season, top 10 bowlers by economy, and top 10 batters by boundary percentage—plus a death-economy ranking table and compact W/L/T summary. With All teams selected, show weighted league run rate; with a team selected, show that team’s rate. Apply the team filter by bowling team for bowler metrics, batting team for batter metrics, and match participation for records. Show a clear empty-state message when no player qualifies under the active threshold.

6. **Orchestrate, document, and test.** Create `scripts/run_pipeline.py` to run clean → metrics → export in order, and use Python’s built-in `unittest` so pandas remains the only added Python dependency. Add `tests/test_clean.py`, `tests/test_metrics.py`, and `tests/test_export.py`. Create `docs/pipeline_architecture.svg` as a hand-written SVG during the build.

## Tests and acceptance

- One calculation test for each metric: team run rate, bowler economy, batter boundary percentage, and death-over economy including its sample cutoff.
- Additional tests for all four team aliases, keeping Deccan Chargers and Sunrisers Hyderabad distinct, deriving `season_year` from `start_date`, wide/no-ball legal-ball handling, and excluding innings above 2 from every delivery metric.
- Test both season-dependent sample thresholds and empty qualification results, no-result exclusion and tie counting in team records, `super_over_winner` extraction, plus the JSON schema and required metric arrays.
- Run `python -m unittest discover -s tests`, then `python scripts/run_pipeline.py`. For the current raw archive, confirm 1,243 per-match files, 295,732 delivery rows before super-over filtering, and 175 super-over rows excluded from delivery metrics. Compare raw-file hashes before and after the pipeline to confirm raw data stayed unchanged.
- Preview the site locally over HTTP; verify JSON loading, filters, ranking thresholds, and loading/empty/error states at desktop and phone widths.

## Risks and open questions

- No metric-definition questions remain; the boundary formula, sample thresholds, no-result treatment, chart mix, and tie handling are set above.
- `all_matches.csv` duplicates the per-match delivery export, so file selection must stay restricted to match-ID files.
- Official OpenAI documentation recommends checking a compatible local project before publishing to Sites. It also says local-source versions are associated with a Git commit, and deployments are production deployments; publishing needs a separate compatibility/review and commit step. [Create a site](https://learn.chatgpt.com/docs/sites/creating-a-site), [Manage a site](https://learn.chatgpt.com/docs/sites/managing-a-site)
- Image generation is not available through the tools exposed in this session. The architecture diagram will be a hand-written SVG at `docs/pipeline_architecture.svg`, created during the build rather than this setup step.
