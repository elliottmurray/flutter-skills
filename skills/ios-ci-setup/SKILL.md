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
Release builds run on a hosted `macos-latest` runner. Leave `runs-on` there:
signing changes the user keychain search list, and a dev machine is the wrong
place for that.

Local steps go through one script, `ios_signing.py`. It keeps passwords out of
argv and stdout, reads p12 files from both OpenSSL 3 and the macOS Keychain,
and needs no Xcode.

```bash
H="python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ios_signing.py"
```

## Secret handling

Everything a tool prints is part of the conversation. Keep these out of it:
the p12 password, the `.p8` contents, the p12 and `.p8` base64, GitHub tokens.

- Passwords go in through the helper's hidden prompt: a hidden macOS dialog
  under `!` (there is no terminal there, so `read -s` fails silently), or a
  hidden terminal prompt in a normal Terminal window.
- Files go to GitHub through the helper, which pipes them to `gh` on stdin.
  Show a file's name and length. Show a password nowhere, fingerprint included.
- Identifiers are safe to show: Team ID, Key ID, Issuer ID, profile UUID,
  certificate SHA-1.
- If a secret does reach the conversation, rotate it: revoke the API key in
  App Store Connect, or revoke the certificate in the portal, and redo the step.

## 0. Choose a mode

Ask once: **Guided** (default) or **Chrome-assisted**.

- **Guided:** the user clicks in their own browser. For each portal step, give
  the exact URL and the button names, then wait for "done". Run every local
  command yourself.
- **Chrome-assisted:** requires `/chrome` connected. Drive developer.apple.com
  after the user finishes Apple 2FA. Find elements by ref, since window resizes
  move coordinates. Ask before each download, and let the user type any
  password. After two failed browser calls, say so and continue in Guided.

Done when the mode is stated back to the user.

## 1. Preflight

```bash
gh auth status          # needs repo + workflow; refresh now if the token is old
git remote -v           # needs origin
grep -m1 PRODUCT_BUNDLE_IDENTIFIER ios/Runner.xcodeproj/project.pbxproj
```

- No `origin`: offer `gh repo create OWNER/NAME --private --source=. --remote=origin`.
- A token that expires mid-flow fails later steps with 404s. If `gh auth status`
  reports an invalid token, have the user run
  `! gh auth login -h github.com -s repo,workflow`.
- The Apple account needs a paid Developer Program membership and the Admin or
  Account Holder role. A free Apple ID cannot do steps 2, 4 or 5; stop and say so.
- The App Store Connect app record must exist before the first real upload:
  Apps → **+** → New App, with the bundle id. The dry run in step 7 does not need it.

Done when `gh` is authenticated, `origin` exists, and the bundle id is known.

## 2. Distribution certificate and p12

```bash
$H identities
```

Pick by SHA-1. A revoked certificate can share its name with the valid one.
A team holds three Distribution certificates at most, so reuse before creating,
and leave any certificate that other apps use alone.

**A. Reuse a valid one from this Mac.** Keychain Access → **My Certificates**
(the identity with a key under it) → right-click → Export → `.p12`, into
`~/ios-signing/`. No file in that folder means the export was cancelled or saved
elsewhere; ask again before moving on.

**B. Create one, no Xcode.**

```bash
$H csr --email "<apple id email>"            # key stays in ~/ios-signing
```

Portal → Certificates → **+** → Apple Distribution → upload `dist.csr` →
download the `.cer` into `~/ios-signing/`. Then:

```bash
$H p12 --key ~/ios-signing/dist.key --cer ~/ios-signing/<name>.cer --out ~/ios-signing/dist.p12
```

**C. Xcode:** Settings → Accounts → Manage Certificates → **+** → Apple
Distribution, then export as in A.

```bash
$H verify-p12 --p12 ~/ios-signing/dist.p12   # hidden password prompt
```

Done when `verify-p12` exits 0 with `private key : present`, an expiry in the
future, and a team id. Record the team id and SHA-1.

## 3. Team ID

Replace `YOUR_TEAM_ID` in `.github/workflows/release.yml` with the team id from
step 2. Show the one-line diff.

## 4. App ID and provisioning profile

Portal → Identifiers → **+** → App IDs → App → Explicit, the bundle id, no
capabilities. App Attest belongs to `/app-check`.

Portal → Profiles → **+** → Distribution → **App Store Connect** → that App ID →
the certificate from step 2 (match the expiry) → name it `<app> App Store` →
Generate → Download.

```bash
$H profile-info ~/Downloads/<name>.mobileprovision --bundle-id <bundle id>
```

Name the file in the command from the profile name chosen in the portal. The
newest `.mobileprovision` by timestamp can be another app's.

Done when `profile-info` exits 0 with `type : app-store`, a matching app id, and
a future expiry. Record the UUID.

## 5. App Store Connect API key

Portal → Users and Access → Integrations → App Store Connect API → Team Keys →
**+** → name `<app>-ci`, access **App Manager** → Generate. Copy the **Key ID**
from the row and the **Issuer ID** from the top of the page. **Download API
Key** works once; save it to `~/ios-signing/`, not Downloads.

```bash
openssl pkey -in ~/ios-signing/AuthKey_<KEYID>.p8 -noout && echo valid
```

Done when the `.p8` validates and its file name carries the Key ID.

## 6. GitHub secrets

| Secret | Source |
|---|---|
| `IOS_DISTRIBUTION_CERT_P12` | `--file` the p12 |
| `IOS_DISTRIBUTION_CERT_PASSWORD` | `--prompt` (hidden) |
| `IOS_PROVISIONING_PROFILE` | `--file` the `.mobileprovision` |
| `IOS_PROVISIONING_PROFILE_UUID` | `--env` from step 4 |
| `APP_STORE_CONNECT_API_KEY_ID` | `--env` from step 5 |
| `APP_STORE_CONNECT_ISSUER_ID` | `--env` from step 5 |
| `APP_STORE_CONNECT_API_KEY_CONTENT` | `--file` the `.p8` |

Show the table with the repo name, then ask which to set. One yes covers the
names listed. Each secret is one call:

```bash
$H set-secret NAME --repo OWNER/REPO --file PATH      # or --prompt
KEYID=ABC123DEFG $H set-secret APP_STORE_CONNECT_API_KEY_ID --repo OWNER/REPO --env KEYID
```

Done when `gh secret list --repo OWNER/REPO` shows all seven.

## 7. Dry run

The workflow must be on GitHub. Commit and push first, with the user's yes.

```bash
gh workflow run Release --repo OWNER/REPO -f upload_target=none -f force=true
gh run list --repo OWNER/REPO --workflow Release --limit 1
gh run view RUN_ID --repo OWNER/REPO --json status,conclusion,jobs
```

Read `conclusion`; `gh run watch` exits 0 even when it lost its login. A pass
means certificate, password, profile and build config all work. Failures map to
causes in [troubleshooting.md](troubleshooting.md).

Done when the run's `conclusion` is `success`.

## 8. Tidy

Signing files live in `~/ios-signing/` (mode 700). The `.p8` cannot be
downloaded again; keep one copy there or delete it, since a new key replaces it.

## Do not

- Run `gh secret set` for names the user has not seen listed.
- Commit `.p12`, `.p8`, `.mobileprovision`, or base64 of them.
- Bake `--dart-define` into `release.yml`: it beats Remote Config for the life
  of the IPA.
- Replace `release.yml`'s signing scheme here. Change secrets and the team id only.
