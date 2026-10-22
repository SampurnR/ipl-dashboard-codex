#!/usr/bin/env python3
"""Clean per-match Cricsheet CSVs into delivery and match tables."""

import csv
from collections import defaultdict
from pathlib import Path
import re

import pandas as pd

try:
    from . import config
except ImportError:  # Supports ``python scripts/clean.py``.
    import config


_RUN_COLUMNS = ("runs_off_bat", "extras", "wides", "noballs", "byes", "legbyes", "penalty")
_BALL_LABEL = re.compile(r"^(\d+)\.(\d+)$")


def _canonical_team(value):
    value = str(value).strip()
    return config.TEAM_ALIASES.get(value, value)


def _read_info(path):
    values = defaultdict(list)
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.reader(handle):
                if len(row) >= 2 and row[0].strip() == "info":
                    values[row[1].strip()].append(",".join(row[2:]).strip())
    except OSError as error:
        raise ValueError(f"{path.name}: unable to read info file: {error}") from error
    return values


def _first(values, key, default=""):
    for value in values.get(key, []):
        if value.strip():
            return value.strip()
    return default


def _season_source(frame, info):
    if "season" in frame and not frame.empty:
        seasons = frame["season"].astype(str).str.strip()
        seasons = seasons[seasons.ne("")]
        if not seasons.empty:
            return seasons.iloc[0]
    return _first(info, "season")


def _parse_start_dates(frame, filename):
    raw_dates = frame["start_date"].astype(str).str.strip()
    parsed = pd.to_datetime(raw_dates, errors="coerce")
    invalid = parsed.isna()
    if invalid.any():
        row = int(invalid[invalid].index[0]) + 2
        raise ValueError(f"{filename}: unparseable date in start_date at CSV row {row}")
    return parsed


def _numeric_column(frame, column, filename):
    raw = frame[column].astype(str).str.strip()
    numeric = pd.to_numeric(raw.mask(raw.eq(""), "0"), errors="coerce")
    invalid = numeric.isna()
    if invalid.any():
        row = int(invalid[invalid].index[0]) + 2
        raise ValueError(f"{filename}: invalid numeric value in {column} at CSV row {row}")
    return numeric.fillna(0).astype("int64")


def _over_number(ball, filename, row_number):
    label = str(ball).strip()
    match = _BALL_LABEL.fullmatch(label)
    if match is None:
        raise ValueError(f"{filename}: invalid ball label {label!r} at CSV row {row_number}")
    return int(match.group(1)) + 1


def _boolean_column(values):
    return values.astype(str).str.strip().str.lower().isin({"true", "1", "yes"})


def _outcome_and_status(info, winner):
    outcome_values = [value.strip() for value in info.get("outcome", []) if value.strip()]
    normalized = [value.lower().replace(" ", "_") for value in outcome_values]
    if any(value == "tie" for value in normalized):
        return "tie", "tie"
    if any(value in {"no_result", "noresult", "abandoned"} for value in normalized):
        return "no_result", "no_result"
    if winner:
        outcome = outcome_values[0].replace(",", " ") if outcome_values else ""
        return outcome, "normal"
    outcome = outcome_values[0].replace(",", " ") if outcome_values else "no_result"
    return outcome, "no_result"


def _super_over_winner(info):
    for value in info.get("outcome", []):
        parts = [part.strip() for part in value.split(",")]
        if len(parts) >= 2 and parts[0].lower() == "eliminator" and parts[1]:
            return _canonical_team(",".join(parts[1:]))
    for value in info.get("eliminator", []):
        if value.strip():
            return _canonical_team(value)
    return ""


