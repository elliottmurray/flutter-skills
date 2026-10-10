# Complexity

`scripts/complexity_sensor.py` measures cyclomatic complexity (Dart via
`dart_code_linter`, Python via `radon` when `backend/` exists) and compares
every function to `.complexity-baseline.json`.

The baseline can only shrink. New functions must come in at or under
`default_threshold` (10). Grandfathered hotspots stay until someone
refactors them and runs `--update-baseline`.

```bash
python3 scripts/complexity_sensor.py --report
python3 scripts/complexity_sensor.py --check
python3 scripts/complexity_sensor.py --lang dart --update-baseline
```

CI runs `--check` warn-only. Use `/complexity` for the report / ratchet /
occasional hotspot pass. Never raise a ceiling to make the gate pass.
