#!/usr/bin/env python3
"""Print a read-only profile of the Cricsheet IPL CSV2 data."""

from collections import Counter, defaultdict
import csv
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"


def read_match_info(info_files):
    """Read Cricsheet's key/value companion files without changing them."""
    metadata = {}
    for path in info_files:
        match_id = path.name.removesuffix("_info.csv")
        values = defaultdict(list)
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.reader(handle):
                if len(row) >= 2 and row[0] == "info":
                    values[row[1]].append(",".join(row[2:]).strip())
        metadata[match_id] = values
    return metadata


def sample_rows(frame, mask, limit=5):
    columns = [
        column
        for column in ("match_id", "innings", "ball", "actual_delivery")
        if column in frame.columns
    ]
    return frame.loc[mask, columns].head(limit).to_dict("records")


def main():
    info_files = sorted(RAW_DIR.glob("*_info.csv"))
    ball_files = sorted(
        path
        for path in RAW_DIR.glob("*.csv")
        if not path.stem.endswith("_info") and path.name != "all_matches.csv"
    )
    metadata = read_match_info(info_files)

    frames = []
    empty_ball_files = []
    schema_variants = Counter()
    canonical_columns = None
    file_id_mismatches = []

    for path in ball_files:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        columns = tuple(frame.columns)
        schema_variants[columns] += 1
        if canonical_columns is None:
            canonical_columns = columns
        if frame.empty:
            empty_ball_files.append(path.name)
        if "match_id" in frame.columns:
            ids = set(frame["match_id"].astype(str).str.strip()) - {""}
            if ids and ids != {path.stem}:
                file_id_mismatches.append((path.name, sorted(ids)))
        frames.append(frame)

    if frames:
        data = pd.concat(frames, ignore_index=True)
    else:
        data = pd.DataFrame()

    print("Cricsheet IPL CSV2 profile")
    print(f"Raw directory: {RAW_DIR}")
    print(f"Match data CSV files: {len(ball_files)}")
    print(f"Companion info files: {len(info_files)}")
    print(
        "Aggregate all_matches.csv excluded by design; it is not read."
    )
    print(f"Distinct match_id values in ball rows: {data['match_id'].nunique() if 'match_id' in data else 0}")
    print(f"Ball rows: {len(data)}")
    print(f"Columns ({len(canonical_columns or ())}): {', '.join(canonical_columns or ())}")

    if len(schema_variants) > 1:
        print("Schema variation by file:")
        for columns, count in schema_variants.items():
            print(f"  {count} files: {', '.join(columns)}")
    else:
        print(f"Schema variants: 1 across {sum(schema_variants.values())} files")

    seasons = Counter()
    missing_season_matches = []
    for match_id, values in metadata.items():
        season_values = values.get("season", [])
        season = season_values[0] if season_values else "<missing>"
        seasons[season] += 1
        if season == "<missing>":
            missing_season_matches.append(match_id)
    print("\nMatches per season (from companion info files):")
    def season_sort_key(value):
        prefix = value[:4]
        return (int(prefix) if prefix.isdigit() else 9999, value)

    for season in sorted(seasons, key=season_sort_key):
        print(f"  {season}: {seasons[season]}")

    teams = set()
    for column in ("batting_team", "bowling_team"):
        if column in data:
            teams.update(value.strip() for value in data[column].astype(str) if value.strip())
    print(f"\nDistinct team names ({len(teams)}): {', '.join(sorted(teams))}")

    if "bowler" in data:
        missing_bowler = data["bowler"].astype(str).str.strip().eq("")
        print(f"Rows with missing/empty bowler: {int(missing_bowler.sum())}")
        if missing_bowler.any():
            print(f"  Examples: {sample_rows(data, missing_bowler)}")
    else:
        print("Rows with missing/empty bowler: column absent")

    print("\nWides and no-balls (non-empty values in their dedicated columns):")
    for label, column in (("wides", "wides"), ("no-balls", "noballs")):
        if column not in data:
            print(f"  {label}: column absent")
            continue
        values = data[column].astype(str).str.strip()
        recorded = values.ne("")
        numeric = pd.to_numeric(values.where(recorded), errors="coerce")
        invalid = recorded & numeric.isna()
        value_counts = Counter(values[recorded])
        total = numeric.fillna(0).sum()
        print(
            f"  {label}: {int(recorded.sum())} rows, recorded total {total:g}, "
            f"values {dict(sorted(value_counts.items()))}"
        )
        if invalid.any():
            print(f"    Non-numeric examples: {sample_rows(data, invalid)}")

    print("\nData-quality checks:")
    print(f"  Empty ball-data files: {len(empty_ball_files)}" + (f" ({empty_ball_files[:5]})" if empty_ball_files else ""))
    print(f"  Match ID/file-name mismatches: {len(file_id_mismatches)}" + (f" ({file_id_mismatches[:5]})" if file_id_mismatches else ""))
    print(f"  Matches missing season metadata: {len(missing_season_matches)}" + (f" ({missing_season_matches[:5]})" if missing_season_matches else ""))

    if not data.empty:
        exact_duplicates = data.duplicated(keep="first")
        exact_duplicate_groups = data.duplicated(keep=False)
        print(
            "  Exact duplicate ball rows: "
            f"{int(exact_duplicates.sum())} extra rows across "
            f"{int(exact_duplicate_groups.sum())} affected rows"
        )
        if exact_duplicate_groups.any():
            print(f"    Examples: {sample_rows(data, exact_duplicate_groups)}")

        key_columns = [name for name in ("match_id", "innings", "ball") if name in data]
        if len(key_columns) == 3:
            delivery_duplicates = data.duplicated(subset=key_columns, keep="first")
            delivery_duplicate_groups = data.duplicated(subset=key_columns, keep=False)
            print(
                "  Repeated (match_id, innings, ball) keys: "
                f"{int(delivery_duplicates.sum())} extra rows across "
                f"{int(delivery_duplicate_groups.sum())} affected rows"
            )
            if delivery_duplicate_groups.any():
                print(f"    Examples: {sample_rows(data, delivery_duplicate_groups)}")

        legal_index_columns = [name for name in ("match_id", "innings", "actual_delivery") if name in data]
        if len(legal_index_columns) == 3:
            reused_index = data.duplicated(subset=legal_index_columns, keep=False)
            repeated_groups = data.loc[reused_index].groupby(legal_index_columns, dropna=False)
            groups_with_extras = 0
            for _, group in repeated_groups:
                if any(
                    column in group
                    and group[column].astype(str).str.strip().ne("").any()
                    for column in ("wides", "noballs")
                ):
                    groups_with_extras += 1
            extra_rows = int(data.duplicated(subset=legal_index_columns, keep="first").sum())
            print(
                "  Reused actual_delivery labels: "
                f"{extra_rows} extra rows across {len(repeated_groups)} repeated labels; "
                f"{groups_with_extras} labels include a wide/no-ball row"
            )

        required = ["match_id", "innings", "ball", "batting_team", "bowling_team", "striker"]
        missing_columns = [name for name in required if name not in data]
        missing_required = {}
        for column in required:
            if column in data:
                missing_required[column] = int(data[column].astype(str).str.strip().eq("").sum())
        print(f"  Missing required columns: {missing_columns}")
        print(f"  Empty required identifiers/labels: {missing_required}")

        run_columns = [
            name
            for name in ("runs_off_bat", "extras", "wides", "noballs", "byes", "legbyes", "penalty")
            if name in data
        ]
        numeric_issues = {}
        for column in run_columns:
            values = data[column].astype(str).str.strip()
            present = values.ne("")
            numeric = pd.to_numeric(values.where(present), errors="coerce")
            invalid = present & numeric.isna()
            negative = numeric.lt(0).fillna(False)
            if invalid.any() or negative.any():
                numeric_issues[column] = {
                    "non_numeric_rows": int(invalid.sum()),
                    "negative_rows": int(negative.sum()),
                    "examples": sample_rows(data, invalid | negative),
                }
        print(f"  Non-numeric or negative run values: {numeric_issues if numeric_issues else 'none'}")

        if "non_boundary" in data:
            values = data["non_boundary"].astype(str).str.strip().str.lower()
            recorded = values.ne("")
            allowed = {"true", "false", "1", "0"}
            unusual = recorded & ~values.isin(allowed)
            print(
                "  non_boundary markers: "
                f"{int(recorded.sum())} populated values {dict(Counter(values[recorded]))}; "
                f"unexpected values {int(unusual.sum())}"
            )

        same_team = (
            data["batting_team"].astype(str).str.strip()
            == data["bowling_team"].astype(str).str.strip()
        )
        print(f"  Rows where batting and bowling teams match: {int(same_team.sum())}")

        innings = pd.to_numeric(data["innings"], errors="coerce") if "innings" in data else pd.Series(dtype=float)
        super_over_rows = innings.gt(2).fillna(False)
        super_over_matches = {
            match_id for match_id, values in metadata.items() if values.get("super_over")
        }
        row_super_over_matches = set(data.loc[super_over_rows, "match_id"].astype(str)) if "match_id" in data else set()
        super_over_innings_entries = sum(
            len(values.get("super_over", [])) for values in metadata.values()
        )
        print(
            f"  Super overs: {len(super_over_matches)} matches flagged in info metadata "
            f"({super_over_innings_entries} super_over innings entries); "
            f"{int(super_over_rows.sum())} rows in innings > 2 across "
            f"{len(row_super_over_matches)} matches"
        )
        if super_over_matches:
            print(f"    Example match IDs: {sorted(super_over_matches)[:5]}")
        if super_over_matches - row_super_over_matches:
            print(f"    Flagged without innings > 2 rows: {sorted(super_over_matches - row_super_over_matches)[:10]}")
        if row_super_over_matches - super_over_matches:
            print(f"    Innings > 2 without metadata flag: {sorted(row_super_over_matches - super_over_matches)[:10]}")

    no_result_matches = []
    for match_id, values in metadata.items():
        if any(value.lower() == "no result" for value in values.get("outcome", [])):
            no_result_matches.append(match_id)
    print(f"  No-result/abandoned matches in info metadata: {len(no_result_matches)}" + (f"; IDs {no_result_matches}" if no_result_matches else ""))


if __name__ == "__main__":
    main()
