#!/usr/bin/env python3
"""Copy plugin templates into a target project, substituting {{PLACEHOLDERS}}.

Usage:
  render.py --dest PATH --app-name NAME --bundle-id ID [options]

Always copies templates/common/. With --firebase / --fastapi, also copies
those overlay trees. Existing files are overwritten only with --force.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = PLUGIN_ROOT / "templates"

DEFAULTS = {
    "FLUTTER_VERSION": "3.47.2",
    "RUNNER_LABEL": "macos-latest",
    "APPLE_TEAM_ID": "YOUR_TEAM_ID",
}


def package_name(app_name: str) -> str:
    """Dart package name: lowercase, underscores, leading letter."""
    chars = []
    for ch in app_name.strip():
        if ch.isalnum():
            chars.append(ch.lower())
        else:
            chars.append("_")
    name = "".join(chars).strip("_")
    while "__" in name:
        name = name.replace("__", "_")
    if not name or not name[0].isalpha():
        name = f"app_{name}" if name else "app"
    return name


def render_text(text: str, mapping: dict[str, str]) -> str:
    for key, value in mapping.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def copy_tree(src: Path, dest: Path, mapping: dict[str, str], *, force: bool) -> list[str]:
    written: list[str] = []
    if not src.is_dir():
        return written
    for path in src.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(src)
        target = dest / rel
        if target.exists() and not force:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix in {".png", ".jpg", ".jpeg", ".p12", ".mobileprovision"}:
            shutil.copy2(path, target)
        else:
            target.write_text(render_text(path.read_text(), mapping))
        written.append(str(rel))
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", required=True, type=Path)
    parser.add_argument("--app-name", required=True)
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--flutter-version", default=DEFAULTS["FLUTTER_VERSION"])
    parser.add_argument("--runner-label", default=DEFAULTS["RUNNER_LABEL"])
    parser.add_argument("--apple-team-id", default=DEFAULTS["APPLE_TEAM_ID"])
    parser.add_argument("--package-name", default="")
    parser.add_argument("--firebase", action="store_true")
    parser.add_argument("--fastapi", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    dest = args.dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    pkg = args.package_name or package_name(args.app_name)
    mapping = {
        "APP_NAME": args.app_name,
        "BUNDLE_ID": args.bundle_id,
        "PACKAGE_NAME": pkg,
        "FLUTTER_VERSION": args.flutter_version,
        "RUNNER_LABEL": args.runner_label,
        "APPLE_TEAM_ID": args.apple_team_id,
    }

    written = copy_tree(TEMPLATES / "common", dest, mapping, force=args.force)
    if args.firebase:
        written += copy_tree(TEMPLATES / "firebase", dest, mapping, force=args.force)
    if args.fastapi:
        written += copy_tree(TEMPLATES / "fastapi", dest, mapping, force=args.force)

    extra = PLUGIN_ROOT / "scripts" / "sim_driver.py"
    if extra.is_file():
        target = dest / "scripts" / "sim_driver.py"
        if args.force or not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(extra, target)
            target.chmod(target.stat().st_mode | 0o111)
            written.append("scripts/sim_driver.py")

    hook_src = dest / "scripts" / "pre-commit"
    git_dir = dest / ".git"
    if hook_src.is_file() and git_dir.is_dir():
        hook_dst = git_dir / "hooks" / "pre-commit"
        hook_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(hook_src, hook_dst)
        hook_dst.chmod(0o755)
        written.append(".git/hooks/pre-commit")

    print(f"Rendered {len(written)} files into {dest}")
    for rel in written:
        print(f"  {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
