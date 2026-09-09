---
name: feature-flags
description: >
  Add, graduate, or delete a Remote Config feature flag in the registry.
  Trigger when the user mentions feature flags, Remote Config, flag tiers
  (release/ops/config), TestFlight channel targeting, or /feature-flags.
user_invocable: true
---

# Feature Flags

**Not shipped yet.** `/setup-project` copies the registry stub
(`lib/config/flag_registry.dart`) and `docs/feature-flags.md` when Firebase
is enabled. This skill will own adding, graduating, and deleting flags.

## What this skill will do

- Add a `FlagDefinition` (key, tier, default, originating spec)
- Keep Remote Config defaults derived from the registry
- For `release` flags: default `false`, plus a TestFlight conditional on the
  `app_channel` custom signal
- Graduate: flip production default to `true` and delete the conditional in
  the same console edit
- Delete a flag that has been on for two production releases

Until this skill ships, follow the precedence table and tier rules in the
generated `docs/feature-flags.md`.
