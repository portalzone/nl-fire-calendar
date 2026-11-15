"""Shared setup: lets the tests import the pipeline scripts, and stops tests from
passing quietly when the app data has not been built."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))

APP_DATA = ROOT / "app" / "data"
NEEDED_FILES = ("summary.json", "hotspots_clean.csv", "monthly_harmonized.csv",
                "monthly_baseline.csv", "validation.png", "co_monthly.json")
BUILD_HINT = "run python pipeline/build_harmonized.py and python pipeline/build_co.py"


def missing_app_data(folder=APP_DATA):
    """Return the names of the app data files that are missing from folder."""
    return [f for f in NEEDED_FILES if not (Path(folder) / f).exists()]


def require_app_data(folder=APP_DATA):
    """Fail (never skip) with a clear message when the app data files are missing."""
    missing = missing_app_data(folder)
    if missing:
        pytest.fail(f"app/data is missing {', '.join(missing)}: {BUILD_HINT}", pytrace=False)
