---
name: flutter-sdk-check
description: >
  Check for a newer Flutter stable SDK and bump the pinned flutter-version
  across CI workflows. Trigger on /flutter-sdk-check, Flutter version bump,
  or an out-of-date pin.
user_invocable: true
---

# Flutter SDK Check

Local counterpart to `.github/workflows/flutter-sdk-update.yml`. The file
list and the bump logic must stay in sync with that workflow. Dart is
bundled with Flutter — Flutter is the only pin. Touch `pubspec.yaml`'s
`sdk:` constraint only when a dependency requires a higher Dart SDK.

## 1. Confirm the companion Action exists

```bash
test -f .github/workflows/flutter-sdk-update.yml \
  && echo "OK: periodic Action present" \
  || echo "MISSING — recreate flutter-sdk-update.yml before proceeding"
```

If the workflow is missing, copy it from flutter-ship
(`templates/common/.github/workflows/flutter-sdk-update.yml`) and stop.
Do not bump pins locally without the Action.

**Plugin-repo exception.** If this repo *is* flutter-ship (templates use
`{{FLUTTER_VERSION}}` and there is no app-level `flutter.yml` pin), skip
the Action check and jump to [Maintaining flutter-ship](#maintaining-flutter-ship).

## 2. Read the pin list from the workflow

Do not invent a fourth file. Use `PINNED_FILES` from
`flutter-sdk-update.yml` (today: `flutter.yml`, `release.yml`,
`integration_tests.yml`).

```bash
# Current pin (same grep as the Action)
current=$(grep -m1 "flutter-version:" .github/workflows/flutter.yml \
  | sed -E "s/.*'([0-9.]+)'.*/\1/")

read latest dart < <(curl -sSf \
  https://storage.googleapis.com/flutter_infra_release/releases/releases_linux.json \
  | python3 -c "import json,sys; d=json.load(sys.stdin); h=d['current_release']['stable']; r=next(x for x in d['releases'] if x['hash']==h); print(r['version'], r.get('dart_sdk_version','?'))")

echo "Pinned in CI: $current | Latest stable: $latest (Dart $dart)"

grep -n "flutter-version:" .github/workflows/flutter.yml \
  .github/workflows/release.yml .github/workflows/integration_tests.yml
```

Report both versions. If every pin already equals `$latest`, say
**up to date** and stop.

If the three files disagree with each other, fix that first (they must
all match `$current`) before considering a bump.

## 3. Apply the bump

Only when `$latest` is strictly newer (`sort -V`). Never downgrade.
Confirm with the user first.

```bash
# macOS sed. On Linux CI the Action uses sed -i without ''.
for f in .github/workflows/flutter.yml \
         .github/workflows/release.yml \
         .github/workflows/integration_tests.yml; do
  sed -i '' -E "s/(flutter-version: ')[0-9.]+(')/\1$latest\2/" "$f"
done

# No file should still carry the old pin.
if grep -rn "flutter-version: '$current'" \
     .github/workflows/flutter.yml \
     .github/workflows/release.yml \
     .github/workflows/integration_tests.yml; then
  echo "STALE PIN — fix before committing"
else
  echo "All pins updated to $latest"
fi
```

If you change this loop, change `PINNED_FILES` and the `sed` in
`flutter-sdk-update.yml` in the same commit.

## 4. Open a PR

Never commit the bump to `main`.

```bash
git checkout -b chore/flutter-sdk-$latest
git add .github/workflows/flutter.yml \
        .github/workflows/release.yml \
        .github/workflows/integration_tests.yml
git commit -m "chore: bump Flutter SDK to $latest"
git push -u origin HEAD
gh pr create --label dependencies \
  --title "chore: bump Flutter SDK $current → $latest" \
  --body "$(cat <<EOF
## Summary

- [ ] Flutter app
- [ ] Python backend
- [x] CI / docs / other

Bumps the pinned Flutter SDK from $current to $latest (Dart $dart).

## Testing

- [x] N/A — CI runs the suite against the new pin
EOF
)"
```

Write the body explicitly so the repo PR template still applies.
`--fill` skips it.

After merge, install the same SDK locally (`flutter upgrade` or the
project's version manager) so local matches CI.

## GH_PAT (scheduled Action)

The Action edits `.github/workflows/*`. GitHub rejects those pushes from
`GITHUB_TOKEN`. The repo secret **`GH_PAT`** needs Contents, Pull
requests, and Workflows write (fine-grained) or `repo` + `workflow`
(classic).

Without `GH_PAT` the Monday job fails at "Require GH_PAT" with setup
text in the log. Add the secret on this repository, then re-run
**Actions → Flutter SDK Update Check**.

## Maintaining flutter-ship

When this skill runs inside the plugin repo (no rendered `flutter.yml`):

1. Fetch `$latest` with the same `releases_linux.json` snippet as above.
2. Bump `DEFAULTS["FLUTTER_VERSION"]` in `plugins/flutter-ship/scripts/render.py`.
3. Bump the default in `plugins/flutter-ship/skills/setup-project/SKILL.md`
   (table + `--flutter-version` example). Templates already use
   `{{FLUTTER_VERSION}}` — do not hardcode a version in the workflow
   templates.
4. Open a PR on a `chore/flutter-sdk-$latest` branch.

Keep `flutter-sdk-update.yml`'s version-detection script identical to
the commands in this skill.
