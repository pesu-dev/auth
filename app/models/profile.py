"""Model representing the user's profile data returned after successful authentication."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ProfileModel(BaseModel):
    """Model representing the user's profile data returned after successful authentication."""

    model_config = ConfigDict(strict=True, alias_generator=to_camel, populate_by_name=True)

    name: str | None = Field(
        None,
        title="Full Name",
        description="Full name of the user, as registered with PESU.",
        json_schema_extra={"example": "John Doe"},
    )
    prn: str | None = Field(
        None,
        title="PRN",
        description="PRN of the user. Null when PESU Academy does not return one.",
        json_schema_extra={"example": "PES1202000001"},
    )
    srn: str | None = Field(
        None,
        title="SRN",
        description="SRN of the user.",
        json_schema_extra={"example": "PES1UG20CS001"},
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
        description="Current semester the user is pursuing. Null when the user is not in a class.",
        json_schema_extra={"example": "Sem-2"},
    )
    section: str | None = Field(
        None,
        title="Section",
        description="Section the user belongs to. Null when the user is not in a class.",
        json_schema_extra={"example": "Section C"},
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
