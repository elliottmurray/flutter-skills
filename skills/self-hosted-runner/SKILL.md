---
name: self-hosted-runner
description: >
  Configure a local Mac as a GitHub Actions self-hosted runner for iOS
  integration tests (LaunchAgent in the GUI session, not svc.sh). Trigger
  on /self-hosted-runner, Mac mini runner setup, or swapping runs-on off
  macos-latest.
user_invocable: true
---

# Self-Hosted Runner

Walk **this Mac** through registering as a GitHub Actions runner for iOS
Simulator integration tests. `/setup-project` may already have set
`runs-on`; this skill registers the machine and points
`integration_tests.yml` at it.

The runner must live in a **logged-in GUI session**. Simulator boot talks
to WindowServer. `./svc.sh install` puts a LaunchDaemon in a non-Aqua
session — boots fail with vague CoreSimulator errors. Use a per-user
**LaunchAgent**. Never `svc.sh`.

## 0. Scope: use this Mac as a runner?

Ask: **Do you want to use this Mac as a runner?** Offer two scopes.

- **Integration tests only (recommended).** Tests boot the Simulator and never
  touch signing, so a machine you also develop on is a fine host. This sets
  `runs-on` for the `integration-test` job only.
- **Integration tests and release.** The release job imports a certificate
  into a temporary keychain and adds it to the user keychain search list for
  the length of the run. A killed job can leave that list altered. Offer this
  for a dedicated macOS user or a dedicated machine, and say why before
  agreeing on a dev machine. Hosted `macos-latest` stays the default.

Done when the scope is stated back and the label (step 1) is chosen.

## 1. Confirm the machine

Run these on the Mac that will stay on:

```bash
uname -m                    # arm64 or x86_64
sw_vers
xcodebuild -version
xcodebuild -checkFirstLaunchStatus || sudo xcodebuild -runFirstLaunch
sudo xcodebuild -license accept
gh auth status
```

Ask for a runner **label** if they do not have one (suggestion:
`app-runner`). Labels are added on top of GitHub's automatic
`self-hosted`, `macOS`, and arch labels.

A runner belongs to one repository. A Mac that already runs one for another
repo needs a second instance for this one, each with its own directory and
LaunchAgent. List what exists, and leave it untouched:

```bash
ls ~/Library/LaunchAgents | grep -i 'github.actions'
launchctl list | grep -i runner
```

Two runners on one Mac take jobs independently and share one Simulator, so
tell the user if both repos can run integration tests at the same time.

## 2. Registration token and install

From the **app repo** (the Flutter project, not lastmile):

```bash
TOKEN=$(gh api -X POST repos/:owner/:repo/actions/runners/registration-token --jq .token)
REPO_URL=$(gh repo view --json url -q .url)
REPO=$(basename "$REPO_URL")
RUNNER_DIR="$HOME/actions-runner-$REPO"
echo "$REPO_URL"
```

`:owner/:repo` resolves from the current remotes. Do not hardcode a path.

Install into a directory **outside** the app repo, named for the repo
(`$HOME/actions-runner-<repo>`), so an existing runner is never overwritten.
Reuse the directory if `config.sh` is already there.

```bash
RUNNER_VERSION=$(curl -sSf https://api.github.com/repos/actions/runner/releases/latest \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['tag_name'].lstrip('v'))")
ARCH=$(uname -m)
case "$ARCH" in
  arm64) PKG=osx-arm64 ;;
  x86_64) PKG=osx-x64 ;;
  *) echo "unsupported arch: $ARCH" >&2; exit 1 ;;
esac

mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"
curl -L -o actions-runner.tgz \
  "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-${PKG}-${RUNNER_VERSION}.tar.gz"
tar xzf actions-runner.tgz
rm actions-runner.tgz

./config.sh --url "$REPO_URL" --token "$TOKEN" \
  --name "$(scutil --get LocalHostName)-$REPO" \
  --labels "$LABEL" \
  --unattended --replace
```

Confirm `./run.sh` exists. Do not start it yet, and do not run
`./svc.sh install`.

## 3. LaunchAgent (Aqua session)

