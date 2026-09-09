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

**Not shipped yet.** `/setup-project` can already set `runs-on` to a
custom label. This skill will register the machine.

## What this skill will do

Walk a local Mac through:

1. Download and `config.sh` with `--labels <label>`
2. A per-user LaunchAgent (not `./svc.sh install` — that has no
   WindowServer, and Simulator boots fail)
3. Automatic login, `pmset` sleep off, Xcode license
4. Swap `integration_tests.yml` `runs-on` to
   `[self-hosted, macOS, <label>]`
5. Verify with `gh workflow run "Integration Tests"`
