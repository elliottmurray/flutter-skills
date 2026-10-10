import 'package:flutter_test/flutter_test.dart';

import 'package:{{PACKAGE_NAME}}/config/app_channel.dart';

void main() {
  group('resolveAppChannel', () {
    test('CHANNEL override wins', () {
      expect(
        resolveAppChannel(
          installerStore: kTestFlightStore,
          isDebug: false,
          override: 'appStore',
        ),
        AppChannel.appStore,
      );
    });

    test('debug or simulator is dev', () {
      expect(
        resolveAppChannel(installerStore: null, isDebug: true),
        AppChannel.dev,
      );
      expect(
        resolveAppChannel(
          installerStore: kSimulatorStore,
          isDebug: false,
        ),
        AppChannel.dev,
      );
    });

    test('TestFlight store is testflight', () {
      expect(
        resolveAppChannel(
          installerStore: kTestFlightStore,
          isDebug: false,
        ),
        AppChannel.testflight,
      );
    });

    test('unknown store fails safe to appStore', () {
      expect(
        resolveAppChannel(
          installerStore: 'com.unknown.store',
          isDebug: false,
        ),
        AppChannel.appStore,
      );
      expect(
        resolveAppChannel(installerStore: null, isDebug: false),
        AppChannel.appStore,
      );
    });
  });
}
