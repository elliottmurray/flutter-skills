---
name: setup-project
description: >
  Bootstrap a Flutter iOS project with CI, lint, unit tests, a complexity
  ratchet, and an integration-test harness. Use when the user wants to start
  a new Flutter app, run /setup-project, or install flutter-ship templates
  into an empty or new repo.
user_invocable: true
---

# Setup Project

Interview first, then create (if needed), render templates, install the git
hook. Do not clobber an existing non-empty project without confirmation.

Plugin root: `${CLAUDE_PLUGIN_ROOT}` (or the path of this skill's
`../../` directory). The renderer is
`${CLAUDE_PLUGIN_ROOT}/scripts/render.py`.

## 1. Interview (one question at a time)

Ask these in order. Do not invent extra questions.

1. **App name** and **iOS bundle id** (e.g. `com.example.myapp`).
2. **Firebase Console?** If yes, also: Remote Config (hooks feature flags)
   and App Check — treat both as yes unless they opt out.
3. **Backend:** FastAPI (drop the thin template) / other (prompt only, no
   files) / none.
4. **iOS release CI now**, or later (`/ios-ci-setup`)? If now, ask for
   Apple Team ID if they have it; otherwise leave `YOUR_TEAM_ID`.
5. **Self-hosted Mac runner now**, or later (`/self-hosted-runner`)? If now,
   ask for the runner label (default suggestion: `app-runner`). If later,
   `runs-on` stays `macos-latest`.

Defaults you may assume after they answer:

| Placeholder | Default |
|---|---|
| `FLUTTER_VERSION` | `3.47.2` |
| `RUNNER_LABEL` | `macos-latest` (or `[self-hosted, macOS, <label>]` if they want a runner now) |
| `APPLE_TEAM_ID` | `YOUR_TEAM_ID` |

Derive `PACKAGE_NAME` by lowercasing the app name and replacing non-alphanumerics
with `_`. `render.py` does this if you omit `--package-name`.

## 2. Confirm before writing

If the destination already has files other than `.git`, `README.md`, or
`.gitignore`, stop and ask. Do not overwrite `lib/main.dart` or an existing
`pubspec.yaml` from `flutter create`.

## 3. Create the Flutter app if the directory is empty

Destination is the current workspace root unless they named another path.

Empty means no `pubspec.yaml`. Then:

```bash
flutter create --platforms=ios \
  --org <bundle-id-minus-last-segment> \
  --project-name <PACKAGE_NAME> \
  .
```

`--org` is every segment of the bundle id except the last
(`com.example.myapp` → `--org com.example`). If they already have a Flutter
app, skip `flutter create`.

Add the integration-test dependency if it is missing:

```bash
flutter pub add dev:integration_test --sdk=flutter
```

## 4. Render templates

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render.py" \
  --dest . \
  --app-name "<APP_NAME>" \
  --bundle-id "<BUNDLE_ID>" \
  --flutter-version 3.47.2 \
  --runner-label "<RUNNER_LABEL>" \
  --apple-team-id "<APPLE_TEAM_ID>" \
  --force
```

Add `--firebase` if they use Firebase. Add `--fastapi` if the backend is
FastAPI.

`render.py` copies `templates/common/` (and overlays), substitutes
`{{PLACEHOLDERS}}`, and installs `scripts/pre-commit` as
`.git/hooks/pre-commit` when `.git` exists.

If git is not initialized yet:

```bash
git init
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render.py" ... --force
```

Make the integration script executable:

```bash
chmod +x scripts/pre-commit scripts/run_integration_tests.sh scripts/complexity_sensor.py
```

## 5. iOS bundle id

If `flutter create` used `--org` correctly, skip. Otherwise set
`PRODUCT_BUNDLE_IDENTIFIER` in `ios/Runner.xcodeproj/project.pbxproj` to the
bundle id they gave.

## 6. Backend = other

Do not invent a server. Say: FastAPI is the templated option; for anything
else they should point you at the repo or docs, and `/fastapi-setup` later
can still add App Check-style middleware patterns.

## 7. Print "run these next"

After a successful render, print this list (drop lines that already landed):

```
Done. Next:

  flutter test
  flutter analyze
  ./scripts/run_integration_tests.sh    # iOS Simulator; write more tests in integration_test/

Skills when you need them:
  /tdd
  /ios-ci-setup          # signing secrets + Apple portal
  /self-hosted-runner    # Mac LaunchAgent, swap runs-on
  /firebase-setup        # console + Remote Config app_channel
  /app-check             # DeviceCheck / App Attest + backend flag
  /fastapi-setup         # uv, ruff, pytest, optional Docker
  /verify                # drive the simulator from Claude
  /complexity            # ratchet cyclomatic complexity
  /flutter-sdk-check     # bump the pinned Flutter version
  /pr-review             # review a PR
```

If they chose iOS CI now, remind them `/ios-ci-setup` still has to put
secrets in GitHub — this skill only wrote `release.yml`.

If they chose a self-hosted runner now, remind them `/self-hosted-runner`
still has to register the machine — this skill only set `runs-on`.

## 8. Do not

- Copy app-specific agents or one-off guards from another project
- Bake `--dart-define` into `release.yml`
- Run `flutter create` on top of an existing app
- Skip the interview
