#!/usr/bin/env python3
"""Map a changed-file list to which CI jobs should run.

Stdlib only. Fail closed: an unrecognised path under a service tree runs that
service's full suite; an unrecognised path under `.github/` runs every job.
Documentation and agent-skill files run nothing.

Usage:
  ci_change_classifier.py --all --github-output "$GITHUB_OUTPUT"
  ci_change_classifier.py --files-from <path|-> --github-output "$GITHUB_OUTPUT"
  ci_change_classifier.py --files a.md b.dart --format env
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import PurePosixPath

FLAG_NAMES: tuple[str, ...] = (
    "flutter_lint",
    "flutter_unit",
    "flutter_complexity",
    "flutter_integration",
    "python_lint",
    "python_unit",
    "python_complexity",
)

FLUTTER_LINT_UNIT = frozenset({"flutter_lint", "flutter_unit"})
FLUTTER_FULL = frozenset(
    {"flutter_lint", "flutter_unit", "flutter_complexity", "flutter_integration"}
)
PYTHON_LINT_UNIT = frozenset({"python_lint", "python_unit"})
PYTHON_FULL = frozenset({"python_lint", "python_unit", "python_complexity"})
COMPLEXITY_ONLY = frozenset({"flutter_complexity", "python_complexity"})
ALL_FLAGS = frozenset(FLAG_NAMES)

_DOC_SUFFIXES = {".md", ".markdown", ".rst"}
_DOC_DIR_NAMES = {".agent", ".claude", ".cursor", ".vscode", "docs", "specs"}
_DOC_FILENAMES = {
    "authors",
    "changelog",
    "codeowners",
    "contributing",
    "license",
    "licence",
}

_PREFIX_RULES: tuple[tuple[str, frozenset[str]], ...] = (
    ("test", FLUTTER_LINT_UNIT),
    ("integration_test", FLUTTER_FULL),
    ("lib", FLUTTER_FULL),
    ("ios", FLUTTER_FULL),
    ("android", FLUTTER_FULL),
    ("backend/tests", PYTHON_LINT_UNIT),
    ("backend", PYTHON_FULL),
    (".github", ALL_FLAGS),
)

_EXACT_RULES: dict[str, frozenset[str]] = {
    "scripts/ci_change_classifier.py": ALL_FLAGS,
    "scripts/complexity_sensor.py": COMPLEXITY_ONLY,
    "scripts/compute_release_tag.py": COMPLEXITY_ONLY,
    "scripts/ci_integration_green.py": COMPLEXITY_ONLY,
    ".complexity-baseline.json": COMPLEXITY_ONLY,
    ".github/workflows/flutter.yml": frozenset(
        {"flutter_lint", "flutter_unit", "flutter_complexity"}
    ),
    ".github/workflows/python-api.yml": PYTHON_FULL,
    ".github/workflows/integration_tests.yml": FLUTTER_FULL,
    "scripts/run_integration_tests.sh": FLUTTER_FULL,
    "analysis_options.yaml": frozenset({"flutter_lint"}),
    "pubspec.yaml": FLUTTER_FULL,
    "pubspec.lock": FLUTTER_FULL,
}


def classify(files: Iterable[str], *, force_all: bool = False) -> dict[str, bool]:
    if force_all:
        return {name: True for name in FLAG_NAMES}
    found: set[str] = set()
    for raw in files:
        found.update(_flags_for(_posix(raw)))
    return {name: name in found for name in FLAG_NAMES}


def format_github_output(flags: dict[str, bool]) -> str:
    return "".join(
        f"{name}={'true' if flags[name] else 'false'}\n" for name in FLAG_NAMES
    )


def _posix(path: str) -> str:
    normalised = path.replace("\\", "/")
    while normalised.startswith("./"):
        normalised = normalised[2:]
    return normalised


def _is_doc(path: str) -> bool:
    p = PurePosixPath(path)
    if p.suffix.lower() in _DOC_SUFFIXES:
        return True
    if any(part.lower() in _DOC_DIR_NAMES for part in p.parts):
        return True
    stem = p.name.lower()
    return stem in _DOC_FILENAMES or stem.split(".")[0] in _DOC_FILENAMES


def _under(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def _flags_for(path: str) -> frozenset[str]:
    if not path or _is_doc(path):
        return frozenset()
    exact = _EXACT_RULES.get(path)
    if exact is not None:
        return exact
    for prefix, flags in _PREFIX_RULES:
        if _under(path, prefix):
            return flags
    return frozenset()


def _read_files(args: argparse.Namespace) -> list[str]:
    if args.files_from == "-":
        return [line.strip() for line in sys.stdin if line.strip()]
    if args.files_from:
        with open(args.files_from, encoding="utf-8") as fh:
            return [line.strip() for line in fh if line.strip()]
    return list(args.files or [])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--files", nargs="*", default=[])
    parser.add_argument("--files-from", metavar="PATH")
    parser.add_argument("--github-output", metavar="PATH")
    parser.add_argument("--format", choices=("github", "env"), default="github")
    args = parser.parse_args(argv)

    flags = classify(_read_files(args), force_all=args.all)
    text = format_github_output(flags)
    if args.github_output and args.github_output != "-":
        with open(args.github_output, "a", encoding="utf-8") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
