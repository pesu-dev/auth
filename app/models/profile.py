"""Model representing the user's profile data returned after successful authentication."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ProfileModel(BaseModel):
    """The user's profile, returned after a successful login when it was requested.

    Every requested field is present. A field PESU Academy has no value for is null, as is one of the
    fields added with the mobile API (name parts, short codes, institute, roll number, gender, date of
    birth) if PESU sends it in an unexpected shape.
    """

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
        description=(
            "PRN of the user: PES, the campus digit, the year of joining and a 5-digit number. Null when "
            "PESU Academy does not return one."
        ),
        json_schema_extra={"example": "PES1202000001"},
    )
    srn: str | None = Field(
        None,
        title="SRN",
        description=(
            "SRN of the user: PES, the campus digit, the program, the last two digits of the year of joining, "
            "the branch and a 3-digit number. For students who joined before SRNs were introduced, it is the "
            "same as their PRN."
        ),
        json_schema_extra={"example": "PES1UG20CS001"},
    )
    program: str | None = Field(
        None,
        title="Program",
        description=(
            "Full name of the academic program the user is enrolled in. A program abbreviation that is not "
            "recognised is returned as PESU Academy sent it."
        ),
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
        description="Current semester, such as Sem-4. Null when the user is not in a class.",
        json_schema_extra={"example": "Sem-2"},
    )
    section: str | None = Field(
        None,
        title="Section",
        description="Current section, such as Section C. Null when the user is not in a class.",
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
        description=(
            "Code of the campus, 1 for RR and 2 for EC, worked out from the SRN (or the PRN when there is no SRN)."
        ),
        json_schema_extra={"example": 1},
    )
    campus: str | None = Field(
        None,
        title="Campus",
        description="Abbreviation of the campus: RR or EC.",
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
        description="Abbreviation of the branch, such as CSE.",
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
        description=(
            "Roll number in the user's current semester, or their last one if they have graduated. Null when "
            "that semester has none."
        ),
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
