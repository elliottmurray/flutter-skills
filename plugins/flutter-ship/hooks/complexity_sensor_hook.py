#!/usr/bin/env python3
"""PostToolUse hook: warn when an edit leaves a function over its complexity ceiling.

Looks for the project's `scripts/complexity_sensor.py` (copied by
`/setup-project`). Advisory only: always exits 0. Quiet when the sensor,
toolchain, or file type is missing.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
SENSOR = PROJECT_DIR / "scripts" / "complexity_sensor.py"


def analyze(file_path: str) -> list[dict]:
    suffix = Path(file_path).suffix
    if suffix not in {".py", ".dart"}:
        return []
    if not SENSOR.is_file():
        return []
    env = dict(os.environ)
    backend = PROJECT_DIR / "backend"
    if suffix == ".py" and (backend / "pyproject.toml").is_file():
        env.setdefault("COMPLEXITY_RADON_CMD", "uv run radon")
    try:
        proc = subprocess.run(
            [sys.executable, str(SENSOR), "--file", file_path, "--json"],
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True,
            timeout=12,
            env=env,
        )
        payload = json.loads(proc.stdout.strip() or "{}")
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return []
    over = payload.get("over")
    return over if isinstance(over, list) else []


def reminder(file_path: str, over: list[dict]) -> str:
    lines = "\n".join(
        f"  - {o.get('qualname')} (line {o.get('lineno')}): complexity "
        f"{o.get('complexity')}, ceiling {o.get('ceiling')}"
        for o in over
    )
    return (
        f"Complexity sensor: your edit to {file_path} leaves {len(over)} "
        f"function(s) over their cyclomatic-complexity ceiling:\n{lines}\n"
        "Simplify (extract helpers, flatten nesting, table-drive branches) "
        "before finishing. If the complexity is essential, leave it and later "
        "run `python3 scripts/complexity_sensor.py --update-baseline` — the "
        "baseline can only be lowered, so prefer refactoring first."
    )


def main(argv: list[str] | None = None) -> int:
    del argv  # hooks read stdin, not argv
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    file_path = (event.get("tool_input") or {}).get("file_path") or ""
    over = analyze(file_path)
    if not over:
        return 0

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": reminder(file_path, over),
            }
        },
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
