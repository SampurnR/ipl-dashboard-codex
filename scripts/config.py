"""Shared configuration for the IPL cleaning and metrics pipeline."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
CLEAN_DATA_DIR = PROJECT_ROOT / "data" / "clean"
DELIVERIES_PATH = CLEAN_DATA_DIR / "deliveries.csv"
MATCHES_PATH = CLEAN_DATA_DIR / "matches.csv"

MATCH_FILE_PATTERN = r"^[0-9]+(?:_info)?\.csv$"
TEAM_ALIASES = {
    "Delhi Daredevils": "Delhi Capitals",
    "Kings XI Punjab": "Punjab Kings",
    "Royal Challengers Bangalore": "Royal Challengers Bengaluru",
    "Rising Pune Supergiants": "Rising Pune Supergiant",
}
SAMPLE_THRESHOLDS = {
    "all_seasons": 60,
    "single_season": 30,
}
DEATH_OVER_RANGE = (16, 20)

DELIVERY_REQUIRED_COLUMNS = (
    "match_id",
    "season",
    "start_date",
    "venue",
    "innings",
    "ball",
    "batting_team",
    "bowling_team",
    "striker",
    "bowler",
    "runs_off_bat",
    "extras",
    "wides",
    "noballs",
    "byes",
    "legbyes",
    "penalty",
    "non_boundary",
)
MATCH_COLUMNS = (
    "match_id",
    "season_year",
    "source_season",
    "date",
    "venue",
    "team1",
    "team2",
    "toss_winner",
    "winner",
    "outcome",
    "result_status",
    "super_over_winner",
)
