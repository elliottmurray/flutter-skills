---
name: verify
description: >
  Drive a Flutter iOS Simulator build from Claude — launch, tap, eval Dart
  via the VM Service, screenshot. Trigger on /verify, simulator drive,
  or end-to-end UI checks.
user_invocable: true
---

# Verify

Interactive driver for a **booted iOS Simulator**. Integration tests stay
on `./scripts/run_integration_tests.sh`. This skill is for a live
`flutter run` plus tap / eval / screenshot over the Dart VM Service.

The driver is generic: **tap**, **eval**, **screenshot**, widget **tree**,
background / kill / relaunch. No app-specific subcommands (no domain
helpers, no "do the happy path" wrappers). If a flow needs those, write
an integration test instead.

If the **Dart/Flutter MCP server** is connected, prefer its tools
(`launch_app`, `get_widget_tree`, `tap`) for tree and tap — they are better
integrated and `flutter-add-integration-test` upstream knows how to turn that
session into a test. Use this driver when there is no MCP server, or for the
iOS-specific parts it does not reach: `simctl` device screenshots including
native UI, background / foreground, relaunch by bundle id, and choosing a
simulator UDID.

## Driver

Prefer the copy in the app repo (installed by `/setup-project`):

```bash
python3 scripts/sim_driver.py --help
```

If that file is missing, use the plugin copy (and copy it into the app
so later invocations match CI machines):

```bash
cp "${CLAUDE_PLUGIN_ROOT}/scripts/sim_driver.py" scripts/sim_driver.py
chmod +x scripts/sim_driver.py
python3 scripts/sim_driver.py --help
```

State lives at `.sim_driver_state.json` (gitignored). Stdlib only.

## 1. Boot and run

From the Flutter app root:

```bash
python3 scripts/sim_driver.py boot
python3 scripts/sim_driver.py run --target lib/main.dart
python3 scripts/sim_driver.py status
```

`run` starts `flutter run --machine` on the booted simulator, waits for
`app.debugPort`, and stores the VM Service WebSocket URL. If a session is
already running, `status` is enough — do not stack a second `flutter run`.

Need a specific device:

```bash
python3 scripts/sim_driver.py boot --udid "$SIMULATOR_UDID"
python3 scripts/sim_driver.py run --device "$SIMULATOR_UDID"
```

### iPad

`boot` with no `--udid` reuses whatever is already booted, and otherwise
creates an **iPhone**. For iPad, find or create the simulator yourself and pass
its UDID:

```bash
xcrun simctl list devices available | grep -i ipad
python3 scripts/sim_driver.py boot --udid "$IPAD_UDID"
python3 scripts/sim_driver.py run --device "$IPAD_UDID"
python3 scripts/sim_driver.py screenshot screenshots/verify-ipad.png
```

Running a layout change against an iPhone and an iPad simulator is the cheap
check on the responsive work that `flutter-build-responsive-layout` designs.
Remember `kill` between the two — one `flutter run` at a time.

## 2. Drive

Coordinates are **logical pixels** in the Flutter view, origin top-left:

```bash
python3 scripts/sim_driver.py tap 120 340
python3 scripts/sim_driver.py eval 'WidgetsBinding.instance.platformDispatcher.views.length'
python3 scripts/sim_driver.py tree
python3 scripts/sim_driver.py screenshot screenshots/verify.png
```

`eval` compiles as if it appeared in Flutter's widgets binding library,
so `WidgetsBinding`, `Offset`, and similar names resolve. Keep
expressions short and side-effect explicit. Do not eval app-private
types unless `tree` / a prior eval showed they are in scope.

`screenshot` prefers `simctl io screenshot` (full device, including
native UI). It falls back to `ext.flutter.inspector.screenshot` if
simctl fails.

Read the PNG (and the widget tree) before the next tap. Do not hammer
taps blindly.

## 3. Background, kill, relaunch

```bash
python3 scripts/sim_driver.py background    # Simulator Home (Cmd-Shift-H)
python3 scripts/sim_driver.py foreground    # simctl launch by bundle id
python3 scripts/sim_driver.py kill          # stop flutter run; app may stay
python3 scripts/sim_driver.py shutdown      # kill + simulator shutdown if we created it
```

`foreground` needs `--bundle-id` on `run` (or a `PRODUCT_BUNDLE_IDENTIFIER`
it can grep from `ios/Runner.xcodeproj/project.pbxproj`). If launch fails,
ask for the bundle id rather than guessing a different product.

## 4. When to stop using this

- Assertions that must not regress → `integration_test/` + `/tdd`.
- CI → `./scripts/run_integration_tests.sh`, not this driver.
- Physical devices → out of scope (Simulator only).

## Do not

- Add app-named commands to `sim_driver.py`.
- Commit `.sim_driver_state.json`.
- `eval` secrets, tokens, or `String.fromEnvironment` values into the
  chat log.
- Drive a physical device UDID.