def _clean_match(delivery_path, info_path):
    match_id = delivery_path.stem
    try:
        frame = pd.read_csv(delivery_path, dtype=str, keep_default_na=False)
    except Exception as error:
        raise ValueError(f"{delivery_path.name}: unable to read delivery file: {error}") from error

    missing = [column for column in config.DELIVERY_REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"{delivery_path.name}: missing required column(s): {', '.join(missing)}")
    if frame.empty:
        raise ValueError(f"{delivery_path.name}: no delivery rows found")

    ids = set(frame["match_id"].astype(str).str.strip())
    if ids != {match_id}:
        raise ValueError(
            f"{delivery_path.name}: inconsistent match_id values; expected {match_id}, found {sorted(ids)}"
        )

    info = _read_info(info_path)
    parsed_dates = _parse_start_dates(frame, delivery_path.name)
    source_season = _season_source(frame, info)
    if not source_season:
        raise ValueError(f"{delivery_path.name}: missing source season")

    for column in _RUN_COLUMNS:
        frame[column] = _numeric_column(frame, column, delivery_path.name)
    innings = pd.to_numeric(frame["innings"], errors="coerce")
    if innings.isna().any():
        row = int(innings[innings.isna()].index[0]) + 2
        raise ValueError(f"{delivery_path.name}: invalid numeric value in innings at CSV row {row}")
    frame["innings"] = innings.astype("int64")

    frame["source_season"] = source_season
    frame["season_year"] = parsed_dates.dt.year.astype("int64")
    frame["start_date"] = parsed_dates.dt.strftime("%Y-%m-%d")
    frame["batting_team"] = frame["batting_team"].map(_canonical_team)
    frame["bowling_team"] = frame["bowling_team"].map(_canonical_team)
    frame["legal_ball"] = frame["wides"].eq(0) & frame["noballs"].eq(0)
    frame["is_super_over"] = frame["innings"].gt(2)
    frame["team_runs"] = frame["runs_off_bat"] + frame["extras"]
    frame["bowler_runs"] = frame["runs_off_bat"] + frame["wides"] + frame["noballs"]
    frame["over_number"] = [
        _over_number(ball, delivery_path.name, index + 2)
        for index, ball in enumerate(frame["ball"].astype(str))
    ]
    frame["non_boundary"] = _boolean_column(frame["non_boundary"])

    team_entries = info.get("team", []) + info.get("teams", [])
    teams = [_canonical_team(team) for team in team_entries if team.strip()]
    if len(teams) < 2:
        raise ValueError(f"{info_path.name}: missing two team entries")
    toss_winner = _canonical_team(_first(info, "toss_winner"))
    winner = _canonical_team(_first(info, "winner"))
    outcome, result_status = _outcome_and_status(info, winner)
    super_over_winner = _super_over_winner(info)
    date = parsed_dates.iloc[0].strftime("%Y-%m-%d")
    venue = _first(info, "venue") or str(frame["venue"].iloc[0]).strip()

    match = {
        "match_id": match_id,
        "season_year": int(parsed_dates.iloc[0].year),
        "source_season": source_season,
        "date": date,
        "venue": venue,
        "team1": teams[0],
        "team2": teams[1],
        "toss_winner": toss_winner,
        "winner": winner,
        "outcome": outcome,
        "result_status": result_status,
        "super_over_winner": super_over_winner,
    }
    return frame, match


def clean_data(source_dir=config.RAW_DATA_DIR, output_dir=config.CLEAN_DATA_DIR):
    """Clean matching delivery/info files and write the two clean CSV outputs."""
    source_dir = Path(source_dir)
    output_dir = Path(output_dir)
    matcher = re.compile(config.MATCH_FILE_PATTERN)
    delivery_files = sorted(
        path for path in source_dir.iterdir()
        if path.is_file() and matcher.fullmatch(path.name) and path.name.endswith(".csv")
        and not path.stem.endswith("_info")
    )

    delivery_frames = []
    matches = []
    for delivery_path in delivery_files:
        info_path = delivery_path.with_name(f"{delivery_path.stem}_info.csv")
        if not info_path.is_file() or not matcher.fullmatch(info_path.name):
            raise ValueError(f"{info_path.name}: missing required companion info file")
        deliveries, match = _clean_match(delivery_path, info_path)
        delivery_frames.append(deliveries)
        matches.append(match)

    if not delivery_frames:
        raise ValueError(f"{source_dir}: no files matching {config.MATCH_FILE_PATTERN}")

    all_deliveries = pd.concat(delivery_frames, ignore_index=True)
    match_table = pd.DataFrame(matches, columns=config.MATCH_COLUMNS)
    output_dir.mkdir(parents=True, exist_ok=True)
    all_deliveries.to_csv(output_dir / "deliveries.csv", index=False)
    match_table.to_csv(output_dir / "matches.csv", index=False)
    return {
        "match_files_read": len(delivery_files),
        "delivery_rows": len(all_deliveries),
        "matches": len(match_table),
    }


def main():
    summary = clean_data()
    print(f"Match files read: {summary['match_files_read']}")
    print(f"Delivery rows written: {summary['delivery_rows']}")
    print(f"Matches written: {summary['matches']}")
    print(f"Clean outputs: {config.CLEAN_DATA_DIR}")


if __name__ == "__main__":
    main()
