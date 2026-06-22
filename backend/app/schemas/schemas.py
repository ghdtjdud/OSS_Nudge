import re
from typing import Optional

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    field_validator,
)


class SignupRequest(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    email: EmailStr

    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
    )

    phone: str = Field(
        ...,
        min_length=10,
        max_length=20,
    )

    guardian_phone: Optional[str] = Field(
        default=None,
        max_length=30,
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized_name = value.strip()

        if not normalized_name:
            raise ValueError(
                "이름을 입력해주세요."
            )

        return normalized_name

    @field_validator("email")
    @classmethod
    def normalize_email(
        cls,
        value: EmailStr,
    ) -> str:
        return str(value).strip().lower()

    @field_validator("phone")
    @classmethod
    def validate_phone(
        cls,
        value: str,
    ) -> str:
        digits = re.sub(r"\D", "", value)

        if len(digits) not in (10, 11):
            raise ValueError(
                "전화번호는 숫자 기준 "
                "10자리 또는 11자리여야 합니다."
            )

        return digits

    @field_validator("guardian_phone")
    @classmethod
    def validate_guardian_phone(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None

        value = value.strip()

        if not value:
            return None

        digits = re.sub(r"\D", "", value)

        if len(digits) not in (10, 11):
            raise ValueError(
                "보호자 또는 주치의 연락처는 "
                "숫자 기준 10자리 또는 11자리여야 합니다."
            )

        return digits


class LoginRequest(BaseModel):
    email: EmailStr

    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    @field_validator("email")
    @classmethod
    def normalize_email(
        cls,
        value: EmailStr,
    ) -> str:
        return str(value).strip().lower()


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    name: str
    phone: str
    guardian_phone: Optional[str] = None

    model_config = {
        "from_attributes": True,
    }


class SignupResponse(BaseModel):
    message: str
    user: UserResponse


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse