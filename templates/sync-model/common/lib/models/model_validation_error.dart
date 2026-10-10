/// Thrown when JSON or constructor input breaks a model rule.
///
/// [field] is the wire (snake_case) name, so a Dart failure names the same
/// field as the `loc` of the matching Pydantic error on the backend. Tests on
/// both sides assert on that field, not on the message.
class ModelValidationError implements Exception {
  const ModelValidationError(this.field, this.message);

  final String field;
  final String message;

  @override
  String toString() => 'ModelValidationError($field): $message';
}

/// Reads a required string. Absent, null, or any other type is an error —
/// Pydantic's strict `str` behaves the same way.
String requireString(Map<String, Object?> json, String field) {
  final value = json[field];
  if (value == null) throw ModelValidationError(field, 'is required');
  if (value is! String) throw ModelValidationError(field, 'must be a string');
  return value;
}

/// Reads an optional int. Absent or null is null; `"30"` and `30.5` are
/// errors, matching Pydantic's `StrictInt`.
int? optionalInt(Map<String, Object?> json, String field) {
  final value = json[field];
  if (value == null) return null;
  if (value is! int) throw ModelValidationError(field, 'must be an integer');
  return value;
}
