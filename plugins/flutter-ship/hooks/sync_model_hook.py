#!/usr/bin/env python3
"""PostToolUse hook: nudge when a model edit needs a cross-language counterpart update.

Keeps Dart models (lib/) and Python models (backend/) in sync. When a model
file changes, finds the counterpart class on the other side by name, compares
fields, and checks test parity. An optional .sync-model.json in the project
root declares explicit pairs (for models whose names differ across sides) and
ignored model names. Advisory only: always exits 0, quiet when the changed
file holds no models or no counterpart exists.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

PROJECT_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))

DART_DIR = "lib"
PY_DIR = "backend"
DART_TEST_DIR = "test"
PY_TEST_DIR = "tests"
MANIFEST_NAME = ".sync-model.json"

# Dart: "final String name;", "late final int? age;" (also non-final fields).
_DART_FIELD = re.compile(r"^\s+(?:late\s+)?final\s+[\w<>?,. ]+?\s+(\w+)\s*;", re.MULTILINE)
# Python: "name: str", "age: int | None = None" (annotated assignments only).
_PY_FIELD = re.compile(r"^\s+(\w+)\s*:\s*[^=\n]+", re.MULTILINE)
_DART_CLASS = re.compile(r"^class\s+(\w+)", re.MULTILINE)
_DART_ENUM = re.compile(r"^enum\s+(\w+)\s*\{", re.MULTILINE)
_PY_CLASS = re.compile(r"^class\s+(\w+)(?:\s*\(([^)]*)\))?", re.MULTILINE)
_PY_ENUM_BASE = re.compile(r"\b(Enum|StrEnum|IntEnum)\b")
_IDENT = re.compile(r"[A-Za-z_]\w*")


def snake(name: str) -> str:
    """Normalize camelCase and SCREAMING_SNAKE to a common lowercase form."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", name)
    return spaced.lower()


def _dart_body(text: str, start: int) -> str:
    """Return the body of a top-level Dart declaration starting at `start`."""
    end = text.find("\n}", start)
    return text[start:] if end == -1 else text[start : end + 2]


def _py_body(text: str, start: int) -> str:
    """Return the body of a top-level Python class starting at `start`."""
    lines = text[start:].splitlines(keepends=True)
    body: list[str] = []
    for line in lines[1:]:
        if line.strip() and not line[0].isspace() and not line.startswith("#"):
            break
        body.append(line)
    return "".join(body)


def dart_models(text: str) -> dict[str, list[str]]:
    """Extract class/enum names and their field names from Dart source."""
    models: dict[str, list[str]] = {}
    for m in _DART_CLASS.finditer(text):
        fields = [f.group(1) for f in _DART_FIELD.finditer(_dart_body(text, m.start()))]
        if fields:
            models[m.group(1)] = fields
    for m in _DART_ENUM.finditer(text):
        body = _dart_body(text, m.start())
        values_part = body[body.find("{") :]
        values = [v for v in _IDENT.findall(values_part) if v != m.group(1)]
        if values:
            models[m.group(1)] = values
    return models


def py_models(text: str) -> dict[str, list[str]]:
    """Extract class/enum names and their field names from Python source."""
    models: dict[str, list[str]] = {}
    for m in _PY_CLASS.finditer(text):
        body = _py_body(text, m.start())
        if _PY_ENUM_BASE.search(m.group(2) or ""):
            values = [
                v
                for v in re.findall(r"^\s+(\w+)\s*=", body, re.MULTILINE)
                if v != m.group(1)
            ]
        else:
            values = [f.group(1) for f in _PY_FIELD.finditer(body)]
        if values:
            models[m.group(1)] = values
    return models


def index_side(root: Path, suffix: str, extractor) -> dict[str, Path]:
    """Map model name -> file for every model under `root`."""
    index: dict[str, Path] = {}
    if not root.is_dir():
        return index
    for path in sorted(root.rglob(f"*{suffix}")):
        if any(part.startswith(".") for part in path.parts):
            continue
        for name in extractor(path.read_text(errors="replace")):
            index.setdefault(name, path)
    return index


def find_test(roots: list[Path], rel_stem: str, suffix: str) -> Path | None:
    """Look for a test file matching `rel_stem` under any of `roots`."""
    for root in roots:
        if not root.is_dir():
            continue
        for candidate in root.rglob(f"*{suffix}"):
            stem = candidate.stem
            if stem in (rel_stem, f"test_{rel_stem}", f"{rel_stem}_test"):
                return candidate
    return None


def compare(changed_fields: list[str], other_fields: list[str]) -> tuple[list[str], list[str]]:
    """Return (missing in other, only in other) as normalized field names."""
    changed = {snake(f) for f in changed_fields}
    other = {snake(f) for f in other_fields}
    missing = sorted(changed - other)
    extra = sorted(other - changed)
    return missing, extra


def check_counterpart(
    name: str | None,
    fields: list[str],
    counterpart_rel: str,
    other_models: dict[str, list[str]],
    other_side: str,
    findings: list[str],
) -> bool:
    """Record drift findings for one model/counterpart pair. True if compared."""
    other_fields = other_models.get(name) if name is not None else None
    if other_fields is None and len(other_models) == 1:
        other_fields = next(iter(other_models.values()))
    if other_fields is None:
        return False
    missing, extra = compare(fields, other_fields)
    if missing or extra:
        label = f" (counterpart of {name})" if name else ""
        detail = [f"  {counterpart_rel}{label}:"]
        if missing:
            detail.append(f"    - missing fields: {', '.join(missing)}")
        if extra:
            detail.append(f"    - only in {other_side}: {', '.join(extra)}")
        findings.extend(detail)
    return True


