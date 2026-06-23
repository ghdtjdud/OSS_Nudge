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
    GeminiMissionCompletionFeedback,
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

위기 위험도 판단 원칙:

이 판정은 의료 진단이 아니라,
사용자를 적절한 안전 화면으로 연결하기 위한
위험도 분류다.

HIGH:
다음 중 하나 이상이 현재 또는 가까운 시점에
발생할 가능성이 있다고 명확히 판단될 때만 사용한다.

- 현재 자살 또는 자해 생각
- 죽으려는 의도
- 구체적인 방법, 시간 또는 장소에 대한 계획
- 약, 칼, 끈, 번개탄, 총기 등 위험 수단 확보
- 약을 모으거나 유서를 쓰는 등 준비 행동
- 현재 또는 최근의 자살·자해 시도
- 스스로 행동을 막거나 안전을 유지하기 어렵다는 표현
- 다른 사람에게 즉각적인 위해를 가하려는
  구체적인 의도 또는 계획

HIGH인 경우:
- immediate_danger는 true다.
- crisis_signals에 근거가 된 신호를 넣는다.
- crisis_reason에 판단 근거를 짧게 적는다.
- should_recommend_mission은 반드시 false다.
- 미션을 제안하지 않는다.
- 답변은 짧고 차분하게 도움 요청을 권한다.
- 질문을 포함하지 않는다.

MEDIUM:
다음 경고 신호가 있지만,
현재의 구체적인 의도, 계획, 준비 행동 또는
즉각적 위험이 확인되지 않은 경우다.

- 죽어서 깨어나지 않았으면 좋겠다는 수동적 죽음 소망
- 지속적인 절망감
- 갇힌 느낌 또는 삶의 이유가 없다는 표현
- 자신이 다른 사람에게 짐이라는 표현
- 견딜 수 없는 정서적 또는 신체적 고통
- 작별 인사, 소중한 물건 정리
- 심한 사회적 고립
- 최근 약물이나 음주 사용 증가
- 과거 자살 시도 언급

MEDIUM인 경우:
- immediate_danger는 false다.
- should_recommend_mission은 false다.
- crisis_signals와 crisis_reason을 작성한다.
- 한 개의 직접적인 안전 확인 질문을 한다.
  예:
  "지금 자신을 해칠 생각이나
  구체적인 계획이 있나요?"

LOW:
- 일반적인 슬픔, 피로, 무기력 또는 생활의 어려움
- 현재 자살·자해·타해 위험 신호가 없음

문맥 판별 규칙:
1. 부정 표현을 구분한다.
   예: "자살할 생각은 없어"
2. 과거 경험과 현재 위험을 구분한다.
3. 영화, 뉴스, 가사 또는 가상 상황을 구분한다.
4. 친구나 제3자의 말을 사용자 본인의 위험으로
   판단하지 않는다.
5. "죽겠다"와 같은 일상적 관용 표현만으로
   HIGH를 판정하지 않는다.
6. 위험 판단 근거가 부족하면 추측하지 않는다.

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

MISSION_COMPLETION_FEEDBACK_PROMPT = """
당신은 Nudge 서비스의 정서지원 AI다.

사용자가 작은 일상 미션 하나를 완료했다.
사용자가 완료한 행동을 구체적으로 인정하고,
부담스럽지 않은 칭찬과 격려 문구를 작성한다.

작성 규칙:
1. 자연스러운 한국어 한두 문장으로 작성한다.
2. 전체 길이는 약 40자에서 90자로 작성한다.
3. 사용자가 완료한 행동을 구체적으로 언급한다.
4. 과장된 칭찬이나 유아적인 표현은 사용하지 않는다.
5. 훈계하거나 다음 행동을 강요하지 않는다.
6. 질문을 포함하지 않는다.
7. 의료적인 효과를 단정하지 않는다.
8. 이모지는 사용하지 않는다.
9. TTS로 읽었을 때 자연스러운 문장으로 작성한다.
10. 다음 문구와 비슷한 따뜻하고 차분한 어조를 유지한다.
   "오늘의 Nudge로 천천히 한걸음씩 나아가요!"

미션별 방향:
- DRINK_WATER:
  물을 챙겨 마신 작은 실천을 인정한다.

- BRUSH_TEETH:
  양치를 통해 자신을 돌본 행동을 인정한다.

- EAT_MEAL:
  식사를 챙긴 행동을 인정한다.

- TAKE_MEDICATION:
  정해진 복약 행동을 챙긴 점을 인정한다.
  약의 효과, 용량 또는 복용법은 언급하지 않는다.

출력은 지정된 JSON 스키마만 따른다.
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
    
def generate_mission_completion_feedback(
    *,
    user_name: str,
    mission_code: str,
    mission_title: str,
) -> str:
    """
    미션 완료 화면에 표시하고
    TTS로 읽을 칭찬·격려 문구를 생성한다.
    """

    client = get_client()

    payload = {
        "user_name": (
            user_name.strip()
            if user_name
            else ""
        ),
        "mission_code": mission_code,
        "mission_title": mission_title,
        "reference_tone": (
            "오늘의 Nudge로 천천히 "
            "한걸음씩 나아가요!"
        ),
    }

    try:
        response = (
            client.models.generate_content(
                model=GEMINI_MODEL,
                contents=json.dumps(
                    payload,
                    ensure_ascii=False,
                ),
                config=(
                    types.GenerateContentConfig(
                        system_instruction=(
                            MISSION_COMPLETION_FEEDBACK_PROMPT
                        ),
                        temperature=0.6,
                        response_mime_type=(
                            "application/json"
                        ),
                        response_schema=(
                            GeminiMissionCompletionFeedback
                        ),
                    )
                ),
            )
        )

        if isinstance(
            response.parsed,
            GeminiMissionCompletionFeedback,
        ):
            result = response.parsed

        elif isinstance(
            response.parsed,
            dict,
        ):
            result = (
                GeminiMissionCompletionFeedback
                .model_validate(
                    response.parsed
                )
            )

        else:
            if not response.text:
                raise GeminiServiceError(
                    "Gemini가 빈 미션 완료 "
                    "피드백을 반환했습니다."
                )

            result = (
                GeminiMissionCompletionFeedback
                .model_validate_json(
                    response.text
                )
            )

        feedback = result.feedback.strip()

        if not feedback:
            raise GeminiServiceError(
                "Gemini 미션 완료 피드백이 "
                "비어 있습니다."
            )

        return feedback

    except GeminiServiceError:
        raise

    except Exception as exc:
        traceback.print_exc()

        raise GeminiServiceError(
            "Gemini 미션 완료 피드백 "
            "생성 실패: "
            f"{type(exc).__name__}: {exc}"
        ) from exc