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

대화 원칙:
1. 사용자의 감정을 먼저 짧게 확인하고 공감한다.
2. 한 번의 응답에는 질문을 최대 하나만 포함한다.
3. 자연스럽고 짧은 한국어로 답한다.
4. 과장된 위로, 훈계, 평가를 하지 않는다.
5. 의료적 진단을 내리지 않는다.
6. 처방약의 종류, 용량, 횟수 또는 복용법을
   변경하도록 지시하지 않는다.
7. 미션을 직접 확정했다고 말하지 않는다.
   미션 생성은 서버가 별도로 처리한다.
8. current_time.medication_check_required가 true이면
   서버가 복약 질문을 뒤에 붙이므로
   당신의 답변에는 질문을 넣지 않는다.

일반 미션 추천 판단:
- 사용자가 현재 작은 생활 행동을 시작하면
  도움이 될 상태인지 판단한다.
- 다음 표현은 LOW 위험도라면
  should_recommend_mission을 true로 판단한다.
  예:
  "기운이 없어"
  "축 처져"
  "아무것도 하기 싫어"
  "밥을 못 먹었어"
  "물을 거의 안 마셨어"
  "씻거나 양치하기가 힘들어"
- 단순 인사, 정보 질문, 일상 잡담이면 false다.
- 사용자가 미션을 거부했거나
  현재 원하지 않는다고 말하면 false다.
- 위험도가 HIGH이면 반드시 false다.
- 복약 미션은 이 단계에서 판단하지 않는다.
  복약 미션은 서버의 별도 복약 확인 절차에서만 생성한다.
- true인 경우 mission_context에는
  미션이 도움이 된다고 판단한 핵심 근거를
  짧게 작성한다.
- should_recommend_mission이 true이면
  답변 끝에 질문을 넣지 않는다.
- 사용자가 바로 미션 인증 화면으로 이동하므로,
  짧은 공감과 작은 행동을 제안하는 문장으로 끝낸다.

위험도:
- LOW:
  일반적인 감정 저하 또는 생활의 어려움
- MEDIUM:
  지속적 절망, 심각한 기능 저하,
  장기간의 무기력
- HIGH:
  자해, 자살, 타해 또는
  즉각적 위험을 명시함

출력은 지정된 JSON 스키마만 따른다.
"""


MISSION_SYSTEM_PROMPT = """
당신은 Nudge 서비스의 일반 생활 미션 추천 모델이다.

available_missions 목록에서 정확히 하나만 선택한다.

규칙:
1. 후보에 없는 mission_code를 만들지 않는다.
2. TAKE_MEDICATION은 선택하지 않는다.
3. 가장 최근 사용자 메시지의 직접적인 필요를
   최우선으로 본다.
4. 직접적인 단서가 부족하면
   사용자 상태정보를 보조적으로 사용한다.
5. 여러 미션이 적절하면 가장 부담이 적고
   즉시 시작하기 쉬운 것을 선택한다.
6. 사용자가 기운이 없거나 축 처졌다고만 말했고
   다른 직접 단서가 없다면,
   후보 중 가장 부담이 적은 기본 생활 미션을 선택한다.

판단 예시:
- EAT_MEAL:
  식사를 거르거나 배가 고프거나
  식사 리듬이 무너진 맥락

- BRUSH_TEETH:
  씻기, 양치, 위생관리 시작이 어려운 맥락

- DRINK_WATER:
  수분 섭취 부족, 기운 저하,
  또는 더 강한 직접 단서가 없는 맥락

reason은 사용자가 바로 행동할 수 있도록
자연스러운 한국어 한두 문장으로 작성한다.

출력은 지정된 JSON 스키마만 따른다.
"""

MEDICATION_ANSWER_PROMPT = """
사용자의 문장이 복약 여부 질문에 대한 답인지 분류한다.

TAKEN:
- 약을 먹었다고 명확히 답한 경우
- 먹었어
- 응, 먹었어
- 이미 먹었어
- 복용했어
- 약 챙겼어
- 방금 먹었어
- 아까 먹었어

NOT_TAKEN:
- 약을 아직 먹지 않았다고 명확히 답한 경우
- 안 먹었어
- 아직 안 먹었어
- 못 먹었어
- 깜빡했어
- 못 챙겼어
- 나중에 먹으려고
- 지금 먹으려고

UNCLEAR:
- 복약 여부가 명확하지 않은 경우
- 질문과 관계없는 말을 한 경우
- 먹었는지 여부를 판단할 수 없는 경우
- 단순히 모르겠다고 답한 경우

중요 규칙:
1. "아직 안 먹었어"는 반드시 NOT_TAKEN이다.
2. "이미 먹었어"는 반드시 TAKEN이다.
3. 추측하지 않는다.
4. 지정된 JSON 스키마만 반환한다.
"""


def generate_chat_response_with_gemini(
    *,
    user_message: str,
    user_profile: dict[str, Any] | None,
    recent_messages: list[dict[str, str]],
    current_time_context: dict[str, Any],
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