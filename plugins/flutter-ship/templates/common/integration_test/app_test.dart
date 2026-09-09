import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

import 'app_test_helper.dart';
import 'screenshot_helper.dart';

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('smoke: home screen renders', (tester) async {
    await tester.pumpWidget(
      buildTestApp(
        home: const Scaffold(
          body: Center(child: Text('{{APP_NAME}}')),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('{{APP_NAME}}'), findsOneWidget);
    await takeScreenshot(binding, 'smoke-home');
  });
}
