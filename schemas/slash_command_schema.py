from typing import Literal, Optional
from pydantic import BaseModel, model_validator

class SlashCommandOption(BaseModel):
    name: str
    description: str
    type: Literal["str", "int", "bool", "enum", "float"]
    choices: Optional[list[str]] = None
    required: bool = True

    @model_validator(mode="after")
    def validate_enum_choices(self):
        if self.type == "enum" and not self.choices:
            raise ValueError("Enum options must define a non-empty 'choices' list")
        return self

class SlashCommand(BaseModel):
    name: str
    description: str
    whitelistRoles: Optional[list[str]] = None
    blacklistRoles: Optional[list[str]] = None
    options: list[SlashCommandOption] = []
    ephemeral: bool = False
