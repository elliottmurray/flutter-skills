---
name: feature-flags
description: >
  Add, graduate, or delete a Remote Config feature flag in the registry.
  Trigger when the user mentions feature flags, Remote Config, flag tiers
  (release/ops/config), TestFlight channel targeting, or /feature-flags.
user_invocable: true
---

# Feature Flags

The registry in `lib/config/flag_registry.dart` is authoritative. Remote
Config defaults are derived from it. `/setup-project --firebase` copies
that file, `docs/feature-flags.md`, and `lib/config/app_channel.dart`.

Read `docs/feature-flags.md` before editing. If those files are missing,
stop: run `/setup-project` with Firebase, or copy the firebase templates
from flutter-ship, before adding a flag.

`/firebase-setup` owns creating the Firebase project and the console
`TestFlight` condition. This skill owns the registry lifecycle.

## Decide the mode

1. **Add** — new key, or "gate this behind a flag".
2. **Graduate** — ship a `release` flag to App Store users.
3. **Delete** — flag has been on in production for two releases, or the
   guarded code is gone.

Ask if it is unclear. Do one flag per invocation.

## Tiers

| Tier | Across channels | Ends its life |
|------|-----------------|---------------|
| `release` | On in TestFlight, off in production until promoted | Deleted once everyone has the feature |
| `ops` | Identical everywhere | Deleted when the thing it guards is no longer at risk |
| `config` | Identical everywhere | Never. It is a setting, not a toggle |

Ops flags read the same on every channel on purpose. A kill switch that
behaved differently in beta is not the kill switch you would use in
production.

`release` flags default to `false` in the registry.

## Naming

- Remote Config key = Dart `key`. snake_case.
- Booleans end in `_enabled` (`stats_page_enabled`).
- Settings keep the noun (`api_base_url`).
- Do not add `DISABLE_FIREBASE_APP_CHECK` or `CHANNEL` to the registry —
  those are build-config defines.

## Add

1. Confirm the key is not already in `kFlagRegistry` (`lookupFlag`).
2. Append a `FlagDefinition`:

   ```dart
   FlagDefinition(
     key: 'stats_page_enabled',
     tier: FlagTier.release,
     defaultValue: false,
     spec: 'specs/stats-page.md',  // or the issue / PR that introduced it
   ),
   ```

3. Gate call sites through the project's existing Remote Config reader,
   using `flagDefaults` as the pre-fetch fallback. If no reader exists
   yet, say so and add the registry entry only — do not invent a second
   source of truth.
4. Create the parameter in the Firebase Remote Config console with the
   **same key** and the registry default.
5. If `tier` is `release`, add a conditional value under the `TestFlight`
   condition (`app_channel` exactly matches `testflight`), typically
   `true` for a boolean. If that condition does not exist, stop and run
   `/firebase-setup` (or create it by hand) before publishing.
6. Publish the Remote Config template. Do not bake `--dart-define` into
   `release.yml`.

Channel resolution lives in `lib/config/app_channel.dart`. The running
app must publish `app_channel` (`dev` / `testflight` / `appStore`) as a
Remote Config custom signal **before** the first fetch. If
`package_info_plus` is missing:

```bash
flutter pub add package_info_plus
```

Pass `PackageInfo.fromPlatform().installerStore` into `resolveAppChannel`.
Unknown installers resolve to `appStore`.

## Graduate

Same console edit, in this order:

1. Flip the **production** default to the shipped value (`true` for a
   boolean release flag).
2. Delete the `TestFlight` conditional for that parameter.
3. Publish.
4. Set `defaultValue` on the registry entry to match production.
5. Keep the key until it has been on for two production releases.

## Delete

Only after the graduate soak, or when the guarded code is already gone.

1. Remove call sites TDD-first (`/tdd`). Tests stay green with the flag
   gone (the feature is just on, or the code is deleted).
2. Remove the `FlagDefinition` from `kFlagRegistry`.
3. Delete the parameter in the Remote Config console and publish.

## Do not

- Add a console parameter with no registry entry, or a registry entry
  you never create in the console.
- Raise a `release` default to `true` without deleting its TestFlight
  conditional in the same publish.
- Use `--dart-define` on a release IPA to force a flag. A baked define
  beats Remote Config for the life of that binary.
