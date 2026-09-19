#!/usr/bin/env python3
"""Cross-language cyclomatic-complexity sensor + ratchet baseline.

Measures Python (radon) and Dart (dart_code_linter), compares every function
against a committed baseline that can only shrink, and gates on regressions.

Standard library only. Measurement tools are subprocesses:

  * radon — defaults to `<this python> -m radon`; override COMPLEXITY_RADON_CMD
  * dart  — defaults to `dart run dart_code_linter:metrics`;
            override COMPLEXITY_DART_METRICS_CMD

Layout comes from `project_layout.py` (see there for how to override it);
COMPLEXITY_PYTHON_TARGETS (space-separated, default ".") still narrows what
radon scans inside the Python package.

Usage:
  complexity_sensor.py --report
  complexity_sensor.py --check
  complexity_sensor.py --update-baseline
  complexity_sensor.py --lang python|dart|all
  complexity_sensor.py --file <path> --json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import project_layout as layout

REPO_ROOT = layout.REPO_ROOT
BASELINE_PATH = REPO_ROOT / ".complexity-baseline.json"
DEFAULT_THRESHOLD = 10


def _python_root() -> Path:
    return REPO_ROOT / layout.python_dir()


def _python_targets() -> list[str]:
    raw = os.environ.get("COMPLEXITY_PYTHON_TARGETS", ".")
    return [p for p in raw.split() if p]


def record_key(rec: dict) -> str:
    return f"{rec['relpath']}::{rec['qualname']}"


def _relpath(path: str, root) -> str:
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve()))
    except ValueError:
        return str(path).replace("\\", "/").lstrip("./")


def normalize_radon(data: dict, root) -> list[dict]:
    records: list[dict] = []
    for file_path, blocks in data.items():
        if not isinstance(blocks, list):
            continue
        rel = _relpath(file_path, root)
        for block in blocks:
            _emit_radon_block(block, rel, records, prefix="")
    seen: set[tuple] = set()
    deduped: list[dict] = []
    for rec in records:
        ident = (rec["relpath"], rec["qualname"], rec["lineno"])
        if ident not in seen:
            seen.add(ident)
            deduped.append(rec)
    return deduped


def _emit_radon_block(block: dict, rel: str, records: list, prefix: str) -> None:
    btype = block.get("type")
    if btype == "class":
        for method in block.get("methods", []) or []:
            _emit_radon_block(method, rel, records, prefix="")
        return
    classname = block.get("classname")
    if classname:
        qualname = f"{classname}.{block['name']}"
    else:
        qualname = f"{prefix}{block['name']}"
    records.append({
        "relpath": rel,
        "qualname": qualname,
        "complexity": block["complexity"],
        "lineno": block.get("lineno"),
        "lang": "python",
    })
    for closure in block.get("closures", []) or []:
        _emit_radon_block(closure, rel, records, prefix=f"{qualname}.")


def normalize_dart(data: dict, package_relpath: str) -> list[dict]:
    records: list[dict] = []
    for entry in data.get("records", []) or []:
        rel_in_pkg = str(entry.get("path", "")).replace("\\", "/").lstrip("./")
        if package_relpath in (".", ""):
            relpath = rel_in_pkg
        else:
            relpath = f"{package_relpath}/{rel_in_pkg}" if rel_in_pkg else package_relpath
        for scope in ("functions", "classes"):
            for name, info in (entry.get(scope) or {}).items():
                cc = _dart_cc(info)
                if cc is not None:
                    records.append({
                        "relpath": relpath,
                        "qualname": name,
                        "complexity": cc,
                        "lineno": info.get("lineno") if isinstance(info, dict) else None,
                        "lang": "dart",
                    })
    return records


def _dart_cc(info) -> int | None:
    if not isinstance(info, dict):
        return None
    metrics = info.get("metrics")
    if isinstance(metrics, list):
        for metric in metrics:
            mid = str(metric.get("metricsId") or metric.get("id") or metric.get("name") or "")
            if mid.replace("_", "-") == "cyclomatic-complexity":
                return int(metric.get("value"))
    for alt in ("cyclomaticComplexity", "cyclomatic-complexity"):
        if alt in info:
            return int(info[alt])
    return None


def load_baseline(path=BASELINE_PATH) -> dict:
    try:
        raw = json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"default_threshold": DEFAULT_THRESHOLD, "entries": {}}
    raw.setdefault("default_threshold", DEFAULT_THRESHOLD)
    raw.setdefault("entries", {})
    return raw


def save_baseline(baseline: dict, path=BASELINE_PATH) -> None:
    ordered = {
        "default_threshold": baseline.get("default_threshold", DEFAULT_THRESHOLD),
        "entries": dict(sorted(baseline.get("entries", {}).items())),
    }
    Path(path).write_text(json.dumps(ordered, indent=2) + "\n")


def find_regressions(records: list[dict], baseline: dict) -> list[dict]:
    threshold = baseline.get("default_threshold", DEFAULT_THRESHOLD)
    entries = baseline.get("entries", {})
    out = []
    for rec in records:
        ceiling = entries.get(record_key(rec), threshold)
        if rec["complexity"] > ceiling:
            out.append({**rec, "ceiling": ceiling})
    return out


def ratchet_baseline(records: list[dict], baseline: dict) -> dict:
    threshold = baseline.get("default_threshold", DEFAULT_THRESHOLD)
    old = baseline.get("entries", {})
    new: dict[str, int] = {}
    current = {record_key(r): r["complexity"] for r in records}
    for key, cc in current.items():
        prior = old.get(key)
        if prior is not None:
            kept = min(prior, cc)
            if kept > threshold:
                new[key] = kept
        elif cc > threshold:
            new[key] = cc
    return {"default_threshold": threshold, "entries": new}


def _radon_cmd() -> list[str]:
    override = os.environ.get("COMPLEXITY_RADON_CMD")
    return override.split() if override else [sys.executable, "-m", "radon"]


def _dart_metrics_cmd() -> list[str]:
    override = os.environ.get("COMPLEXITY_DART_METRICS_CMD")
    return override.split() if override else ["dart", "run", "dart_code_linter:metrics"]


def collect_python(targets=None) -> list[dict]:
    root = _python_root()
    if not root.is_dir():
        return []
    paths = targets or _python_targets()
    try:
        proc = subprocess.run(
            [*_radon_cmd(), "cc", "-j", *paths],
            cwd=str(root), capture_output=True, text=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if not proc.stdout.strip():
        return []
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    records = normalize_radon(data, root=root)
    try:
        prefix = root.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        prefix = root.name
    for rec in records:
        rec["relpath"] = f"{prefix}/{rec['relpath']}"
    return records


def collect_dart(packages=None) -> list[dict]:
    records: list[dict] = []
    for pkg in packages or layout.dart_packages():
        pkg_dir = REPO_ROOT / pkg if pkg != "." else REPO_ROOT
        if not (pkg_dir / "lib").is_dir():
            continue
        try:
            proc = subprocess.run(
                [*_dart_metrics_cmd(), "analyze", "lib", "--reporter=json"],
                cwd=str(pkg_dir), capture_output=True, text=True, timeout=300,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        out = proc.stdout.strip()
        if not out:
            continue
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            continue
        records.extend(normalize_dart(data, package_relpath=pkg))
    return records


def collect(lang: str) -> list[dict]:
    records: list[dict] = []
    if lang in ("python", "all"):
        records += collect_python()
    if lang in ("dart", "all"):
        records += collect_dart()
    return records


def run_report(records: list[dict], baseline: dict, top: int = 20, stream=sys.stdout) -> int:
    regressions = find_regressions(records, baseline)
    ranked = sorted(records, key=lambda r: (-r["complexity"], r["relpath"], r["qualname"]))
    threshold = baseline.get("default_threshold", DEFAULT_THRESHOLD)
    print(f"Scanned {len(records)} functions "
          f"(default threshold {threshold}, {len(baseline.get('entries', {}))} grandfathered).",
          file=stream)
    print(f"\nTop {min(top, len(ranked))} by cyclomatic complexity:", file=stream)
    for rec in ranked[:top]:
        print(f"  {rec['complexity']:4d}  {record_key(rec)}", file=stream)
    if regressions:
        print(f"\n⚠️  {len(regressions)} function(s) over their ceiling:", file=stream)
        for rec in regressions:
            print(f"  {rec['complexity']:4d} (ceiling {rec['ceiling']})  {record_key(rec)}",
                  file=stream)
    else:
        print("\n✅ No complexity regressions vs baseline.", file=stream)
    return 0


def run_check(records: list[dict], baseline: dict, stream=sys.stdout) -> int:
    regressions = find_regressions(records, baseline)
    if not regressions:
        print(f"✅ complexity: {len(records)} functions, no regressions vs baseline.",
              file=stream)
        return 0
    print(f"❌ complexity: {len(regressions)} regression(s) beyond baseline:", file=stream)
    for rec in sorted(regressions, key=lambda r: -r["complexity"]):
        print(f"  {rec['complexity']:4d} > {rec['ceiling']:<3}  {record_key(rec)}"
              f"  (line {rec.get('lineno')})", file=stream)
    print("\nRefactor these, or run --update-baseline only if the higher value is intentional.",
          file=stream)
    return 1


def run_file(file_path: str, baseline: dict, as_json: bool, stream=sys.stdout) -> int:
    p = Path(file_path)
    if p.suffix == ".py":
        records = [r for r in collect_python() if file_path.replace("\\", "/").endswith(r["relpath"])]
    elif p.suffix == ".dart":
        records = [r for r in collect_dart() if file_path.replace("\\", "/").endswith(r["relpath"])]
    else:
        records = []
    over = find_regressions(records, baseline)
    if as_json:
        print(json.dumps({"file": file_path, "over": over}), file=stream)
    else:
        for rec in over:
            print(f"{rec['complexity']} > {rec['ceiling']}  {record_key(rec)}", file=stream)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--report", action="store_true")
    group.add_argument("--check", action="store_true")
    group.add_argument("--update-baseline", action="store_true")
    parser.add_argument("--lang", choices=["python", "dart", "all"], default="all")
    parser.add_argument("--file")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    baseline = load_baseline()

    if args.file:
        return run_file(args.file, baseline, as_json=args.json)

    records = collect(args.lang)

    if args.update_baseline:
        new = ratchet_baseline(records, baseline)
        if args.lang != "all":
            scanned_langs = {r["lang"] for r in records} or {args.lang}
            for key, val in baseline.get("entries", {}).items():
                lang = layout.lang_for_path(key.split("::", 1)[0])
                if lang not in scanned_langs and lang != args.lang:
                    new["entries"].setdefault(key, val)
        save_baseline(new)
        print(f"Baseline updated: {len(new['entries'])} grandfathered functions "
              f"(threshold {new['default_threshold']}).")
        return 0

    if args.check:
        return run_check(records, baseline)
    return run_report(records, baseline)


if __name__ == "__main__":
    sys.exit(main())
