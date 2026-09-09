# flutter-skills

A Claude Code marketplace with one plugin, **flutter-ship**. Install it, then
run `/setup-project` in an empty directory (or a new Flutter repo) to get CI,
lint, unit tests, a complexity ratchet, and an iOS integration-test harness
so the next thing you write is a test, not a workflow.

Cursor can consume the same `SKILL.md` files later. This first ship is
Claude Code only.

## Install

```text
/plugin marketplace add /path/to/flutter-skills
/plugin install flutter-ship@flutter-skills
```

Once this repo is on GitHub:

```text
/plugin marketplace add <github-org-or-user>/flutter-skills
/plugin install flutter-ship@flutter-skills
```

## What you get

| Skill | Status |
|---|---|
| `/setup-project` | Implemented — interview, `flutter create`, templates, pre-commit |
| `/tdd` | Implemented — Flutter red-green-refactor |
| `/feature-flags` | Stub |
| `/ios-ci-setup` | Stub |
| `/self-hosted-runner` | Stub |
| `/firebase-setup` | Stub |
| `/app-check` | Stub |
| `/fastapi-setup` | Stub |
| `/verify` | Stub |
| `/complexity` | Stub (the sensor script already ships with `/setup-project`) |
| `/flutter-sdk-check` | Stub |
| `/pr-review` | Stub |

See [CATALOG.md](CATALOG.md) for what each stub will do.

## After `/setup-project`

```bash
flutter test
flutter analyze
./scripts/run_integration_tests.sh   # iOS Simulator
```

Docs-only commits skip the Mac integration job. App / native / pubspec /
integration-test diffs run it.

## License

MIT
