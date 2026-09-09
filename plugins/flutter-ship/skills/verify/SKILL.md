---
name: verify
description: >
  Drive a Flutter iOS Simulator build from Claude — launch, tap, eval Dart
  via the VM Service, screenshot. Trigger on /verify, simulator drive,
  or end-to-end UI checks.
user_invocable: true
---

# Verify

**Not shipped yet.** Integration tests already run via
`./scripts/run_integration_tests.sh`. This skill will add an interactive
VM Service driver.

## What this skill will do

- `flutter run` on a booted simulator
- Generic tap / eval / screenshot over the Dart VM Service
- Background / kill / relaunch via `simctl`
- Keep the driver generic — no app-specific helpers
