---
name: sync-model
description: >
  Create, audit, and configure Dart ↔ Python models that cross the wire. Use
  to add a new synced model (a Flutter class with its FastAPI twin and tests
  on both sides), on /sync-model, model drift, test-case parity ("are the
  tests equal"), "what's being synced", or choosing intent vs shared test
  vectors.
user_invocable: true
---

# Sync Model

The client is always Flutter/Dart (`lib/`); the backend is FastAPI
(`backend/`). A synced model is a **twin pair** — one class per side, the same
wire contract — plus tests on both sides that pin that contract down.

A PostToolUse hook (`sync_model_hook.py`) nudges after every edit to a model,
a test file, or a vector file. This skill creates new pairs, runs the full
audit, and changes the config.

## Two test flavours

Set once per project in `.sync-model.json` as `"tests"`:

- **intent** (default) — each side has hand-written tests, and every test
  case has a **twin**: the Python test function name is the slugified Dart
  test description, so `test('round-trips through serialization')` ↔
  `def test_round_trips_through_serialization`. The hook slugs both lists and
  names the cases only in Dart or only in Python. Mark a deliberately
  one-sided case by ending its name in `(dart only)` / `_python_only`.
- **shared** — the cases live once, in `test_vectors/<stem>.json`, and both
  suites iterate over them (`loadVectors('<stem>')` / `load_vectors("<stem>")`).
  The hook checks the file against `test_vectors/vectors.schema.json`, that
  every `error_field` is a real field, that every field is set by some valid
  case, and that both suites load it. Behaviour JSON cannot reach (the
  constructor) gets ordinary twinned tests below the loop.

A model whose vector file exists is shared whatever the project default, so
one project can mix them. Shared vectors suit models, data structures and
validation rules — data in, data or error out. Logic with collaborators
usually stays intent; see [techniques.md](techniques.md) before vectoring it.

## The known-good example

`${CLAUDE_PLUGIN_ROOT}/templates/sync-model/` holds a `UserProfile` pair that
passes `flutter test`, `flutter analyze`, `pytest` and `ruff`, and leaves the
hook quiet:

| Path | What |
|---|---|
| `common/lib/models/user_profile.dart` | Dart model: validating factory, `fromJson`, `toJson`, value equality |
| `common/lib/models/model_validation_error.dart` | `ModelValidationError(field, message)` + strict JSON readers |
| `common/backend/models/user_profile.py` | Pydantic v2 model, strict types, `to_json()` |
| `intent/test/models/user_profile_test.dart`, `intent/backend/tests/test_user_profile.py` | Twinned tests |
| `shared/test_vectors/user_profile.json`, `vectors.schema.json` | The vectors and their format |
| `shared/test/support/test_vectors.dart`, `shared/backend/tests/vectors.py` | Loaders |
| `shared/test/models/…`, `shared/backend/tests/…` | Vector runners |

Every new pair is built from these files, not from scratch.

## Create a synced model

1. **Prerequisites.** `backend/pyproject.toml` exists (else run
   `/fastapi-setup` or `/setup-project` first). If `lib/models/model_validation_error.dart`
   is missing, copy it from `common/`. For the shared flavour, copy
   `test_vectors/vectors.schema.json` and both loaders if missing. If
   `.sync-model.json` is missing, ask intent or shared and write it.
2. **Contract first.** Agree with the user, in one table: each wire field
   (snake_case), type, required/optional/default, and its rules (trim, case,
   length, range, pattern, enum values). Unknown keys are ignored; null
   optional fields are omitted from JSON. Done when every field has a type and
   every rule is stated.
3. **Tests.** Every pair starts with the standard case set, named
   identically on both sides: **`constructs with valid fields`** (build with
   every field set, assert each value stuck) and **`round-trips through
   serialization`** (`fromJson`/`toJson` ↔ `model_validate`/`to_json`). Then
   one case per rule. Intent: both test files, every case twinned. Shared:
   `test_vectors/<stem>.json` — the round-trip and at least one valid case
   setting every field, one invalid case per rule, each invalid case breaking
   exactly one field — then the two thin runners, with `constructs with valid
   fields` below the loop on both sides. Done when `flutter test` and
   `uv run pytest` both fail for the missing model.
4. **Models.** Read the example model on each side and follow its structure
   exactly; change only names, fields and rules. Done when both suites are
   green.
5. **Check.** `flutter analyze`, `cd backend && uv run ruff check .`, and the
   hook is quiet on the two model files.

### Parity rules

These are where the two sides silently disagree. The example handles each:

- **Strict types on the Python side** (`StrictInt`, `StringConstraints(strict=True)`).
  Dart's `is int` never coerces; lax Pydantic turns `"30"` into `30`.
- **One regex string, copied to both sides.** Library validators (`EmailStr`)
  disagree with any Dart equivalent.
- **Length in code points:** Dart `.runes.length`, Python `len()`. Dart
  `.length` counts an emoji as two.
- **Explicit null ≠ absent** for fields with a default: Pydantic rejects
  `"role": null`, so Dart checks `containsKey`.
- **Errors name the wire field.** `ModelValidationError.field` and Pydantic's
  `loc[0]` are both snake_case; tests assert on the field, never the message.
- **Validation in the constructor.** The Dart factory validates, so a model
  built in the app obeys the same rules as one decoded from the API.

## Audit

1. Read `.sync-model.json` if present: `tests` flavour, `pairs`, `ignore`.
2. List models on each side: `^class` and `^enum` under `lib/**/*.dart`,
   `^class` under `backend/**/*.py` (excluding tests).
3. For each pair (declared or name-matched), compare fields normalized
   (`emailAddress` ≡ `email_address`, `APP_STORE` ≡ `appStore`).
4. For each pair, check tests by stem — `test/**/<stem>_test.dart` ↔
   `backend/tests/test_<stem>.py` — then the slugged case lists (intent) or
   the vector file (shared), as the hook does.
5. Present one table: model, flavour, fields in sync, tests in step. For each
   drifted pair show the specific fields and cases, not a count.

## Configure

```json
{
  "tests": "intent",
  "pairs": [
    { "dart": "lib/models/user.dart", "python": "backend/models/account.py" }
  ],
  "ignore": ["AppChannel"]
}
```

- **Names differ across sides** → add a `pairs` entry.
- **Model is intentionally one-sided** → add its name to `ignore`.
- **Switch one model to shared** → write its vector file and runners, delete
  the hand-written twins that the vectors now cover.
- **Switch the project default** → change `tests`.

The file is optional: without it, name matching and intent apply. Re-run the
audit after any change.

## Fix drift

Change the side that is behind — usually the backend leads — then the tests:
port the missing case to the other side under the identical name (intent) or
add cases to the vector file (shared). Finish on both suites green and the
hook quiet.

## Other languages

Case extraction is per language and every side slugs to the same form. A
TypeScript/JavaScript side (Jest/Vitest `it('...')` / `test('...')`
descriptions) plugs into the same comparison when a web or Node half joins
the project, and the vector format works there unchanged.
