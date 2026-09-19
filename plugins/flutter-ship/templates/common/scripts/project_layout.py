#!/usr/bin/env python3
"""Where this project's Dart and Python packages live.

Single source of truth for the repo layout. `ci_change_classifier.py`,
`complexity_sensor.py`, `pre-commit`, and `run_integration_tests.sh` all ask
here instead of hardcoding `lib/` and `backend/`, so moving the Flutter app
into `app/` or renaming `backend/` to `api/` is a one-file change.

Defaults match `/setup-project`: the Flutter app owns the repo root, the
FastAPI service lives in `backend/`.

Override without editing this file, highest precedence first:

  1. Environment — FLUTTER_SHIP_DART_PACKAGES / FLUTTER_SHIP_PYTHON_PACKAGES,
     space-separated. The older COMPLEXITY_DART_PACKAGES /
     COMPLEXITY_PYTHON_ROOT still work.
  2. `.flutter-ship.json` at the repo root:

        {"dart_packages": ["app"], "python_packages": ["api"]}

Stdlib only, importable from any cwd.

Usage:
  project_layout.py --dart-packages       # one per line
  project_layout.py --python-dir          # the primary Python package
  project_layout.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / ".flutter-ship.json"

DEFAULT_DART_PACKAGES = (".",)
DEFAULT_PYTHON_PACKAGES = ("backend",)

# Conventional sub-paths inside a package. The layout says where they are;
# consumers decide what they mean (which CI flags they set, and so on).
DART_SOURCE_DIRS = ("lib", "ios", "android")
DART_TEST_DIR = "test"
DART_INTEGRATION_DIR = "integration_test"
DART_MANIFESTS = ("pubspec.yaml", "pubspec.lock")
DART_LINT_CONFIG = ("analysis_options.yaml",)
PYTHON_TEST_DIR = "tests"


def posix(path: str) -> str:
    """Normalise a repo-relative path: forward slashes, no leading `./`."""
    normalised = str(path).replace("\\", "/")
    while normalised.startswith("./"):
        normalised = normalised[2:]
    return normalised.rstrip("/")


def under(path: str, prefix: str) -> bool:
    """True if `path` is `prefix` itself or sits beneath it."""
    if prefix in (".", ""):
        return True
    return path == prefix or path.startswith(prefix + "/")


def join(package: str, *parts: str) -> str:
    """Repo-relative path inside `package`; `.` means the repo root."""
    segments = [p for p in (package, *parts) if p and p != "."]
    return "/".join(segments) if segments else "."


def _from_env(*names: str) -> list[str] | None:
    for name in names:
        raw = os.environ.get(name, "")
        packages = [posix(p) for p in raw.split() if p.strip()]
        if packages:
            return packages
    return None


def _from_config(key: str) -> list[str] | None:
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = data.get(key) if isinstance(data, dict) else None
    if isinstance(value, str):
        value = [value]
    if isinstance(value, list):
        packages = [posix(str(v)) for v in value if str(v).strip()]
        if packages:
            return packages
    return None


def dart_packages() -> list[str]:
    """Dart/Flutter package roots, repo-relative. `.` means the repo root."""
    return (
        _from_env("FLUTTER_SHIP_DART_PACKAGES", "COMPLEXITY_DART_PACKAGES")
        or _from_config("dart_packages")
        or list(DEFAULT_DART_PACKAGES)
    )


def python_packages() -> list[str]:
    """Python package roots, repo-relative."""
    return (
        _from_env("FLUTTER_SHIP_PYTHON_PACKAGES", "COMPLEXITY_PYTHON_ROOT")
        or _from_config("python_packages")
        or list(DEFAULT_PYTHON_PACKAGES)
    )


def dart_dir() -> str:
    """The primary Flutter app — what `run_integration_tests.sh` drives."""
    return dart_packages()[0]


def python_dir() -> str:
    """The primary Python service — what CI lints and tests."""
    return python_packages()[0]


def lang_for_path(relpath: str) -> str:
    """Which toolchain owns a repo-relative path: `python` or `dart`."""
    path = posix(relpath)
    if path.endswith(".py"):
        return "python"
    if any(under(path, pkg) for pkg in python_packages()):
        return "python"
    return "dart"


def as_dict() -> dict:
    return {
        "dart_packages": dart_packages(),
        "python_packages": python_packages(),
        "dart_dir": dart_dir(),
        "python_dir": python_dir(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dart-packages", action="store_true")
    group.add_argument("--python-packages", action="store_true")
    group.add_argument("--dart-dir", action="store_true")
    group.add_argument("--python-dir", action="store_true")
    group.add_argument("--json", action="store_true")
    group.add_argument("--github-output", metavar="PATH")
    args = parser.parse_args(argv)

    if args.dart_packages:
        print("\n".join(dart_packages()))
    elif args.python_packages:
        print("\n".join(python_packages()))
    elif args.dart_dir:
        print(dart_dir())
    elif args.python_dir:
        print(python_dir())
    elif args.github_output:
        text = f"dart_dir={dart_dir()}\npython_dir={python_dir()}\n"
        if args.github_output == "-":
            sys.stdout.write(text)
        else:
            with open(args.github_output, "a", encoding="utf-8") as fh:
                fh.write(text)
    else:
        print(json.dumps(as_dict(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
