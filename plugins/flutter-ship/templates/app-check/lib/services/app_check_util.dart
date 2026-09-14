import 'package:firebase_app_check/firebase_app_check.dart';
import 'package:flutter/foundation.dart';

/// Build-config dart-define. Not a Remote Config flag: App Check gates the
/// RC fetch, so an RC value cannot disable the thing that loads RC.
const kDisableFirebaseAppCheck = bool.fromEnvironment(
  'DISABLE_FIREBASE_APP_CHECK',
);

/// Debug on local/simulator builds; App Attest with DeviceCheck fallback
/// in release. Call after [Firebase.initializeApp] and before the first
/// Remote Config fetch.
Future<void> activateAppCheck() async {
  if (kDisableFirebaseAppCheck) {
    return;
  }
  await FirebaseAppCheck.instance.activate(
    appleProvider: kDebugMode
        ? AppleProvider.debug
        : AppleProvider.appAttestWithDeviceCheckFallback,
  );
}
