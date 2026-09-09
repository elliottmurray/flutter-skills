---
name: complexity
description: >
  Measure and ratchet down cyclomatic complexity (Dart via dart_code_linter,
  Python via radon). Trigger on /complexity, complexity sensor, baseline,
  or "most complex function".
user_invocable: true
---

# Complexity

**Skill not shipped yet.** The sensor script already lands with
`/setup-project` (`scripts/complexity_sensor.py`,
`.complexity-baseline.json`). CI runs `--check` warn-only.

## What this skill will do

1. `--report` — find the worst offender that is not intrinsic
2. Refactor TDD-first (`/tdd`)
3. `--update-baseline` — lower-only ratchet
4. Occasional hotspot pass (not every commit)

Never raise a ceiling to make the gate pass.

## Commands (already available after setup)

```bash
python3 scripts/complexity_sensor.py --lang dart --report
python3 scripts/complexity_sensor.py --check
python3 scripts/complexity_sensor.py --lang dart --update-baseline
```
