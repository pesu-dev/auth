"""Models for the responses read from PESU Academy's mobile API."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    ValidatorFunctionWrapHandler,
    field_validator,
    model_validator,
)

# What upstream sends for a value it does not have. "NA" is what the web portal showed for a student
# with no current class; it is a placeholder, not a value, so it is treated like a missing one.
MISSING_VALUES = frozenset({"", "NA"})


class UpstreamModel(BaseModel):
    """Base for the response shapes read from PESU Academy.

    Only the fields this service returns are declared; everything else is dropped as the response is
    parsed. Those responses also carry the student's photo, blood group, addresses, marks and their
    parents' contact details. Never holding them means no log line, exception or repr can leak them.
    """

    model_config = ConfigDict(extra="ignore", coerce_numbers_to_str=True)

    @field_validator("*", mode="before")
    @classmethod
    def _placeholder_to_none(cls, value: Any) -> Any:  # noqa: ANN401
        """Treat a blank or placeholder string as a missing value.

        Upstream sends "" (and the web portal sent "NA") as often as null for a value it does not
        have, and all of them mean the same thing to a caller: null, not a string.

        Args:
            value (Any): The raw value from the response.

        Returns:
            Any: The value stripped, or None if it was blank or a placeholder.
        """
        if isinstance(value, str):
            value = value.strip()
            return None if value in MISSING_VALUES else value
        return value


class UpstreamDetails(UpstreamModel):
    """Base for a block of the user's details, whose every field is null unless PESU sent a usable value.

    A field PESU sends in an unexpected shape is null, like one it sends no value for, and the rest of
    the profile still comes back: one changed field does not fail every login that asks for a profile.
    """

    @field_validator("*", mode="wrap")
    @classmethod
    def _none_if_invalid(cls, value: Any, handler: ValidatorFunctionWrapHandler, info: ValidationInfo) -> Any:  # noqa: ANN401
        """Validate a field, turning a value of an unexpected shape into None.

        Args:
            value (Any): The raw value from the response.
            handler (ValidatorFunctionWrapHandler): The field's own validation.
            info (ValidationInfo): Which field is being validated.

        Returns:
            Any: The validated value, or None if it did not validate.
        """
        try:
            return handler(value)
        except ValidationError:
            # The field's name only: the value is from a response full of personal data
            logging.warning(f"Ignored an unexpected value for {info.field_name} in a PESU Academy response.")
            return None


class LoginUser(UpstreamDetails):
    """The user as described by the login response's `mobileJsonObject`.

    Read for the success marker and for isParent, which only the login response has. The rest of the
    profile comes from the profile response, so the login response's copies of the same details (some
    of them partial: its "name" is the first name only) are never mixed into it.
    """

    login: str | None = None
    # 0 for a student's own account; PESU Academy also has parent accounts
    is_parent: bool | None = Field(None, alias="isParent")


class LoginResponse(UpstreamModel):
    """The login response: the user, and the token the profile call needs."""

    user: LoginUser = Field(alias="mobileJsonObject")
    # repr=False so the bearer token cannot reach a log through the model's repr
    access_token: str | None = Field(None, alias="accessToken", repr=False)


class StudentInfo(UpstreamDetails):
    """The student as described by the profile response's `STUDENT_INFO`, the source of every field it has.

    For students whose PRN and SRN differ, PESU sends the PRN as LoginId and the SRN as SRN; for students
    who joined before SRNs existed, both hold the same ID.
    """

    prn: str | None = Field(None, alias="LoginId")
    srn: str | None = Field(None, alias="SRN")
    name: str | None = Field(None, alias="NameAsInSSLC")
    first_name: str | None = Field(None, alias="FirstName")
    middle_name: str | None = Field(None, alias="MiddleName")
    last_name: str | None = Field(None, alias="LastName")
    email: str | None = Field(None, alias="Email")
    mobile: str | None = Field(None, alias="Mobile")
    program: str | None = Field(None, alias="ProgramAbbreviation")
    branch: str | None = Field(None, alias="Branch")
    branch_short_code: str | None = Field(None, alias="BranchAbbreviation")
    class_name: str | None = Field(None, alias="ClassName")
    section_name: str | None = Field(None, alias="SectionName")
    date_of_birth: int | None = Field(None, alias="DateOfBirth")


class StudentPhoto(UpstreamDetails):
    """The profile response's `STUDENT_PHOTO`, read only for what STUDENT_INFO does not have."""

    # The campus, named by its institute: "PES University (Ring Road)"
    campus: str | None = Field(None, alias="instituteName")
    gender: str | None = None


class Student(UpstreamModel):
    """The student, from the blocks of the profile response."""

    info: StudentInfo
    campus: str | None = None
    gender: str | None = None


class ErrorEnvelope(UpstreamModel):
    """PESU's error body, which it can send with an HTTP 200, as in {"status": 400, "message": "..."}."""

    status: int
    message: str | None = None


def _has_values(block: BaseModel | None) -> bool:
    """Tell whether a parsed block holds any value at all.

    Args:
        block (BaseModel | None): The block, or None if it was absent.

    Returns:
        bool: True if the block is present and at least one of its fields is not None.
    """
    return block is not None and any(value is not None for value in block.model_dump().values())


class ProfileResponse(UpstreamModel):
    """The profile (dispatcher) response."""

    message: str = Field(alias="MESSAGE")
    info: StudentInfo | None = Field(None, alias="STUDENT_INFO")
    photo: StudentPhoto | None = Field(None, alias="STUDENT_PHOTO")

    @model_validator(mode="after")
    def _has_student(self) -> ProfileResponse:
        """Reject a response whose STUDENT_INFO describes no student.

        STUDENT_INFO is where most of the profile comes from, and nothing stands in for it. A block
        counts only if it holds a value: PESU sends `{}` for an empty block (PLACEMENT_DETAILS is one),
        and since every field is optional, `{}` -- or a block of only unknown, null or unusable values --
        would otherwise parse into an all-empty block and pass as a profile.

        Returns:
            ProfileResponse: The response, unchanged.

        Raises:
            ValueError: If STUDENT_INFO is missing or holds no student data.
        """
        if not _has_values(self.info):
            raise ValueError("STUDENT_INFO holds no student data")
        return self

    def student(self) -> Student:
        """Gather the student from the blocks of the response.

        Returns:
            Student: The student details.
        """
        photo = self.photo or StudentPhoto()
        return Student(info=self.info, campus=photo.campus, gender=photo.gender)
