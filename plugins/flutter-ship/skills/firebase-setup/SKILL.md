---
name: firebase-setup
description: >
  Help create a Firebase project, register the iOS app, and set up Remote
  Config with an app_channel TestFlight condition. Trigger on /firebase-setup,
  Firebase Console, or Remote Config channel setup.
user_invocable: true
---

# Firebase Setup

**Not shipped yet.** `/setup-project` asks whether Firebase is in use and
copies the flag registry when yes.

## What this skill will do

Checklist / Chrome on the Firebase console:

- Create or select a project
- Register the iOS app (bundle id)
- Enable Remote Config
- Custom signal `app_channel` and a `TestFlight` condition
  (`app_channel` exactly matches `testflight`)
- Point the user at `/feature-flags` and `/app-check` for the next steps
