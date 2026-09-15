---
name: app-check
description: >
  Configure Firebase App Check (DeviceCheck / App Attest on iOS, debug
  tokens locally) and the backend enforcement flag. Trigger on /app-check,
  App Attest, DeviceCheck, or X-Firebase-AppCheck.
user_invocable: true
---

# App Check

Turn on Firebase App Check for the iOS app, register debug tokens for
local work, and only then flip backend enforcement. The FastAPI template
already has `verify_app_check` with `FIREBASE_APP_CHECK_ENABLED` defaulting
to `false`.

A Firebase project and iOS app must exist. If `GoogleService-Info.plist`
is missing, stop and run `/firebase-setup` first.

`DISABLE_FIREBASE_APP_CHECK` is a dart-define. It cannot live in Remote
Config: App Check gates the RC fetch, so a kill switch served by RC
cannot disable the thing that loads RC.

## 1. Apple: App Attest + DeviceCheck

On [developer.apple.com](https://developer.apple.com) (after 2FA, same
Chrome rules as `/ios-ci-setup`):

1. Identifiers → the App ID → enable **App Attest**.
2. Keys → **+** → enable **DeviceCheck** → download the `.p8` (once).
   Note Key ID and Team ID. This key is for Firebase's DeviceCheck
   provider, not App Store Connect upload (`/ios-ci-setup` uses a
   different .p8).

Regenerate the App Store provisioning profile if enabling App Attest
invalidated it, then update GitHub secrets with `/ios-ci-setup` if those
are already in use.

Optional entitlement (production App Attest environment):

```xml
<key>com.apple.developer.devicecheck.appattest-environment</key>
<string>production</string>
```

in `ios/Runner/Runner.entitlements`. Skip if Xcode already injected it
from the capability.

## 2. Firebase console

Chrome: Project → **Build → App Check**.

1. Register the iOS app.
2. Production provider: **App Attest** with **DeviceCheck** fallback.
   Upload the DeviceCheck `.p8`, Team ID, and Key ID when the console
   asks.
3. Enable the **debug** provider for this app (simulator and
   `flutter run` on a desktop).
4. Leave **enforcement** off on Cloud products until a real-device token
   succeeds. Metrics first, then enforce.

## 3. Flutter client

```bash
flutter pub add firebase_core firebase_app_check
```

Copy the helper from the plugin after the package is in `pubspec.yaml`
(it imports `firebase_app_check`; copying it earlier breaks analyze):

```bash
mkdir -p lib/services
cp "${CLAUDE_PLUGIN_ROOT}/templates/app-check/lib/services/app_check_util.dart" \
   lib/services/app_check_util.dart
```

Call `activateAppCheck()` **after** `Firebase.initializeApp()` and
**before** the first Remote Config fetch. Do not invent a second helper
if the app already activates App Check — wire the existing call to the
same order instead.

Debug builds use `AppleProvider.debug`. Release uses
`AppleProvider.appAttestWithDeviceCheckFallback`.

## 4. Debug tokens

`flutter run` on a simulator (or a debug device) and watch the log for:

```text
Firebase App Check Debug Token: <token>
```

Chrome: App Check → **Apps** → the iOS app → **Manage debug tokens** →
add that token. Until it is registered, debug traffic looks like
unverified.

For a one-off without tokens:

```bash
flutter run --dart-define=DISABLE_FIREBASE_APP_CHECK=true
```

Do not add that define to `release.yml`. Do not add it to
`kFlagRegistry`.

## 5. Backend enforcement

FastAPI template (`backend/sample.env`):

```text
FIREBASE_APP_CHECK_ENABLED=false
```

Keep it `false` until:

1. A simulator debug token is accepted (client log + App Check metrics).
2. A TestFlight or device build with App Attest / DeviceCheck shows
   verified requests.

Then set `FIREBASE_APP_CHECK_ENABLED=true` in the hosted environment
(not committed `.env`). `verify_app_check` reads `X-Firebase-AppCheck`.
Routes that should stay public must **not** `Depends(verify_app_check)`.

If there is no FastAPI backend, still do steps 1–4. Tell them how the
other API should verify the token (Firebase Admin `app_check.verify_token`)
without porting a whole server.

## 6. Confirm

- [ ] `lib/services/app_check_util.dart` present and called in the right order
- [ ] Debug token registered, **or** they are using `DISABLE_FIREBASE_APP_CHECK` locally on purpose
- [ ] Console enforcement still off until metrics look clean
- [ ] `FIREBASE_APP_CHECK_ENABLED` still false in git-tracked env samples
- [ ] Next real-device / TestFlight run will use App Attest, not debug

## Do not

- Enforce App Check on Remote Config or the API on the same day you first
  activate the client.
- Put `DISABLE_FIREBASE_APP_CHECK` in Remote Config.
- Reuse the App Store Connect `.p8` as the DeviceCheck key.
- Ship a debug provider in a release IPA (`kDebugMode` is the split).
