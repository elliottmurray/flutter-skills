#!/usr/bin/env python3
"""Compute the release version and a collision-free git tag for the day.

The version is the UTC date (`YYYY.M.D`) and is used as the iOS marketing
version. The build number (`GITHUB_RUN_NUMBER`) makes each upload unique.

The git tag must be unique: first release of a day is `v<version>`; a second
gets `-2`, then `-3`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterable
from datetime import datetime, timezone


def utc_version(now: datetime | None = None) -> str:
    d = now or datetime.now(timezone.utc)
    return f"{d.year}.{d.month}.{d.day}"


def next_release_tag(base_tag: str, existing_tags: Iterable[str]) -> str:
    existing = set(existing_tags)
    if base_tag not in existing:
        return base_tag
    suffix = 2
    while f"{base_tag}-{suffix}" in existing:
        suffix += 1
    return f"{base_tag}-{suffix}"


def parse_tags(raw: str) -> list[str]:
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _local_tags() -> list[str]:
    return parse_tags(subprocess.check_output(["git", "tag"], text=True))


def main(argv: list[str] | None = None) -> int:
    del argv
    version = utc_version()
    tag = next_release_tag(f"v{version}", _local_tags())
    print(f"version={version}")
    print(f"tag={tag}")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as fh:
            fh.write(f"version={version}\n")
            fh.write(f"tag={tag}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
