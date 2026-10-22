#!/usr/bin/env python3
"""Build additive IPL metric grains and query rankings from those tables."""

from pathlib import Path

import pandas as pd

try:
    from . import config
except ImportError:  # Supports ``python scripts/metrics.py``.
    import config


GRAIN_COLUMNS = {
    "team_run_rate": ["season_year", "team", "runs", "legal_balls"],
    "bowler_economy": ["season_year", "team", "bowler", "runs_conceded", "legal_balls"],
    "batter_boundary": [
        "season_year", "team", "batter", "batter_runs", "boundary_runs", "balls_faced",
    ],
    "death_over_economy": ["season_year", "team", "bowler", "runs_conceded", "legal_balls"],
    "team_records": [
        "season_year", "team", "played", "wins", "losses", "ties", "no_results",
    ],
}


def _numeric(values):
    return pd.to_numeric(values, errors="coerce").fillna(0)


def _as_bool(values):
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False)
    return values.astype(str).str.strip().str.lower().isin({"true", "1", "yes"})


def _empty_grain(name):
    return pd.DataFrame(columns=GRAIN_COLUMNS[name])


def _group_sum(frame, keys, aggregations, columns):
    if frame.empty:
        return pd.DataFrame(columns=columns)
    result = frame.groupby(keys, as_index=False, dropna=False).agg(**aggregations)
    return result.loc[:, columns]


def _clean_delivery_values(deliveries):
    required = {
        "season_year", "batting_team", "bowling_team", "striker", "bowler",
        "runs_off_bat", "team_runs", "bowler_runs", "wides", "legal_ball",
        "is_super_over", "non_boundary", "over_number",
    }
    missing = sorted(required - set(deliveries.columns))
    if missing:
        raise ValueError(f"deliveries.csv is missing required columns: {', '.join(missing)}")
    result = deliveries.copy()
    result["season_year"] = pd.to_numeric(result["season_year"], errors="raise").astype("int64")
    for column in ("runs_off_bat", "team_runs", "bowler_runs", "wides", "over_number"):
        result[column] = _numeric(result[column])
    result["legal_ball"] = _as_bool(result["legal_ball"])
    result["is_super_over"] = _as_bool(result["is_super_over"])
    result["non_boundary"] = _as_bool(result["non_boundary"])
    result["batting_team"] = result["batting_team"].astype(str).str.strip()
    result["bowling_team"] = result["bowling_team"].astype(str).str.strip()
    result["striker"] = result["striker"].astype(str).str.strip()
    result["bowler"] = result["bowler"].astype(str).str.strip()
    return result.loc[~result["is_super_over"]].copy()


def _make_team_records(matches):
    required = {"season_year", "team1", "team2", "winner", "result_status"}
    missing = sorted(required - set(matches.columns))
    if missing:
        raise ValueError(f"matches.csv is missing required columns: {', '.join(missing)}")

    rows = []
    for match in matches.itertuples(index=False):
        season_year = int(pd.to_numeric(match.season_year, errors="raise"))
        team1 = str(match.team1).strip()
        team2 = str(match.team2).strip()
        winner = str(match.winner).strip()
        status = str(match.result_status).strip().lower()
        for team in (team1, team2):
            record = {
                "season_year": season_year,
                "team": team,
                "played": 1,
                "wins": 0,
                "losses": 0,
                "ties": 0,
                "no_results": 0,
            }
            if status == "tie":
                record["ties"] = 1
            elif status == "no_result":
                record["no_results"] = 1
            elif status == "normal":
                if winner == team:
                    record["wins"] = 1
                elif winner:
                    record["losses"] = 1
            else:
                raise ValueError(f"Unknown result_status {status!r} in match {getattr(match, 'match_id', '')}")
            rows.append(record)

    if not rows:
        return _empty_grain("team_records")
    frame = pd.DataFrame(rows)
    return frame.groupby(["season_year", "team"], as_index=False, dropna=False)[
        ["played", "wins", "losses", "ties", "no_results"]
    ].sum().loc[:, GRAIN_COLUMNS["team_records"]]