Write `$HOME/Library/LaunchAgents/com.github.actions.<repo>-runner.plist`.
Substitute the real home directory and repo name; do not leave `$HOME` inside
the plist `ProgramArguments`.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.github.actions.REPO-runner</string>
  <key>WorkingDirectory</key>
  <string>/Users/YOU/actions-runner-REPO</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/YOU/actions-runner-REPO/run.sh</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ProcessType</key>
  <string>Interactive</string>
  <key>LimitLoadToSessionType</key>
  <string>Aqua</string>
  <key>ThrottleInterval</key>
  <integer>30</integer>
  <key>StandardOutPath</key>
  <string>/Users/YOU/actions-runner-REPO/launchd.stdout.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/YOU/actions-runner-REPO/launchd.stderr.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
</dict>
</plist>
```

Load it into the **current GUI session** (replace `YOU` and `REPO` first):

```bash
uid=$(id -u)
plist="$HOME/Library/LaunchAgents/com.github.actions.REPO-runner.plist"
launchctl bootout "gui/$uid/com.github.actions.REPO-runner" 2>/dev/null || true
launchctl bootstrap "gui/$uid" "$plist"
launchctl enable "gui/$uid/com.github.actions.REPO-runner"
launchctl kickstart -k "gui/$uid/com.github.actions.REPO-runner"
```

On older macOS where `bootstrap` is missing: `launchctl load -w "$plist"`.

Confirm GitHub sees the runner:

```bash
gh api repos/:owner/:repo/actions/runners --jq '.runners[] | {name,status,labels:[.labels[].name]}'
```

Status should be `online`. If it is `offline`, read
`$RUNNER_DIR/launchd.stderr.log` — the usual cause is the agent
running outside Aqua (`svc.sh`) or no GUI login.

## 4. Stay awake, stay logged in

The LaunchAgent does not start at the login window. Automatic login is
required for unattended overnight runs:

1. System Settings → Users & Groups → Login Options → **Automatic login**
   as the runner user.
2. FileVault: automatic login is unavailable when FileVault is on. Say so
   if `fdesetup status` reports On; they must unlock once after reboot.

Sleep:

```bash
sudo pmset -a sleep 0 disksleep 0 displaysleep 0
sudo pmset -a hibernatemode 0
# Some Macs:
sudo pmset -a disablesleep 1 || true
pmset -g
```

Do not use `caffeinate` as the only keep-awake mechanism; it dies with
the terminal.

## 5. Seed caches

First integration job is slow unless Flutter and SPM already exist:

```bash
flutter precache --ios
# from the app repo
flutter pub get
xcrun simctl list devices available | head
```

Xcode DerivedData and `~/Library/Caches/org.swift.swiftpm` fill on the
first `flutter build ios`. That is expected.

## 6. Swap `runs-on`

In `.github/workflows/integration_tests.yml`, the integration job's
`runs-on` must be a YAML list (not a quoted string):

```yaml
    runs-on: [self-hosted, macOS, LABEL]
```

Replace `LABEL` with the label from step 1. `release.yml` keeps its hosted
`runs-on` unless step 0 chose release too. In that case set it the same way,
and tell the user the keychain repair command:
`security list-keychains -d user -s "$HOME/Library/Keychains/login.keychain-db"`.

If `{{RUNNER_LABEL}}` or `{{RELEASE_RUNNER_LABEL}}` is still unrendered, the app was not run through
`/setup-project` — stop and render templates first.

## 7. Verify

```bash
gh workflow run "Integration Tests"
gh run list --workflow "Integration Tests" --limit 3
gh run view RUN_ID --json status,conclusion,jobs
```

The job must land on the self-hosted runner (`Run self-hosted/…` in the
log), not `macos-latest`. Simulator boot should succeed. If it fails with
CoreSimulator / WindowServer, the LaunchAgent is not in Aqua — undo
`svc.sh` if they ran it (`./svc.sh uninstall`) and go back to step 3.

## Do not

- Run `./svc.sh install` or load a LaunchDaemon for this runner.
- Put the runner install inside the Flutter git checkout.
- Change `release.yml` `runs-on` unless asked.
- Disable SIP or turn off Gatekeeper to make Simulator quieter.
- Point `release.yml` at the Mac the user develops on without the step 0 warning.
