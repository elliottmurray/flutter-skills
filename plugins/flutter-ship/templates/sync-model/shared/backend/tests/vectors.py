"""Load test_vectors/<name>.json for pytest.

The format is documented in test_vectors/vectors.schema.json;
test/support/test_vectors.dart reads the same files. Not a test module —
pytest only collects test_*.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _find_up(relative: str) -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / relative
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"{relative} not found above {Path(__file__).parent}")


def load_vectors(name: str) -> list[pytest.param]:
    """One pytest.param per case, with the description as the test id."""
    data = json.loads(_find_up(f"test_vectors/{name}.json").read_text(encoding="utf-8"))
    params = []
    for case in data["cases"]:
        if not case["valid"] and "error_field" not in case:
            raise ValueError(f"invalid case needs error_field: {case['description']}")
        params.append(pytest.param(case, id=case["description"]))
    return params
