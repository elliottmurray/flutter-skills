#!/usr/bin/env python3
"""PostToolUse hook: nudge when an edit needs a cross-language counterpart update.

Keeps Dart models (lib/) and Python models (backend/) in sync, and keeps their
tests in step. When a model file changes, finds the counterpart class on the
other side by name, compares fields, and checks the tests. An optional
.sync-model.json in the project root declares explicit pairs (for models whose
names differ across sides), ignored model names, and the test flavour:

- "intent" (default): each side has its own hand-written tests, twinned by
  name ('rejects unknown role' <-> test_rejects_unknown_role). Editing a model
  or either test file compares the two lists.
- "shared": both suites iterate over test_vectors/<stem>.json. Editing a
  model, its tests, or the vector file checks the vectors are well formed,
  cover every field, and are loaded by both suites.

A model whose vector file exists is treated as shared whatever the flavour.
Advisory only: always exits 0, quiet when nothing applies.
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
VECTORS_DIR = "test_vectors"
VECTORS_SCHEMA = "vectors.schema.json"
FLAVOURS = ("intent", "shared")
# A test named '... (dart only)' or test_..._python_only has no twin by design.
ONE_SIDED_SUFFIXES = ("_dart_only", "_python_only")

# Dart: "final String name;", "late final int? age;" (also non-final fields).
_DART_FIELD = re.compile(r"^\s+(?:late\s+)?final\s+[\w<>?,. ]+?\s+(\w+)\s*;", re.MULTILINE)
# Python: "name: str", "age: int | None = None" (annotated assignments only).
_PY_FIELD = re.compile(r"^\s+(\w+)\s*:\s*[^=\n]+", re.MULTILINE)
_DART_CLASS = re.compile(r"^class\s+(\w+)", re.MULTILINE)
_DART_ENUM = re.compile(r"^enum\s+(\w+)\s*\{", re.MULTILINE)
_PY_CLASS = re.compile(r"^class\s+(\w+)(?:\s*\(([^)]*)\))?", re.MULTILINE)
_PY_ENUM_BASE = re.compile(r"\b(Enum|StrEnum|IntEnum)\b")
_IDENT = re.compile(r"[A-Za-z_]\w*")
# Enum value noise: comments, constructor args, annotations.
_ENUM_NOISE = re.compile(r"//[^\n]*|\([^)]*\)|@\w+")
# Test cases: Dart test descriptions vs pytest function names.
_DART_TEST_CASE = re.compile(r"^\s*(?:test|testWidgets)\(\s*(['\"])(.*?)\1", re.MULTILINE)
_PY_TEST_CASE = re.compile(r"^\s*(?:async\s+)?def (test_\w+)", re.MULTILINE)


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


def _dart_enum_values(text: str, open_brace: int, name: str) -> list[str]:
    """Values of the enum whose `{` is at `open_brace`.

    Matches braces rather than looking for the next top-level `}`, so a
    one-line `enum Role { member, admin }` stops at its own brace. An enhanced
    enum's values end at the first `;`.
    """
    depth = 0
    end = len(text)
    for i in range(open_brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    values = text[open_brace + 1 : end].split(";", 1)[0]
    return [v for v in _IDENT.findall(_ENUM_NOISE.sub("", values)) if v != name]


def dart_models(text: str) -> dict[str, list[str]]:
    """Extract class/enum names and their field names from Dart source."""
    models: dict[str, list[str]] = {}
    for m in _DART_CLASS.finditer(text):
        fields = [f.group(1) for f in _DART_FIELD.finditer(_dart_body(text, m.start()))]
        if fields:
            models[m.group(1)] = fields
    for m in _DART_ENUM.finditer(text):
        values = _dart_enum_values(text, m.end() - 1, m.group(1))
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


def _rel(path: Path) -> str:
    return path.relative_to(PROJECT_DIR).as_posix()


def _read(path: Path) -> str:
    return path.read_text(errors="replace")


def find_tests(stem: str, findings: list[str]) -> tuple[Path | None, Path | None]:
    """Locate both test files for `stem`, recording any that are missing."""
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
    return dart_test, py_test


def check_tests(stem: str, findings: list[str], flavour: str = "intent") -> None:
    """Record test drift for a model: missing files, then intents or vectors."""
    dart_test, py_test = find_tests(stem, findings)
    if flavour == "shared" or (PROJECT_DIR / VECTORS_DIR / f"{stem}.json").is_file():
        check_vectors(stem, findings)
        check_vector_refs(stem, dart_test, py_test, findings)
    elif dart_test is not None and py_test is not None:
        compare_test_cases(dart_test, py_test, findings)


def slug(text: str) -> str:
    """Normalize a test description/name to a comparable canonical form.

    Strips a leading `test_` so pytest function names and Dart test
    descriptions slug to the same form.
    """
    text = text.lower()
    if text.startswith("test_"):
        text = text[len("test_"):]
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def dart_test_cases(text: str) -> list[str]:
    """Extract test case names from Dart test source.

    Convention: the case name is the test/testWidgets description, slugified.
    A description built at runtime (`test(c.description, ...)`) is not a case.
    """
    return [slug(m.group(2)) for m in _DART_TEST_CASE.finditer(text)]


def py_test_cases(text: str) -> list[str]:
    """Extract test case names from pytest source.

    Convention: the case name is the test function name, slugified — the
    `test_` prefix is stripped by slug(), matching the Dart description.
    """
    return [slug(m.group(1)) for m in _PY_TEST_CASE.finditer(text)]


def _twinned(cases: list[str]) -> set[str]:
    return {c for c in cases if not c.endswith(ONE_SIDED_SUFFIXES)}


def compare_test_cases(dart_test: Path, py_test: Path, findings: list[str]) -> None:
    """Record test cases that have no same-named twin on the other side."""
    dart = dart_test_cases(_read(dart_test))
    py = py_test_cases(_read(py_test))
    only_dart = sorted(_twinned(dart) - set(py))
    only_py = sorted(_twinned(py) - set(dart))
    if only_dart:
        findings.append(f"  {_rel(py_test)}: cases only in Dart:")
        findings.extend(f"    - {c} → add test_{c}" for c in only_dart)
    if only_py:
        findings.append(f"  {_rel(dart_test)}: cases only in Python:")
        findings.extend(f"    - {c} → add test('{c.replace('_', ' ')}')" for c in only_py)


def _model_file(root: str, stem: str, suffix: str) -> Path | None:
    """First non-test source file named `<stem><suffix>` under `root`."""
    base = PROJECT_DIR / root
    if not base.is_dir():
        return None
    for path in sorted(base.rglob(f"{stem}{suffix}")):
        parts = path.relative_to(base).parts
        if not any(p.startswith(".") or p in (DART_TEST_DIR, PY_TEST_DIR) for p in parts):
            return path
    return None


def vector_fields(data: dict, stem: str) -> set[str]:
    """Normalized wire fields of the vector file's model, Python side first."""
    name = data.get("model")
    sides = (("python", PY_DIR, ".py", py_models), ("dart", DART_DIR, ".dart", dart_models))
    for key, root, suffix, extractor in sides:
        ref = data.get(key)
        path = PROJECT_DIR / ref if isinstance(ref, str) else _model_file(root, stem, suffix)
        if path is None or not path.is_file():
            continue
        fields = extractor(_read(path)).get(name)
        if fields:
            return {snake(f) for f in fields}
    return set()


