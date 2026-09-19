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

## 2. Registration token and install

From the **app repo** (the Flutter project, not flutter-ship):

```bash
TOKEN=$(gh api -X POST repos/:owner/:repo/actions/runners/registration-token --jq .token)
REPO_URL=$(gh repo view --json url -q .url)
echo "$REPO_URL"
```

`:owner/:repo` resolves from the current remotes. Do not hardcode a path.

Install into a directory **outside** the app repo (default
`$HOME/actions-runner`). Reuse it if `config.sh` is already there.

```bash
RUNNER_VERSION=$(curl -sSf https://api.github.com/repos/actions/runner/releases/latest \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['tag_name'].lstrip('v'))")
ARCH=$(uname -m)
case "$ARCH" in
  arm64) PKG=osx-arm64 ;;
  x86_64) PKG=osx-x64 ;;
  *) echo "unsupported arch: $ARCH" >&2; exit 1 ;;
esac

mkdir -p "$HOME/actions-runner"
cd "$HOME/actions-runner"
curl -L -o actions-runner.tgz \
  "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-${PKG}-${RUNNER_VERSION}.tar.gz"
tar xzf actions-runner.tgz
rm actions-runner.tgz

./config.sh --url "$REPO_URL" --token "$TOKEN" \
  --name "$(scutil --get LocalHostName)" \
  --labels "$LABEL" \
  --unattended --replace
```

Confirm `./run.sh` exists. Do not start it yet, and do not run
`./svc.sh install`.

## 3. LaunchAgent (Aqua session)

Write `$HOME/Library/LaunchAgents/com.github.actions.runner.plist`.
Substitute the real home directory; do not leave `$HOME` inside the plist
`ProgramArguments`.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.github.actions.runner</string>
  <key>WorkingDirectory</key>
  <string>/Users/YOU/actions-runner</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/YOU/actions-runner/run.sh</string>
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
  <string>/Users/YOU/actions-runner/launchd.stdout.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/YOU/actions-runner/launchd.stderr.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
</dict>
</plist>
```

Load it into the **current GUI session** (replace `YOU` first):

```bash
uid=$(id -u)
plist="$HOME/Library/LaunchAgents/com.github.actions.runner.plist"
launchctl bootout "gui/$uid/com.github.actions.runner" 2>/dev/null || true
launchctl bootstrap "gui/$uid" "$plist"
launchctl enable "gui/$uid/com.github.actions.runner"
launchctl kickstart -k "gui/$uid/com.github.actions.runner"
```

On older macOS where `bootstrap` is missing: `launchctl load -w "$plist"`.

Confirm GitHub sees the runner:

```bash
gh api repos/:owner/:repo/actions/runners --jq '.runners[] | {name,status,labels:[.labels[].name]}'
```

Status should be `online`. If it is `offline`, read
`$HOME/actions-runner/launchd.stderr.log` — the usual cause is the agent
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

Replace `LABEL` with the label from step 1. Leave `release.yml` on
`macos-latest` unless they explicitly want signing on this Mac too.

If `{{RUNNER_LABEL}}` is still unrendered, the app was not run through
`/setup-project` — stop and render templates first.

## 7. Verify

```bash
gh workflow run "Integration Tests"
gh run list --workflow "Integration Tests" --limit 3
gh run watch
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
