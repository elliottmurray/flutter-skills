# iOS CI troubleshooting

Symptom, cause, fix. Each row came from a real run.

## p12

| Symptom | Cause | Fix |
|---|---|---|
| `openssl … unsupported … RC2-40-CBC` | macOS Keychain writes legacy p12 files that OpenSSL 3 opens only with `-legacy` | `ios_signing.py verify-p12` retries with `-legacy` for you. By hand: add `-legacy` |
| `Mac verify error: invalid password?` | Wrong password | Retype. The helper reports it as `wrong p12 password` |
| Keychain export saved nothing | Export cancelled, saved elsewhere, or the format was `.cer` | Re-export from **My Certificates** as `.p12`, approve the login prompt, then `ls` the folder |
| Two `Apple Distribution` rows in `identities`, one `CSSMERR_TP_CERT_REVOKED` | Same name, different certificates | Choose the `valid` SHA-1; match its expiry in the portal |
| `read -s` does nothing under `!` | `!` has no terminal | Use the helper: it opens a hidden dialog |
| `security import` rejects a p12 made by OpenSSL 3 | OpenSSL 3 defaults to AES and a SHA-256 MAC | `ios_signing.py p12` writes the 3DES/SHA-1 form macOS accepts |
| `.cer` was not issued for this private key | Key and certificate come from different CSRs | Keep `dist.key` with its CSR; make a new CSR if the key is lost |

## Build

| Symptom | Cause | Fix |
|---|---|---|
| `Build IPA`: `errSecInternalComponent`, `unable to build chain to self-signed root` | The CI keychain replaced the user keychain search list, hiding Apple's intermediate certificates | Use the current `release.yml` template, which adds to the list and restores it. Hosted runner by default |
| `flutter pub get`: `requires SDK version ^3.x` | `flutter-version` pin is older than the SDK that ran `flutter create` | `/flutter-sdk-check`. `render.py` now pins the installed SDK |
| Keychain Access shows nothing after a local run | A job left the user search list pointing elsewhere | `security list-keychains -d user -s "$HOME/Library/Keychains/login.keychain-db"`. The keychain file was never deleted |

## GitHub and browser

| Symptom | Cause | Fix |
|---|---|---|
| `The token in default is invalid`, 404 on `gh run` | Expired token | `! gh auth login -h github.com -s repo,workflow` |
| `gh run watch` exits 0 with no result | It lost auth | Read `gh run view --json conclusion` |
| `gh secret set` cannot find a repo | No `origin`, or several remotes | `gh repo create … --source=. --remote=origin`, and pass `--repo` |
| Browser calls fail with `different extension` | Another extension took the tab | `/chrome` → Reconnect, or continue in Guided mode |
| A click lands on nothing | The window resized | Find by ref, not coordinates |
| Newest `.mobileprovision` is the wrong app | Sorted by time | Run `profile-info` on the file named in the portal |
