import json
import os
import traceback
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

from backend.app.schemas.schemas import (
    GeminiChatResult,
    GeminiMedicationAnswer,
    GeminiMissionChoice,
)


load_dotenv()

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY"
)

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.5-flash",
)


class GeminiServiceError(Exception):
    pass


def get_client() -> genai.Client:
    if not GEMINI_API_KEY:
        raise GeminiServiceError(
            "GEMINI_API_KEY 환경변수가 "
            "설정되지 않았습니다."
        )

    return genai.Client(
        api_key=GEMINI_API_KEY
    )


CHAT_SYSTEM_PROMPT = """
당신은 Nudge 서비스의 정서지원 대화 AI다.

역할:
1. 사용자의 감정을 먼저 짧게 확인하고 공감한다.
2. 한 번에 질문은 하나만 한다.
3. 답변은 자연스러운 한국어로 작성한다.
4. 과장된 위로나 훈계를 하지 않는다.
5. 의료적 진단을 내리지 않는다.
6. 처방약의 종류, 용량, 횟수 또는 복용법을 변경하도록 지시하지 않는다.

일반 미션 추천 판단:
- 물 마시기, 양치하기, 식사하기처럼
  작은 생활 행동이 도움 될 때만
  should_recommend_mission을 true로 한다.
- 단순 인사나 일반적인 대화이면 false다.
- 사용자가 미션을 거부하면 false다.
- 위험도가 HIGH이면 false다.
- 약 먹기 미션은 이 단계에서 판단하지 않는다.
  약 먹기 미션은 별도 복약 확인 절차에서만 생성한다.

위험도:
- LOW: 일반적인 감정 또는 생활 어려움
- MEDIUM: 지속적 절망이나 심각한 기능 저하
- HIGH: 자해, 자살, 타해 또는 즉각적 위험을 명시함

출력은 지정된 JSON 스키마만 따른다.
"""


MISSION_SYSTEM_PROMPT = """
당신은 Nudge 서비스의 일반 생활 미션 추천 모델이다.

available_missions 목록에서 정확히 하나만 선택한다.

규칙:
1. 후보에 없는 mission_code를 만들지 않는다.
2. TAKE_MEDICATION은 선택하지 않는다.
3. 최근 대화에서 사용자가 직접 표현한 필요를 우선한다.
4. 명확한 단서가 없으면 사용자 상태정보를 사용한다.
5. 여러 미션이 적절하면 가장 부담이 적은 것을 선택한다.

미션별 기준:
- EAT_MEAL:
  식사를 거르거나 식욕이 줄었다는 맥락
- BRUSH_TEETH:
  씻기, 양치, 위생관리 저하 맥락
- DRINK_WATER:
  수분 섭취 부족 또는 다른 강한 근거가 없을 때

reason은 자연스러운 한국어 한두 문장으로 작성한다.
출력은 지정된 JSON 스키마만 따른다.
"""


MEDICATION_ANSWER_PROMPT = """
사용자의 문장이 복약 여부 질문에 대한 답인지 분류한다.

TAKEN:
- 먹었다
- 복용했다
- 이미 챙겼다
- 방금 먹었다

NOT_TAKEN:
- 안 먹었다
- 아직 안 먹었다
- 깜빡했다
- 못 챙겼다

UNCLEAR:
- 복약 여부가 명확하지 않음
- 질문과 관계없는 말
- 먹었는지 여부를 판단할 수 없음

추측하지 말고 지정된 JSON 스키마만 반환한다.
"""


def generate_chat_response_with_gemini(
    *,
    user_message: str,
    user_profile: dict[str, Any] | None,
    recent_messages: list[dict[str, str]],
    current_time_context: dict[str, str],
) -> GeminiChatResult:
    client = get_client()

    payload = {
        "current_time": current_time_context,
        "user_profile": user_profile,
        "recent_messages": recent_messages,
        "current_user_message": user_message,
    }

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=json.dumps(
                payload,
                ensure_ascii=False,
            ),
            config=types.GenerateContentConfig(
                system_instruction=(
                    CHAT_SYSTEM_PROMPT
                ),
                temperature=0.5,
                response_mime_type=(
                    "application/json"
                ),
                response_schema=(
                    GeminiChatResult
                ),
            ),
        )

        if isinstance(
            response.parsed,
            GeminiChatResult,
        ):
            return response.parsed

        if isinstance(response.parsed, dict):
            return GeminiChatResult.model_validate(
                response.parsed
            )

        if not response.text:
            raise GeminiServiceError(
                "Gemini가 빈 채팅 응답을 반환했습니다."
            )

        return GeminiChatResult.model_validate_json(
            response.text
        )

    except GeminiServiceError:
        raise

    except Exception as exc:
        traceback.print_exc()

        raise GeminiServiceError(
            "Gemini 채팅 응답 생성 실패: "
            f"{type(exc).__name__}: {exc}"
        ) from exc


def classify_medication_answer(
    user_message: str,
) -> GeminiMedicationAnswer:
    client = get_client()

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=(
                    MEDICATION_ANSWER_PROMPT
                ),
                temperature=0,
                response_mime_type=(
                    "application/json"
                ),
                response_schema=(
                    GeminiMedicationAnswer
                ),
            ),
        )

        if isinstance(
            response.parsed,
            GeminiMedicationAnswer,
        ):
            return response.parsed

        if isinstance(response.parsed, dict):
            return (
                GeminiMedicationAnswer
                .model_validate(response.parsed)
            )

        if not response.text:
            raise GeminiServiceError(
                "복약 답변 분류 결과가 없습니다."
            )

        return (
            GeminiMedicationAnswer
            .model_validate_json(response.text)
        )

    except GeminiServiceError:
        raise

    except Exception as exc:
        traceback.print_exc()

        raise GeminiServiceError(
            "복약 답변 분류 실패: "
            f"{type(exc).__name__}: {exc}"
        ) from exc


def recommend_mission_with_gemini(
    *,
    user_profile: dict[str, Any],
    recent_messages: list[dict[str, str]],
    available_missions: list[dict[str, Any]],
) -> GeminiMissionChoice:
    client = get_client()

    if not available_missions:
        raise GeminiServiceError(
            "추천 가능한 미션이 없습니다."
        )

    payload = {
        "user_profile": user_profile,
        "recent_messages": recent_messages,
        "available_missions": (
            available_missions
        ),
    }

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=json.dumps(
                payload,
                ensure_ascii=False,
            ),
            config=types.GenerateContentConfig(
                system_instruction=(
                    MISSION_SYSTEM_PROMPT
                ),
                temperature=0.2,
                response_mime_type=(
                    "application/json"
                ),
                response_schema=(
                    GeminiMissionChoice
                ),
            ),
        )

        if isinstance(
            response.parsed,
            GeminiMissionChoice,
        ):
            return response.parsed

        if isinstance(response.parsed, dict):
            return GeminiMissionChoice.model_validate(
                response.parsed
            )

        if not response.text:
            raise GeminiServiceError(
                "Gemini가 빈 미션 결과를 반환했습니다."
            )

        return GeminiMissionChoice.model_validate_json(
            response.text
        )

    except GeminiServiceError:
        raise

    except Exception as exc:
        traceback.print_exc()

        raise GeminiServiceError(
            "Gemini 미션 추천 호출 실패: "
            f"{type(exc).__name__}: {exc}"
        ) from exc