# Skill catalog

What each skill does and whether it ships in this version.

| Skill | Status | What it does |
|---|---|---|
| `/setup-project` | **Shipped** | Interview, `flutter create`, render templates, install git hook |
| `/tdd` | **Shipped** | Red-green-refactor for Flutter |
| `/complexity` | **Shipped** | Report / ratchet / occasional hotspot pass. Sensor + PostToolUse hook |
| `/feature-flags` | **Shipped** | Add / graduate / delete registry flags; TestFlight `app_channel` condition |
| `/flutter-sdk-check` | **Shipped** | Bump pinned `flutter-version` across workflows; stay in sync with the Monday Action |
| `/pr-review` | **Shipped** | Generic rubric + keep `claude.yml`; danger areas from the app `CLAUDE.md` |
| `/ios-ci-setup` | Stub | Wizard + Chrome on developer.apple.com after 2FA; confirm before `gh secret set`. Cert private key still needs Xcode/Keychain |
| `/self-hosted-runner` | Stub | Walk a local Mac: `config.sh`, LaunchAgent (not `svc.sh`), `pmset`, swap `runs-on` |
| `/firebase-setup` | Stub | Checklist / Chrome: project, iOS app, RC `app_channel` condition |
| `/app-check` | Stub | DeviceCheck / App Attest, debug tokens, backend enforcement flag |
| `/fastapi-setup` | Stub | Expand the stub: uv, ruff, pytest, Docker optional |
| `/verify` | Stub | Generic VM Service driver (tap / eval / screenshot) |

The complexity PostToolUse hook is advisory and stays quiet when the project has no sensor. Pre-commit is a **git** hook, installed by `/setup-project`.
