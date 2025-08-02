"""PESUAuth Profile Model."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProfileModel(BaseModel):
    """Model representing the user's profile data returned after successful authentication."""

    model_config = ConfigDict(strict=True)

    name: str | None = Field(
        None,
        title="Full Name",
        description="Full name of the user.",
        json_schema_extra={"example": "John Doe"},
    )
    prn: str | None = Field(
        None,
        title="PRN",
        description="PRN of the user.",
        json_schema_extra={"example": "PES1201800001"},
    )
    srn: str | None = Field(
        None,
        title="SRN",
        description="SRN of the user.",
        json_schema_extra={"example": "PES1201800001"},
    )
    program: str | None = Field(
        None,
        title="Program",
        description="Academic program that the user is enrolled in.",
        json_schema_extra={"example": "Bachelor of Technology"},
    )
    branch: str | None = Field(
        None,
        title="Branch",
        description="Full name of the branch the user is pursuing.",
        json_schema_extra={"example": "Computer Science and Engineering"},
    )
    semester: str | None = Field(
        None,
        title="Semester",
        description="Current semester of the user.",
        json_schema_extra={"example": "2"},
    )
    section: str | None = Field(
        None,
        title="Section",
        description="Section the user belongs to.",
        json_schema_extra={"example": "C"},
    )
    email: str | None = Field(
        None,
        title="Email",
        description="Email address registered with PESU.",
        json_schema_extra={"example": "johndoe@gmail.com"},
    )
    phone: str | None = Field(
        None,
        title="Phone Number",
        description="Phone number registered with PESU.",
        json_schema_extra={"example": "1234567890"},
    )
    campus_code: Literal[1, 2] | None = Field(
        None,
        title="Campus Code",
        description="Numeric code representing the campus (1 for RR, 2 for EC).",
        json_schema_extra={"example": 1},
    )
    campus: str | None = Field(
        None,
        title="Campus",
        description="Abbreviation of the campus name.",
        json_schema_extra={"example": "RR"},
    )