def build_grain_tables(deliveries, matches):
    """Return the five unrounded additive metric tables from cleaned inputs."""
    source = _clean_delivery_values(deliveries)
    legal = source["legal_ball"].astype("int64")

    team_run_rate = source.assign(_legal_balls=legal).groupby(
        ["season_year", "batting_team"], as_index=False, dropna=False
    ).agg(runs=("team_runs", "sum"), legal_balls=("_legal_balls", "sum"))
    team_run_rate = team_run_rate.rename(columns={"batting_team": "team"})[
        GRAIN_COLUMNS["team_run_rate"]
    ]

    bowler_economy = source.assign(_legal_balls=legal).groupby(
        ["season_year", "bowling_team", "bowler"], as_index=False, dropna=False
    ).agg(runs_conceded=("bowler_runs", "sum"), legal_balls=("_legal_balls", "sum"))
    bowler_economy = bowler_economy.rename(columns={"bowling_team": "team"})[
        GRAIN_COLUMNS["bowler_economy"]
    ]

    boundary_delivery = source["runs_off_bat"].isin({4, 6}) & ~source["non_boundary"]
    batter_source = source.assign(
        _boundary_runs=source["runs_off_bat"].where(boundary_delivery, 0),
        _balls_faced=source["wides"].eq(0).astype("int64"),
    )
    batter_boundary = batter_source.groupby(
        ["season_year", "batting_team", "striker"], as_index=False, dropna=False
    ).agg(
        batter_runs=("runs_off_bat", "sum"),
        boundary_runs=("_boundary_runs", "sum"),
        balls_faced=("_balls_faced", "sum"),
    )
    batter_boundary = batter_boundary.rename(
        columns={"batting_team": "team", "striker": "batter"}
    )[GRAIN_COLUMNS["batter_boundary"]]

    death_start, death_end = config.DEATH_OVER_RANGE
    death_source = source.loc[source["over_number"].between(death_start, death_end)]
    death_over_economy = death_source.assign(
        _legal_balls=death_source["legal_ball"].astype("int64")
    ).groupby(
        ["season_year", "bowling_team", "bowler"], as_index=False, dropna=False
    ).agg(runs_conceded=("bowler_runs", "sum"), legal_balls=("_legal_balls", "sum"))
    death_over_economy = death_over_economy.rename(columns={"bowling_team": "team"})[
        GRAIN_COLUMNS["death_over_economy"]
    ]

    tables = {
        "team_run_rate": team_run_rate,
        "bowler_economy": bowler_economy,
        "batter_boundary": batter_boundary,
        "death_over_economy": death_over_economy,
        "team_records": _make_team_records(matches),
    }
    for name, columns in GRAIN_COLUMNS.items():
        tables[name] = tables[name].loc[:, columns]
    return tables


