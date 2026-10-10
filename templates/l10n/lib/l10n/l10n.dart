import 'package:flutter/widgets.dart';
import 'package:{{PACKAGE_NAME}}/l10n/app_localizations.dart';

export 'package:{{PACKAGE_NAME}}/l10n/app_localizations.dart';

extension L10nContext on BuildContext {
  /// The strings for this context's locale.
  ///
  /// Falls back to English when no [AppLocalizations] delegate is in the tree,
  /// which is the case for widget tests that pump a bare `MaterialApp`.
  AppLocalizations get l10n =>
      AppLocalizations.of(this) ?? lookupAppLocalizations(const Locale('en'));
}
