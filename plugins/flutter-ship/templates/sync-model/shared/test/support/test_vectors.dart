import 'dart:convert';
import 'dart:io';

/// One case from `test_vectors/<name>.json`. The format is documented in
/// `test_vectors/vectors.schema.json`; backend/tests/vectors.py reads the
/// same files.
class VectorCase {
  VectorCase.fromJson(Map<String, Object?> json)
      : description = json['description']! as String,
        data = json['data']! as Map<String, Object?>,
        valid = json['valid']! as bool,
        errorField = json['error_field'] as String?,
        _expected = json['expected'] as Map<String, Object?>? {
    if (!valid && errorField == null) {
      throw FormatException('invalid case needs error_field: $description');
    }
  }

  final String description;
  final Map<String, Object?> data;
  final bool valid;
  final String? errorField;
  final Map<String, Object?>? _expected;

  /// The model's JSON after decoding [data]. Defaults to [data].
  Map<String, Object?> get expected => _expected ?? data;
}

/// Loads `test_vectors/<name>.json`, searching upward from the working
/// directory so the Flutter app can live at the repo root or in a subfolder.
List<VectorCase> loadVectors(String name) {
  final file = _findUp('test_vectors/$name.json');
  final json = jsonDecode(file.readAsStringSync()) as Map<String, Object?>;
  return [
    for (final c in json['cases']! as List<Object?>)
      VectorCase.fromJson(c! as Map<String, Object?>),
  ];
}

File _findUp(String relative) {
  var dir = Directory.current.absolute;
  while (true) {
    final file = File('${dir.path}/$relative');
    if (file.existsSync()) return file;
    if (dir.parent.path == dir.path) {
      throw StateError('$relative not found above ${Directory.current.path}');
    }
    dir = dir.parent;
  }
}
