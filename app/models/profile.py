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
    first_name: str | None = Field(
        None,
        title="First Name",
        description="First name of the user.",
        json_schema_extra={"example": "John"},
    )
    middle_name: str | None = Field(
        None,
        title="Middle Name",
        description="Middle name of the user. Null when the user has none.",
        json_schema_extra={"example": "Michael"},
    )
    last_name: str | None = Field(
        None,
        title="Last Name",
        description="Last name of the user.",
        json_schema_extra={"example": "Doe"},
    )
    program_short_code: str | None = Field(
        None,
        title="Program Short Code",
        description="Abbreviation of the program, as PESU Academy writes it.",
        json_schema_extra={"example": "B.Tech."},
    )
    branch_short_code: str | None = Field(
        None,
        title="Branch Short Code",
        description="Abbreviation of the branch.",
        json_schema_extra={"example": "CSE"},
    )
    institute: str | None = Field(
        None,
        title="Institute",
        description="Full name of the institute and campus.",
        json_schema_extra={"example": "PES University (Ring Road)"},
    )
    roll_number: int | None = Field(
        None,
        title="Roll Number",
        description="Roll number in the user's current (or latest) semester.",
        json_schema_extra={"example": 27},
    )
    gender: str | None = Field(
        None,
        title="Gender",
        description="Gender of the user, as recorded by PESU.",
        json_schema_extra={"example": "Male"},
    )
    date_of_birth: str | None = Field(
        None,
        title="Date of Birth",
        description="Date of birth of the user, as YYYY-MM-DD.",
        json_schema_extra={"example": "2002-01-31"},
    )
    blood_group: str | None = Field(
        None,
        title="Blood Group",
        description="Blood group of the user.",
        json_schema_extra={"example": "O+"},
    )
