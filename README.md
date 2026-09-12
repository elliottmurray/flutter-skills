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
| `/complexity` | Implemented — report, ratchet, hotspot pass |
| `/feature-flags` | Implemented — add / graduate / delete Remote Config flags |
| `/flutter-sdk-check` | Implemented — bump pinned `flutter-version` |
| `/pr-review` | Implemented — risk rubric; `@claude` workflow unchanged |
| `/ios-ci-setup` | Stub |
| `/self-hosted-runner` | Stub |
| `/firebase-setup` | Implemented — console project, iOS app, RC `app_channel` |
| `/app-check` | Stub |
| `/fastapi-setup` | Stub |
| `/verify` | Implemented — generic VM Service tap / eval / screenshot |

See [CATALOG.md](CATALOG.md) for what each skill does.

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
