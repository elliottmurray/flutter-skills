---
name: sync-model
description: >
  Keep Dart and Python models in sync across the wire. Audit which models are
  paired, find field drift and missing tests, and change what is being synced
  via .sync-model.json. Trigger on /sync-model, "what's being synced", model
  drift, "keep models in sync", or "sync config".
user_invocable: true
---

# Sync Model

Keeps the Flutter (`lib/`) and FastAPI (`backend/`) halves consistent: when a
model exists on both sides, its fields should match, and both sides should
test it.

A PostToolUse hook (`sync_model_hook.py`) already nudges you right after you
edit a model file. This skill is the bigger hammer: the full audit, and the
configuration of what gets synced.

## What is being synced

By default, **name matching**: any class (or enum) under `lib/` with the same
name as one under `backend/` is a pair. Field names are compared normalized —
`emailAddress` ≡ `email_address`, `APP_STORE` ≡ `appStore`. Tests are checked
by stem: `test/<stem>_test.dart` ↔ `backend/tests/test_<stem>.py`.

`.sync-model.json` in the project root overrides and extends this:

```json
{
  "pairs": [
    { "dart": "lib/models/user.dart", "python": "backend/models/account.py" }
  ],
  "ignore": ["AppChannel"]
}
```

- `pairs` — explicit files to compare, for models whose names differ across
  sides. Each side's classes are matched by name; if each file holds exactly
  one class, those two are compared.
- `ignore` — model names the hook should never nudge about (intentionally
  one-sided).

The file is optional. Without it, only name matching runs.

## Audit

Run this to see the current state of the whole project:

1. Read `.sync-model.json` if it exists. That is the sync config: the declared
   pairs and ignored names.
2. List every model on each side: grep `^class` under `lib/**/*.dart` and
   `backend/**/*.py`, plus `^enum` on the Dart side.
3. For each pair (declared or name-matched), compare fields normalized with
   the snake rule above. Report missing fields per side.
4. For each model, check both test files exist by stem.
5. Summarize: paired and in sync / paired and drifted / model with no
   counterpart (one-sided by design or an oversight — your call).

Present the summary as a table. For each drifted pair, show the specific
fields, not just a count.

## Changing what is synced

Edit `.sync-model.json`:

- **Names differ across sides** → add a `pairs` entry with both paths.
- **A model is intentionally one-sided** → add its name to `ignore`.
- **Stop syncing a pair** → remove the `pairs` entry (or the whole file to
  return to pure name matching).

After editing the config, re-run the audit to show the new state.

## Fixing drift

When fields have drifted, change the counterpart to match — usually the
backend schema leads and the Dart model follows, but use your judgement on
which side is ahead. Then:

- Run both test suites: `flutter test` and `cd backend && uv run pytest -q`.
- If a test is missing on either side, write it. Cover the same fields on
  both sides — the tests are the readable statement of the contract.
- The hook stays quiet when a pair is in sync and both tests exist.
