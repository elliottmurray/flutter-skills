import 'package:flutter_test/flutter_test.dart';

import 'package:{{PACKAGE_NAME}}/models/model_validation_error.dart';
import 'package:{{PACKAGE_NAME}}/models/user_profile.dart';

// Every test here has a twin in backend/tests/test_user_profile.py with the
// same name in snake_case ('rejects unknown role' ↔ test_rejects_unknown_role).
// The sync-model hook compares the two lists; add and rename them in pairs.

Map<String, Object?> minimal() => {
      'id': 'u1',
      'display_name': 'Ada',
      'email': 'ada@example.com',
    };

void expectRejects(Map<String, Object?> json, String field) {
  expect(
    () => UserProfile.fromJson(json),
    throwsA(isA<ModelValidationError>().having((e) => e.field, 'field', field)),
  );
}

void main() {
  group('UserProfile', () {
    test('constructs with valid fields', () {
      final profile = UserProfile(
        id: 'u1',
        displayName: 'Ada',
        email: 'ada@example.com',
        age: 36,
        role: UserRole.admin,
      );
      expect(profile.id, 'u1');
      expect(profile.displayName, 'Ada');
      expect(profile.email, 'ada@example.com');
      expect(profile.age, 36);
      expect(profile.role, UserRole.admin);
    });

    test('accepts a minimal profile', () {
      final profile = UserProfile.fromJson(minimal());
      expect(profile.role, UserRole.member);
      expect(profile.age, isNull);
      expect(profile.toJson(), {...minimal(), 'role': 'member'});
    });

    test('round-trips through serialization', () {
      final json = {...minimal(), 'age': 36, 'role': 'admin'};
      expect(UserProfile.fromJson(json).toJson(), json);
    });

    test('trims display name', () {
      final profile = UserProfile.fromJson({
        ...minimal(),
        'display_name': '  Ada  ',
      });
      expect(profile.displayName, 'Ada');
    });

    test('trims and lowercases email', () {
      final profile = UserProfile.fromJson({
        ...minimal(),
        'email': ' Ada@Example.COM ',
      });
      expect(profile.email, 'ada@example.com');
    });

    test('rejects missing id', () {
      expectRejects(minimal()..remove('id'), 'id');
    });

    test('rejects blank display name', () {
      expectRejects({...minimal(), 'display_name': '   '}, 'display_name');
    });

    test('rejects display name over 50 characters', () {
      expectRejects({...minimal(), 'display_name': 'a' * 51}, 'display_name');
    });

    test('counts display name length in characters', () {
      final profile = UserProfile.fromJson({
        ...minimal(),
        'display_name': '🙂' * 50,
      });
      expect(profile.displayName.runes.length, 50);
    });

    test('rejects email without at sign', () {
      expectRejects({...minimal(), 'email': 'ada.example.com'}, 'email');
    });

    test('rejects age below 13', () {
      expectRejects({...minimal(), 'age': 12}, 'age');
    });

    test('rejects age above 130', () {
      expectRejects({...minimal(), 'age': 131}, 'age');
    });

    test('rejects age given as a string', () {
      expectRejects({...minimal(), 'age': '30'}, 'age');
    });

    test('rejects fractional age', () {
      expectRejects({...minimal(), 'age': 30.5}, 'age');
    });

    test('rejects unknown role', () {
      expectRejects({...minimal(), 'role': 'owner'}, 'role');
    });

    test('rejects null role', () {
      expectRejects({...minimal(), 'role': null}, 'role');
    });

    test('ignores unknown keys', () {
      final profile = UserProfile.fromJson({...minimal(), 'legacy_id': 7});
      expect(profile.toJson().containsKey('legacy_id'), isFalse);
    });

    test('omits null age from json', () {
      final profile = UserProfile.fromJson({...minimal(), 'age': null});
      expect(profile.toJson().containsKey('age'), isFalse);
    });

    test('validates when constructed directly', () {
      expect(
        () => UserProfile(id: '', displayName: 'Ada', email: 'ada@example.com'),
        throwsA(isA<ModelValidationError>()),
      );
    });
  });
}