def _case_problems(index: int, case: object, fields: set[str], seen: set[str]) -> list[str]:
    """Structural problems with one vector case (see vectors.schema.json)."""
    if not isinstance(case, dict):
        return [f"case {index}: not an object"]
    label = case.get("description")
    problems: list[str] = []
    if not isinstance(label, str) or not label:
        label = f"case {index}"
        problems.append(f"{label}: needs a description")
    elif label in seen:
        problems.append(f"'{label}': duplicate description")
    seen.add(label)
    if not isinstance(case.get("data"), dict):
        problems.append(f"'{label}': data must be an object")
    if not isinstance(case.get("valid"), bool):
        problems.append(f"'{label}': valid must be true or false")
    elif not case["valid"]:
        problems.extend(_error_field_problems(label, case.get("error_field"), fields))
    return problems


def _error_field_problems(label: str, field: object, fields: set[str]) -> list[str]:
    """An invalid case names exactly one real field it breaks."""
    if not isinstance(field, str) or not field:
        return [f"'{label}': invalid case needs error_field"]
    if fields and snake(field) not in fields:
        return [f"'{label}': error_field '{field}' is not a model field"]
    return []


def vector_problems(data: dict, fields: set[str]) -> list[str]:
    """Every case well formed, and every field set by at least one valid case."""
    problems: list[str] = []
    seen: set[str] = set()
    covered: set[str] = set()
    for index, case in enumerate(data["cases"]):
        problems.extend(_case_problems(index, case, fields, seen))
        if isinstance(case, dict) and case.get("valid") is True:
            covered.update(snake(k) for k in case.get("data") or {})
    uncovered = sorted(fields - covered)
    if uncovered:
        problems.append(f"no valid case sets: {', '.join(uncovered)}")
    return problems


