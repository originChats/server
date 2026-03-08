from typing import Literal, Optional
from pydantic import BaseModel, Base64Str, field_validator
import re
import base64

DATA_URI_PATTERN = re.compile(r"^data:(image\/[a-zA-Z0-9.+-]+);base64,(.+)$")

class Emoji_add(BaseModel):
    cmd: Literal["emoji_add"]
    name: str
    image: Base64Str
    
class Emoji_delete(BaseModel):
    cmd: Literal["emoji_delete"]
    emoji_id: int

class Emoji_get_all(BaseModel):
    cmd: Literal["emoji_get_all"]

class Emoji_get_id(BaseModel):
    cmd: Literal["emoji_get_id"]
    name: str

class Emoji_get_filename(BaseModel):
    cmd: Literal["emoji_get_filename"]
    name: str

class Emoji_update(BaseModel):
    cmd: Literal["emoji_update"]
    emoji_id: int
    name: Optional[str] = None
    image: Optional[str] = None
    
    @field_validator("image")
    @classmethod
    def validate_data_uri(cls, v):
        if v is None:
            return v

        match = DATA_URI_PATTERN.match(v)
        if not match:
            raise ValueError("Invalid image data URI")

        mime, b64_data = match.groups()

        try:
            base64.b64decode(b64_data, validate=True)
        except Exception:
            raise ValueError("Invalid base64 image data")

        return v
