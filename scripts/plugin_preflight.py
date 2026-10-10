#!/usr/bin/env python3
"""Check a plugin folder against Anthropic's directory rules before release.

Usage:
  plugin_preflight.py [PLUGIN_DIR]          # default: . (the repo root)
  plugin_preflight.py --version             # print plugin.json's version
  plugin_preflight.py --base REF            # also fail if the plugin changed
                                            # since REF but version did not

`claude plugin validate --strict` covers the manifest schema. This covers the
directory's extra rules from
https://claude.com/docs/plugins/pre-submission-checklist that a script can
check offline: README length, licence, junk files, file size and count, binary
files, symlinks, and file names. The portal's Validate step is still the
authority; this catches the common misses before a push.

Only git-tracked files count, because the directory reads the repository.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PLUGIN = "."
# Changes here don't reach plugin users, so they don't need a version bump.
NON_SHIPPING = (":!.github", ":!docs", ":!*.md")

MAX_FILES = 512
MAX_TEXT_BYTES = 256 * 1024
MIN_README_WORDS = 40
JUNK_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}
MEDIA_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
                  ".ttf", ".otf", ".woff", ".woff2"}
WINDOWS_DEVICES = {"con", "prn", "aux", "nul",
                   *(f"com{i}" for i in range(1, 10)),
                   *(f"lpt{i}" for i in range(1, 10))}
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, check=True,
                          capture_output=True, text=True).stdout


def tracked_files(plugin: str) -> list[str]:
    return git("ls-files", "-s", "--", plugin).splitlines()


def readme_words(text: str) -> int:
    without_code = re.sub(r"```.*?```", " ", text, flags=re.S)
    return len(re.findall(r"[A-Za-z0-9][\w'-]*", without_code))


def check_manifest(plugin_dir: Path, rel_paths: set[str]) -> list[str]:
    problems = []
    manifest = json.loads((plugin_dir / ".claude-plugin/plugin.json").read_text())
    for field in ("name", "description", "version", "author"):
        if not manifest.get(field):
            problems.append(f"plugin.json: `{field}` is missing")
    if manifest.get("version") and not SEMVER.match(manifest["version"]):
        problems.append(f"plugin.json: version {manifest['version']!r} is not semver")
    if not manifest.get("license") and "LICENSE" not in rel_paths:
        problems.append("no `license` in plugin.json and no LICENSE in the plugin folder")
    readme = plugin_dir / "README.md"
    if "README.md" not in rel_paths:
        problems.append("README.md missing from the plugin folder")
    elif readme_words(readme.read_text()) < MIN_README_WORDS:
        problems.append(f"README.md has under {MIN_README_WORDS} words outside code blocks")
    return problems


def check_files(entries: list[str]) -> list[str]:
    problems = []
    if len(entries) > MAX_FILES:
        problems.append(f"{len(entries)} files; the directory holds plugins over {MAX_FILES} for review")
    seen_lower: dict[str, str] = {}
    for entry in entries:
        meta, path = entry.split("\t", 1)
        mode = meta.split()[0]
        rel = PurePosixPath(path)
        if mode == "120000":
            problems.append(f"{path}: symlink; commit a regular file")
        elif mode == "160000":
            problems.append(f"{path}: git submodule; the directory won't follow it")
        for part in rel.parts:
            if part in JUNK_NAMES or part == "__MACOSX":
                problems.append(f"{path}: OS junk file; remove it from git")
            if ":" in part or part.endswith((".", " ")) or part.split(".")[0].lower() in WINDOWS_DEVICES:
                problems.append(f"{path}: name is not valid on Windows")
        clash = seen_lower.setdefault(path.lower(), path)
        if clash != path:
            problems.append(f"{path}: differs from {clash} only by case")
        if mode != "100644" and mode != "100755":
            continue
        full = REPO_ROOT / path
        if rel.suffix.lower() in MEDIA_SUFFIXES:
            continue
        data = full.read_bytes()
        if len(data) > MAX_TEXT_BYTES:
            problems.append(f"{path}: {len(data)} bytes; non-image files over 256 KiB are held for review")
        if b"\0" in data[:8192]:
            problems.append(f"{path}: binary file; only text, images and fonts pass without review")
    return problems


def plugin_version(plugin_dir: Path) -> str:
    return json.loads((plugin_dir / ".claude-plugin/plugin.json").read_text())["version"]


def check_version_bump(plugin: str, base: str) -> list[str]:
    changed = git("diff", "--name-only", f"{base}...HEAD", "--", plugin, *NON_SHIPPING).split()
    if not changed:
        return []
    try:
        old = json.loads(git("show", f"{base}:{plugin}/.claude-plugin/plugin.json"))["version"]
    except subprocess.CalledProcessError:
        return []
    new = plugin_version(REPO_ROOT / plugin)
    if old == new:
        return [f"plugin changed since {base} but version is still {new}; "
                "users on the marketplace won't receive it (fine if you are batching a release)"]
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("plugin", nargs="?", default=DEFAULT_PLUGIN)
    parser.add_argument("--version", action="store_true", help="print the plugin version and exit")
    parser.add_argument("--base", help="git ref to compare against for a version bump (warning only)")
    args = parser.parse_args(argv)

    plugin = args.plugin.rstrip("/")
    plugin_dir = REPO_ROOT / plugin
    if args.version:
        print(plugin_version(plugin_dir))
        return 0

    entries = tracked_files(plugin)
    rel_paths = {str(PurePosixPath(e.split("\t", 1)[1]).relative_to(plugin)) for e in entries}
    problems = check_manifest(plugin_dir, rel_paths) + check_files(entries)
    warnings = check_version_bump(plugin, args.base) if args.base else []

    for w in warnings:
        print(f"::warning::{w}" if _in_actions() else f"warning: {w}")
    for p in problems:
        print(f"::error::{p}" if _in_actions() else f"error: {p}")
    if problems:
        return 1
    print(f"✔ {plugin} passes the directory preflight ({len(entries)} files)")
    return 0


def _in_actions() -> bool:
    return os.environ.get("GITHUB_ACTIONS") == "true"


if __name__ == "__main__":
    sys.exit(main())
