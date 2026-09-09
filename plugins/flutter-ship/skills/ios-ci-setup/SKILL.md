---
name: ios-ci-setup
description: >
  Walk through Apple Distribution certs, App Store provisioning profiles,
  and App Store Connect API keys, then upload GitHub Actions secrets for
  iOS release CI. Trigger on /ios-ci-setup, signing failures, or setting
  up TestFlight / App Store upload.
user_invocable: true
---

# iOS CI Setup

**Not shipped yet.** `/setup-project` already writes `release.yml`. This
skill will put the secrets in GitHub.

## What this skill will do

Wizard + Chrome on [developer.apple.com](https://developer.apple.com) after
the user completes Apple 2FA. Confirm before every `gh secret set`.

Secrets: `IOS_DISTRIBUTION_CERT_P12`, `IOS_DISTRIBUTION_CERT_PASSWORD`,
`IOS_PROVISIONING_PROFILE`, `IOS_PROVISIONING_PROFILE_UUID`,
`APP_STORE_CONNECT_API_KEY_ID`, `APP_STORE_CONNECT_ISSUER_ID`,
`APP_STORE_CONNECT_API_KEY_CONTENT`.

The certificate private key still needs Xcode → Manage Certificates or
Keychain export. Do not promise unattended portal automation.
