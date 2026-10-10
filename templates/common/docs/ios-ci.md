# iOS CI signing

`release.yml` builds a signed IPA. GitHub secrets are created by
`/ios-ci-setup` (wizard + Chrome on developer.apple.com after 2FA).

The certificate private key is exported from Xcode / Keychain — the Apple
portal cannot invent it. Confirm before every `gh secret set`.

Do not bake `--dart-define` into release builds.
