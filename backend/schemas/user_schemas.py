import re
import unicodedata
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from backend.core.email import normalize_email

NAME_MAX_LENGTH = 100
# bcrypt só considera os primeiros 72 bytes da senha; o resto seria
# ignorado em silêncio. Recusar é mais honesto do que truncar.
PASSWORD_MAX_BYTES = 72


def clean_name(value: Optional[str]) -> Optional[str]:
    """Normaliza o nome: apara, junta espaços repetidos; vazio vira None."""
    if value is None:
        return None
    if any(unicodedata.category(char).startswith("C") for char in value if char not in " \t"):
        raise ValueError("O nome contém caracteres inválidos")
    cleaned = re.sub(r"\s+", " ", value).strip()
    if not cleaned:
        return None
    if len(cleaned) > NAME_MAX_LENGTH:
        raise ValueError(f"O nome pode ter no máximo {NAME_MAX_LENGTH} caracteres")
    return cleaned


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(
        ...,
        min_length=8,
        description="Mínimo de 8 caracteres, ao menos uma letra e um número; até 72 bytes.",
    )
    name: Optional[str] = Field(
        default=None,
        description=f"Nome de exibição, opcional (até {NAME_MAX_LENGTH} caracteres).",
    )

    @field_validator("email")
    @classmethod
    def normalize(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        if len(value.encode("utf-8")) > PASSWORD_MAX_BYTES:
            raise ValueError(f"A senha pode ter no máximo {PASSWORD_MAX_BYTES} bytes")
        if not any(char.isdigit() for char in value):
            raise ValueError("A senha deve conter pelo menos um número")
        if not any(char.isalpha() for char in value):
            raise ValueError("A senha deve conter pelo menos uma letra")
        return value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        return clean_name(value)


class UserOut(BaseModel):
    id: int
    email: EmailStr
    name: Optional[str] = None

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str
