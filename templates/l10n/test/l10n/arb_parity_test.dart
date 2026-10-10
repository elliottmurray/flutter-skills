import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// Matches `l10n.yaml`. The Claude hook and `scripts/l10n_locales.py` read
/// the same paths.
const _arbDir = 'lib/l10n';
const _template = 'app_en.arb';
const _infoPlist = 'ios/Runner/Info.plist';

/// An ICU argument after its `{`: `name}` or `name, kind,` / `name, kind}`.
final _argument = RegExp(r'\s*([A-Za-z_]\w*)\s*(?:,\s*(\w+)\s*)?([,}])');

/// A plural/select branch key and its opening `{`, or the argument's `}`.
final _branch = RegExp(r'\s*(?:([^\s{}]+)\s*\{|\})');
const _branched = {'plural', 'select', 'selectordinal'};

/// Translatable messages, minus ARB metadata (`@key`, `@@locale`).
Map<String, String> _messages(File file) {
  final json = jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;
  return {
    for (final entry in json.entries)
      if (!entry.key.startsWith('@')) entry.key: entry.value as String,
  };
}

/// Argument names in an ICU message: `{name}`, `{n, plural, …}`,
/// `{g, select, …}`. Plural and select branch bodies are messages in their own
/// right, so a one-word branch such as `other{they}` is text, not a
/// placeholder.
Set<String> _placeholders(String message) {
  final found = <String>{};
  // A stray top-level `}` is just text.
  for (var i = 0; i < message.length; i++) {
    i = _scanText(message, i, found);
  }
  return found;
}

/// Scans message text from [i]; returns the index of its closing `}` (or the
/// end).
int _scanText(String text, int i, Set<String> found) {
  for (; i < text.length; i++) {
    if (text[i] == '}') return i;
    if (text[i] == '{') i = _scanArgument(text, i + 1, found);
  }
  return i;
}

/// Scans an argument from just after its `{`; returns the index of its `}`.
int _scanArgument(String text, int i, Set<String> found) {
  final match = _argument.matchAsPrefix(text, i);
  if (match == null) return _skipBraces(text, i);
  found.add(match.group(1)!);
  i = match.end;
  if (match.group(3) == '}') return i - 1;
  // `{amount, number, currency}`
  if (!_branched.contains(match.group(2))) return _skipBraces(text, i);
  while (true) {
    final branch = _branch.matchAsPrefix(text, i);
    if (branch == null) return _skipBraces(text, i);
    if (branch.group(1) == null) return branch.end - 1;
    i = _scanText(text, branch.end, found) + 1;
  }
}

/// Index of the `}` that closes an already-open `{`, or the end.
int _skipBraces(String text, int i) {
  for (var depth = 1; i < text.length; i++) {
    if (text[i] == '{') depth++;
    if (text[i] == '}' && --depth == 0) return i;
  }
  return i;
}

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

  group('placeholders', () {
    test('one-word plural and select branches are text', () {
      expect(_placeholders('{g, select, male{he} female{she} other{they}}'),
          {'g'});
      expect(_placeholders('{n, plural, =0{none} other{{n} items}}'), {'n'});
    });

    test('arguments inside branches and formatted arguments count', () {
      expect(_placeholders('Hi {name}, {n, plural, other{{n} from {who}}}'),
          {'name', 'n', 'who'});
      expect(_placeholders('{amount, number, currency} on {day, date}'),
          {'amount', 'day'});
    });
  });

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
