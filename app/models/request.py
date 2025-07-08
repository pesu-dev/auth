from pydantic import BaseModel, field_validator, ConfigDict
from typing import Optional, Literal
from app.constants import PESUAcademyConstants


class RequestModel(BaseModel):
    model_config = ConfigDict(strict=True)

    username: str
    password: str
    profile: bool = False
    fields: Optional[list[Literal[*PESUAcademyConstants.DEFAULT_FIELDS]]] = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Username cannot be empty.")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Password cannot be empty.")
        return v

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is not None:
            if not v:
                raise ValueError("Fields must be a non-empty list or None.")
            invalid = [f for f in v if f not in PESUAcademyConstants.DEFAULT_FIELDS]
            if invalid:
                raise ValueError(
                    f"Invalid fields: {', '.join(invalid)}. Valid fields are: {', '.join(PESUAcademyConstants.DEFAULT_FIELDS)}"
                )
        return v
