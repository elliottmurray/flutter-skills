# Skill catalog

What each skill does and whether it ships in this version.

| Skill | Status | Needs | What it does |
|---|---|---|---|
| `/setup-project` | **Shipped** | — | Interview, `flutter create`, render templates, install git hook |
| `/tdd` | **Shipped** | standalone | Red-green-refactor for Flutter |
| `/complexity` | **Shipped** | `/setup-project` | Report / ratchet / occasional hotspot pass. Sensor + PostToolUse hook |
| `/feature-flags` | **Shipped** | `/setup-project --firebase` | Add / graduate / delete registry flags; TestFlight `app_channel` condition |
| `/flutter-sdk-check` | **Shipped** | `/setup-project` | Bump pinned `flutter-version` across workflows; stay in sync with the Monday Action |
| `/pr-review` | **Shipped** | standalone | Generic rubric + keep `claude.yml`; danger areas from the app `CLAUDE.md` |
| `/architecture` | **Shipped** | standalone | MVVM + repository (Flutter) and transport/logic/data (API) checked against the diff from `HEAD`; backend rules in `backends/*.md` |
| `/ios-ci-setup` | **Shipped** | `/setup-project` | Wizard + Chrome on developer.apple.com after 2FA; confirm before `gh secret set`. Cert private key still needs Xcode/Keychain |
| `/self-hosted-runner` | **Shipped** | `/setup-project` | Walk a local Mac: `config.sh`, LaunchAgent (not `svc.sh`), `pmset`, swap `runs-on` |
| `/firebase-setup` | **Shipped** | `/setup-project --firebase` | Checklist / Chrome: project, iOS app, RC `app_channel` condition |
| `/app-check` | **Shipped** | `/firebase-setup` | DeviceCheck / App Attest, debug tokens, backend enforcement flag |
| `/fastapi-setup` | **Shipped** | standalone | Expand the stub: uv, ruff, pytest, Docker optional |
| `/verify` | **Shipped** | standalone | Generic VM Service driver (tap / eval / screenshot) |

The complexity PostToolUse hook is advisory and stays quiet when the project has no sensor. Pre-commit is a **git** hook, installed by `/setup-project`.

**Needs** is what must already exist for the skill to run. The `standalone`
ones work on any Flutter repo; the rest expect templates that `/setup-project`
renders, and will stop and tell you so rather than guess. On a brownfield app,
start with the standalone column.

See the README for how these sit alongside
[flutter/agent-plugins](https://github.com/flutter/agent-plugins).