def write_grain_tables(tables, output_dir=config.CLEAN_DATA_DIR):
    """Write each grain table as ``<name>.csv`` into the selected directory."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, columns in GRAIN_COLUMNS.items():
        table = tables.get(name, _empty_grain(name)).loc[:, columns]
        table.to_csv(output_dir / f"{name}.csv", index=False)


def _read_grain(name, data_dir):
    path = Path(data_dir) / f"{name}.csv"
    if not path.is_file():
        return _empty_grain(name)
    return pd.read_csv(path, keep_default_na=False, low_memory=False)


def _filter_scope(frame, season_year, team):
    result = frame.copy()
    if season_year is not None and not result.empty:
        result = result.loc[pd.to_numeric(result["season_year"], errors="coerce").eq(int(season_year))]
    if team is not None and not result.empty:
        result = result.loc[result["team"].astype(str).str.strip().eq(str(team).strip())]
    return result


def _scope_label(value):
    return value if value is not None else "All"


def run_rate_by_season(team=None, data_dir=config.CLEAN_DATA_DIR):
    """Return weighted run rate by season, optionally scoped to a batting team."""
    frame = _filter_scope(_read_grain("team_run_rate", data_dir), None, team)
    columns = ["season_year", "team", "runs", "legal_balls", "run_rate"]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    frame["runs"] = _numeric(frame["runs"])
    frame["legal_balls"] = _numeric(frame["legal_balls"])
    result = frame.groupby("season_year", as_index=False).agg(
        runs=("runs", "sum"), legal_balls=("legal_balls", "sum")
    )
    result["run_rate"] = (result["runs"] / result["legal_balls"] * 6).round(2)
    result["team"] = team if team is not None else "All teams"
    return result.loc[:, columns].sort_values("season_year").reset_index(drop=True)


def _rank_players(name, season_year, team, top, player_column, sample_column,
                  numerator_column, rate_column, descending, data_dir):
    frame = _filter_scope(_read_grain(name, data_dir), season_year, team)
    result_columns = [
        "season_year", "team", player_column, numerator_column, sample_column, rate_column,
    ]
    if frame.empty:
        return pd.DataFrame(columns=result_columns)

    frame[numerator_column] = _numeric(frame[numerator_column])
    frame[sample_column] = _numeric(frame[sample_column])
    frame = frame.loc[frame[player_column].astype(str).str.strip().ne("")]
    grouped = frame.groupby(player_column, as_index=False, dropna=False).agg(
        **{
            numerator_column: (numerator_column, "sum"),
            sample_column: (sample_column, "sum"),
        }
    )
    minimum = config.SAMPLE_THRESHOLDS[
        "all_seasons" if season_year is None else "single_season"
    ]
    grouped = grouped.loc[grouped[sample_column].ge(minimum)]
    if name == "batter_boundary":
        grouped = grouped.loc[grouped[numerator_column].gt(0)]
        boundary_runs = frame.groupby(player_column)["boundary_runs"].sum()
        grouped["boundary_runs"] = grouped[player_column].map(boundary_runs)
        grouped[rate_column] = (
            grouped["boundary_runs"] / grouped[numerator_column] * 100
        ).round(2)
        result_columns = [
            "season_year", "team", player_column, numerator_column,
            "boundary_runs", sample_column, rate_column,
        ]
    else:
        grouped[rate_column] = (
            grouped[numerator_column] / grouped[sample_column] * 6
        ).round(2)

    sort_columns = [rate_column, sample_column, player_column]
    sort_ascending = [not descending, False, True]
    grouped = grouped.sort_values(sort_columns, ascending=sort_ascending, kind="mergesort")
    grouped = grouped.head(max(0, int(top))).copy()
    grouped["season_year"] = _scope_label(season_year)
    grouped["team"] = team if team is not None else "All teams"
    return grouped.loc[:, result_columns].reset_index(drop=True)


def rank_bowlers(season_year, team, top=10, data_dir=config.CLEAN_DATA_DIR):
    """Rank bowlers by economy in the requested season and bowling-team scope."""
    return _rank_players(
        "bowler_economy", season_year, team, top, "bowler", "legal_balls",
        "runs_conceded", "economy", False, data_dir,
    )


def rank_batters(season_year, team, top=10, data_dir=config.CLEAN_DATA_DIR):
    """Rank batters by boundary percentage in the requested season and batting-team scope."""
    return _rank_players(
        "batter_boundary", season_year, team, top, "batter", "balls_faced",
        "batter_runs", "boundary_percentage", True, data_dir,
    )


def rank_death_bowlers(season_year, team, top=10, data_dir=config.CLEAN_DATA_DIR):
    """Rank death-over bowlers by economy in the requested scope."""
    return _rank_players(
        "death_over_economy", season_year, team, top, "bowler", "legal_balls",
        "runs_conceded", "economy", False, data_dir,
    )


def team_records(season_year, team, data_dir=config.CLEAN_DATA_DIR):
    """Return W/L/T/no-result counts for the selected season and team scope."""
    frame = _filter_scope(_read_grain("team_records", data_dir), season_year, team)
    columns = GRAIN_COLUMNS["team_records"]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    count_columns = ["played", "wins", "losses", "ties", "no_results"]
    for column in count_columns:
        frame[column] = _numeric(frame[column])
    result = frame.groupby("team", as_index=False)[count_columns].sum()
    result["season_year"] = _scope_label(season_year)
    if team is not None:
        result = result.loc[result["team"].astype(str).str.strip().eq(str(team).strip())]
    return result.loc[:, columns].sort_values("team").reset_index(drop=True)


def main():
    deliveries = pd.read_csv(config.DELIVERIES_PATH, keep_default_na=False, low_memory=False)
    matches = pd.read_csv(config.MATCHES_PATH, keep_default_na=False, low_memory=False)
    tables = build_grain_tables(deliveries, matches)
    write_grain_tables(tables, config.CLEAN_DATA_DIR)
    for name in GRAIN_COLUMNS:
        print(f"{name}.csv: {len(tables[name])} rows")


if __name__ == "__main__":
    main()
