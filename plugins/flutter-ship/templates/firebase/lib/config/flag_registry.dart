/// What a flag is *for*, which decides how it behaves across channels and how
/// its life ends.
enum FlagTier {
  /// Gates an unreleased feature. On in TestFlight, off in production until
  /// deliberately promoted. Ends its life deleted, once the feature ships.
  release,

  /// A kill switch or operational lever. Reads identically on every channel —
  /// one that behaved differently in beta would mean the thing you soak-tested
  /// is not the thing you would be killing in production.
  ops,

  /// A setting rather than a toggle: it is never "turned off", it is pointed
  /// somewhere. Has no lifecycle ending in deletion.
  config,
}

/// One Remote Config-backed flag.
class FlagDefinition {
  const FlagDefinition({
    required this.key,
    required this.tier,
    required this.defaultValue,
    this.spec,
  });

  /// Remote Config parameter name.
  final String key;

  final FlagTier tier;

  /// Served when Remote Config has no value — no fetch yet, or the parameter
  /// does not exist in the console.
  final Object defaultValue;

  /// Spec that introduced this flag. Null if the flag predates specs.
  final String? spec;
}

/// The single source of truth for every remotely-configurable flag.
///
/// Remote Config defaults are derived from this list, so a flag cannot exist
/// without an entry here.
const kFlagRegistry = <FlagDefinition>[];

/// Remote Config defaults, derived so they cannot diverge from the registry.
Map<String, Object> get flagDefaults => {
      for (final flag in kFlagRegistry) flag.key: flag.defaultValue,
    };

/// Dart-defines that are deliberately *not* remote flags.
///
/// Each is unservable from a console by construction.
const kBuildConfigDefines = <String>{
  'DISABLE_FIREBASE_APP_CHECK',
  'CHANNEL',
};
