import 'model_validation_error.dart';

// Wire contract shared with backend/models/user_profile.py. Keys are
// snake_case, null fields are omitted, unknown keys are ignored. Every rule
// below has a twin on the Python side; change them together.

enum UserRole { member, admin }

class UserProfile {
  /// Validates and normalizes, so a profile built in the app obeys the same
  /// rules as one decoded from the API.
  factory UserProfile({
    required String id,
    required String displayName,
    required String email,
    int? age,
    UserRole role = UserRole.member,
  }) {
    return UserProfile._(
      id: _validId(id),
      displayName: _validDisplayName(displayName),
      email: _validEmail(email),
      age: _validAge(age),
      role: role,
    );
  }

  const UserProfile._({
    required this.id,
    required this.displayName,
    required this.email,
    required this.age,
    required this.role,
  });

  factory UserProfile.fromJson(Map<String, Object?> json) {
    return UserProfile(
      id: requireString(json, 'id'),
      displayName: requireString(json, 'display_name'),
      email: requireString(json, 'email'),
      age: optionalInt(json, 'age'),
      role: _roleFromJson(json),
    );
  }

  static const minAge = 13;
  static const maxAge = 130;
  static const displayNameMaxLength = 50;

  final String id;
  final String displayName;
  final String email;
  final int? age;
  final UserRole role;

  Map<String, Object?> toJson() => {
        'id': id,
        'display_name': displayName,
        'email': email,
        if (age != null) 'age': age,
        'role': role.name,
      };

  @override
  bool operator ==(Object other) =>
      other is UserProfile &&
      other.id == id &&
      other.displayName == displayName &&
      other.email == email &&
      other.age == age &&
      other.role == role;

  @override
  int get hashCode => Object.hash(id, displayName, email, age, role);
}

// Same pattern string as EMAIL_PATTERN in the Python model. Deliberately
// simple: a library validator on either side would disagree with the other.
final _emailPattern = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');

String _validId(String id) {
  if (id.isEmpty) throw const ModelValidationError('id', 'must not be empty');
  return id;
}

String _validDisplayName(String raw) {
  final name = raw.trim();
  if (name.isEmpty) {
    throw const ModelValidationError('display_name', 'must not be blank');
  }
  // Count code points, not UTF-16 units: Python's len() counts code points,
  // and String.length would count an emoji as two.
  if (name.runes.length > UserProfile.displayNameMaxLength) {
    throw const ModelValidationError(
      'display_name',
      'must be at most ${UserProfile.displayNameMaxLength} characters',
    );
  }
  return name;
}

String _validEmail(String raw) {
  final email = raw.trim().toLowerCase();
  if (!_emailPattern.hasMatch(email)) {
    throw const ModelValidationError('email', 'is not an email address');
  }
  return email;
}

int? _validAge(int? age) {
  if (age == null) return null;
  if (age < UserProfile.minAge || age > UserProfile.maxAge) {
    throw const ModelValidationError(
      'age',
      'must be between ${UserProfile.minAge} and ${UserProfile.maxAge}',
    );
  }
  return age;
}

// Absent means the default; an explicit null is an error, as in Pydantic.
UserRole _roleFromJson(Map<String, Object?> json) {
  if (!json.containsKey('role')) return UserRole.member;
  final value = json['role'];
  for (final role in UserRole.values) {
    if (role.name == value) return role;
  }
  throw ModelValidationError('role', 'unknown role: $value');
}
