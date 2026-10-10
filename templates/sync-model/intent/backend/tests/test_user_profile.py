"""Twin of test/models/user_profile_test.dart.

Every test here has a Dart twin with the same name in words
(test_rejects_unknown_role <-> 'rejects unknown role'). The sync-model hook
compares the two lists; add and rename them in pairs.
"""

import pytest
from pydantic import ValidationError

from models.user_profile import UserProfile, UserRole


def minimal() -> dict:
    return {"id": "u1", "display_name": "Ada", "email": "ada@example.com"}


def expect_rejects(data: dict, field: str) -> None:
    with pytest.raises(ValidationError) as exc:
        UserProfile.model_validate(data)
    assert field in {error["loc"][0] for error in exc.value.errors()}


def test_constructs_with_valid_fields():
    profile = UserProfile(
        id="u1", display_name="Ada", email="ada@example.com", age=36, role=UserRole.ADMIN
    )
    assert profile.id == "u1"
    assert profile.display_name == "Ada"
    assert profile.email == "ada@example.com"
    assert profile.age == 36
    assert profile.role is UserRole.ADMIN


def test_accepts_a_minimal_profile():
    profile = UserProfile.model_validate(minimal())
    assert profile.role is UserRole.MEMBER
    assert profile.age is None
    assert profile.to_json() == {**minimal(), "role": "member"}


def test_round_trips_through_serialization():
    data = {**minimal(), "age": 36, "role": "admin"}
    assert UserProfile.model_validate(data).to_json() == data


def test_trims_display_name():
    profile = UserProfile.model_validate({**minimal(), "display_name": "  Ada  "})
    assert profile.display_name == "Ada"


def test_trims_and_lowercases_email():
    profile = UserProfile.model_validate({**minimal(), "email": " Ada@Example.COM "})
    assert profile.email == "ada@example.com"


def test_rejects_missing_id():
    data = minimal()
    del data["id"]
    expect_rejects(data, "id")


def test_rejects_blank_display_name():
    expect_rejects({**minimal(), "display_name": "   "}, "display_name")


def test_rejects_display_name_over_50_characters():
    expect_rejects({**minimal(), "display_name": "a" * 51}, "display_name")


def test_counts_display_name_length_in_characters():
    profile = UserProfile.model_validate({**minimal(), "display_name": "🙂" * 50})
    assert len(profile.display_name) == 50


def test_rejects_email_without_at_sign():
    expect_rejects({**minimal(), "email": "ada.example.com"}, "email")


def test_rejects_age_below_13():
    expect_rejects({**minimal(), "age": 12}, "age")


def test_rejects_age_above_130():
    expect_rejects({**minimal(), "age": 131}, "age")


def test_rejects_age_given_as_a_string():
    expect_rejects({**minimal(), "age": "30"}, "age")


def test_rejects_fractional_age():
    expect_rejects({**minimal(), "age": 30.5}, "age")


def test_rejects_unknown_role():
    expect_rejects({**minimal(), "role": "owner"}, "role")


def test_rejects_null_role():
    expect_rejects({**minimal(), "role": None}, "role")


def test_ignores_unknown_keys():
    profile = UserProfile.model_validate({**minimal(), "legacy_id": 7})
    assert "legacy_id" not in profile.to_json()


def test_omits_null_age_from_json():
    profile = UserProfile.model_validate({**minimal(), "age": None})
    assert "age" not in profile.to_json()


def test_validates_when_constructed_directly():
    with pytest.raises(ValidationError):
        UserProfile(id="", display_name="Ada", email="ada@example.com")
