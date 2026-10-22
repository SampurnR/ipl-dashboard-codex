import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scripts.metrics import (
    build_grain_tables,
    rank_batters,
    rank_bowlers,
    rank_death_bowlers,
    run_rate_by_season,
    team_records,
    write_grain_tables,
)


class MetricsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def delivery(
        *, season_year=2020, batting_team="Bat A", bowling_team="Bowl A",
        striker="Alpha", bowler="Bowler A", runs_off_bat=0, extras=0,
        wides=0, noballs=0, byes=0, legbyes=0, penalty=0,
        over_number=1, innings=1, non_boundary=False, match_id="m1",
    ):
        return {
            "match_id": match_id,
            "season_year": season_year,
            "batting_team": batting_team,
            "bowling_team": bowling_team,
            "striker": striker,
            "bowler": bowler,
            "runs_off_bat": runs_off_bat,
            "extras": extras,
            "wides": wides,
            "noballs": noballs,
            "byes": byes,
            "legbyes": legbyes,
            "penalty": penalty,
            "over_number": over_number,
            "innings": innings,
            "non_boundary": non_boundary,
            "legal_ball": wides == 0 and noballs == 0,
            "is_super_over": innings > 2,
            "team_runs": runs_off_bat + extras,
            "bowler_runs": runs_off_bat + wides + noballs,
        }

    def write_grains(self, tables):
        write_grain_tables(tables, self.data_dir)

    def write_table(self, name, rows):
        pd.DataFrame(rows).to_csv(self.data_dir / f"{name}.csv", index=False)

    def test_grain_formulas_exclusions_and_scope_rates(self):
        rows = [
            self.delivery(runs_off_bat=4),
            self.delivery(runs_off_bat=0, extras=2, wides=2),  # wide: runs, no legal ball, not faced
            self.delivery(runs_off_bat=1, extras=1, noballs=1),  # no-ball: runs, no legal ball, faced
            self.delivery(runs_off_bat=0, extras=2, byes=2),  # team runs, not bowler runs
            self.delivery(runs_off_bat=4, non_boundary=True),
            self.delivery(runs_off_bat=6),
            self.delivery(runs_off_bat=0),
            self.delivery(striker="Zero", runs_off_bat=0),
            self.delivery(runs_off_bat=2, over_number=15),
            self.delivery(runs_off_bat=3, over_number=16),
            self.delivery(runs_off_bat=1, over_number=20),
            self.delivery(runs_off_bat=6, over_number=21),
            self.delivery(runs_off_bat=99, over_number=18, innings=3),  # excluded super over
        ]
        # Add legal dots to reach the single-season sample boundaries without changing runs.
        rows.extend(self.delivery() for _ in range(20))
        rows.extend(self.delivery(over_number=16) for _ in range(28))
        rows.extend(self.delivery(striker="Zero") for _ in range(30))
        deliveries = pd.DataFrame(rows)
        matches = pd.DataFrame([{
            "match_id": "m1", "season_year": 2020, "team1": "Bat A", "team2": "Bowl A",
            "winner": "", "result_status": "no_result", "super_over_winner": "",
        }])

        tables = build_grain_tables(deliveries, matches)
        self.write_grains(tables)

        team_row = tables["team_run_rate"].iloc[0]
        bowler_row = tables["bowler_economy"].iloc[0]
        batter_row = tables["batter_boundary"].query("batter == 'Alpha'").iloc[0]
        death_row = tables["death_over_economy"].iloc[0]

        self.assertEqual((team_row["runs"], team_row["legal_balls"]), (32, 88))
        self.assertEqual((bowler_row["runs_conceded"], bowler_row["legal_balls"]), (30, 88))
        self.assertEqual(
            (batter_row["batter_runs"], batter_row["boundary_runs"], batter_row["balls_faced"]),
            (27, 16, 58),
        )
        self.assertEqual((death_row["runs_conceded"], death_row["legal_balls"]), (4, 30))
        zero_row = tables["batter_boundary"].query("batter == 'Zero'").iloc[0]
        self.assertEqual((zero_row["batter_runs"], zero_row["balls_faced"]), (0, 31))

        run_rate = run_rate_by_season(data_dir=self.data_dir)
        self.assertEqual(run_rate.iloc[0]["run_rate"], 2.18)  # 32 / 88 * 6, includes no-result match
        economy = rank_bowlers(2020, "Bowl A", data_dir=self.data_dir)
        self.assertEqual(economy.iloc[0]["economy"], 2.05)  # 30 / 88 * 6
        boundary = rank_batters(2020, "Bat A", data_dir=self.data_dir)
        self.assertEqual(boundary.iloc[0]["boundary_percentage"], 59.26)  # 16 / 27 * 100
        self.assertNotIn("Zero", set(boundary["batter"]))
        death = rank_death_bowlers(2020, "Bowl A", data_dir=self.data_dir)
        self.assertEqual(death.iloc[0]["economy"], 0.8)  # (over 16 + 20 only): 4 / 30 * 6

    def test_team_records_keep_ties_and_no_results_separate(self):
        deliveries = pd.DataFrame([self.delivery()])
        matches = pd.DataFrame([
            {"match_id": "normal", "season_year": 2020, "team1": "Alpha XI", "team2": "Beta XI",
             "winner": "Alpha XI", "result_status": "normal", "super_over_winner": ""},
            {"match_id": "tie", "season_year": 2020, "team1": "Alpha XI", "team2": "Gamma XI",
             "winner": "", "result_status": "tie", "super_over_winner": "Gamma XI"},
            {"match_id": "abandoned", "season_year": 2020, "team1": "Alpha XI", "team2": "Beta XI",
             "winner": "", "result_status": "no_result", "super_over_winner": ""},
        ])
        tables = build_grain_tables(deliveries, matches)
        records = tables["team_records"].set_index("team")
        self.assertEqual(records.loc["Alpha XI", ["played", "wins", "losses", "ties", "no_results"]].tolist(), [3, 1, 0, 1, 1])
        self.assertEqual(records.loc["Beta XI", ["played", "wins", "losses", "ties", "no_results"]].tolist(), [2, 0, 1, 0, 1])
        self.assertEqual(records.loc["Gamma XI", ["played", "wins", "losses", "ties", "no_results"]].tolist(), [1, 0, 0, 1, 0])
        self.write_grains(tables)
        scoped = team_records(2020, None, data_dir=self.data_dir).set_index("team")
        self.assertEqual(scoped.loc["Gamma XI", "ties"], 1)

    def test_threshold_boundaries_for_all_and_single_season(self):
        bowler_rows = [
            {"season_year": 2015, "team": "Bowl A", "bowler": "Exact all", "runs_conceded": 30, "legal_balls": 30},
            {"season_year": 2016, "team": "Bowl B", "bowler": "Exact all", "runs_conceded": 30, "legal_balls": 30},
            {"season_year": 2015, "team": "Bowl A", "bowler": "Below all", "runs_conceded": 30, "legal_balls": 30},
            {"season_year": 2016, "team": "Bowl B", "bowler": "Below all", "runs_conceded": 29, "legal_balls": 29},
            {"season_year": 2024, "team": "Bowl C", "bowler": "Exact season", "runs_conceded": 15, "legal_balls": 30},
            {"season_year": 2024, "team": "Bowl C", "bowler": "Below season", "runs_conceded": 15, "legal_balls": 29},
        ]
        batter_rows = [
            {"season_year": 2015, "team": "Bat A", "batter": "Exact all", "batter_runs": 30, "boundary_runs": 12, "balls_faced": 30},
            {"season_year": 2016, "team": "Bat B", "batter": "Exact all", "batter_runs": 30, "boundary_runs": 12, "balls_faced": 30},
            {"season_year": 2015, "team": "Bat A", "batter": "Below all", "batter_runs": 30, "boundary_runs": 12, "balls_faced": 30},
            {"season_year": 2016, "team": "Bat B", "batter": "Below all", "batter_runs": 29, "boundary_runs": 12, "balls_faced": 29},
            {"season_year": 2024, "team": "Bat C", "batter": "Exact season", "batter_runs": 20, "boundary_runs": 8, "balls_faced": 30},
            {"season_year": 2024, "team": "Bat C", "batter": "Below season", "batter_runs": 20, "boundary_runs": 8, "balls_faced": 29},
        ]
        death_rows = [
            {"season_year": 2015, "team": "Bowl A", "bowler": "Exact all", "runs_conceded": 30, "legal_balls": 30},
            {"season_year": 2016, "team": "Bowl B", "bowler": "Exact all", "runs_conceded": 30, "legal_balls": 30},
            {"season_year": 2015, "team": "Bowl A", "bowler": "Below all", "runs_conceded": 30, "legal_balls": 30},
            {"season_year": 2016, "team": "Bowl B", "bowler": "Below all", "runs_conceded": 29, "legal_balls": 29},
            {"season_year": 2024, "team": "Bowl C", "bowler": "Exact season", "runs_conceded": 15, "legal_balls": 30},
            {"season_year": 2024, "team": "Bowl C", "bowler": "Below season", "runs_conceded": 15, "legal_balls": 29},
        ]
        self.write_table("bowler_economy", bowler_rows)
        self.write_table("batter_boundary", batter_rows)
        self.write_table("death_over_economy", death_rows)

        self.assertEqual(set(rank_bowlers(None, None, data_dir=self.data_dir)["bowler"]), {"Exact all"})
        self.assertEqual(set(rank_bowlers(2024, None, data_dir=self.data_dir)["bowler"]), {"Exact season"})
        self.assertEqual(set(rank_batters(None, None, data_dir=self.data_dir)["batter"]), {"Exact all"})
        self.assertEqual(set(rank_batters(2024, None, data_dir=self.data_dir)["batter"]), {"Exact season"})
        self.assertEqual(set(rank_death_bowlers(None, None, data_dir=self.data_dir)["bowler"]), {"Exact all"})
        self.assertEqual(set(rank_death_bowlers(2024, None, data_dir=self.data_dir)["bowler"]), {"Exact season"})

    def test_team_filters_and_all_teams_sum_players_across_teams(self):
        bowler_rows = [
            {"season_year": 2016, "team": "Bowl One", "bowler": "Shared", "runs_conceded": 60, "legal_balls": 30},
            {"season_year": 2016, "team": "Bowl Two", "bowler": "Shared", "runs_conceded": 120, "legal_balls": 30},
            {"season_year": 2016, "team": "Bowl One", "bowler": "Only One", "runs_conceded": 30, "legal_balls": 30},
        ]
        batter_rows = [
            {"season_year": 2016, "team": "Bat One", "batter": "Shared", "batter_runs": 10, "boundary_runs": 4, "balls_faced": 30},
            {"season_year": 2016, "team": "Bat Two", "batter": "Shared", "batter_runs": 20, "boundary_runs": 12, "balls_faced": 30},
        ]
        self.write_table("bowler_economy", bowler_rows)
        self.write_table("batter_boundary", batter_rows)

        bowler_one = rank_bowlers(2016, "Bowl One", data_dir=self.data_dir).set_index("bowler")
        self.assertEqual(set(bowler_one.index), {"Shared", "Only One"})
        self.assertEqual(bowler_one.loc["Shared", "economy"], 12.0)
        all_bowling_teams = rank_bowlers(2016, None, data_dir=self.data_dir).set_index("bowler")
        self.assertEqual(all_bowling_teams.loc["Shared", "legal_balls"], 60)
        self.assertEqual(all_bowling_teams.loc["Shared", "economy"], 18.0)

        batter_two = rank_batters(2016, "Bat Two", data_dir=self.data_dir).set_index("batter")
        self.assertEqual(set(batter_two.index), {"Shared"})
        self.assertEqual(batter_two.loc["Shared", "boundary_percentage"], 60.0)
        all_batting_teams = rank_batters(2016, None, data_dir=self.data_dir).set_index("batter")
        self.assertEqual(all_batting_teams.loc["Shared", "batter_runs"], 30)
        self.assertEqual(all_batting_teams.loc["Shared", "boundary_percentage"], 53.33)

    def test_ranking_sort_ties_use_more_balls_then_name_and_empty_is_valid(self):
        self.write_table("bowler_economy", [
            {"season_year": 2016, "team": "Bowl", "bowler": "Adam", "runs_conceded": 18, "legal_balls": 60},
            {"season_year": 2016, "team": "Bowl", "bowler": "Aaron", "runs_conceded": 18, "legal_balls": 60},
            {"season_year": 2016, "team": "Bowl", "bowler": "Zed", "runs_conceded": 27, "legal_balls": 90},
            {"season_year": 2016, "team": "Bowl", "bowler": "Below cutoff", "runs_conceded": 9, "legal_balls": 29},
        ])
        self.write_table("batter_boundary", [
            {"season_year": 2016, "team": "Bat", "batter": "Zed", "batter_runs": 20, "boundary_runs": 10, "balls_faced": 60},
            {"season_year": 2016, "team": "Bat", "batter": "Bea", "batter_runs": 30, "boundary_runs": 15, "balls_faced": 90},
            {"season_year": 2016, "team": "Bat", "batter": "Ava", "batter_runs": 30, "boundary_runs": 15, "balls_faced": 90},
            {"season_year": 2016, "team": "Bat", "batter": "High", "batter_runs": 10, "boundary_runs": 8, "balls_faced": 30},
        ])

        bowlers = rank_bowlers(2016, "Bowl", top=4, data_dir=self.data_dir)
        self.assertEqual(list(bowlers["bowler"]), ["Zed", "Aaron", "Adam"])
        batters = rank_batters(2016, "Bat", top=4, data_dir=self.data_dir)
        self.assertEqual(list(batters["batter"]), ["High", "Ava", "Bea", "Zed"])
        self.assertTrue(rank_bowlers(2030, None, data_dir=self.data_dir).empty)


if __name__ == "__main__":
    unittest.main()
