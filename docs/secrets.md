# Secrets and the conversation

`/ios-ci-setup` handles a certificate password, a private key and an App Store
Connect key. This page says where each one goes.

## The rule

Everything a tool prints, and everything you type into the session, is part of
the conversation. The conversation is sent to the model provider to produce the
next reply. Treat anything that appears in it as shared, and check your plan's
data-retention settings with Anthropic if that matters to you.

## What stays out

| Item | How it is handled |
|---|---|
| p12 password | Typed into a hidden prompt (a macOS dialog inside `!`, a terminal prompt in a normal Terminal). Passed to `openssl` and `gh` through the environment or stdin, never as an argument |
| `.p12`, `.p8`, `.mobileprovision` | Read by `scripts/ios_signing.py` and piped to `gh secret set` on stdin. The conversation sees the file name and length |
| GitHub token | Held by `gh`. `gh auth status` masks it |
| CSR private key | Created by `openssl` with mode 600 in `~/ios-signing/` (mode 700), never read back |

## What does reach it

Identifiers that are not secrets on their own: Team ID, Key ID, Issuer ID,
profile UUID, certificate SHA-1, bundle id, file paths. With Chrome connected,
Claude also sees the pages it works on (Apple's developer portal and App Store
Connect), including those identifiers. It never types a password.

## Local files

`~/ios-signing/` holds the p12 (password-protected), the CSR key (not
password-protected) and the `.p8` (not password-protected). Apple lets you
download a `.p8` once; a lost one is replaced by creating a new key. Keep the
folder out of git, and out of `~/Downloads`.

## If something leaks

- API key: App Store Connect → Integrations → revoke it, create another, and
  set `APP_STORE_CONNECT_API_KEY_*` again.
- Certificate or p12 password: revoke the certificate in the portal, make a new
  one, and rerun `/ios-ci-setup` from step 2.
- GitHub token: `gh auth logout`, then log in again, and revoke the old one at
  github.com/settings/tokens.
