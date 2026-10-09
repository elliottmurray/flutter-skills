"""Wire contract shared with lib/models/user_profile.dart.

Keys are snake_case, null fields are omitted, unknown keys are ignored. Every
rule below has a twin on the Dart side; change them together. Types are strict
because Dart's `is int` / `is String` checks never coerce: lax Pydantic would
accept "30" for an int and the two sides would disagree.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints

MIN_AGE = 13
MAX_AGE = 130
DISPLAY_NAME_MAX_LENGTH = 50
# Same pattern string as _emailPattern in the Dart model. Deliberately simple:
# EmailStr on this side would disagree with any Dart validator.
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

Id = Annotated[str, StringConstraints(strict=True, min_length=1)]
DisplayName = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=DISPLAY_NAME_MAX_LENGTH,
    ),
]
Email = Annotated[
    str,
    StringConstraints(
        strict=True, strip_whitespace=True, to_lower=True, pattern=EMAIL_PATTERN
    ),
]
Age = Annotated[StrictInt, Field(ge=MIN_AGE, le=MAX_AGE)]


class UserRole(StrEnum):
    MEMBER = "member"
    ADMIN = "admin"


class UserProfile(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    id: Id
    display_name: DisplayName
    email: Email
    age: Age | None = None
    role: UserRole = UserRole.MEMBER

    def to_json(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)
