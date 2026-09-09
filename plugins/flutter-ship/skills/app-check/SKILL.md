---
name: app-check
description: >
  Configure Firebase App Check (DeviceCheck / App Attest on iOS, debug
  tokens locally) and the backend enforcement flag. Trigger on /app-check,
  App Attest, DeviceCheck, or X-Firebase-AppCheck.
user_invocable: true
---

# App Check

**Not shipped yet.** The FastAPI stub already includes `verify_app_check`
with `FIREBASE_APP_CHECK_ENABLED` defaulting to false.

## What this skill will do

- Activate App Check in the Flutter app (debug provider locally, App
  Attest in release)
- Register debug tokens in the Firebase console
- Turn on backend enforcement (`FIREBASE_APP_CHECK_ENABLED=true`) once
  tokens work
- Document `DISABLE_FIREBASE_APP_CHECK` as a dart-define that cannot live
  in Remote Config (App Check gates the RC fetch)
