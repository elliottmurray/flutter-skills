---
name: flutter-sdk-check
description: >
  Check for a newer Flutter stable SDK and bump the pinned flutter-version
  across CI workflows. Trigger on /flutter-sdk-check, Flutter version bump,
  or an out-of-date pin.
user_invocable: true
---

# Flutter SDK Check

**Not shipped yet.** `/setup-project` already copies
`flutter-sdk-update.yml`, which does the same check on a Monday cron.

## What this skill will do

- Read the pin from `.github/workflows/flutter.yml`
- Compare to the latest Flutter **stable**
- Bump `flutter-version` in every workflow in the pin list
- Open a PR (locally or via the companion Action)

Keep the local skill and `flutter-sdk-update.yml` in sync. If the workflow
is missing, recreate it first.
