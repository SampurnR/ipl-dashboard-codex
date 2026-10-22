import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scripts.clean import clean_data


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "clean"


class CleanPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name) / "clean"

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_clean(self, source_dir=FIXTURES):
        return clean_data(source_dir=source_dir, output_dir=self.output_dir)

    def tables(self):
        deliveries = pd.read_csv(self.output_dir / "deliveries.csv", dtype={"ball": str})
        matches = pd.read_csv(self.output_dir / "matches.csv", keep_default_na=False)
        return deliveries, matches

    def test_delivery_cleaning_aliases_extras_ball_labels_and_super_overs(self):
        self.run_clean()
        deliveries, _ = self.tables()

        # The all_matches.csv decoy contains match 9999 and must not be ingested.
        self.assertNotIn(9999, set(deliveries["match_id"]))
        self.assertEqual(len(deliveries), 12)
        self.assertEqual(set(deliveries["batting_team"]), {
            "Delhi Capitals", "Royal Challengers Bengaluru", "Rising Pune Supergiant",
            "Deccan Chargers", "Sunrisers Hyderabad",
        })
        self.assertEqual(set(deliveries["bowling_team"]), {
            "Punjab Kings", "Rising Pune Supergiant", "Sunrisers Hyderabad",
            "Deccan Chargers", "Royal Challengers Bengaluru",
        })

        first_match = deliveries[deliveries["match_id"] == 101].set_index("ball")
        self.assertEqual(first_match.loc["0.1", "extras"], 0)
        self.assertEqual(first_match.loc["0.1", "team_runs"], 4)
        self.assertEqual(first_match.loc["0.2", "legal_ball"], False)  # wide
        self.assertEqual(first_match.loc["0.3", "legal_ball"], False)  # no-ball
        self.assertEqual(first_match.loc["0.4", "legal_ball"], True)   # bye
        self.assertEqual(first_match.loc["0.5", "legal_ball"], True)   # leg bye
        self.assertEqual(first_match.loc["0.6", "bowler_runs"], 4)
        self.assertEqual(first_match.loc["0.6", "team_runs"], 13)
        self.assertEqual(first_match.loc["0.6", "extras"], 11)
        self.assertEqual(first_match.loc["0.1", "over_number"], 1)
        self.assertEqual(first_match.loc["15.3", "over_number"], 16)
        self.assertEqual(first_match.loc["19.6", "over_number"], 20)
        self.assertEqual(first_match.loc["19.6", "non_boundary"], False)
        self.assertEqual(first_match.loc["0.1", "non_boundary"], True)

        super_over = deliveries[(deliveries["match_id"] == 102) & (deliveries["innings"] == 3)]
        self.assertEqual(len(super_over), 1)
        self.assertTrue(bool(super_over.iloc[0]["is_super_over"]))
        self.assertEqual(bool(super_over.iloc[0]["legal_ball"]), True)
        self.assertFalse(bool(deliveries.loc[deliveries["match_id"] == 102, "is_super_over"].iloc[0]))

    def test_source_season_and_year_derived_from_start_date(self):
        self.run_clean()
        deliveries, matches = self.tables()
        expected = {101: ("2007/08", 2008), 102: ("2009/10", 2010), 103: ("2020/21", 2020)}
        for match_id, (source_season, season_year) in expected.items():
            rows = deliveries[deliveries["match_id"] == match_id]
            self.assertEqual(set(rows["source_season"]), {source_season})
            self.assertEqual(set(rows["season_year"]), {season_year})
            match = matches[matches["match_id"] == match_id].iloc[0]
            self.assertEqual(match["source_season"], source_season)
            self.assertEqual(match["season_year"], season_year)

    def test_match_metadata_repeated_info_keys_and_result_status(self):
        self.run_clean()
        _, matches = self.tables()
        self.assertEqual(list(matches.columns), [
            "match_id", "season_year", "source_season", "date", "venue", "team1",
            "team2", "toss_winner", "winner", "outcome", "result_status",
            "super_over_winner",
        ])
        by_id = matches.set_index("match_id")

        self.assertEqual(by_id.loc[101, "team1"], "Delhi Capitals")
        self.assertEqual(by_id.loc[101, "team2"], "Punjab Kings")
        self.assertEqual(by_id.loc[101, "date"], "2008-04-18")
        self.assertEqual(by_id.loc[101, "venue"], "Test Ground")
        self.assertEqual(by_id.loc[101, "toss_winner"], "Delhi Capitals")
        self.assertEqual(by_id.loc[101, "winner"], "Punjab Kings")
        self.assertEqual(by_id.loc[101, "result_status"], "normal")
        self.assertEqual(by_id.loc[101, "super_over_winner"], "")

        self.assertEqual(by_id.loc[102, "team1"], "Royal Challengers Bengaluru")
        self.assertEqual(by_id.loc[102, "team2"], "Rising Pune Supergiant")
        self.assertEqual(by_id.loc[102, "toss_winner"], "Rising Pune Supergiant")
        self.assertEqual(by_id.loc[102, "outcome"], "tie")
        self.assertEqual(by_id.loc[102, "result_status"], "tie")
        self.assertEqual(by_id.loc[102, "super_over_winner"], "Royal Challengers Bengaluru")

        self.assertEqual(by_id.loc[103, "team1"], "Deccan Chargers")
        self.assertEqual(by_id.loc[103, "team2"], "Sunrisers Hyderabad")
        self.assertEqual(by_id.loc[103, "result_status"], "no_result")
        self.assertEqual(by_id.loc[103, "winner"], "")
        self.assertEqual(by_id.loc[103, "super_over_winner"], "")
        self.assertEqual(set(matches["result_status"]), {"normal", "tie", "no_result"})

    def test_missing_required_column_fails_with_delivery_filename(self):
        with tempfile.TemporaryDirectory() as source:
            source_dir = Path(source)
            (source_dir / "501.csv").write_text(
                "match_id,season,start_date,innings,ball\n"
                "501,2024,2024-04-01,1,0.1\n",
                encoding="utf-8",
            )
            (source_dir / "501_info.csv").write_text(
                "info,dates,2024-04-01\ninfo,season,2024\ninfo,teams,A\ninfo,teams,B\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, r"501\.csv.*missing required column"):
                self.run_clean(source_dir=source_dir)

    def test_unparseable_date_fails_with_delivery_filename(self):
        with tempfile.TemporaryDirectory() as source:
            source_dir = Path(source)
            (source_dir / "502.csv").write_text(
                "match_id,season,start_date,venue,innings,ball,batting_team,bowling_team,"
                "striker,bowler,runs_off_bat,extras,wides,noballs,byes,legbyes,penalty,non_boundary\n"
                "502,2024,not-a-date,Ground,1,0.1,A,B,Batter,Bowler,0,,0,0,0,0,0,false\n",
                encoding="utf-8",
            )
            (source_dir / "502_info.csv").write_text(
                "info,dates,not-a-date\ninfo,season,2024\ninfo,teams,A\ninfo,teams,B\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, r"502\.csv.*unparseable date"):
                self.run_clean(source_dir=source_dir)


if __name__ == "__main__":
    unittest.main()
