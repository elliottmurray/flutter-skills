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

`/setup-project` already writes `release.yml`. This skill puts the seven
signing secrets in GitHub so that workflow can build and upload an IPA.

The certificate **private key** is created on this Mac (Xcode or Keychain).
The Apple portal can issue a `.cer`; it cannot invent the matching key.
Do not promise unattended portal automation. After Apple 2FA, Chrome on
[developer.apple.com](https://developer.apple.com) is a click-through
helper, not a headless API client.

## Secrets `release.yml` expects

| GitHub secret | What it is |
|---|---|
| `IOS_DISTRIBUTION_CERT_P12` | Base64 of the Apple Distribution `.p12` (cert **and** private key) |
| `IOS_DISTRIBUTION_CERT_PASSWORD` | Password used when exporting that `.p12` |
| `IOS_PROVISIONING_PROFILE` | Base64 of the App Store `.mobileprovision` |
| `IOS_PROVISIONING_PROFILE_UUID` | Profile UUID (filename in `~/Library/MobileDevice/Provisioning Profiles`) |
| `APP_STORE_CONNECT_API_KEY_ID` | Key ID from App Store Connect |
| `APP_STORE_CONNECT_ISSUER_ID` | Issuer ID from App Store Connect |
| `APP_STORE_CONNECT_API_KEY_CONTENT` | Base64 of the `.p8` private key |

Confirm with the user before every `gh secret set`. Never `git add` these
files. Never paste full secret values into the PR body.

## 1. Prerequisites

### Apple account

Confirm these before opening the portal. None can be worked around from
this Mac, so stop and say which is missing rather than starting step 2.

- A paid **Apple Developer Program** membership. A free Apple ID cannot
  create an Apple Distribution certificate, an App Store provisioning
  profile, or an App Store Connect API key — the portal does not offer
  them. `security find-identity` passing says nothing about this.
- An **Admin** or **Account Holder** role on that team. A Developer role
  can make a certificate but cannot create the Team API key in step 5.
- For a real upload, the **app record already exists** in App Store
  Connect for this bundle id (Apps → **+** → New App). Step 7's dry run
  does not need it; the first TestFlight upload does.

### This Mac

```bash
xcode-select -p    # must end in Xcode.app, not CommandLineTools
xcodebuild -version
security find-identity -v -p codesigning | head
```

If `xcode-select -p` prints `/Library/Developer/CommandLineTools`, the
Xcode path in step 4 does not exist. Install Xcode, then
`sudo xcode-select -s /Applications/Xcode.app/Contents/Developer`.

Xcode also has to be **signed into an Apple ID on that team** (Xcode →
Settings → Accounts). Step 4 creates the private key through it.

### GitHub

```bash
gh auth status
```

The token needs `repo` and `workflow` scope — `gh auth status` lists what
it has, and `gh auth refresh -s workflow` adds a missing one. The repo
needs Actions enabled. `release.yml` builds on `macos-latest`, at 10×
minutes on a private repo; `/self-hosted-runner` moves that to a local Mac.

### Browser

Steps 2–5 read better with the Claude in Chrome extension installed and
permitted for `developer.apple.com` and `appstoreconnect.apple.com`.
Without it, run the same steps as a spoken checklist — name the page and
the button, wait for them to confirm. A missing extension is not a reason
to stop.

### The project

Read the bundle id and team id the workflows already use:

```bash
# Bundle id from the iOS project
grep -m1 PRODUCT_BUNDLE_IDENTIFIER ios/Runner.xcodeproj/project.pbxproj

# Team id placeholder in the rendered workflow
grep -n APPLE_TEAM_ID .github/workflows/release.yml || \
  grep -n teamID .github/workflows/release.yml
```

If `release.yml` still has `YOUR_TEAM_ID`, ask for the 10-character Team
ID (Apple Developer → Membership) and patch it before a real upload.

If they already have a Distribution `.p12`, an App Store profile, and an
App Store Connect `.p8`, skip to [Encode and set secrets](#6-encode-and-set-secrets).

## 2. Apple 2FA, then Chrome

Ask them to complete Apple two-factor authentication in the browser.
**Do not continue** until they say the session is unlocked.

Then open Chrome to
[developer.apple.com/account](https://developer.apple.com/account)
(Certificates, Identifiers & Profiles). If a click fails or the portal
challenges again, stop driving the browser and switch to a spoken
checklist — wait for them to confirm each page.

Do not call App Store Connect or the developer portal as an unattended
REST client. No `fastlane match` / `sigh` silent login in this skill.

## 3. App ID

Identifiers → App IDs. Create or reuse an **App ID** whose bundle id
matches the Flutter iOS target **exactly**.

Skip extra capabilities unless the app already needs them. App Attest
belongs to `/app-check`, not this step.

## 4. Distribution certificate (private key stays local)

Preferred path (private key is created on this Mac):

1. Xcode → Settings → Accounts → select the team → **Manage Certificates**.
2. **+** → **Apple Distribution**.
3. Keychain Access → **My Certificates** → the new **Apple Distribution**
   identity → Export → `.p12`. Set a password; that is
   `IOS_DISTRIBUTION_CERT_PASSWORD`.

If they generate a CSR and upload it on the portal instead, the matching
private key is the one Keychain created **with that CSR**. Downloading
only the `.cer` from the portal is not enough — codesign in CI will fail
with an empty identity.

Confirm the export contains a key:

```bash
openssl pkcs12 -in "$P12_PATH" -nokeys -passin pass:"$P12_PASSWORD" >/dev/null
openssl pkcs12 -in "$P12_PATH" -nocerts -passin pass:"$P12_PASSWORD" -passout pass:tmp >/dev/null
```

Both must succeed. If the second fails, re-export from **My Certificates**
(the identity with a disclosure triangle / private key), not from
**Certificates**.

## 5. Profile and App Store Connect API key

Still in Chrome, with them confirming each create:

1. **Profiles** → **+** → **App Store Connect** (distribution) → that App
   ID → the Distribution cert from step 4 → download `.mobileprovision`.
2. Read the UUID (this is `IOS_PROVISIONING_PROFILE_UUID`):

   ```bash
   security cms -D -i "$PROFILE_PATH" 2>/dev/null \
     | python3 -c "import sys,re; t=sys.stdin.read(); m=re.search(r'<key>UUID</key>\s*<string>([^<]+)</string>', t); print(m.group(1) if m else 'UUID-NOT-FOUND')"
   ```

3. [App Store Connect → Integrations → App Store Connect API](https://appstoreconnect.apple.com/access/integrations/api)
   → **Team** key with at least **App Manager**. Download the `.p8`
   **once**. Copy **Key ID** and **Issuer ID**.

Keep the `.p12`, `.mobileprovision`, and `.p8` outside the repo
(e.g. a local `~/ios-signing/` directory that is not a git remount of
the app).

## 6. Encode and set secrets

macOS `base64` wraps lines. Strip them:

```bash
b64() { base64 -i "$1" | tr -d '\n'; }
```

For **each** of the seven secrets, in this order:

1. Show the secret **name** and a fingerprint only (`wc -c` plus first
   and last four characters of the value). Do not dump the body.
2. Ask: set `NAME` on this repo?
3. Only after yes:

   ```bash
   # file-backed (p12, profile, p8)
   b64 "$PATH_TO_FILE" | gh secret set NAME

   # short strings (password, uuid, key id, issuer id)
   printf '%s' "$VALUE" | gh secret set NAME
   ```

`gh` infers the repo from remotes. Do not add `--repo` unless they asked
to write to a different repository.

If they say no to a secret, skip it and list what is still missing.

## 7. Verify

```bash
gh secret list
```

All seven names should appear. Then a dry signing build (no upload):

```bash
gh workflow run Release -f upload_target=none -f force=true
gh run watch
```

`upload_target=none` still imports the cert and profile and runs
`flutter build ipa`. Fix signing errors before enabling TestFlight or
App Store Connect upload.

## Do not

- Promise that Chrome can export the cert private key from the portal.
- Run `gh secret set` without a per-secret confirmation.
- Commit `.p12`, `.p8`, `.mobileprovision`, or base64 of them.
- Bake `--dart-define` into `release.yml` to force flags or skip App
  Check. That defeats Remote Config for the life of the IPA.
- Replace `release.yml` with a different signing scheme in this skill.
  Change secrets and `YOUR_TEAM_ID` only.
