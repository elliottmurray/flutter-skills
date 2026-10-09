"""Runs test_vectors/user_profile.json against the Pydantic model.

The cases are shared with test/models/user_profile_test.dart. Add a case to
the JSON, not here. Tests below the parametrized one cover the constructor,
which JSON cannot reach; the Dart file has the same tests by name.
"""

import pytest
from pydantic import ValidationError
from vectors import load_vectors

from models.user_profile import UserProfile, UserRole


@pytest.mark.parametrize("case", load_vectors("user_profile"))
def test_user_profile_vector(case):
    if case["valid"]:
        expected = case.get("expected", case["data"])
        assert UserProfile.model_validate(case["data"]).to_json() == expected
    else:
        with pytest.raises(ValidationError) as exc:
            UserProfile.model_validate(case["data"])
        assert case["error_field"] in {error["loc"][0] for error in exc.value.errors()}


def test_constructs_with_valid_fields():
    profile = UserProfile(
        id="u1", display_name="Ada", email="ada@example.com", age=36, role=UserRole.ADMIN
    )
    assert profile.id == "u1"
    assert profile.display_name == "Ada"
    assert profile.email == "ada@example.com"
    assert profile.age == 36
    assert profile.role is UserRole.ADMIN


def test_validates_when_constructed_directly():
    with pytest.raises(ValidationError):
        UserProfile(id="", display_name="Ada", email="ada@example.com")
