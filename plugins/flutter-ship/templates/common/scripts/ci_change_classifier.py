#!/usr/bin/env python3
"""Map a changed-file list to which CI jobs should run.

Stdlib only. Fail closed: an unrecognised path under a service tree runs that
service's full suite; an unrecognised path under `.github/` runs every job.
Documentation and agent-skill files run nothing.

Where the service trees live comes from `project_layout.py` — this module has
no opinion on whether the Flutter app sits at the repo root or under `app/`.

Usage:
  ci_change_classifier.py --all --github-output "$GITHUB_OUTPUT"
  ci_change_classifier.py --files-from <path|-> --github-output "$GITHUB_OUTPUT"
  ci_change_classifier.py --files a.md b.dart --format env
"""

from __future__ import annotations

import argparse
import functools
import sys
from collections.abc import Iterable
from pathlib import PurePosixPath

import project_layout as layout

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

# Layout-independent: `scripts/` and `.github/` stay at the repo root.
_SHARED_EXACT_RULES: dict[str, frozenset[str]] = {
    "scripts/ci_change_classifier.py": ALL_FLAGS,
    "scripts/project_layout.py": ALL_FLAGS,
    "scripts/complexity_sensor.py": COMPLEXITY_ONLY,
    "scripts/compute_release_tag.py": COMPLEXITY_ONLY,
    "scripts/ci_integration_green.py": COMPLEXITY_ONLY,
    ".flutter-ship.json": ALL_FLAGS,
    ".complexity-baseline.json": COMPLEXITY_ONLY,
    ".github/workflows/flutter.yml": frozenset(
        {"flutter_lint", "flutter_unit", "flutter_complexity"}
    ),
    ".github/workflows/python-api.yml": PYTHON_FULL,
    ".github/workflows/integration_tests.yml": FLUTTER_FULL,
    "scripts/run_integration_tests.sh": FLUTTER_FULL,
}


@functools.lru_cache(maxsize=1)
def _prefix_rules() -> tuple[tuple[str, frozenset[str]], ...]:
    """Longest-match-first prefix table, built from the project layout.

    Order matters: `backend/tests` has to be tested before `backend`, and a
    Dart package rooted at `.` has to come after every narrower rule.
    """
    rules: list[tuple[str, frozenset[str]]] = []
    for pkg in layout.dart_packages():
        rules.append((layout.join(pkg, layout.DART_TEST_DIR), FLUTTER_LINT_UNIT))
        rules.append((layout.join(pkg, layout.DART_INTEGRATION_DIR), FLUTTER_FULL))
        for source_dir in layout.DART_SOURCE_DIRS:
            rules.append((layout.join(pkg, source_dir), FLUTTER_FULL))
    for pkg in layout.python_packages():
        rules.append((layout.join(pkg, layout.PYTHON_TEST_DIR), PYTHON_LINT_UNIT))
        rules.append((pkg, PYTHON_FULL))
    rules.append((".github", ALL_FLAGS))
    rules.sort(key=lambda rule: len(rule[0]), reverse=True)
    return tuple(rules)


@functools.lru_cache(maxsize=1)
def _exact_rules() -> dict[str, frozenset[str]]:
    """Single files whose flags do not follow from the directory they sit in."""
    rules = dict(_SHARED_EXACT_RULES)
    for pkg in layout.dart_packages():
        for manifest in layout.DART_MANIFESTS:
            rules[layout.join(pkg, manifest)] = FLUTTER_FULL
        for config in layout.DART_LINT_CONFIG:
            rules[layout.join(pkg, config)] = frozenset({"flutter_lint"})
    return rules


def classify(files: Iterable[str], *, force_all: bool = False) -> dict[str, bool]:
    if force_all:
        return {name: True for name in FLAG_NAMES}
    found: set[str] = set()
    for raw in files:
        found.update(_flags_for(layout.posix(raw)))
    return {name: name in found for name in FLAG_NAMES}


def format_github_output(flags: dict[str, bool]) -> str:
    return "".join(
        f"{name}={'true' if flags[name] else 'false'}\n" for name in FLAG_NAMES
    )


def _is_doc(path: str) -> bool:
    p = PurePosixPath(path)
    if p.suffix.lower() in _DOC_SUFFIXES:
        return True
    if any(part.lower() in _DOC_DIR_NAMES for part in p.parts):
        return True
    stem = p.name.lower()
    return stem in _DOC_FILENAMES or stem.split(".")[0] in _DOC_FILENAMES


def _flags_for(path: str) -> frozenset[str]:
    if not path or _is_doc(path):
        return frozenset()
    exact = _exact_rules().get(path)
    if exact is not None:
        return exact
    for prefix, flags in _prefix_rules():
        if layout.under(path, prefix):
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
