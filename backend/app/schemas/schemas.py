import re
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    field_validator,
    model_validator,
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

# =========================================================
# 수면 관련 선택지
# =========================================================

class SleepBedtime(str, Enum):
    BEFORE_22 = "BEFORE_22"
    BETWEEN_22_24 = "BETWEEN_22_24"
    BETWEEN_00_02 = "BETWEEN_00_02"
    AFTER_02 = "AFTER_02"


class SleepDuration(str, Enum):
    UNDER_4 = "UNDER_4"
    BETWEEN_4_6 = "BETWEEN_4_6"
    BETWEEN_6_8 = "BETWEEN_6_8"
    OVER_8 = "OVER_8"


class SleepCondition(str, Enum):
    DIFFICULT_TO_FALL_ASLEEP = (
        "DIFFICULT_TO_FALL_ASLEEP"
    )
    WAKE_FREQUENTLY = "WAKE_FREQUENTLY"
    SLEEP_TOO_MUCH = "SLEEP_TOO_MUCH"
    NO_MAJOR_ISSUE = "NO_MAJOR_ISSUE"


# =========================================================
# 식사 관련 선택지
# =========================================================

class BreakfastFrequency(str, Enum):
    REGULAR = "REGULAR"
    SOMETIMES = "SOMETIMES"
    RARELY = "RARELY"
    VARIES = "VARIES"


class LunchDinnerPattern(str, Enum):
    BOTH_REGULAR = "BOTH_REGULAR"
    SKIP_LUNCH_OFTEN = "SKIP_LUNCH_OFTEN"
    SKIP_DINNER_OFTEN = "SKIP_DINNER_OFTEN"
    SKIP_BOTH_OFTEN = "SKIP_BOTH_OFTEN"


class AppetiteChange(str, Enum):
    SAME_AS_USUAL = "SAME_AS_USUAL"
    DECREASED = "DECREASED"
    INCREASED = "INCREASED"
    UNKNOWN = "UNKNOWN"


# =========================================================
# 복약 관련 선택지
# =========================================================

class MedicationStatus(str, Enum):
    CURRENT = "CURRENT"
    NONE = "NONE"
    PAST = "PAST"


class MedicationTiming(str, Enum):
    MORNING = "MORNING"
    LUNCH = "LUNCH"
    EVENING = "EVENING"
    BEFORE_SLEEP = "BEFORE_SLEEP"
    MULTIPLE_TIMES = "MULTIPLE_TIMES"


class MedicationForgetFrequency(str, Enum):
    ALMOST_NEVER = "ALMOST_NEVER"
    SOMETIMES = "SOMETIMES"
    OFTEN = "OFTEN"
    VERY_OFTEN = "VERY_OFTEN"


# =========================================================
# 사용자 상태정보 요청
# =========================================================

class UserRoutineRequest(BaseModel):
    sleep_bedtime: SleepBedtime
    sleep_duration: SleepDuration
    sleep_condition: SleepCondition

    breakfast_frequency: BreakfastFrequency
    lunch_dinner_pattern: LunchDinnerPattern
    appetite_change: AppetiteChange

    medication_status: MedicationStatus

    medication_timing: Optional[
        MedicationTiming
    ] = None

    medication_forget_frequency: Optional[
        MedicationForgetFrequency
    ] = None

    @model_validator(mode="after")
    def validate_medication_information(self):
        if self.medication_status == MedicationStatus.CURRENT:
            if self.medication_timing is None:
                raise ValueError(
                    "현재 복약 중인 경우 "
                    "복약 시간을 선택해야 합니다."
                )

            if self.medication_forget_frequency is None:
                raise ValueError(
                    "현재 복약 중인 경우 "
                    "복약을 잊는 빈도를 선택해야 합니다."
                )

        else:
            # 복약 중이 아니라면 세부 복약정보 제거
            self.medication_timing = None
            self.medication_forget_frequency = None

        return self


class UserRoutineResponse(BaseModel):
    user_id: int

    sleep_bedtime: SleepBedtime
    sleep_duration: SleepDuration
    sleep_condition: SleepCondition

    breakfast_frequency: BreakfastFrequency
    lunch_dinner_pattern: LunchDinnerPattern
    appetite_change: AppetiteChange

    medication_status: MedicationStatus

    medication_timing: Optional[
        MedicationTiming
    ] = None

    medication_forget_frequency: Optional[
        MedicationForgetFrequency
    ] = None

    onboarding_completed: bool = True

    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
    }