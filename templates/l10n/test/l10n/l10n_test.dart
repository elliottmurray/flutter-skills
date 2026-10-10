import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:{{PACKAGE_NAME}}/l10n/l10n.dart';

/// Pumps a bare app and returns the locale `context.l10n` resolved to.
Future<String> _resolvedLocale(
  WidgetTester tester, {
  Locale? locale,
  bool delegates = true,
}) async {
  late String resolved;
  await tester.pumpWidget(MaterialApp(
    locale: locale,
    localizationsDelegates:
        delegates ? AppLocalizations.localizationsDelegates : null,
    supportedLocales: delegates
        ? AppLocalizations.supportedLocales
        : const [Locale('en', 'US')],
    home: Builder(builder: (context) {
      resolved = context.l10n.localeName;
      return const SizedBox();
    }),
  ));
  await tester.pumpAndSettle();
  return resolved;
}

void main() {
  test('English is the first supported locale', () {
    expect(AppLocalizations.supportedLocales.first.languageCode, 'en');
  });

  testWidgets('context.l10n falls back to English with no delegate in the tree',
      (tester) async {
    expect(await _resolvedLocale(tester, delegates: false), 'en');
  });

  testWidgets('an unsupported locale falls back to English', (tester) async {
    expect(await _resolvedLocale(tester, locale: const Locale('tlh')), 'en');
  });

  for (final locale in AppLocalizations.supportedLocales) {
    testWidgets('context.l10n follows the app locale: $locale', (tester) async {
      expect(await _resolvedLocale(tester, locale: locale), locale.toString());
    });
  }
}
