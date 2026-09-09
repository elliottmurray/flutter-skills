import 'package:flutter/foundation.dart';

/// Distribution channel the running build came from.
///
/// The same IPA ships to TestFlight and the App Store, so this is resolved at
/// runtime rather than baked in at build time. Publish it to Remote Config as
/// the `app_channel` custom signal before the first fetch. A console condition
/// named `TestFlight` (`app_channel` exactly matches `testflight`) is how a
/// release flag gets a beta-only value.
enum AppChannel { dev, testflight, appStore }

/// Installer store reported by `package_info_plus` for a TestFlight build.
const kTestFlightStore = 'com.apple.testflight';

/// Installer store reported for a simulator build.
const kSimulatorStore = 'com.apple.simulator';

/// Resolves the channel from the installer store `package_info_plus` reports.
///
/// [override] is the `CHANNEL` dart-define. An unknown override asserts in
/// debug; an empty one means no override. Anything unrecognised fails safe to
/// [AppChannel.appStore].
AppChannel resolveAppChannel({
  required String? installerStore,
  bool isDebug = kDebugMode,
  String? override,
}) {
  if (override != null && override.isNotEmpty) {
    final match = AppChannel.values.where(
      (c) => c.name.toLowerCase() == override.toLowerCase(),
    );
    assert(
      match.isNotEmpty,
      'Unknown CHANNEL override "$override". '
      'Expected one of: ${AppChannel.values.map((c) => c.name).join(', ')}.',
    );
    if (match.isNotEmpty) {
      return match.first;
    }
  }

  if (isDebug || installerStore == kSimulatorStore) {
    return AppChannel.dev;
  }
  if (installerStore == kTestFlightStore) {
    return AppChannel.testflight;
  }
  return AppChannel.appStore;
}

extension AppChannelConfig on AppChannel {
  /// How stale a cached config may be before a fetch re-hits the network.
  Duration get minimumFetchInterval => switch (this) {
        AppChannel.dev => const Duration(seconds: 30),
        AppChannel.testflight => const Duration(minutes: 5),
        AppChannel.appStore => const Duration(hours: 1),
      };
}
