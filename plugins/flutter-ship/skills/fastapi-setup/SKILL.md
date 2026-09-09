---
name: fastapi-setup
description: >
  Expand or create a FastAPI backend with uv, ruff, pytest, and optional
  App Check. Trigger on /fastapi-setup, starting a Python API, or when
  the user picked a non-FastAPI backend and wants the templated stack.
user_invocable: true
---

# FastAPI Setup

**Not shipped yet.** `/setup-project` already drops a thin `backend/`
(`/health` + App Check dependency) when the user chooses FastAPI.

## What this skill will do

- `uv` project, ruff, pytest
- Optional Docker
- App Check middleware wired on routes that need it
- If the user is on a different backend, prompt only and reuse these
  patterns (health, env flags, CI job) without inventing a full port
