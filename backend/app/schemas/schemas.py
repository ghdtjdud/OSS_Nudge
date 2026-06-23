import re
from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)


# =========================================================
# 회원가입 및 로그인 스키마
# =========================================================

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
    # 22시 이전
    BEFORE_22 = "BEFORE_22"

    # 22시 이상 24시 이전
    BETWEEN_22_24 = "BETWEEN_22_24"

    # 24시 이상 02시 이전
    BETWEEN_00_02 = "BETWEEN_00_02"

    # 02시 이후
    AFTER_02 = "AFTER_02"


class SleepDuration(str, Enum):
    # 4시간 미만
    UNDER_4 = "UNDER_4"

    # 4시간 이상 6시간 미만
    BETWEEN_4_6 = "BETWEEN_4_6"

    # 6시간 이상 8시간 미만
    BETWEEN_6_8 = "BETWEEN_6_8"

    # 8시간 이상
    OVER_8 = "OVER_8"


# =========================================================
# 식사 관련 선택지
# =========================================================

class MealRegularity(str, Enum):
    # 아침/점심/저녁을 대체로 규칙적으로 챙김
    ALL_MEALS_REGULAR = "ALL_MEALS_REGULAR"

    # 아침은 가끔 거르지만 점심/저녁은 대체로 챙김
    SOMETIMES_SKIP_BREAKFAST = (
        "SOMETIMES_SKIP_BREAKFAST"
    )

    # 점심이나 저녁 중 한 끼를 자주 거름
    OFTEN_SKIP_ONE_MEAL = "OFTEN_SKIP_ONE_MEAL"

    # 하루 세끼 전반적으로 불규칙하거나
    # 두 끼 이상 자주 거름
    GENERALLY_IRREGULAR = "GENERALLY_IRREGULAR"


# =========================================================
# 복약 관련 선택지
# =========================================================

class MedicationStatus(str, Enum):
    # 있음
    CURRENT = "CURRENT"

    # 없음
    NONE = "NONE"

    # 현재는 없지만 과거에 있었음
    PAST = "PAST"


class MedicationTiming(str, Enum):
    # 아침
    MORNING = "MORNING"

    # 점심
    LUNCH = "LUNCH"

    # 저녁
    EVENING = "EVENING"

    # 자기 전
    BEFORE_SLEEP = "BEFORE_SLEEP"


# =========================================================
# 일상 활동 관련 선택지
# =========================================================

class ActivityStartDifficulty(str, Enum):
    # 쉽게 시작함
    EASY = "EASY"

    # 조금 힘듦
    SOMEWHAT_DIFFICULT = "SOMEWHAT_DIFFICULT"

    # 많이 힘듦
    VERY_DIFFICULT = "VERY_DIFFICULT"

    # 거의 시작하기 어려움
    ALMOST_UNABLE_TO_START = (
        "ALMOST_UNABLE_TO_START"
    )


# =========================================================
# 사용자 상태정보 요청
# =========================================================

class UserRoutineRequest(BaseModel):
    # 최근 주로 잠드는 시간
    sleep_bedtime: SleepBedtime

    # 최근 평균 수면 시간
    sleep_duration: SleepDuration

    # 식사를 얼마나 규칙적으로 챙기는지
    meal_regularity: MealRegularity

    # 정기적으로 복용하는 약이 있는지
    medication_status: MedicationStatus

    # medication_status가 CURRENT인 경우에만 입력
    # 아침·점심·저녁·자기 전 중 복수 선택 가능
    medication_times: Optional[
        list[MedicationTiming]
    ] = None

    # 일상 활동을 시작하는 데 드는 어려움
    activity_start_difficulty: ActivityStartDifficulty

    @model_validator(mode="after")
    def validate_medication_information(self):
        # 정기적으로 복용하는 약이 있는 경우
        if (
            self.medication_status
            == MedicationStatus.CURRENT
        ):
            if not self.medication_times:
                raise ValueError(
                    "정기적으로 복용하는 약이 있는 경우 "
                    "복약 시간대를 하나 이상 선택해야 합니다."
                )

            # 동일한 시간대를 중복으로 보낸 경우 제거
            self.medication_times = list(
                dict.fromkeys(
                    self.medication_times
                )
            )

        # 없음 또는 과거 복약인 경우
        else:
            # 프론트에서 잘못 값을 보내더라도
            # 서버에서는 복약 시간을 저장하지 않음
            self.medication_times = None

        return self


class UserRoutineResponse(BaseModel):
    user_id: int

    sleep_bedtime: SleepBedtime
    sleep_duration: SleepDuration

    meal_regularity: MealRegularity

    medication_status: MedicationStatus

    medication_times: Optional[
        list[MedicationTiming]
    ] = None

    activity_start_difficulty: ActivityStartDifficulty

    onboarding_completed: bool = True

    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
    }

