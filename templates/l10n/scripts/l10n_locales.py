#!/usr/bin/env python3
"""Add languages and keep every file that lists them in step.

A supported language lives in three places: an ARB file in `lib/l10n/`, the
iOS `CFBundleLocalizations` array (which also turns on the per-app language
picker in iOS Settings), and the generated `AppLocalizations`. This script
owns the first two; `flutter gen-l10n` owns the third.

Usage:
  l10n_locales.py setup              # pubspec `generate: true`, plist synced
  l10n_locales.py add fr es pt_BR    # new ARBs + plist; prints keys to translate
  l10n_locales.py sync               # plist <- ARB locales
  l10n_locales.py check              # parity report; exits 1 on drift
  l10n_locales.py list

`--package DIR` picks the Flutter package; default is
`project_layout.dart_dir()`. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import project_layout as layout  # noqa: E402

ARB_DIR = "lib/l10n"
TEMPLATE = "app_en.arb"
PREFIX = "app_"
INFO_PLIST = "ios/Runner/Info.plist"
PUBSPEC = "pubspec.yaml"

_LOCALE = re.compile(r"^[a-z]{2,3}(?:_[A-Z][a-z]{3})?(?:_(?:[A-Z]{2}|\d{3}))?$")
# An ICU argument after its `{`: `name}` or `name, kind,` / `name, kind}`.
_ARGUMENT = re.compile(r"\s*([A-Za-z_]\w*)\s*(?:,\s*(\w+)\s*)?([,}])")
# A plural/select branch key and its opening `{`, or the argument's closing `}`.
_BRANCH = re.compile(r"\s*(?:([^\s{}]+)\s*\{|\})")
_BRANCHED = {"plural", "select", "selectordinal"}
_PLIST_ARRAY = re.compile(
    r"(?P<indent>[ \t]*)<key>CFBundleLocalizations</key>\s*<array>.*?</array>\n?",
    re.DOTALL,
)
_PLIST_STRING = re.compile(r"<string>\s*([^<]+?)\s*</string>")


def canonical(code: str) -> str:
    """`pt-br` -> `pt_BR`, `zh-hant-tw` -> `zh_Hant_TW`; raises on nonsense."""
    parts = code.strip().replace("-", "_").split("_")
    out = [parts[0].lower()]
    for part in parts[1:]:
        out.append(part.title() if len(part) == 4 else part.upper())
    result = "_".join(out)
    if not _LOCALE.match(result):
        raise ValueError(f"not a locale code: {code!r}")
    return result


def package_root(arg: str | None) -> Path:
    rel = arg if arg is not None else layout.dart_dir()
    return layout.REPO_ROOT if rel in (".", "") else layout.REPO_ROOT / rel


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_arb(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def messages(arb: dict) -> dict:
    return {k: v for k, v in arb.items() if not k.startswith("@")}


def placeholders(message) -> set[str]:
    """Argument names in an ICU message: `{name}`, `{n, plural, …}`, `{g, select, …}`.

    Plural and select branch bodies are messages in their own right, so a
    one-word branch such as `other{they}` is text, not a placeholder.
    """
    found: set[str] = set()
    if isinstance(message, str):
        i = 0
        while i < len(message):  # a stray top-level `}` is just text
            i = _scan_text(message, i, found) + 1
    return found


def _scan_text(text: str, i: int, found: set[str]) -> int:
    """Scan message text from `i`; return the index of its closing `}` (or the end)."""
    while i < len(text):
        if text[i] == "}":
            return i
        if text[i] == "{":
            i = _scan_argument(text, i + 1, found)
        i += 1
    return i


def _scan_argument(text: str, i: int, found: set[str]) -> int:
    """Scan an argument from just after its `{`; return the index of its `}`."""
    match = _ARGUMENT.match(text, i)
    if not match:
        return _skip_braces(text, i)
    name, kind, end = match.groups()
    found.add(name)
    i = match.end()
    if end == "}":
        return i - 1
    if kind not in _BRANCHED:
        return _skip_braces(text, i)  # `{amount, number, currency}`
    while True:
        branch = _BRANCH.match(text, i)
        if not branch:
            return _skip_braces(text, i)
        if branch.group(1) is None:
            return branch.end() - 1
        i = _scan_text(text, branch.end(), found) + 1


def _skip_braces(text: str, i: int) -> int:
    """Index of the `}` that closes an already-open `{`, or the end."""
    depth = 1
    while i < len(text):
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if depth == 0:
            return i
        i += 1
    return i


def arb_locales(package: Path) -> list[str]:
    """Every ARB locale, English first."""
    found = [p.stem[len(PREFIX) :] for p in (package / ARB_DIR).glob(f"{PREFIX}*.arb")]
    return sorted(found, key=lambda code: (code != "en", code))


# --- Info.plist -------------------------------------------------------------


def plist_locales(text: str) -> list[str] | None:
    match = _PLIST_ARRAY.search(text)
    return _PLIST_STRING.findall(match.group(0)) if match else None


def set_plist_locales(text: str, locales: list[str]) -> str:
    """Rewrite (or insert) CFBundleLocalizations, keeping the file's tab style."""
    match = _PLIST_ARRAY.search(text)
    indent = match.group("indent") if match else "\t"
    inner = indent + "\t"
    block = (
        f"{indent}<key>CFBundleLocalizations</key>\n"
        f"{indent}<array>\n"
        + "".join(f"{inner}<string>{code}</string>\n" for code in locales)
        + f"{indent}</array>\n"
    )
    if match:
        return text[: match.start()] + block + text[match.end() :]
    dict_open = text.find("<dict>")
    if dict_open == -1:
        raise ValueError("Info.plist has no top-level <dict>")
    insert_at = text.index("\n", dict_open) + 1
    return text[:insert_at] + block + text[insert_at:]


