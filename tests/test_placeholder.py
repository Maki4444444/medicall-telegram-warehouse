"""
test_placeholder.py
Baseline sanity tests so CI has something to run from the very first
commit. Replace/extend with real unit tests as each task branch adds
testable logic (e.g. datalake path helpers, dbt model logic via
dbt-unit-testing, Pydantic schema validation).
"""

import sys
from pathlib import Path

# Ensure project root is importable when pytest runs from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_project_root_importable():
    """Sanity check that the test runner can resolve the repo root."""
    root = Path(__file__).resolve().parent.parent
    assert root.exists()


def test_src_package_importable():
    """src/ must be a valid Python package once task-1 lands scraper code."""
    import src  # noqa: F401
    assert True