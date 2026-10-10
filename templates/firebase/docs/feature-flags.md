# Feature Flags

How a flag is declared, which tier it belongs to, and how TestFlight builds get
different values from the App Store. Read this before adding a Remote Config
flag, changing one's tier, or touching channel resolution.

## The registry is authoritative

Every remotely-configurable flag has exactly one entry in
[`lib/config/flag_registry.dart`](../lib/config/flag_registry.dart), recording
its key, tier, default, and the spec that introduced it. Remote Config defaults
are derived from that list, so a flag cannot exist without an entry.

## Precedence

| Source | Wins over | Notes |
|--------|-----------|-------|
| `--dart-define` | everything | Local development only. Release builds bake none. |
| Remote Config | the default | What the console serves for this channel. |
| Registry default | nothing | Used before the first fetch, or when the console has no such parameter. |

A baked dart-define beats Remote Config permanently for the life of that binary
and cannot be killed remotely. That is why `release.yml` has no `dart_defines`
input.

## Tiers

| Tier | Across channels | Ends its life |
|------|-----------------|---------------|
| `release` | On in TestFlight, off in production until promoted | Deleted, once the feature ships to everyone |
| `ops` | Identical everywhere | Deleted when the thing it guards is no longer at risk |
| `config` | Identical everywhere | Never. It is a setting, not a toggle |

Ops flags read the same on every channel deliberately. A kill switch that
behaved differently in beta would mean the thing you soak-tested is not the
thing you would be killing in production.

## Channels

Resolve the channel at runtime with
[`lib/config/app_channel.dart`](../lib/config/app_channel.dart) from the
installer store (`package_info_plus`). Unknown resolves to `appStore` on
purpose.

| Installer store | Channel |
|-----------------|---------|
| simulator, or any debug build | `dev` |
| TestFlight | `testflight` |
| App Store, or anything else | `appStore` |

Publish the channel to Remote Config as the custom signal `app_channel` before
the first fetch. A console condition named `TestFlight` (`app_channel` exactly
matches `testflight`) is how a release flag gets a beta-only value.

## Adding a flag

1. Add a `FlagDefinition` to `kFlagRegistry` with its key, tier, default, and
   originating spec.
2. Create the parameter in the Remote Config console with the same key.
3. If it is a release flag, add a conditional value under the `TestFlight`
   condition.

Release flags default to `false`.

## Graduating and deleting

Promoting a release flag to everyone means flipping the production default to
`true` and deleting its conditional value in the same console edit.

A release flag that has been on in production for two releases has stopped
being a flag. Delete it from the registry.

## Build-config defines

`DISABLE_FIREBASE_APP_CHECK` and `CHANNEL` are deliberately not remote flags:
App Check gates the Remote Config fetch, and the channel decides which console
values apply.
