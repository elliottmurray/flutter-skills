# Project layout

By default the Flutter app owns the repo root and the FastAPI service lives in
`backend/`:

```
.                      # pubspec.yaml, lib/, test/, integration_test/, ios/
├── backend/           # FastAPI service
├── scripts/           # tooling — always at the repo root
├── docs/
└── .github/
```

The Flutter app sits at the root because `flutter`, `dart`, Xcode, the IDE run
configurations and `subosito/flutter-action` all resolve the package from the
working directory. Nesting it costs a `cd` on every command for no real gain
while there is only one Dart package.

## Changing the layout

`scripts/project_layout.py` is the single source of truth. Everything that
needs to know where code lives — the CI change classifier, the complexity
sensor, the pre-commit hook, the integration-test runner and the GitHub
workflows — asks it rather than hardcoding `lib/` or `backend/`.

To move the app into `app/` and rename the service to `api/`, add
`.flutter-ship.json` at the repo root:

```json
{
  "dart_packages": ["app"],
  "python_packages": ["api"]
}
```

then `git mv` the directories to match. Check the result with:

```bash
python3 scripts/project_layout.py --json
python3 scripts/ci_change_classifier.py --files app/lib/main.dart api/main.py
```

Environment variables override the file for a single command, which is how the
tests exercise alternate layouts:

```bash
FLUTTER_SHIP_DART_PACKAGES=app FLUTTER_SHIP_PYTHON_PACKAGES=api \
  python3 scripts/ci_change_classifier.py --files app/lib/main.dart
```

`COMPLEXITY_DART_PACKAGES` and `COMPLEXITY_PYTHON_ROOT` still work as
overrides for the complexity sensor.

## When a move is worth it

Not at a given root file count — the trigger is a *second Dart package*:
shared models between the app and a web admin, a `packages/api_client`, a
design system. At that point move to a Dart pub workspace (`workspace:` in
`pubspec.yaml`, Dart 3.6+) with `app/`, `packages/*` and `backend/`, and do it
in one commit.

## Still layout-coupled

`.github/workflows/release.yml` hardcodes `ios/` and `build/ios/ipa` in about
nine places (SPM and DerivedData cache keys, `Release.xcconfig`, the IPA
artifact paths). It is deliberately left alone: it is the signing and release
path, and it is easier to review as part of the move than to parameterise up
front. Update it in the same commit as the `git mv`.
