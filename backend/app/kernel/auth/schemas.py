from pydantic import BaseModel, Field, field_validator


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=8, max_length=72)
    nickname: str = Field(min_length=1, max_length=64)
    grade: str | None = Field(default=None, max_length=32)
    main_subject: str | None = Field(default=None, max_length=32)


class LoginRequest(BaseModel):
    username: str
    password: str


class UserUpdateRequest(BaseModel):
    nickname: str | None = Field(default=None, min_length=1, max_length=64)
    grade: str | None = Field(default=None, max_length=32)
    school: str | None = Field(default=None, max_length=128)
    main_subject: str | None = Field(default=None, max_length=32)

    @field_validator("nickname", mode="before")
    @classmethod
    def nickname_cannot_be_null(cls, value: object):
        if value is None:
            raise ValueError("nickname cannot be null")
        return value


class PasswordUpdateRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=72)
