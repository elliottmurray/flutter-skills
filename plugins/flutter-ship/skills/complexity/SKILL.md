---
name: complexity
description: >
  Measure and ratchet down cyclomatic complexity (Dart via dart_code_linter,
  Python via radon). Trigger on /complexity, complexity sensor, baseline,
  ratchet, hotspot, or "most complex function".
user_invocable: true
---

# Complexity

One sensor, `scripts/complexity_sensor.py` (stdlib), measures Dart with
`dart_code_linter` and Python with `radon`, then compares every function to
`.complexity-baseline.json`. Ceilings only shrink.

`/setup-project` already copies the sensor, an empty baseline
(`default_threshold` 10), and `docs/complexity.md`. This skill is the
report / refactor / ratchet loop.

## Baseline

```json
{ "default_threshold": 10, "entries": { "<relpath>::<qualname>": 14 } }
```

- No entry → allowance is `default_threshold` (10).
- `--check` fails only when a function exceeds its allowance.
- `--update-baseline` lowers entries and drops any that fall to ≤10. It
  never raises a ceiling.

`10` is the radon A/B–C boundary: A 1–5, B 6–10, C 11–20, D 21–30, E 31–40,
F 41+. Dart uses the same numbers (`cyclomatic-complexity`).

## Commands

Install measurement tools once. Dart: `dart pub global activate dart_code_linter`.
Python (only if `backend/` exists): `uv add --dev radon` in `backend/`, or
`python3 -m pip install radon`.

```bash
# Report — worst offenders + regressions (default)
python3 scripts/complexity_sensor.py --report
python3 scripts/complexity_sensor.py --lang dart --report

# Gate — mirrors CI, exit 1 on regression
python3 scripts/complexity_sensor.py --check
python3 scripts/complexity_sensor.py --lang dart --check

# Lock in a lower ceiling after a refactor
python3 scripts/complexity_sensor.py --lang dart --update-baseline
```

CI sets `COMPLEXITY_DART_METRICS_CMD` to
`dart pub global run dart_code_linter:metrics`. Override radon with
`COMPLEXITY_RADON_CMD` (default: `<this python> -m radon`).

If `scripts/complexity_sensor.py` is missing, stop and run `/setup-project`
(or copy the template from the plugin) before continuing.

## Hotspot pass (the main use)

Do this when asked for a report, a ratchet, or "the worst function". One
function at a time — not every commit.

1. **Report.** Run `--report`. Take the top entry that is not intrinsic
   (generated code, a table of cases that *is* the algorithm). Skip
   `*.g.dart` / `*.freezed.dart`.
2. **Refactor TDD-first.** Use `/tdd`. Behaviour stays the same: lean on
   existing tests (`flutter test`, and `uv run pytest` in `backend/` if
   present). Add a characterization test first if coverage is thin.
   Extract helpers, flatten nesting, or table-drive branch ladders.
3. **Confirm.** Re-run `--report` (or `--file <path>`) and the tests.
   The number must have dropped.
4. **Ratchet.** `--update-baseline`. Commit the refactor and
   `.complexity-baseline.json` together.
5. Mention before/after complexity in the PR body.

Never raise a ceiling to make the gate pass. If a function must stay
above 10, say so in the PR and leave the grandfathered entry. Prefer
refactoring first.

## How it is wired

- **CI — warn-only.** `flutter.yml` (and `python-api.yml` when FastAPI
  landed) run `--check` with `continue-on-error: true`. Flip to blocking
  by deleting that line once the baseline has settled. The change
  classifier skips the step on docs-only diffs.
- **Live nudge.** flutter-ship installs a PostToolUse hook that warns
  after an `.dart` / `.py` edit that leaves a function over its ceiling.
  Advisory only; it never blocks.

Full reference in the generated project: `docs/complexity.md`.
