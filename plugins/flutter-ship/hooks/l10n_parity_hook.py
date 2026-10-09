#!/usr/bin/env python3
"""PostToolUse hook: keep every ARB translation in step with the template.

Fires when an `.arb` file inside a gen-l10n `arb-dir` changes. Finds the
package by walking up from the edited file to the nearest `l10n.yaml`, then
diffs every locale against the template ARB (missing keys, extra keys,
placeholder drift) and checks iOS `CFBundleLocalizations` lists the same
locales. Always asks Claude to review the change in every language, because a
changed English value needs new translations even when the keys still match.

`test/l10n/arb_parity_test.dart` (rendered by /setup-project) enforces the
same rules in CI; this gives the feedback while editing. Advisory only:
always exits 0, quiet for files that are not translation files.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

PROJECT_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))

L10N_CONFIG = "l10n.yaml"
DEFAULT_ARB_DIR = "lib/l10n"
DEFAULT_TEMPLATE = "app_en.arb"
INFO_PLIST = "ios/Runner/Info.plist"

# `{name,` or `{name}`: a placeholder or a plural/select argument. Branch text
# such as `=1{1 mistake}` doesn't match because a space follows the word.
_PLACEHOLDER = re.compile(r"\{([A-Za-z_]\w*)[,}]")
_YAML_SCALAR = re.compile(r"^([\w-]+)\s*:\s*['\"]?([^'\"#\n]*?)['\"]?\s*(?:#.*)?$", re.MULTILINE)
_PLIST_LOCALIZATIONS = re.compile(
    r"<key>CFBundleLocalizations</key>\s*<array>(.*?)</array>", re.DOTALL
)
_PLIST_STRING = re.compile(r"<string>\s*([^<]+?)\s*</string>")


def load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def messages(arb: dict) -> dict:
    """Translatable messages, minus ARB metadata (`@key`, `@@locale`)."""
    return {k: v for k, v in arb.items() if not k.startswith("@")}


def placeholders(message) -> set[str]:
    return set(_PLACEHOLDER.findall(message)) if isinstance(message, str) else set()


def _braced(names: set[str]) -> str:
    return " ".join(f"{{{n}}}" for n in sorted(names)) or "none"


def normalize_locale(code: str) -> str:
    """`pt-BR`, `pt_br` and `pt_BR` compare equal."""
    return code.strip().replace("-", "_").lower()


def read_config(package: Path) -> tuple[Path, str]:
    """(arb dir, template file name) from `l10n.yaml`, with gen-l10n defaults."""
    values: dict[str, str] = {}
    try:
        text = (package / L10N_CONFIG).read_text(encoding="utf-8")
    except OSError:
        text = ""
    for key, value in _YAML_SCALAR.findall(text):
        values[key] = value.strip()
    arb_dir = values.get("arb-dir") or DEFAULT_ARB_DIR
    template = values.get("template-arb-file") or DEFAULT_TEMPLATE
    return package / arb_dir, template


def find_package(path: Path) -> Path | None:
    """Nearest ancestor of `path` holding `l10n.yaml`, stopping at the project."""
    for parent in path.parents:
        if (parent / L10N_CONFIG).is_file():
            return parent
        if parent == PROJECT_DIR or parent == parent.parent:
            break
    return None


def arb_prefix(template: str) -> str:
    """`app_en.arb` -> `app_`: the part every locale file shares."""
    stem = Path(template).stem
    return stem[: stem.rfind("_") + 1] if "_" in stem else ""


def locale_files(arb_dir: Path, template: str) -> dict[str, Path]:
    """Locale code -> ARB file, for every file that shares the template's prefix."""
    prefix = arb_prefix(template)
    found: dict[str, Path] = {}
    for path in sorted(arb_dir.glob(f"{prefix}*.arb")):
        found[path.stem[len(prefix) :]] = path
    return found


def locale_problems(name: str, template: dict, other: dict) -> list[str]:
    problems = [f"{name}: missing {k}" for k in template if k not in other]
    problems += [f"{name}: extra {k} (not in the template)" for k in other if k not in template]
    for key in template:
        if key not in other:
            continue
        want, got = placeholders(template[key]), placeholders(other[key])
        if want != got:
            problems.append(
                f"{name}: {key} placeholders {_braced(got)} vs template {_braced(want)}"
            )
    return problems


def parity_problems(arb_dir: Path, template: str) -> list[str]:
    english = messages(load(arb_dir / template))
    problems: list[str] = []
    for path in locale_files(arb_dir, template).values():
        if path.name != template:
            problems += locale_problems(path.name, english, messages(load(path)))
    return problems


def plist_locales(package: Path) -> list[str] | None:
    """Locales in `CFBundleLocalizations`, or None when there is no iOS plist."""
    try:
        text = (package / INFO_PLIST).read_text(encoding="utf-8")
    except OSError:
        return None
    match = _PLIST_LOCALIZATIONS.search(text)
    return _PLIST_STRING.findall(match.group(1)) if match else []


def plist_problems(package: Path, locales: list[str]) -> list[str]:
    listed = plist_locales(package)
    if listed is None:
        return []
    have = {normalize_locale(code) for code in listed}
    want = {normalize_locale(code) for code in locales}
    problems = [
        f"{INFO_PLIST}: CFBundleLocalizations is missing {code}"
        for code in sorted(want - have)
    ]
    problems += [
        f"{INFO_PLIST}: CFBundleLocalizations lists {code} but there is no ARB for it"
        for code in sorted(have - want)
    ]
    return problems


def reminder(rel_path: str, locales: list[str], problems: list[str]) -> str:
    found = (
        "Out of sync:\n" + "\n".join(f"- {p}" for p in problems)
        if problems
        else "Keys, placeholders and the iOS locale list match across every locale."
    )
    return (
        f"You edited a translation file ({rel_path}). Supported locales: "
        f"{', '.join(locales)}.\n{found}\n"
        "Make the same change in every language: same keys, same placeholders, "
        "plural and select forms right for each language, and the same meaning. "
        "Translate new or changed values; do not leave English in another "
        "locale. Then run `flutter gen-l10n` and `flutter test test/l10n`. "
        "Run /localization to audit everything or add a language."
    )


def main(argv: list[str] | None = None) -> int:
    del argv  # hooks read stdin, not argv
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    file_path = (event.get("tool_input") or {}).get("file_path") or ""
    if not file_path.endswith(".arb"):
        return 0
    path = Path(file_path)
    if not path.is_absolute():
        path = PROJECT_DIR / path

    package = find_package(path)
    if package is None:
        return 0
    arb_dir, template = read_config(package)
    if path.parent.resolve() != arb_dir.resolve():
        return 0

    locales = list(locale_files(arb_dir, template))
    problems = parity_problems(arb_dir, template) + plist_problems(package, locales)
    try:
        rel = path.relative_to(PROJECT_DIR).as_posix()
    except ValueError:
        rel = file_path

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": reminder(rel, locales, problems),
            }
        },
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