# =========================================================
# 채팅 관련 스키마
# =========================================================

class ChatInputType(str, Enum):
    TEXT = "text"
    VOICE = "voice"


class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatAction(str, Enum):
    CHAT = "CHAT"

    MEDICATION_CHECK_REQUIRED = (
        "MEDICATION_CHECK_REQUIRED"
    )

    MEDICATION_CONFIRMED = (
        "MEDICATION_CONFIRMED"
    )

    OPEN_MISSION_VERIFICATION = (
        "OPEN_MISSION_VERIFICATION"
    )


class ChatSessionResponse(BaseModel):
    id: int
    user_id: int
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


class ChatMessageRequest(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        max_length=5000,
    )

    input_type: ChatInputType = ChatInputType.TEXT

    @field_validator("content")
    @classmethod
    def validate_content(
        cls,
        value: str,
    ) -> str:
        normalized_content = value.strip()

        if not normalized_content:
            raise ValueError(
                "메시지 내용을 입력해주세요."
            )

        return normalized_content


class ChatMessageResponse(BaseModel):
    id: int
    session_id: int
    role: ChatRole
    content: str
    input_type: ChatInputType
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }

class ChatSessionCreateResponse(
    ChatSessionResponse
):
    initial_message: ChatMessageResponse

class ChatHistoryResponse(BaseModel):
    session_id: int
    messages: List[ChatMessageResponse]


# =========================================================
# 미션 관련 스키마
# =========================================================

class MissionResponse(BaseModel):
    id: int
    code: str
    title: str
    description: str
    category: str
    difficulty: int
    verification_code: str
    requires_current_medication: bool

    model_config = {
        "from_attributes": True,
    }


class GeminiMissionChoice(BaseModel):
    mission_code: str = Field(
        ...,
        description=(
            "후보 목록에 존재하는 "
            "mission_code 하나"
        ),
    )

    reason: str = Field(
        ...,
        min_length=1,
        max_length=300,
        description=(
            "사용자에게 보여줄 짧은 추천 이유"
        ),
    )


class UserMissionResponse(BaseModel):
    id: int
    user_id: int
    status: str
    recommended_reason: Optional[str] = None

    instance_key: str

    assigned_date: date
    assigned_at: datetime
    completed_at: Optional[datetime] = None

    mission: MissionResponse

    model_config = {
        "from_attributes": True,
    }


class MissionRecommendationResponse(BaseModel):
    message: str
    user_mission: UserMissionResponse


class MedicationAnswer(str, Enum):
    TAKEN = "TAKEN"
    NOT_TAKEN = "NOT_TAKEN"
    UNCLEAR = "UNCLEAR"


class GeminiMedicationAnswer(BaseModel):
    answer: MedicationAnswer


class ChatRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class GeminiChatResult(BaseModel):
    reply: str = Field(
        ...,
        min_length=1,
        max_length=2000,
    )

    should_recommend_mission: bool = False

    mission_context: Optional[str] = Field(
        default=None,
        max_length=300,
    )

    risk_level: ChatRiskLevel = ChatRiskLevel.LOW


class RecommendedMissionCard(BaseModel):
    user_mission_id: int
    mission_code: str

    # GENERAL 또는 MEDICATION
    mission_type: str

    # DB에 저장된 기본 미션 정보
    title: str
    description: str
    reason: Optional[str] = None
    status: str
    verification_code: str
    instance_key: str

    # 미션 카드 전체 화면에 표시할 문구
    card_title: str
    card_subtitle: str

    # 카메라 인증 준비 화면에 표시할 문구
    verification_title: str
    verification_subtitle: str


class ChatReplyResponse(BaseModel):
    session_id: int

    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse

    action: ChatAction = ChatAction.CHAT

    medication_check_slot: Optional[str] = None

    should_recommend_mission: bool = False
    mission_context: Optional[str] = None
    risk_level: ChatRiskLevel = ChatRiskLevel.LOW

    # 화면 전환용
    should_navigate_to_mission: bool = False
    next_screen: Optional[str] = None

    recommended_mission: Optional[
        RecommendedMissionCard
    ] = None

class BoundingBoxResponse(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class DetectedObjectResponse(BaseModel):
    class_id: int
    class_name: str
    confidence: float
    matched: bool
    bounding_box: BoundingBoxResponse


class MissionFrameVerificationResponse(
    BaseModel
):
    user_mission_id: int
    mission_code: str
    verification_code: str

    detected: bool
    expected_classes: list[str]
    detected_objects: list[
        DetectedObjectResponse
    ]

    stable_seconds: float
    required_seconds: float
    progress_percent: int

    completed: bool
    status: str