---
name: fastapi-setup
description: >
  Expand or create a FastAPI backend with uv, ruff, pytest, and optional
  App Check. Trigger on /fastapi-setup, starting a Python API, or when
  the user picked a non-FastAPI backend and wants the templated stack.
user_invocable: true
---

# FastAPI Setup

`/setup-project` already drops a thin `backend/` (`/health` + App Check
dependency) when the user chooses FastAPI. This skill fills that out:
**uv**, **ruff**, **pytest**, optional Docker, and App Check on the
routes that need it.

If they chose a **different** backend at setup, do not invent a port.
Reuse the patterns (health, env flags, CI job) only where they ask, and
leave their framework in place.

## 1. Decide the mode

1. **Expand** — `backend/` exists (from setup or an earlier copy).
2. **Create** — no `backend/`, they want the templated FastAPI stack.
3. **Prompt only** — they have Django / Rails / Go / etc. Stop after
   listing the patterns in [Other backends](#other-backends).

Ask if it is unclear.

## 2. Create (if needed)

From the app repo, with the same placeholders `/setup-project` used:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render.py" \
  --dest . \
  --app-name "<APP_NAME>" \
  --bundle-id "<BUNDLE_ID>" \
  --fastapi \
  --force
```

`--force` overwrites template files in `backend/` and
`.github/workflows/python-api.yml`. Do not pass `--force` if they already
have a hand-written API they want to keep — expand in place instead.

`render.py` copies:

- `backend/main.py` — `/health` + `verify_app_check`
- `backend/pyproject.toml` — uv, ruff, pytest, httpx, firebase-admin
- `backend/sample.env` — `FIREBASE_APP_CHECK_ENABLED=false`
- `backend/tests/test_health.py`
- `backend/Dockerfile` — optional to *use*, always present in the template
- `.github/workflows/python-api.yml`

## 3. uv, ruff, pytest

Install [uv](https://docs.astral.sh/uv/) if `uv --version` fails
(`curl -LsSf https://astral.sh/uv/install.sh | sh`, or Homebrew).

```bash
cd backend
uv sync --group dev
uv run ruff check .
uv run pytest -q
uv run uvicorn main:app --reload --port 8000
```

`GET /health` must be `{"status":"ok"}` while App Check enforcement is
off. Keep `backend/.env` untracked (`.gitignore` already lists it). Copy
from `sample.env`.

Ruff config lives in `pyproject.toml` (`E`, `F`, `I`, `UP`, line length
100, py311). Do not add a second `ruff.toml` unless they ask.

CI: `python-api.yml` already runs `uv sync`, `ruff check`, `pytest`, and
a warn-only complexity `--check`. Do not replace that workflow in this
skill.

If they want the complexity sensor to see Python, `uv add --dev radon`
and use `/complexity`. Not required to finish this skill.

## 4. App Check on routes

`verify_app_check` is a FastAPI dependency. `/health` uses it so a probe
exercises the same gate as real routes.

- Enforcement off (`FIREBASE_APP_CHECK_ENABLED=false`): dependency no-ops.
- Enforcement on: missing or invalid `X-Firebase-AppCheck` → 401.

When adding routes, `Depends(verify_app_check)` on anything the Flutter
client calls that must not be anonymously hittable. Leave truly public
endpoints without it.

Do not set `FIREBASE_APP_CHECK_ENABLED=true` until `/app-check` has a
working debug token (and, for production, App Attest). The hosted env
var is the switch; do not commit `true` in `sample.env`.

`GOOGLE_APPLICATION_CREDENTIALS` (or ADC) is required only when
enforcement is on.

## 5. Docker (optional)

Ask. If yes, they already have `backend/Dockerfile` from the template.
Build from `backend/`:

```bash
cd backend
docker build -t app-api .
docker run --rm -p 8000:8000 \
  -e FIREBASE_APP_CHECK_ENABLED=false \
  app-api
```

Do not add Compose, Kubernetes, or a cloud vendor in this skill. If the
Dockerfile is missing (old project), copy it from
`${CLAUDE_PLUGIN_ROOT}/templates/fastapi/backend/Dockerfile`.

## 6. Confirm

```bash
cd backend && uv run ruff check . && uv run pytest -q
```

Print the run command and remind them `/app-check` owns turning
enforcement on.

## Other backends

If the API is not FastAPI:

- Health endpoint the Flutter client (and CI) can hit.
- An env flag to verify Firebase App Check, default off.
- A CI job that lints and tests **that** tree.
- Do not generate a parallel FastAPI app "for later" unless they ask.

## Do not

- Run `uv init` on top of the templated `pyproject.toml`.
- Add Puzzle / domain routes from some other repo.
- Wire App Check through Remote Config (`DISABLE_FIREBASE_APP_CHECK` is
  a dart-define on the client; the API flag is `FIREBASE_APP_CHECK_ENABLED`).
