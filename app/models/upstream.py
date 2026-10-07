"""Models for the responses read from PESU Academy's mobile API."""

from __future__ import annotations

from typing import Any, ClassVar

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

# The key in a validation context under which the validators below list the fields they set to None
UNEXPECTED_FIELDS = "unexpected_fields"


def _note_unexpected(info: ValidationInfo, name: str) -> None:
    """Record that a field was set to None for an unexpected shape, if the caller asked to be told.

    The models cannot reach the metrics collector or name the user, so they record the field here and
    PESUAcademy, which can do both, reports it.

    Args:
        info (ValidationInfo): The validation in progress, whose context holds the list to record into.
        name (str): The field, named as PESU names it, such as "STUDENT_INFO.SRN". Never its value.
    """
    if isinstance(info.context, dict) and isinstance(found := info.context.get(UNEXPECTED_FIELDS), list):
        found.append(name)


class UpstreamModel(BaseModel):
    """Base for the response shapes read from PESU Academy.

    Only the fields this service uses are declared; everything else is dropped as the response is
    parsed. Those responses also carry the student's photo, blood group, addresses, marks and their
    parents' contact details. Never holding them means no log line, exception or repr can leak them.
    """

    # coerce_numbers_to_str: PESU sends some text as numbers, a mobile number or an ID among them, and a
    # number where text is expected is the same value rather than an unexpected shape
    model_config = ConfigDict(extra="ignore", coerce_numbers_to_str=True)

    @field_validator("*", mode="before")
    @classmethod
    def _blank_to_none(cls, value: Any) -> Any:  # noqa: ANN401
        """Treat a blank string as a missing value.

        For a value it does not have, PESU sends either null or "" -- a student with no middle name gets
        "" -- and both mean the same thing to a caller: null, not an empty string. Any other text is
        returned as PESU wrote it, "NA" included: PESU's mobile API does not use it to mark a missing
        value, so in a field this service reads it would be real text, such as a surname stored in capitals.

        Args:
            value (Any): The raw value from the response.

        Returns:
            Any: The value stripped, or None if it was blank.
        """
        if isinstance(value, str):
            return value.strip() or None
        return value


class UpstreamDetails(UpstreamModel):
    """Base for a block of the user's details, whose every field is null unless PESU sent a usable value.

    A field PESU sends in an unexpected shape is null, like one it sends no value for, and the rest of
    the profile still comes back: one changed field does not fail every login that asks for a profile.

    Attributes:
        BLOCK (str): The name of the block in PESU's response, for naming its fields in logs.
    """

    BLOCK: ClassVar[str]

    @classmethod
    def pesu_name(cls, field_name: str) -> str:
        """Name a field as PESU does, with its block, such as "STUDENT_INFO.SRN".

        Args:
            field_name (str): The field's name on the model.

        Returns:
            str: The block and the key PESU sends the field under.
        """
        return f"{cls.BLOCK}.{cls.model_fields[field_name].alias or field_name}"

    @classmethod
    def missing_fields(cls, block: UpstreamDetails | None) -> list[str]:
        """List the fields PESU did not send at all, as opposed to sending without a value.

        Args:
            block (UpstreamDetails | None): The parsed block, or None if the response had no such block.

        Returns:
            list[str]: Each absent field, named as PESU names it.
        """
        sent = block.model_fields_set if block is not None else set()
        return [cls.pesu_name(name) for name in cls.model_fields if name not in sent]

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
            _note_unexpected(info, cls.pesu_name(info.field_name))
            return None


class LoginUser(UpstreamDetails):
    """The user as described by the login response's `mobileJsonObject`.

    Read only for the success marker. The profile comes from the profile response, so the login
    response's copies of the same details (some of them partial: its "name" is the first name only)
    are never mixed into it.
    """

    BLOCK = "mobileJsonObject"

    login: str | None = None


class LoginResponse(UpstreamModel):
    """The login response: the user, and the token the profile call needs."""

    user: LoginUser = Field(alias="mobileJsonObject")
    # repr=False so the bearer token cannot reach a log through the model's repr
    access_token: str | None = Field(None, alias="accessToken", repr=False)

    @field_validator("access_token", mode="wrap")
    @classmethod
    def _no_token_if_invalid(
        cls,
        value: Any,  # noqa: ANN401
        handler: ValidatorFunctionWrapHandler,
        info: ValidationInfo,
    ) -> str | None:
        """Treat a token of an unexpected shape as a missing one.

        Only a profile request needs the token, and it reports a missing one as a 502. Failing the
        whole login over it would turn every login into a 502, including the ones that never use it.

        Args:
            value (Any): The raw value from the response.
            handler (ValidatorFunctionWrapHandler): The field's own validation.
            info (ValidationInfo): The validation in progress.

        Returns:
            str | None: The token, or None if it did not validate.
        """
        try:
            return handler(value)
        except ValidationError:
            # Never the value: it would be a credential
            _note_unexpected(info, "accessToken")
            return None


class StudentInfo(UpstreamDetails):
    """The student as described by the profile response's `STUDENT_INFO`, the source of every field it has.

    For students whose PRN and SRN differ, PESU sends the PRN as LoginId and the SRN as SRN; for students
    who joined before SRNs existed, both hold the same ID.
    """

    BLOCK = "STUDENT_INFO"

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
    """The profile response's `STUDENT_PHOTO` block, read only for what STUDENT_INFO does not have.

    Named after the block PESU sends, as StudentInfo is after STUDENT_INFO. Besides the photo, the block
    carries the campus and gender; the photo itself is never read.
    """

    BLOCK = "STUDENT_PHOTO"

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

    @property
    def succeeded(self) -> bool:
        """Whether PESU says it found the profile: MESSAGE is "SUCCESS_Record found Successfully" then.

        Returns:
            bool: True if MESSAGE reports success.
        """
        return self.message.startswith("SUCCESS")

    @model_validator(mode="after")
    def _has_student(self) -> ProfileResponse:
        """Reject a successful response whose STUDENT_INFO describes no student.

        STUDENT_INFO is where most of the profile comes from, and nothing stands in for it. A block
        counts only if it holds a value: PESU sends `{}` for an empty block (PLACEMENT_DETAILS is one),
        and since every field is optional, `{}` -- or a block of only unknown, null or unusable values --
        would otherwise parse into an all-empty block and pass as a profile.

        Only a response that reports success has to describe a student. One that does not is PESU
        declining to serve the profile, which the caller reports as such; it need not carry a student.

        Returns:
            ProfileResponse: The response, unchanged.

        Raises:
            ValueError: If the response reports success but STUDENT_INFO is missing or holds no student data.
        """
        if self.succeeded and not _has_values(self.info):
            raise ValueError("STUDENT_INFO holds no student data")
        return self

    def missing_fields(self) -> list[str]:
        """List the fields this service reads that PESU did not send at all, named as PESU names them.

        A key PESU sends with no value ("" or null) is not missing: that is PESU having no value for
        this student. A key that is absent means PESU stopped sending it, which is a change to its API.

        Returns:
            list[str]: The absent fields, such as "STUDENT_INFO.SRN".
        """
        return StudentInfo.missing_fields(self.info) + StudentPhoto.missing_fields(self.photo)

    def student(self) -> Student:
        """Gather the student from the blocks of the response.

        Returns:
            Student: The student details.
        """
        photo = self.photo or StudentPhoto()
        return Student(info=self.info, campus=photo.campus, gender=photo.gender)
