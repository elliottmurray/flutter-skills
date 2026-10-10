# lastmile

A Claude Code plugin, and the marketplace that serves it, for the last mile
of a Flutter iOS app: everything between "it runs on my simulator" and
"it's on TestFlight". It writes CI workflows and config, installs hooks that
watch your edits, and walks the Apple and Firebase consoles with you.

Run `/setup-project` in an empty directory (or a new Flutter repo) and you get
CI, lint, unit tests, a complexity ratchet and an iOS integration-test harness
before you write any app code.

New here? [docs/getting-started.md](docs/getting-started.md) goes from an empty
directory to a Flutter app calling its own FastAPI backend on the simulator,
and explains where the Firebase credentials go on each side.

This first version is Claude Code only. The `SKILL.md` files are plain
Markdown, so Cursor could use them later.

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
stops early without one. Tests, lint, complexity and the simulator all work
without paying Apple.

### Chrome is optional

`/ios-ci-setup`, `/firebase-setup` and `/app-check` do most of their work in
the Apple and Firebase web consoles. With the Claude in Chrome extension
connected (`claude --chrome`), Claude clicks through those pages in your own
Chrome window while you watch and confirm each create. Without it, Claude
names the page and the button and waits for you. You sign in and clear 2FA
yourself either way. Claude never sees your Apple or Google password.

[docs/chrome.md](docs/chrome.md) covers setup, which sites to allow, what a
run looks like, and which steps stay with you.

## Install

```text
/plugin install lastmile --marketplace elliottmurray/lastmile
```

That adds this repo as a marketplace and installs the plugin in one step
(Claude Code 2.1.275 or later). On older versions:

```text
/plugin marketplace add elliottmurray/lastmile
/plugin install lastmile@lastmile
```

To work on the plugin from a clone, point the marketplace at the path:
`/plugin marketplace add /path/to/lastmile`.

Releases and the Anthropic directory listing: [docs/releasing.md](docs/releasing.md).

## What you get

Skills you use while building the app:

| Skill | What it does |
|---|---|
| `/setup-project` | Interview, `flutter create`, render templates, install the pre-commit hook |
| `/tdd` | Test-first loop for Flutter and pytest: failing test, make it pass, tidy, repeat |
| `/architecture` | Reviews the diff against MVVM + repository layers, and the client/API contract |
| `/sync-model` | Dart ↔ Python model pairs, with twinned tests or shared JSON vectors. A hook flags drift as you edit |
| `/localization` | gen-l10n, add languages (ARB + iOS plist), translate. A hook and a test keep ARBs in step with English |
| `/complexity` | Report, ratchet and hotspot pass. A hook warns as you edit |
| `/verify` | Drive the running simulator over the VM Service: tap, eval, screenshot |
| `/fastapi-setup` | Expand the backend stub: uv, ruff, pytest, optional Docker |

Skills you use to ship it:

| Skill | What it does |
|---|---|
| `/ios-ci-setup` | Apple certs, profiles and API key, then the GitHub secrets for `release.yml` |
| `/firebase-setup` | Firebase project, iOS app, Remote Config `app_channel` condition |
| `/app-check` | App Attest / DeviceCheck, debug tokens, backend enforcement |
| `/feature-flags` | Add, graduate and delete Remote Config flags |
| `/pr-review` | Risk rubric for PRs, alongside the `@claude` workflow |
| `/flutter-sdk-check` | Bump the pinned `flutter-version` across workflows |
| `/self-hosted-runner` | Run the Mac CI jobs on a Mac you own instead of `macos-latest` |

[CATALOG.md](CATALOG.md) lists what each skill needs before it will run.

## How this differs from the official Flutter plugin

The Flutter team ships [flutter/agent-plugins](https://github.com/flutter/agent-plugins)
(the `dart-flutter` plugin). It bundles the Dart MCP server and the
[dart-lang/skills](https://github.com/dart-lang/skills) set, generated from
docs.flutter.dev. Use both. They don't conflict.

The split is roughly this. The official skills teach Claude how to write
Flutter and Dart code: layout fixes, responsive layouts, `go_router`, JSON
serialization, widget previews, pattern matching, coverage, FFI. They are
technique and work the same in any Flutter project. They don't change your
project config, add hooks, or touch a cloud console.

lastmile is about one kind of project, a Flutter iOS app with an optional
Python backend, and it changes that project. It writes the CI workflows and
`analysis_options.yaml`, installs a pre-commit hook and three edit hooks
(complexity, model sync, ARB parity), and keeps them working. It also helps
while you build, but at the level of workflow and project rules rather than
Dart idiom: a test-first loop, a layer review of your diff, Dart and Python
models kept in step. And it covers the release side the official plugin
leaves out: signing, TestFlight, Firebase, App Check, Remote Config.

Where the two overlap:

| Official skill | lastmile | Use the official one for | Use lastmile for |
|---|---|---|---|
| `flutter-apply-architecture-best-practices` | `/architecture` | Designing a new feature | Reviewing what changed, including the backend contract |
| `flutter-setup-localization` | `/localization` | How gen-l10n works | Adding languages with the iOS plist entries, and the parity hook and CI check |
| `flutter-implement-json-serialization` | `/sync-model` | `fromJson`/`toJson` on the Dart side | Keeping a Dart model and its Python twin in step, tests included |
| `flutter-add-integration-test` | `/verify` | Driving the app through the Dart MCP server | No MCP server, or you need `simctl` screenshots, backgrounding, relaunch by bundle id |
| `dart-add-unit-test`, `flutter-add-widget-test` | `/tdd` | Test file layout, `package:test` idiom, mocks | The order you work in, plus pytest for the backend |

`/tdd` defers to the official test skills for the mechanics when they're
installed. The official integration-test skill targets Chrome, Android and
Firebase Test Lab, not the iOS Simulator.

## What it runs on your machine

**Hooks.** Three `PostToolUse` hooks run after Claude edits a file. Each is a
local `python3` script in `hooks/` that reads the edited file and files in
your project, prints an advisory message, and always exits 0. They make no
network calls and write nothing.

- `complexity_sensor_hook.py` runs your project's own
  `scripts/complexity_sensor.py` (copied in by `/setup-project`) on Dart and
  Python edits. Quiet if that script is absent.
- `sync_model_hook.py` warns when a Dart or Python model changes without its
  twin.
- `l10n_parity_hook.py` warns when ARB translation files drift apart.

**Scripts.** `scripts/render.py` copies `templates/` into your project when
`/setup-project` runs. `scripts/sim_driver.py` drives the app for `/verify`
by talking to the Dart VM Service on `localhost`.

**Commands the skills ask Claude to run.** `flutter`, `xcrun simctl`, `gh`
(for repository secrets and workflows, with confirmation first), `uv`, and
`git`. Skills that set up Apple or Firebase walk you through their web
consoles. Claude never handles your Apple or Google passwords.

The plugin sends no data anywhere itself.

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
