---
name: firebase-setup
description: >
  Help create a Firebase project, register the iOS app, and set up Remote
  Config with an app_channel TestFlight condition. Trigger on /firebase-setup,
  Firebase Console, or Remote Config channel setup.
user_invocable: true
---

# Firebase Setup

Checklist plus Chrome on the [Firebase console](https://console.firebase.google.com).
`/setup-project --firebase` copies the flag registry, `app_channel.dart`,
and `docs/feature-flags.md`. This skill creates the **cloud** side and
drops `GoogleService-Info.plist`.

`/feature-flags` owns registry add/graduate/delete. `/app-check` owns
DeviceCheck / App Attest. Do not do those jobs here.

## 1. Confirm the app side

```bash
test -f lib/config/flag_registry.dart && echo "OK: registry" || echo "MISSING registry"
test -f lib/config/app_channel.dart && echo "OK: app_channel" || echo "MISSING app_channel"
grep -m1 PRODUCT_BUNDLE_IDENTIFIER ios/Runner.xcodeproj/project.pbxproj
```

If the Dart files are missing, copy the firebase templates with
`render.py --firebase --force` (same `--app-name` / `--bundle-id` as
setup) or run `/setup-project` with Firebase enabled. Do not invent a
second flag map.

Bundle id in the console must match the iOS target **exactly**.

## 2. Chrome

Needs a Google account that can create a Firebase project, and the Claude
in Chrome extension installed and permitted for
`console.firebase.google.com`. Without the extension, run every step below
as a spoken checklist — name the page and the button, wait for them to
confirm, ask them to read values back. The result is the same; do not stop
for a missing extension.

With it, open [console.firebase.google.com](https://console.firebase.google.com).
If Google 2FA or an account picker appears, wait. Drive Chrome only after
they are inside the console. If a click misses, fall back to naming the
button and waiting.

## 3. Project

Create a project or select an existing one. Google Analytics is optional;
do not turn it on just to finish this skill.

## 4. Register the iOS app

Project settings → **Add app** → iOS:

1. iOS bundle ID = the Flutter iOS bundle id.
2. App nickname = the human app name.
3. App Store ID can wait.
4. Download `GoogleService-Info.plist`.
5. Place it at `ios/Runner/GoogleService-Info.plist` (Flutter's default
   lookup). Confirm it is referenced by the Xcode project; if `flutter
   run` later complains it is missing, add it to the Runner target in
   Xcode.
6. Skip the console's sample `Firebase.initializeApp` snippet if the app
   already initializes Firebase.

Do not commit a plist from a different bundle id.

## 5. Packages

Add what the registry and channel code need, if missing:

```bash
flutter pub add firebase_core firebase_remote_config package_info_plus
```

`Firebase.initializeApp` must run before any Remote Config fetch. Publish
`app_channel` (`dev` / `testflight` / `appStore`) as a custom signal
**before** that fetch — `resolveAppChannel` in `lib/config/app_channel.dart`,
fed by `PackageInfo.fromPlatform().installerStore`.

Unknown installers resolve to `appStore` on purpose. Do not bake
`CHANNEL` into `release.yml`.

## 6. Remote Config + `app_channel` condition

In the console: **Build → Remote Config** (enable if prompted).

1. Open **Conditions** (or the condition builder on a parameter).
2. Ensure a **custom signal** named `app_channel` (string) exists. The
   running app sends this; the console does not invent values.
3. Create a condition named exactly **`TestFlight`**.
4. Rule: `app_channel` **exactly matches** `testflight`.
5. Save. Publish the template even if it has no parameters yet so the
   condition exists for `/feature-flags`.

`/feature-flags` will add a `TestFlight` conditional value on every
`release` tier flag. If this condition is missing, that skill stops.

Do not create a second condition named `testflight`, `Testflight`, or
`channel == TestFlight`. The name is `TestFlight`; the signal value is
`testflight`.

## 7. Done

Print:

```
Firebase project: <id>
iOS bundle id:    <id>
Plist:            ios/Runner/GoogleService-Info.plist
RC condition:     TestFlight (app_channel == testflight)

Next:
  /feature-flags   # add / graduate / delete registry flags
  /app-check       # DeviceCheck / App Attest + debug tokens
```

## Do not

- Put `DISABLE_FIREBASE_APP_CHECK` or `CHANNEL` in Remote Config. They
  are build-config defines (`kBuildConfigDefines` in the registry).
- Publish production flag defaults that turn a `release` feature on for
  App Store users (that is `/feature-flags` graduate).
- Download an Android `google-services.json` for an iOS-only app.
- Rewrite `flag_registry.dart` as part of this skill.
