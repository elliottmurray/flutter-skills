import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// Matches `l10n.yaml`. The Claude hook and `scripts/l10n_locales.py` read
/// the same paths.
const _arbDir = 'lib/l10n';
const _template = 'app_en.arb';
const _infoPlist = 'ios/Runner/Info.plist';

/// `{name,` or `{name}`: a placeholder or a plural/select argument. Branch
/// text such as `=1{1 item}` doesn't match because a space follows the word.
final _placeholder = RegExp(r'\{([A-Za-z_]\w*)[,}]');

/// Translatable messages, minus ARB metadata (`@key`, `@@locale`).
Map<String, String> _messages(File file) {
  final json = jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;
  return {
    for (final entry in json.entries)
      if (!entry.key.startsWith('@')) entry.key: entry.value as String,
  };
}

Set<String> _placeholders(String message) =>
    _placeholder.allMatches(message).map((m) => m.group(1)!).toSet();

String _normalize(String locale) => locale.replaceAll('-', '_').toLowerCase();

void main() {
  final arbFiles = Directory(_arbDir)
      .listSync()
      .whereType<File>()
      .where((f) => f.path.endsWith('.arb'))
      .toList()
    ..sort((a, b) => a.path.compareTo(b.path));
  final template = _messages(File('$_arbDir/$_template'));
  final translations =
      arbFiles.where((f) => !f.path.endsWith('/$_template')).toList();
  final locales = arbFiles
      .map((f) => f.uri.pathSegments.last)
      .map((name) => name.substring('app_'.length, name.length - '.arb'.length))
      .toSet();

  for (final file in translations) {
    final name = file.uri.pathSegments.last;

    test('$name has exactly the template keys', () {
      final keys = _messages(file).keys.toSet();
      expect(template.keys.toSet().difference(keys), isEmpty,
          reason: 'missing translations');
      expect(keys.difference(template.keys.toSet()), isEmpty,
          reason: 'keys not in $_template');
    });

    test('$name uses the template placeholders', () {
      final messages = _messages(file);
      for (final MapEntry(:key, :value) in template.entries) {
        final translated = messages[key];
        if (translated == null) continue;
        expect(_placeholders(translated), _placeholders(value), reason: key);
      }
    });
  }

  test('iOS CFBundleLocalizations lists every ARB locale', () {
    final plist = File(_infoPlist);
    if (!plist.existsSync()) return;
    final array = RegExp(
      r'<key>CFBundleLocalizations</key>\s*<array>(.*?)</array>',
      dotAll: true,
    ).firstMatch(plist.readAsStringSync());
    final listed = array == null
        ? <String>{}
        : RegExp(r'<string>\s*([^<]+?)\s*</string>')
            .allMatches(array.group(1)!)
            .map((m) => _normalize(m.group(1)!))
            .toSet();
    expect(listed, locales.map(_normalize).toSet(),
        reason: 'run python3 scripts/l10n_locales.py sync');
  });
}
