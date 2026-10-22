#!/usr/bin/env python3
"""Run the IPL clean, metrics, and export stages with a raw-data integrity check."""

import hashlib
from pathlib import Path
import re
import subprocess
import sys
import time

try:
    from . import config
except ImportError:  # Supports ``python scripts/run_pipeline.py``.
    import config


_MATCH_FILE = re.compile(r"^[0-9]+\.csv$")
_METRIC_OUTPUT = re.compile(r"^([a-z_]+\.csv): ([0-9]+) rows$")


def require_match_files(raw_dir):
    """Return numeric per-match delivery files or raise with the download hint."""
    raw_dir = Path(raw_dir)
    match_files = sorted(
        path for path in raw_dir.iterdir()
        if path.is_file() and _MATCH_FILE.fullmatch(path.name)
    ) if raw_dir.is_dir() else []
    if not match_files:
        raise FileNotFoundError(
            f"No per-match CSV files found in {raw_dir}; populate raw data with scripts/download_data.py first."
        )
    return match_files


def hash_raw_files(raw_dir):
    """Return relative-path SHA-256 hashes, excluding the prohibited aggregate CSV."""
    raw_dir = Path(raw_dir)
    hashes = {}
    if not raw_dir.is_dir():
        return hashes
    for path in sorted(raw_dir.rglob("*")):
        if not path.is_file() or path.name == "all_matches.csv":
            continue
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        hashes[path.relative_to(raw_dir).as_posix()] = digest.hexdigest()
    return hashes


def verify_raw_unchanged(raw_dir, before_hashes):
    """Raise if any hashed raw file was added, removed, or changed."""
    after_hashes = hash_raw_files(raw_dir)
    changed = sorted(
        path for path in set(before_hashes) | set(after_hashes)
        if before_hashes.get(path) != after_hashes.get(path)
    )
    if changed:
        sample = ", ".join(changed[:10])
        suffix = " …" if len(changed) > 10 else ""
        raise RuntimeError(f"data/raw changed during the pipeline: {sample}{suffix}")
    return True


def _run_stage(root, script_name):
    script_path = root / "scripts" / script_name
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(
            f"Stage {script_name} failed with exit code {result.returncode}"
            + (f": {detail}" if detail else "")
        )
    return result.stdout


def _clean_summary(stdout):
    values = {}
    for line in stdout.splitlines():
        key, separator, value = line.partition(":")
        if separator:
            values[key.strip()] = value.strip()
    return (
        f"clean: read {values.get('Match files read', '?')} match files; "
        f"wrote {values.get('Delivery rows written', '?')} deliveries and "
        f"{values.get('Matches written', '?')} matches"
    )


def _metrics_summary(stdout):
    values = []
    for line in stdout.splitlines():
        match = _METRIC_OUTPUT.fullmatch(line.strip())
        if match:
            values.append(f"{match.group(1)[:-4]}={match.group(2)}")
    return "metrics: wrote " + (", ".join(values) if values else "five grain tables")


def run_pipeline(project_root=config.PROJECT_ROOT):
    """Run all three stages, check raw hashes, then report outputs and runtime."""
    root = Path(project_root).resolve()
    raw_dir = root / "data" / "raw"
    require_match_files(raw_dir)
    before_hashes = hash_raw_files(raw_dir)
    start = time.perf_counter()

    try:
        clean_output = _run_stage(root, "clean.py")
        print(_clean_summary(clean_output))

        metrics_output = _run_stage(root, "metrics.py")
        print(_metrics_summary(metrics_output))

        _run_stage(root, "export.py")
        export_path = root / "site" / "data" / "ipl_metrics.json"
        print(f"export: wrote site/data/ipl_metrics.json ({export_path.stat().st_size} bytes)")
    finally:
        verify_raw_unchanged(raw_dir, before_hashes)

    output_paths = [
        root / "data" / "clean" / name
        for name in (
            "deliveries.csv", "matches.csv", "team_run_rate.csv", "bowler_economy.csv",
            "batter_boundary.csv", "death_over_economy.csv", "team_records.csv",
        )
    ] + [root / "site" / "data" / "ipl_metrics.json"]
    print("Output file sizes:")
    for path in output_paths:
        print(f"  {path.relative_to(root).as_posix()}: {path.stat().st_size} bytes")
    print(f"Raw data hashes unchanged: {len(before_hashes)} files checked (all_matches.csv excluded)")
    print(f"Pipeline runtime: {time.perf_counter() - start:.2f} seconds")
    return output_paths[-1]


def main():
    try:
        run_pipeline()
    except Exception as error:
        print(f"Pipeline failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
