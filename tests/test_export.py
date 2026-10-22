import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from scripts import config
from scripts.export import export_metrics


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.clean_dir = self.root / "data" / "clean"
        self.site_data_dir = self.root / "site" / "data"
        self.clean_dir.mkdir(parents=True)
        self.site_data_dir.mkdir(parents=True)
        self.output_path = self.site_data_dir / "ipl_metrics.json"
        self.write_fixtures()

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_csv(self, name, rows):
        pd.DataFrame(rows).to_csv(self.clean_dir / name, index=False)

    def write_fixtures(self):
        self.write_csv("deliveries.csv", [
            {"match_id": "101", "season_year": 2020, "batting_team": "Team Alpha", "bowling_team": "Team Beta",
             "innings": 1, "team_runs": 4, "legal_ball": True, "is_super_over": False},
            {"match_id": "101", "season_year": 2020, "batting_team": "Team Beta", "bowling_team": "Team Alpha",
             "innings": 2, "team_runs": 6, "legal_ball": True, "is_super_over": False},
            {"match_id": "101", "season_year": 2020, "batting_team": "Team Alpha", "bowling_team": "Team Beta",
             "innings": 3, "team_runs": 10, "legal_ball": True, "is_super_over": True},
            {"match_id": "102", "season_year": 2021, "batting_team": "Team Beta", "bowling_team": "Team Gamma",
             "innings": 1, "team_runs": 3, "legal_ball": True, "is_super_over": False},
        ])
        self.write_csv("matches.csv", [
            {"match_id": "101", "season_year": 2020, "date": "2020-04-01", "team1": "Team Alpha",
             "team2": "Team Beta", "winner": "Team Alpha", "result_status": "normal", "super_over_winner": ""},
            {"match_id": "102", "season_year": 2021, "date": "2021-04-01", "team1": "Team Beta",
             "team2": "Team Gamma", "winner": "Team Beta", "result_status": "normal", "super_over_winner": ""},
        ])
        self.write_csv("team_run_rate.csv", [
            {"season_year": 2020, "team": "Team Alpha", "runs": 120, "legal_balls": 60},
            {"season_year": 2020, "team": "Team Beta", "runs": 60, "legal_balls": 30},
            {"season_year": 2021, "team": "Team Beta", "runs": 120, "legal_balls": 60},
            {"season_year": 2021, "team": "Team Gamma", "runs": 60, "legal_balls": 30},
        ])
        self.write_csv("bowler_economy.csv", [
            {"season_year": 2020, "team": "Team Beta", "bowler": "Qual Bowler", "runs_conceded": 30, "legal_balls": 30},
            {"season_year": 2020, "team": "Team Beta", "bowler": "Below Bowler", "runs_conceded": 29, "legal_balls": 29},
            {"season_year": 2021, "team": "Team Gamma", "bowler": "Qual Bowler", "runs_conceded": 60, "legal_balls": 30},
        ])
        self.write_csv("batter_boundary.csv", [
            {"season_year": 2020, "team": "Team Beta", "batter": "Qual Batter", "batter_runs": 30, "boundary_runs": 15, "balls_faced": 30},
            {"season_year": 2020, "team": "Team Alpha", "batter": "Below Batter", "batter_runs": 29, "boundary_runs": 12, "balls_faced": 29},
            {"season_year": 2021, "team": "Team Gamma", "batter": "Qual Batter", "batter_runs": 40, "boundary_runs": 20, "balls_faced": 30},
        ])
        self.write_csv("death_over_economy.csv", [
            {"season_year": 2020, "team": "Team Beta", "bowler": "Qual Bowler", "runs_conceded": 30, "legal_balls": 30},
            {"season_year": 2021, "team": "Team Gamma", "bowler": "Qual Bowler", "runs_conceded": 60, "legal_balls": 30},
        ])
        self.write_csv("team_records.csv", [
            {"season_year": 2020, "team": "Team Alpha", "played": 1, "wins": 1, "losses": 0, "ties": 0, "no_results": 0},
            {"season_year": 2020, "team": "Team Beta", "played": 1, "wins": 0, "losses": 1, "ties": 0, "no_results": 0},
            {"season_year": 2021, "team": "Team Beta", "played": 1, "wins": 1, "losses": 0, "ties": 0, "no_results": 0},
            {"season_year": 2021, "team": "Team Gamma", "played": 1, "wins": 0, "losses": 1, "ties": 0, "no_results": 0},
        ])

    def export(self):
        return export_metrics(clean_dir=self.clean_dir, output_path=self.output_path)

    def read_json(self):
        def reject_constant(value):
            raise ValueError(f"invalid JSON constant: {value}")
        return json.loads(self.output_path.read_text(encoding="utf-8"), parse_constant=reject_constant)

    def test_json_schema_types_scopes_and_config_thresholds(self):
        self.export()
        payload = self.read_json()
        self.assertEqual(set(payload), {
            "schema_version", "data_through", "match_count", "delivery_count",
            "super_over_rows_excluded", "thresholds", "definitions", "seasons",
            "teams", "teams_by_season", "run_rate_by_season", "scopes",
        })
        self.assertIs(type(payload["schema_version"]), int)
        self.assertEqual(payload["schema_version"], 1)
        self.assertIs(type(payload["data_through"]), str)
        self.assertIs(type(payload["match_count"]), int)
        self.assertIs(type(payload["delivery_count"]), int)
        self.assertIs(type(payload["super_over_rows_excluded"]), int)
        self.assertEqual(payload["thresholds"], config.SAMPLE_THRESHOLDS)
        self.assertTrue(all(isinstance(value, str) for value in payload["definitions"].values()))
        self.assertEqual(payload["seasons"], [2020, 2021])
        self.assertEqual(payload["teams"], ["Team Alpha", "Team Beta", "Team Gamma"])
        self.assertEqual(payload["teams_by_season"], {
            "2020": ["Team Alpha", "Team Beta"],
            "2021": ["Team Beta", "Team Gamma"],
        })
        self.assertEqual(payload["match_count"], 2)
        self.assertEqual(payload["delivery_count"], 4)
        self.assertEqual(payload["super_over_rows_excluded"], 1)

        self.assertIn("All", payload["run_rate_by_season"])
        self.assertIn("Team Alpha", payload["run_rate_by_season"])
        self.assertIn("All", payload["scopes"])
        self.assertIn("All", payload["scopes"]["All"])
        self.assertEqual(payload["scopes"]["2020"]["Team Alpha"]["bowlers"], [])
        self.assertNotIn("Team Gamma", payload["scopes"]["2020"])
        self.assertNotIn("Team Alpha", payload["scopes"]["2021"])
        self.assertIn("bowlers", payload["scopes"]["2020"]["Team Beta"])
        self.assertIn("records", payload["scopes"]["All"]["All"])

    def test_two_exports_are_byte_identical_and_contain_no_non_finite_constants(self):
        self.export()
        first = self.output_path.read_bytes()
        self.export()
        second = self.output_path.read_bytes()
        self.assertEqual(first, second)
        self.read_json()

    def test_export_reads_clean_and_writes_only_to_site_data(self):
        before = {path.resolve() for path in self.root.rglob("*") if path.is_file()}
        read_paths = []
        original_read_csv = pd.read_csv

        def tracked_read_csv(path, *args, **kwargs):
            read_paths.append(Path(path).resolve())
            return original_read_csv(path, *args, **kwargs)

        with patch("pandas.read_csv", side_effect=tracked_read_csv):
            self.export()

        after = {path.resolve() for path in self.root.rglob("*") if path.is_file()}
        self.assertTrue(read_paths)
        self.assertTrue(all(path.is_relative_to(self.clean_dir.resolve()) for path in read_paths))
        self.assertEqual(after - before, {self.output_path.resolve()})
        self.assertTrue(self.output_path.resolve().is_relative_to(self.site_data_dir.resolve()))


if __name__ == "__main__":
    unittest.main()
