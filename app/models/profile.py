from typing import Optional
from pydantic import BaseModel, ConfigDict


class ProfileModel(BaseModel):
    model_config = ConfigDict(strict=True)

    name: Optional[str] = None
    prn: Optional[str] = None
    srn: Optional[str] = None
    program: Optional[str] = None
    branch_short_code: Optional[str] = None
    branch: Optional[str] = None
    semester: Optional[str] = None
    section: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    campus_code: Optional[int] = None
    campus: Optional[str] = None
