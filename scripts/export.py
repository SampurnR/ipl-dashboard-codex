#!/usr/bin/env python3
"""Export metric scopes as a deterministic, versioned site JSON file."""

import json
import math
from numbers import Integral, Real
from pathlib import Path

import pandas as pd

try:
    from . import config, metrics
except ImportError:  # Supports ``python scripts/export.py``.
    import config
    import metrics


SITE_DATA_DIR = config.PROJECT_ROOT / "site" / "data"
SITE_DATA_PATH = SITE_DATA_DIR / "ipl_metrics.json"

METRIC_DEFINITIONS = {
    "run_rate": "Team runs divided by legal balls, multiplied by 6.",
    "economy": (
        "Bowler runs conceded, including wides and no-balls but excluding byes and leg byes, "
        "divided by legal balls and multiplied by 6."
    ),
    "boundary_percentage": (
        "Runs off the bat from fours and sixes, excluding non-boundary hits, "
        "divided by batter runs and multiplied by 100."
    ),
    "death_over_economy": "Bowler economy for overs 16 through 20.",
    "team_records": (
        "Wins, losses, and ties from match results; a super-over eliminator does not change a tie. "
        "No-result matches are counted separately."
    ),
    "qualification_rule": (
        "Bowlers qualify with at least {all_seasons} legal balls bowled across all seasons or "
        "{single_season} legal balls bowled in a selected season. Batters qualify with at least "
        "{all_seasons} balls faced across all seasons or {single_season} balls faced in a selected "
        "season; balls faced count every delivery except a wide, so no-balls count. Batters with zero "
        "runs are excluded."
    ),
}


def _json_safe(value):
    if hasattr(value, "item"):
        value = value.item()
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        number = float(value)
        return number if math.isfinite(number) else None
    if pd.isna(value):
        return None
    return value


def _records(frame):
    return [
        {key: _json_safe(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def _bool_values(values):
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False)
    return values.astype(str).str.strip().str.lower().isin({"true", "1", "yes"})


def _metadata(clean_dir):
    clean_dir = Path(clean_dir)
    deliveries = pd.read_csv(clean_dir / "deliveries.csv", keep_default_na=False, low_memory=False)
    matches = pd.read_csv(clean_dir / "matches.csv", keep_default_na=False, low_memory=False)
    if "is_super_over" in deliveries:
        super_over_count = int(_bool_values(deliveries["is_super_over"]).sum())
    else:
        super_over_count = 0

    season_values = pd.to_numeric(matches.get("season_year", pd.Series(dtype=int)), errors="coerce")
    seasons = sorted({int(value) for value in season_values.dropna().tolist()})
    teams_by_season = {season: set() for season in seasons}
    teams = set()
    for row in matches.itertuples(index=False):
        season_year = int(pd.to_numeric(row.season_year, errors="raise"))
        for field in ("team1", "team2"):
            team = str(getattr(row, field, "")).strip()
            if team:
                teams.add(team)
                teams_by_season.setdefault(season_year, set()).add(team)
    if not teams:
        for field in ("batting_team", "bowling_team"):
            if field in deliveries:
                teams.update(value.strip() for value in deliveries[field].astype(str) if value.strip())

    data_through = ""
    if "date" in matches and not matches.empty:
        dates = pd.to_datetime(matches["date"], errors="coerce")
        latest = dates.max()
        if pd.notna(latest):
            data_through = latest.strftime("%Y-%m-%d")

    return {
        "deliveries": deliveries,
        "matches": matches,
        "data_through": data_through,
        "match_count": int(len(matches)),
        "delivery_count": int(len(deliveries)),
        "super_over_rows_excluded": super_over_count,
        "seasons": seasons,
        "teams": sorted(teams),
        "teams_by_season": {
            str(season): sorted(teams_by_season.get(season, set())) for season in seasons
        },
    }


def build_payload(clean_dir=config.CLEAN_DATA_DIR):
    """Build the complete schema-version-1 JSON-ready object from clean CSVs."""
    clean_dir = Path(clean_dir)
    metadata = _metadata(clean_dir)
    season_values = metadata["seasons"]
    teams = metadata["teams"]
    thresholds = dict(config.SAMPLE_THRESHOLDS)

    run_rates = {
        "All": _records(metrics.run_rate_by_season(data_dir=clean_dir)),
    }
    for team in teams:
        run_rates[team] = _records(metrics.run_rate_by_season(team=team, data_dir=clean_dir))

    scopes = {}
    scope_seasons = [("All", None)] + [(str(season), season) for season in season_values]
    for season_label, season_value in scope_seasons:
        participating_teams = teams if season_value is None else metadata["teams_by_season"][season_label]
        scope_teams = [("All", None)] + [(team, team) for team in participating_teams]
        scopes[season_label] = {}
        for team_label, team_value in scope_teams:
            scopes[season_label][team_label] = {
                "bowlers": _records(metrics.rank_bowlers(
                    season_value, team_value, top=10, data_dir=clean_dir
                )),
                "batters": _records(metrics.rank_batters(
                    season_value, team_value, top=10, data_dir=clean_dir
                )),
                "death_bowlers": _records(metrics.rank_death_bowlers(
                    season_value, team_value, top=10, data_dir=clean_dir
                )),
                "records": _records(metrics.team_records(
                    season_value, team_value, data_dir=clean_dir
                )),
            }

    definitions = dict(METRIC_DEFINITIONS)
    definitions["qualification_rule"] = definitions["qualification_rule"].format(
        all_seasons=thresholds["all_seasons"],
        single_season=thresholds["single_season"],
    )
    return {
        "schema_version": 1,
        "data_through": metadata["data_through"],
        "match_count": metadata["match_count"],
        "delivery_count": metadata["delivery_count"],
        "super_over_rows_excluded": metadata["super_over_rows_excluded"],
        "thresholds": thresholds,
        "definitions": definitions,
        "seasons": season_values,
        "teams": teams,
        "teams_by_season": metadata["teams_by_season"],
        "run_rate_by_season": run_rates,
        "scopes": scopes,
    }


def export_metrics(clean_dir=config.CLEAN_DATA_DIR, output_path=SITE_DATA_PATH):
    """Write deterministic, strict JSON and return the destination path."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload(clean_dir=clean_dir)
    serialized = json.dumps(
        payload,
        sort_keys=True,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n"
    output_path.write_text(serialized, encoding="utf-8", newline="\n")
    print(f"Exported {output_path.relative_to(config.PROJECT_ROOT) if output_path.is_relative_to(config.PROJECT_ROOT) else output_path}: {len(serialized.encode('utf-8'))} bytes")
    return output_path


def main():
    export_metrics()


if __name__ == "__main__":
    main()
