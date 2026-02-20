from pydantic import BaseModel, EmailStr, Field, field_validator  # Pydantic v2


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(
        ...,
        min_length=8,
        description="A senha deve ter no mínimo 8 caracteres, uma letra e um número."
    )

    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(char.isdigit() for char in v):
            raise ValueError('A senha deve conter pelo menos um número')
        if not any(char.isalpha() for char in v):
            raise ValueError('A senha deve conter pelo menos uma letra')
        return v


class UserOut(BaseModel):
    id: int
    email: EmailStr

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str
    