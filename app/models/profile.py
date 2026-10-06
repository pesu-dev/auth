"""Model representing the user's profile data returned after successful authentication."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

# The name of every field in ProfileModel, as a caller writes it in a request's fields
ProfileField = Literal[
    "name",
    "prn",
    "srn",
    "program",
    "branch",
    "semester",
    "section",
    "email",
    "mobile",
    "campusCode",
    "campus",
    "firstName",
    "middleName",
    "lastName",
    "branchShortCode",
    "gender",
    "dateOfBirth",
]


class ProfileModel(BaseModel):
    """The user's profile, returned after a successful login when it was requested.

    Only the fields below can be requested; any other name is a 400. Every requested field is present,
    and is null when PESU Academy has no value for it or sends it in an unexpected shape.
    """

    model_config = ConfigDict(strict=True, alias_generator=to_camel, populate_by_name=True)

    name: str | None = Field(
        None,
        title="Full Name",
        description="Full name of the user.",
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
        description="Abbreviation of the academic program the user is enrolled in, as PESU Academy writes it.",
        json_schema_extra={"example": "B.Tech."},
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
        description="Current semester, as PESU Academy writes it. Null when the user has graduated.",
        json_schema_extra={"example": "Sem-2"},
    )
    section: str | None = Field(
        None,
        title="Section",
        description="Current section, as PESU Academy writes it. Null when the user has graduated.",
        json_schema_extra={"example": "Section C"},
    )
    email: str | None = Field(
        None,
        title="Email",
        description="Email address registered with PESU.",
        json_schema_extra={"example": "johndoe@gmail.com"},
    )
    mobile: str | None = Field(
        None,
        title="Mobile Number",
        description="Mobile number registered with PESU.",
        json_schema_extra={"example": "1234567890"},
    )
    campus_code: Literal[1, 2] | None = Field(
        None,
        title="Campus Code",
        description=(
            "Code of the campus: 1 for PES University (Ring Road), 2 for PES University (Electronic City). Null "
            "for a campus whose name is not one of those."
        ),
        json_schema_extra={"example": 1},
    )
    campus: str | None = Field(
        None,
        title="Campus",
        description="Name of the campus's institute, as PESU Academy writes it.",
        json_schema_extra={"example": "PES University (Ring Road)"},
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
    branch_short_code: str | None = Field(
        None,
        title="Branch Short Code",
        description="Abbreviation of the branch, as PESU Academy writes it.",
        json_schema_extra={"example": "CSE"},
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