def check_vectors(stem: str, findings: list[str]) -> None:
    """Record problems with test_vectors/<stem>.json, or that it is missing."""
    rel = f"{VECTORS_DIR}/{stem}.json"
    try:
        data = json.loads((PROJECT_DIR / rel).read_text())
    except FileNotFoundError:
        findings.append(
            f"  {rel}: missing — the shared flavour keeps this model's cases there "
            f"(format: {VECTORS_DIR}/{VECTORS_SCHEMA})"
        )
        return
    except (OSError, ValueError) as exc:
        findings.append(f"  {rel}: not valid JSON ({exc})")
        return
    if not isinstance(data, dict) or not isinstance(data.get("cases"), list):
        findings.append(f'  {rel}: needs a top-level "cases" list')
        return
    fields = vector_fields(data, stem)
    problems = vector_problems(data, fields)
    if data.get("model") and not fields:
        problems.insert(0, f"model '{data['model']}' not found on either side")
    if problems:
        findings.append(f"  {rel}:")
        findings.extend(f"    - {p}" for p in problems)


def check_vector_refs(
    stem: str, dart_test: Path | None, py_test: Path | None, findings: list[str]
) -> None:
    """Record test files that do not load the shared vectors for `stem`."""
    loads = re.compile(rf"""['"]{re.escape(stem)}['"]""")
    calls = ((dart_test, f"loadVectors('{stem}')"), (py_test, f'load_vectors("{stem}")'))
    for test, call in calls:
        if test is not None and not loads.search(_read(test)):
            findings.append(
                f"  {_rel(test)}: does not load {VECTORS_DIR}/{stem}.json — "
                f"iterate over {call} instead of hand-written cases"
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
    return _wrap(
        f"Cross-language sync: your edit to {rel_path} may need a matching "
        f"change on the {other_side} side.",
        findings,
    )


def _wrap(headline: str, findings: list[str]) -> str:
    lines = [
        headline,
        "",
        *findings,
        "",
        "Update the counterpart so the wire contract stays in sync, and keep "
        "the tests covering the same fields. Run /sync-model to see or change "
        "everything being synced.",
    ]
    return "\n".join(lines)


def flavour_of(manifest: dict) -> str:
    flavour = manifest.get("tests")
    return flavour if flavour in FLAVOURS else "intent"


def _manifest_pair(manifest: dict, rel_posix: str) -> dict | None:
    """The .sync-model.json pair that names the edited file, if any."""
    for pair in manifest.get("pairs") or []:
        if isinstance(pair, dict) and rel_posix in (pair.get("dart"), pair.get("python")):
            return pair
    return None


def _check_pair_edit(pair: dict, rel_posix: str, findings: list[str]) -> bool:
    """Compare a declared pair after one of its files was edited."""
    dart_ref = pair.get("dart") or ""
    py_ref = pair.get("python") or ""
    dart_path = PROJECT_DIR / dart_ref if dart_ref else None
    py_path = PROJECT_DIR / py_ref if py_ref else None
    if not (dart_path and py_path and dart_path.is_file() and py_path.is_file()):
        return False
    return compare_manifest_pair(
        dart_models(_read(dart_path)),
        py_models(_read(py_path)),
        dart_ref,
        py_ref,
        "python" if rel_posix == py_ref else "dart",
        findings,
    )


def _check_named_edit(path: Path, edited_side: str, ignore: set[str], findings: list[str]) -> bool:
    """Compare every model in the edited file with its same-named counterpart."""
    if edited_side == "dart":
        changed, other_root, other_suffix, other_extract, other_side = (
            dart_models(_read(path)), PY_DIR, ".py", py_models, "Python"
        )
    else:
        changed, other_root, other_suffix, other_extract, other_side = (
            py_models(_read(path)), DART_DIR, ".dart", dart_models, "Dart"
        )
    if not changed:
        return False
    index = index_side(PROJECT_DIR / other_root, other_suffix, other_extract)
    matched = False
    for name, fields in changed.items():
        counterpart = index.get(name)
        if name in ignore or counterpart is None:
            continue
        other_fields = other_extract(_read(counterpart))[name]
        matched = check_counterpart(
            name, fields, _rel(counterpart), {name: other_fields}, other_side, findings
        ) or matched
    return matched


def _source_side(rel: Path) -> str | None:
    """"dart" for lib/**.dart, "python" for backend/**.py, else None."""
    if rel.parts[0] == DART_DIR and rel.suffix == ".dart":
        return "dart"
    if rel.parts[0] == PY_DIR and rel.suffix == ".py":
        return "python"
    return None


def check_model_edit(path: Path, rel: Path, manifest: dict) -> str | None:
    """A model file changed: fields against the counterpart, then the tests."""
    rel_posix = rel.as_posix()
    findings: list[str] = []
    # An explicit manifest pair covering the edited file wins over name matching.
    pair = _manifest_pair(manifest, rel_posix)
    side = _source_side(rel)
    if pair is not None:
        matched = _check_pair_edit(pair, rel_posix, findings)
    elif side is not None:
        matched = _check_named_edit(path, side, set(manifest.get("ignore") or []), findings)
    else:
        return None
    if matched:
        check_tests(path.stem, findings, flavour_of(manifest))
    if not findings:
        return None
    other_side = "Python" if rel.parts[0] == DART_DIR else "Dart"
    return report(rel_posix, other_side, findings)


def test_stem(rel: Path) -> str | None:
    """Model stem for a Dart or pytest test file, or None for anything else."""
    name = rel.name
    if rel.parts[0] == DART_TEST_DIR and name.endswith("_test.dart"):
        return name[: -len("_test.dart")]
    in_py_tests = rel.parts[:2] == (PY_DIR, PY_TEST_DIR)
    if in_py_tests and name.startswith("test_") and name.endswith(".py"):
        return name[len("test_") : -len(".py")]
    return None


def check_test_edit(rel: Path, stem: str, manifest: dict) -> str | None:
    """A test file changed: keep its twin on the other side in step.

    For a synced model, the full test check (files, cases or vectors). For
    any other stem, the cases are compared when both test files exist.
    """
    findings: list[str] = []
    synced = _model_file(DART_DIR, stem, ".dart") and _model_file(PY_DIR, stem, ".py")
    if synced:
        check_tests(stem, findings, flavour_of(manifest))
    else:
        dart_test = find_test([PROJECT_DIR / DART_TEST_DIR], stem, "_test.dart")
        py_test = find_test([PROJECT_DIR / PY_DIR / PY_TEST_DIR], stem, ".py")
        if dart_test is not None and py_test is not None:
            compare_test_cases(dart_test, py_test, findings)
    if not findings:
        return None
    return _wrap(
        f"Cross-language sync: {rel.as_posix()} has a twin on the other side "
        "that should test the same things.",
        findings,
    )


def check_vector_edit(rel: Path) -> str | None:
    """A shared vector file changed: well formed, covering, and loaded by both."""
    if not (PROJECT_DIR / rel).is_file():
        return None
    stem = rel.stem
    findings: list[str] = []
    check_vectors(stem, findings)
    dart_test, py_test = find_tests(stem, findings)
    check_vector_refs(stem, dart_test, py_test, findings)
    if not findings:
        return None
    return _wrap(
        f"Cross-language sync: {rel.as_posix()} is the shared test contract for "
        "both suites.",
        findings,
    )


def _edited_path(event: dict) -> tuple[Path, Path] | None:
    """(absolute, project-relative) path of the edited file, if in the project."""
    file_path = (event.get("tool_input") or {}).get("file_path") or ""
    if not file_path:
        return None
    path = Path(file_path)
    if not path.is_absolute():
        path = PROJECT_DIR / path
    try:
        rel = path.relative_to(PROJECT_DIR)
    except ValueError:
        return None
    return (path, rel) if rel.parts else None


def check_edit(path: Path, rel: Path) -> str | None:
    """Route the edit to the check for its kind of file."""
    manifest = load_manifest()
    if _manifest_pair(manifest, rel.as_posix()) is not None:
        return check_model_edit(path, rel, manifest)
    if rel.parts[0] == VECTORS_DIR and rel.suffix == ".json" and rel.name != VECTORS_SCHEMA:
        return check_vector_edit(rel)
    stem = test_stem(rel)
    if stem is not None:
        return check_test_edit(rel, stem, manifest)
    return check_model_edit(path, rel, manifest)


def main(argv: list[str] | None = None) -> int:
    del argv  # hooks read stdin, not argv
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    edited = _edited_path(event) if isinstance(event, dict) else None
    if edited is None:
        return 0
    context = check_edit(*edited)
    if context:
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": context,
                }
            },
            sys.stdout,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
