#!/usr/bin/env python3
"""Download and extract Cricsheet's IPL CSV2 per-match files.

The aggregate all_matches.csv is deliberately excluded. Existing match files
make the operation a no-op so a populated raw directory is never overwritten.
"""

import argparse
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from urllib.request import urlopen
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
DOWNLOAD_URL = "https://cricsheet.org/downloads/ipl_csv2.zip"
MATCH_FILE = re.compile(r"^[0-9]+(?:_info)?\.csv$")


def contains_match_files(directory):
    """Return whether the raw directory already has a numeric match CSV."""
    return directory.is_dir() and any(
        path.is_file()
        and path.suffix == ".csv"
        and path.stem.isdecimal()
        for path in directory.iterdir()
    )


def extract_archive(archive_path, destination):
    """Extract safe per-match CSVs and auxiliary files without overwriting."""
    destination.mkdir(parents=True, exist_ok=True)
    extracted = 0
    with ZipFile(archive_path) as archive:
        for member in archive.infolist():
            relative = PurePosixPath(member.filename)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"Unsafe path in Cricsheet archive: {member.filename}")
            if member.is_dir() or relative.name == "all_matches.csv":
                continue
            if relative.name.lower().endswith(".csv") and not MATCH_FILE.fullmatch(relative.name):
                continue

            target = destination.joinpath(*relative.parts)
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
            extracted += 1
    return extracted


def download_and_extract():
    if contains_match_files(RAW_DIR):
        print(f"No download: match files already exist in {RAW_DIR}.")
        return 0

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cricsheet-", dir=ROOT) as temporary_dir:
        archive_path = Path(temporary_dir) / "ipl_csv2.zip"
        with urlopen(DOWNLOAD_URL, timeout=60) as response, archive_path.open("wb") as archive:
            shutil.copyfileobj(response, archive)
        count = extract_archive(archive_path, RAW_DIR)
    print(f"Extracted {count} files into {RAW_DIR} from {DOWNLOAD_URL}.")
    print("Skipped all_matches.csv; the pipeline uses per-match files only.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    return download_and_extract()


if __name__ == "__main__":
    raise SystemExit(main())
