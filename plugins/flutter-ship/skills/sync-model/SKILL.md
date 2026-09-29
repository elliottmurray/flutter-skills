---
name: sync-model
description: >
  Keep Dart and Python models in sync across the wire. Audit which models are
  paired, find field drift and test-case drift, and change what is being
  synced via .sync-model.json. Trigger on /sync-model, "what's being synced",
  model drift, "keep models in sync", "sync config", or "are the tests equal".
user_invocable: true
---

# Sync Model

Keeps the Flutter (`lib/`) and FastAPI (`backend/`) halves consistent: when a
model exists on both sides, its fields should match, and both sides should
test the same cases.

A PostToolUse hook (`sync_model_hook.py`) nudges you right after you edit a
model file (field drift, missing tests) or a test file (case drift). This
skill is the bigger hammer: the full audit, the scaffolding of new pairs, and
the configuration of what gets synced.

## What is being synced

By default, **name matching**: any class (or enum) under `lib/` with the same
name as one under `backend/` is a pair. Field names are compared normalized —
`emailAddress` ≡ `email_address`, `APP_STORE` ≡ `appStore`. Tests are checked
by stem: `test/<stem>_test.dart` ↔ `backend/tests/test_<stem>.py`.

### Test cases

The hook keeps test *cases* equal, not just test files. The convention:

> The Python test function name is the slugified Dart test description.

```dart
test('round-trips through serialization', () { ... });
```
```python
def test_round_trips_through_serialization():
    ...
```

Both slug to `round_trips_through_serialization`, so the hook can compare the
sets and nudge when one side has a case the other lacks. Edit a test file on
either side and the nudge lists the cases only in Dart vs only in Python.

`.sync-model.json` in the project root overrides and extends the model sync:

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

## Creating a pair

When you create a new sync, scaffold both test files so they start equal.
The standard case set for a model:

1. **`constructs with valid fields`** — build the model with every field set,
   assert the values stuck.
2. **`round-trips through serialization`** — serialize, deserialize, compare.
   The case name is identical on both sides; the methods differ (`toJson` /
   `fromJson` vs `model_dump` / `model_validate`).

Then run both suites: `flutter test` and `cd backend && uv run pytest -q`.
Add per-field cases as the model grows — the hook will nudge when one side
has a case the other lacks.

## Audit

Run this to see the current state of the whole project:

1. Read `.sync-model.json` if it exists. That is the sync config: the declared
   pairs and ignored names.
2. List every model on each side: grep `^class` under `lib/**/*.dart` and
   `backend/**/*.py`, plus `^enum` on the Dart side.
3. For each pair (declared or name-matched), compare fields normalized with
   the snake rule above. Report missing fields per side.
4. For each model, check both test files exist by stem, then compare test
   cases: extract `test('...')` descriptions from the Dart file and
   `def test_...` names from the Python file, slug both, report the diff.
5. Summarize: paired and in sync / paired and drifted / model with no
   counterpart (one-sided by design or an oversight — your call).

Present the summary as a table. For each drifted pair, show the specific
fields and cases, not just a count.

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
which side is ahead. When test cases have drifted, port the missing case to
the other side, keeping the case name identical. Then:

- Run both test suites: `flutter test` and `cd backend && uv run pytest -q`.
- The hook stays quiet when a pair is in sync and both test case sets match.

## Other languages

The case extractor is per-language: Dart reads `test('...')` descriptions,
Python reads `def test_...` names, and both slug to the same canonical form.
A TypeScript/JavaScript side (Jest/Vitest `it('...')` / `test('...')`
descriptions) plugs in the same way — same extraction, same slug comparison —
when a web or Node half joins the project.
