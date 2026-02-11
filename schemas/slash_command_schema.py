from typing import Literal, Optional
from pydantic import BaseModel

class SlashCommandOption(BaseModel):
    name: str
    description: str
    type: Literal["string", "integer", "boolean", "enum", "float"]
    choices: Optional[list] = None
    required: bool = True

class SlashCommand(BaseModel):
    name: str
    description: str
    whitelistRoles: Optional[list[str]] = None
    blacklistRoles: Optional[list[str]] = None
    options: list[SlashCommandOption] = []
    ephemeral: bool = False