def check_tests(stem: str, findings: list[str]) -> None:
    """Record missing test files for a model, on both sides."""
    dart_test = find_test([PROJECT_DIR / DART_TEST_DIR], stem, "_test.dart")
    py_test = find_test([PROJECT_DIR / PY_DIR / PY_TEST_DIR], stem, ".py")
    if dart_test is None:
        findings.append(
            f"  test/{stem}_test.dart: missing — add it and cover the same fields"
        )
    if py_test is None:
        findings.append(
            f"  {PY_DIR}/{PY_TEST_DIR}/test_{stem}.py: missing — add it and cover "
            "the same fields"
        )


def compare_manifest_pair(
    dart: dict[str, list[str]],
    py: dict[str, list[str]],
    dart_rel: str,
    py_rel: str,
    edited_side: str,
    findings: list[str],
) -> bool:
    """Compare a declared pair: match by name, fall back to single models.

    Findings are phrased from the edited side's perspective. Returns True if
    any model pair was compared.
    """
    compared = False
    if edited_side == "python":
        for name, fields in py.items():
            if name in dart:
                compared = check_counterpart(
                    name, fields, dart_rel, dart, "Dart", findings
                ) or compared
        unmatched_py = {n: f for n, f in py.items() if n not in dart}
        unmatched_dart = {n: f for n, f in dart.items() if n not in py}
        if len(unmatched_py) == 1 and len(unmatched_dart) == 1:
            name, fields = next(iter(unmatched_py.items()))
            compared = check_counterpart(
                None, fields, dart_rel,
                {name: next(iter(unmatched_dart.values()))}, "Dart", findings,
            ) or compared
        return compared
    for name, fields in dart.items():
        if name in py:
            compared = check_counterpart(
                name, fields, py_rel, py, "Python", findings
            ) or compared
    unmatched_dart = {n: f for n, f in dart.items() if n not in py}
    unmatched_py = {n: f for n, f in py.items() if n not in dart}
    if len(unmatched_dart) == 1 and len(unmatched_py) == 1:
        name, fields = next(iter(unmatched_dart.items()))
        compared = check_counterpart(
            None, fields, py_rel, {name: next(iter(unmatched_py.values()))}, "Python", findings
        ) or compared
    return compared


def load_manifest() -> dict:
    """Read .sync-model.json from the project root, if present and valid."""
    try:
        data = json.loads((PROJECT_DIR / MANIFEST_NAME).read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def report(rel_path: str, other_side: str, findings: list[str]) -> str:
    lines = [
        f"Cross-language sync: your edit to {rel_path} may need a matching "
        f"change on the {other_side} side.",
        "",
        *findings,
        "",
        "Update the counterpart so the wire contract stays in sync, and keep "
        "the tests covering the same fields. Run /sync-model to see or change "
        "everything being synced.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    del argv  # hooks read stdin, not argv
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    file_path = (event.get("tool_input") or {}).get("file_path") or ""
    if not file_path:
        return 0
    path = Path(file_path)
    if not path.is_absolute():
        path = PROJECT_DIR / path
    try:
        rel = path.relative_to(PROJECT_DIR)
    except ValueError:
        return 0
    rel_posix = rel.as_posix()

    manifest = load_manifest()
    ignore = set(manifest.get("ignore") or [])
    findings: list[str] = []

    # An explicit manifest pair covering the edited file wins over name matching.
    pair_entry = next(
        (
            pair
            for pair in manifest.get("pairs") or []
            if rel_posix in (pair.get("dart"), pair.get("python"))
        ),
        None,
    )
    matched = False
    if pair_entry is not None:
        dart_ref = pair_entry.get("dart") or ""
        py_ref = pair_entry.get("python") or ""
        dart_path = PROJECT_DIR / dart_ref if dart_ref else None
        py_path = PROJECT_DIR / py_ref if py_ref else None
        if dart_path and py_path and dart_path.is_file() and py_path.is_file():
            edited_side = "python" if rel_posix == py_ref else "dart"
            matched = compare_manifest_pair(
                dart_models(dart_path.read_text(errors="replace")),
                py_models(py_path.read_text(errors="replace")),
                dart_ref,
                py_ref,
                edited_side,
                findings,
            ) or matched
    elif rel.parts[0] == DART_DIR and path.suffix == ".dart":
        changed = dart_models(path.read_text(errors="replace"))
        if changed:
            index = index_side(PROJECT_DIR / PY_DIR, ".py", py_models)
            for name, fields in changed.items():
                if name in ignore:
                    continue
                counterpart = index.get(name)
                if counterpart is None:
                    continue
                other_fields = py_models(counterpart.read_text(errors="replace"))[name]
                matched = check_counterpart(
                    name, fields, counterpart.relative_to(PROJECT_DIR).as_posix(),
                    {name: other_fields}, "Python", findings,
                ) or matched
    elif rel.parts[0] == PY_DIR and path.suffix == ".py":
        changed = py_models(path.read_text(errors="replace"))
        if changed:
            index = index_side(PROJECT_DIR / DART_DIR, ".dart", dart_models)
            for name, fields in changed.items():
                if name in ignore:
                    continue
                counterpart = index.get(name)
                if counterpart is None:
                    continue
                other_fields = dart_models(counterpart.read_text(errors="replace"))[name]
                matched = check_counterpart(
                    name, fields, counterpart.relative_to(PROJECT_DIR).as_posix(),
                    {name: other_fields}, "Dart", findings,
                ) or matched
    else:
        return 0

    if matched:
        check_tests(path.stem, findings)

    if not findings:
        return 0

    other_side = "Python" if rel.parts[0] == DART_DIR else "Dart"
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": report(rel_posix, other_side, findings),
            }
        },
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
