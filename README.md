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
| `/architecture` | Implemented — layer review of the diff, Flutter + backend |
| `/ios-ci-setup` | Implemented — Apple certs, profiles, GitHub secrets |
| `/self-hosted-runner` | Implemented — LaunchAgent runner, swap `runs-on` |
| `/firebase-setup` | Implemented — console project, iOS app, RC `app_channel` |
| `/app-check` | Implemented — DeviceCheck / App Attest, debug tokens |
| `/fastapi-setup` | Implemented — uv, ruff, pytest, Docker optional |
| `/verify` | Implemented — generic VM Service tap / eval / screenshot |

See [CATALOG.md](CATALOG.md) for what each skill does.

## Alongside the official plugins

The Flutter team ships [flutter/agent-plugins](https://github.com/flutter/agent-plugins),
which also pulls in [dart-lang/skills](https://github.com/dart-lang/skills).
Install both: they cover a different axis and are meant to sit side by side.

| | Covers |
|---|---|
| **flutter/agent-plugins** + **dart-lang/skills** | How to write Flutter and Dart — layout fixes, responsive layouts, `go_router`, localization, JSON, widget previews, pattern matching, coverage, FFI |
| **flutter-ship** | How to ship it on iOS — signing, TestFlight, Firebase, App Check, flags, CI, a complexity ratchet, review gates, a backend |

Those skills are generated from docs.flutter.dev, so they are stateless
technique: they never touch your repo's config or a cloud console. Nothing
there covers CI, code signing, App Store Connect, Remote Config, or App Check,
and their integration-test skill targets Chrome, Android and Firebase Test Lab
— not iOS.

Three skills sit close enough to need a word:

| Reach for | When |
|---|---|
| `flutter-apply-architecture-best-practices` | Building a new feature from scratch |
| `/architecture` | Reviewing what changed, including the client/API contract |
| `flutter-add-integration-test` | Driving the app through the Dart/Flutter MCP server |
| `/verify` | No MCP server, or you need `simctl` screenshots, backgrounding, relaunch by bundle id |
| `dart-add-unit-test`, `flutter-add-widget-test` | Test file layout, `package:test` idiom, mocks |
| `/tdd` | Red-green-refactor as a process, and pytest for the backend |

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
