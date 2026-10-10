import 'package:flutter_test/flutter_test.dart';

import 'package:{{PACKAGE_NAME}}/models/model_validation_error.dart';
import 'package:{{PACKAGE_NAME}}/models/user_profile.dart';

import '../support/test_vectors.dart';

// The cases live in test_vectors/user_profile.json and are shared with
// backend/tests/test_user_profile.py. Add a case there, not here. Tests below
// the loop cover the constructor, which JSON cannot reach; the pytest file has
// the same tests by name.

void main() {
  group('UserProfile vectors', () {
    for (final c in loadVectors('user_profile')) {
      test(c.description, () {
        if (c.valid) {
          expect(UserProfile.fromJson(c.data).toJson(), c.expected);
        } else {
          expect(
            () => UserProfile.fromJson(c.data),
            throwsA(
              isA<ModelValidationError>()
                  .having((e) => e.field, 'field', c.errorField),
            ),
          );
        }
      });
    }
  });

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

    test('validates when constructed directly', () {
      expect(
        () => UserProfile(id: '', displayName: 'Ada', email: 'ada@example.com'),
        throwsA(isA<ModelValidationError>()),
      );
    });
  });
}
