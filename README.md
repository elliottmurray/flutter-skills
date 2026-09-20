# flutter-skills

A Claude Code marketplace with one plugin, **flutter-ship**. Install it, then
run `/setup-project` in an empty directory (or a new Flutter repo) to get CI,
lint, unit tests, a complexity ratchet, and an iOS integration-test harness
so the next thing you write is a test, not a workflow.

Cursor can consume the same `SKILL.md` files later. This first ship is
Claude Code only.

## Requirements

| | Why |
|---|---|
| macOS with full Xcode | `flutter build ipa`, the iOS Simulator, and the Keychain that holds your signing key. Command Line Tools alone is not enough — `xcode-select -p` has to end in `Xcode.app` |
| Flutter SDK | `/setup-project` runs `flutter create`; the workflows pin a version |
| `gh`, authenticated | Every skill that touches CI shells out to it. The token needs `repo` and `workflow` scope |
| A GitHub repo with Actions enabled | The rendered workflows are GitHub Actions. Nothing here emits GitLab CI, Bitrise or Codemagic |

`release.yml` and the integration job run on `macos-latest`, billed at 10× the
minute rate on a private repo. `/self-hosted-runner` moves them to a Mac you own.

Shipping to TestFlight or the App Store also needs a paid **Apple Developer
Program** membership and an **Admin** or **Account Holder** role on the team.
A free Apple ID cannot create a distribution certificate, an App Store
provisioning profile, or an App Store Connect API key, so `/ios-ci-setup`
stops early without one. Everything else — tests, lint, complexity,
the simulator — works without paying Apple.

### Browsers are optional

`/ios-ci-setup`, `/firebase-setup` and `/app-check` walk cloud consoles. With
the Claude in Chrome extension installed, and permission granted for
`developer.apple.com`, `appstoreconnect.apple.com` and
`console.firebase.google.com`, Claude drives those pages. Without it each
skill falls back to naming the page and the button and waiting for you —
slower, same result. Either way you sign in and clear 2FA yourself; Claude
never handles your Apple or Google credentials.

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
Feel free to use both: they cover the build side of flutter. This is complimentary and focused more on the release or shipping.

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