def sync_plist(package: Path) -> str:
    plist = package / INFO_PLIST
    if not plist.is_file():
        return f"skip {INFO_PLIST}: not found (no iOS target)"
    text = plist.read_text(encoding="utf-8")
    locales = arb_locales(package)
    if plist_locales(text) == locales:
        return f"ok   {INFO_PLIST}: {', '.join(locales)}"
    plist.write_text(set_plist_locales(text, locales), encoding="utf-8")
    return f"set  {INFO_PLIST}: CFBundleLocalizations = {', '.join(locales)}"


# --- pubspec.yaml -----------------------------------------------------------


def enable_generate(text: str) -> str:
    """Set `generate: true` in the top-level `flutter:` section."""
    lines = text.splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if re.match(r"flutter:\s*$", line)), None)
    if start is None:
        return text.rstrip("\n") + "\n\nflutter:\n  generate: true\n"
    end = start + 1
    while end < len(lines) and (not lines[end].strip() or lines[end][0] in " \t#"):
        end += 1
    for i in range(start + 1, end):
        if re.match(r"[ \t]+generate:", lines[i]):
            lines[i] = re.sub(r"generate:.*", "generate: true", lines[i])
            return "".join(lines)
    lines.insert(start + 1, "  generate: true\n")
    return "".join(lines)


def missing_dependencies(text: str) -> list[str]:
    commands = []
    if not re.search(r"^[ \t]+flutter_localizations:", text, re.M):
        commands.append("flutter pub add flutter_localizations --sdk=flutter")
    if not re.search(r"^[ \t]+intl:", text, re.M):
        commands.append("flutter pub add intl:any")
    return commands


# --- parity -----------------------------------------------------------------


def parity_problems(package: Path) -> list[str]:
    arb_dir = package / ARB_DIR
    template = messages(load(arb_dir / TEMPLATE))
    problems: list[str] = []
    for code in arb_locales(package):
        name = f"{PREFIX}{code}.arb"
        if name == TEMPLATE:
            continue
        other = messages(load(arb_dir / name))
        problems += [f"{name}: missing {k}" for k in template if k not in other]
        problems += [f"{name}: extra {k}" for k in other if k not in template]
        for key in template.keys() & other.keys():
            if placeholders(template[key]) != placeholders(other[key]):
                problems.append(f"{name}: {key} placeholders differ from {TEMPLATE}")
    plist = package / INFO_PLIST
    if plist.is_file():
        listed = plist_locales(plist.read_text(encoding="utf-8")) or []
        if sorted(listed) != sorted(arb_locales(package)):
            problems.append(f"{INFO_PLIST}: CFBundleLocalizations {listed} != ARB locales")
    return problems


# --- commands ---------------------------------------------------------------


def cmd_setup(package: Path) -> int:
    pubspec = package / PUBSPEC
    if not pubspec.is_file():
        print(f"error: no {PUBSPEC} in {package}", file=sys.stderr)
        return 1
    text = pubspec.read_text(encoding="utf-8")
    updated = enable_generate(text)
    if updated != text:
        pubspec.write_text(updated, encoding="utf-8")
        print(f"set  {PUBSPEC}: flutter.generate = true")
    else:
        print(f"ok   {PUBSPEC}: flutter.generate = true")
    print(sync_plist(package))
    missing = missing_dependencies(updated)
    if missing:
        print("Missing dependencies. Run, in the package:")
        for command in missing:
            print(f"  {command}")
        return 1
    return 0


def cmd_add(package: Path, codes: list[str]) -> int:
    arb_dir = package / ARB_DIR
    template_path = arb_dir / TEMPLATE
    if not template_path.is_file():
        print(f"error: {template_path} not found; run /localization setup first", file=sys.stderr)
        return 1
    try:
        wanted = [canonical(code) for code in codes]
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    existing = set(arb_locales(package))
    # gen-l10n refuses `pt_BR` without a plain `pt` to fall back to.
    for code in wanted:
        base = code.split("_")[0]
        if base != code and base not in existing and base not in wanted:
            print(f"error: {code} needs {base} too (gen-l10n fallback); add both", file=sys.stderr)
            return 1

    template = messages(load(template_path))
    for code in wanted:
        path = arb_dir / f"{PREFIX}{code}.arb"
        if path.exists():
            print(f"ok   {path.relative_to(package)}: already exists")
            continue
        write_arb(path, {"@@locale": code, **template})
        print(f"new  {path.relative_to(package)}: {len(template)} strings copied from English")
        for key in template:
            print(f"       translate {key}")
    print(sync_plist(package))
    return 0


def cmd_check(package: Path) -> int:
    problems = parity_problems(package)
    for problem in problems:
        print(problem)
    if not problems:
        print(f"ok   {len(arb_locales(package))} locales in sync")
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--package", default=None, help="Flutter package, repo-relative")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup")
    add = sub.add_parser("add")
    add.add_argument("locales", nargs="+")
    sub.add_parser("sync")
    sub.add_parser("check")
    sub.add_parser("list")
    args = parser.parse_args(argv)

    package = package_root(args.package)
    if args.command == "setup":
        return cmd_setup(package)
    if args.command == "add":
        return cmd_add(package, args.locales)
    if args.command == "sync":
        print(sync_plist(package))
        return 0
    if args.command == "check":
        return cmd_check(package)
    print("\n".join(arb_locales(package)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
