import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Bootstraps a widget tree for integration tests.
///
/// Skips Firebase, system chrome, and production `main()`. Pass the screen
/// under test as [home]. Clamp text scale so screenshot diffs stay stable.
Widget buildTestApp({required Widget home}) {
  return Builder(
    builder: (context) {
      final mediaQueryData = MediaQuery.of(context);
      final scale = mediaQueryData.textScaler.clamp(
        minScaleFactor: 1.0,
        maxScaleFactor: 1.0,
      );
      return MediaQuery(
        data: mediaQueryData.copyWith(textScaler: scale),
        child: MaterialApp(
          debugShowCheckedModeBanner: false,
          home: home,
        ),
      );
    },
  );
}
