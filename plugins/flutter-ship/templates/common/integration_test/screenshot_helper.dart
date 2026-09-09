import 'package:integration_test/integration_test.dart';

Future<void> takeScreenshot(
  IntegrationTestWidgetsFlutterBinding binding,
  String name,
) async {
  await binding.takeScreenshot(name);
}
