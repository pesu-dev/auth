from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict


class ProfileModel(BaseModel):
    model_config = ConfigDict(strict=True)

    name: Optional[str] = Field(
        None,
        title="Full Name",
        description="Full name of the user.",
        example="John Doe",
    )
    prn: Optional[str] = Field(
        None,
        title="PRN",
        description="PRN of the user.",
        example="PES1201800001",
    )
    srn: Optional[str] = Field(
        None,
        title="SRN",
        description="SRN of the user.",
        example="PES1201800001",
    )
    program: Optional[str] = Field(
        None,
        title="Program",
        description="Academic program that the user is enrolled in.",
        example="Bachelor of Technology",
    )
    branch_short_code: Optional[str] = Field(
        None,
        title="Branch Short Code",
        description="Abbreviation of the branch the user is pursuing.",
        example="CSE",
    )
    branch: Optional[str] = Field(
        None,
        title="Branch",
        description="Full name of the branch the user is pursuing.",
        example="Computer Science and Engineering",
    )
    semester: Optional[str] = Field(
        None, title="Semester", description="Current semester of the user.", example="2"
    )
    section: Optional[str] = Field(
        None, title="Section", description="Section the user belongs to.", example="C"
    )
    email: Optional[str] = Field(
        None,
        title="Email",
        description="Email address registered with PESU.",
        example="johndoe@gmail.com",
    )
    phone: Optional[str] = Field(
        None,
        title="Phone Number",
        description="Phone number registered with PESU.",
        example="1234567890",
    )
    campus_code: Optional[Literal[1, 2]] = Field(
        None,
        title="Campus Code",
        description="Numeric code representing the campus (1 for RR, 2 for EC).",
        example=1,
    )
    campus: Optional[str] = Field(
        None,
        title="Campus",
        description="Abbreviation of the campus name.",
        example="RR",
    )
