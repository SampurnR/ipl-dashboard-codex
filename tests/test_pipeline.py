import tempfile
import unittest
from pathlib import Path

from scripts.run_pipeline import require_match_files, hash_raw_files, verify_raw_unchanged


class PipelineGuardTests(unittest.TestCase):
    def test_empty_raw_directory_points_to_download_script(self):
        with tempfile.TemporaryDirectory() as temporary:
            raw_dir = Path(temporary) / "data" / "raw"
            raw_dir.mkdir(parents=True)
            with self.assertRaisesRegex(FileNotFoundError, r"scripts/download_data\.py"):
                require_match_files(raw_dir)

    def test_raw_hash_guard_ignores_aggregate_and_detects_match_file_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            raw_dir = Path(temporary)
            match_file = raw_dir / "123.csv"
            aggregate = raw_dir / "all_matches.csv"
            match_file.write_text("match_id\n123\n", encoding="utf-8")
            aggregate.write_text("decoy\n", encoding="utf-8")

            before = hash_raw_files(raw_dir)
            self.assertIn("123.csv", before)
            self.assertNotIn("all_matches.csv", before)

            aggregate.write_text("changed but excluded\n", encoding="utf-8")
            verify_raw_unchanged(raw_dir, before)
            match_file.write_text("match_id\n456\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, r"data/raw.*changed"):
                verify_raw_unchanged(raw_dir, before)


if __name__ == "__main__":
    unittest.main()
