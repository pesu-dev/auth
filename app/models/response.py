from typing import Optional
from pydantic import BaseModel, ConfigDict

from app.models.profile import ProfileModel


class ResponseModel(BaseModel):
    model_config = ConfigDict(strict=True)

    status: bool
    message: str
    timestamp: str
    profile: Optional[ProfileModel] = None
