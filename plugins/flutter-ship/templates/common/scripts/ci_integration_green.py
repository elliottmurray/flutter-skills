#!/usr/bin/env python3
"""Decide whether the last *executed* iOS integration-test job on main was green.

Docs / unit-test-only / lint / complexity merges skip `integration-test`. Those
runs must not count as a release gate — walk back to the last run that actually
ran the Mac job (or that failed unit tests, which also blocks a release).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence

FAILURES = frozenset({"failure", "cancelled", "timed_out", "startup_failure"})


def evaluate_integration_runs(
    runs: Sequence[Mapping[str, str]],
) -> tuple[bool, str]:
    if not runs:
        return False, "no completed Integration Tests runs on main"

    for index, jobs in enumerate(runs):
        integ = _conclusion(jobs, "integration-test")
        if integ == "success":
            return True, f"run[{index}]: integration-test=success"
        if integ in FAILURES:
            return False, f"run[{index}]: integration-test={integ}"
        if _any_unit_failed(jobs):
            unit = _unit_conclusion(jobs)
            return False, f"run[{index}]: unit-tests={unit} (integration skipped)"
    return False, "no completed Integration Tests run on main executed integration-test"


def jobs_from_gh_view(payload: Mapping) -> dict[str, str]:
    return {
        str(job.get("name") or ""): str(job.get("conclusion") or "")
        for job in payload.get("jobs") or []
    }


def _conclusion(jobs: Mapping[str, str], name: str) -> str:
    return jobs.get(name, "") or ""


def _unit_names(jobs: Mapping[str, str]) -> list[str]:
    return [
        name
        for name in jobs
        if name == "unit-tests" or name.startswith("unit-tests /")
    ]


def _any_unit_failed(jobs: Mapping[str, str]) -> bool:
    return any((jobs.get(name) or "") in FAILURES for name in _unit_names(jobs))


def _unit_conclusion(jobs: Mapping[str, str]) -> str:
    for name in _unit_names(jobs):
        value = jobs.get(name) or ""
        if value in FAILURES:
            return value
    return "skipped"


def _gh_json(args: list[str]) -> object:
    return json.loads(
        subprocess.check_output(["gh", *args], text=True),
    )


def fetch_recent_job_maps(repo: str, *, limit: int = 30) -> list[dict[str, str]]:
    runs = _gh_json(
        [
            "run", "list",
            "--repo", repo,
            "--workflow", "Integration Tests",
            "--branch", "main",
            "--status", "completed",
            "--limit", str(limit),
            "--json", "databaseId,conclusion",
        ]
    )
    maps: list[dict[str, str]] = []
    for run in runs or []:
        rid = str(run["databaseId"])
        detail = _gh_json(["run", "view", rid, "--repo", repo, "--json", "jobs"])
        maps.append(jobs_from_gh_view(detail if isinstance(detail, dict) else {}))
    return maps


def main(argv: list[str] | None = None) -> int:
    del argv
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        print("GITHUB_REPOSITORY is not set", file=sys.stderr)
        return 2
    green, reason = evaluate_integration_runs(fetch_recent_job_maps(repo))
    print(reason)
    print(f"Last Integration Tests on main (executed): {'success' if green else 'not green'}")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as fh:
            fh.write(f"green={'true' if green else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
