import re

from dataclasses import dataclass

from backend.app.models.models import (
    User,
)


# =========================================================
# 1차 규칙 기반 위기 신호
# =========================================================
#
# 임상 기준에서 확인하는 다음 급성 위험 요소를
# 명시적으로 표현한 경우에만 즉시 HIGH로 분류한다.
#
# - 현재 자살 사고 또는 의도
# - 구체적인 계획이나 준비 행동
# - 위험 수단 확보
# - 현재 또는 방금 전 자살·자해 시도
# - 스스로 안전을 유지하기 어렵다는 표현
# - 타인에게 즉각적인 위해를 가하려는 표현
#
# 이 규칙은 임상 진단이 아니라
# 긴급 지원 화면으로 보내기 위한 안전 라우팅이다.


@dataclass(frozen=True)
class RuleBasedCrisisResult:
    is_high: bool

    signals: tuple[str, ...] = ()
    matched_phrases: tuple[str, ...] = ()

    reason: str | None = None


@dataclass(frozen=True)
class CrisisPattern:
    signal: str
    pattern: re.Pattern[str]


CRISIS_PATTERNS = (
    CrisisPattern(
        signal=(
            "CURRENT_SUICIDAL_IDEATION"
        ),
        pattern=re.compile(
            r"(?:나는|내가|나|저는|제가)?\s*"
            r"(?:지금|오늘|당장|곧)?\s*"
            r"(?:정말|너무|계속|그냥)?\s*"
            r"(?:"
            r"죽고\s*싶"
            r"|"
            r"자살\s*(?:"
            r"하고\s*싶"
            r"|할\s*(?:거|것)"
            r"|하겠"
            r")"
            r"|"
            r"목숨을\s*끊(?:"
            r"고\s*싶"
            r"|을\s*(?:거|것)"
            r")"
            r")"
        ),
    ),

    CrisisPattern(
        signal="CURRENT_SUICIDAL_INTENT",
        pattern=re.compile(
            r"(?:나는|내가|나|저는|제가|"
            r"지금|오늘|당장|곧)"
            r".{0,12}"
            r"(?:죽을\s*거야|"
            r"죽겠다|"
            r"끝낼\s*거야)"
        ),
    ),

    CrisisPattern(
        signal=(
            "SUICIDE_PLAN_OR_PREPARATION"
        ),
        pattern=re.compile(
            r"(?:"
            r"죽으려고|"
            r"자살하려고|"
            r"목숨을\s*끊으려고"
            r")"
            r".{0,30}"
            r"(?:"
            r"준비했|"
            r"준비하고|"
            r"샀|"
            r"모았|"
            r"구했|"
            r"정했|"
            r"올라왔|"
            r"써놨|"
            r"가지고\s*있"
            r")"
        ),
    ),

    CrisisPattern(
        signal="ACCESS_TO_MEANS",
        pattern=re.compile(
            r"(?:"
            r"약|"
            r"수면제|"
            r"농약|"
            r"번개탄|"
            r"칼|"
            r"끈|"
            r"총|"
            r"옥상|"
            r"다리"
            r")"
            r".{0,25}"
            r"(?:"
            r"준비했|"
            r"샀|"
            r"모았|"
            r"구했|"
            r"가지고\s*있|"
            r"올라왔"
            r")"
            r".{0,25}"
            r"(?:죽|자살|목숨)"
        ),
    ),

    CrisisPattern(
        signal="CURRENT_OR_RECENT_ATTEMPT",
        pattern=re.compile(
            r"(?:"
            r"죽으려고|"
            r"자살하려고|"
            r"목숨을\s*끊으려고"
            r")"
            r".{0,20}"
            r"(?:"
            r"약|"
            r"수면제|"
            r"농약|"
            r"번개탄|"
            r"칼|"
            r"끈"
            r")"
            r".{0,20}"
            r"(?:"
            r"먹었|"
            r"복용했|"
            r"피웠|"
            r"그었|"
            r"베었|"
            r"찔렀|"
            r"묶었"
            r")"
            r"|"
            r"(?:약|수면제|농약)"
            r".{0,12}"
            r"(?:많이|한꺼번에|전부)"
            r".{0,12}"
            r"(?:먹었|복용했)"
        ),
    ),

    CrisisPattern(
        signal="CURRENT_SELF_HARM",
        pattern=re.compile(
            r"(?:지금|방금|이미)?"
            r".{0,10}"
            r"(?:손목|팔|몸)"
            r".{0,10}"
            r"(?:그었|베었|찔렀)"
        ),
    ),

    CrisisPattern(
        signal="INABILITY_TO_STAY_SAFE",
        pattern=re.compile(
            r"(?:나\s*자신을|나를)"
            r".{0,12}"
            r"(?:"
            r"못\s*막겠|"
            r"해칠\s*것\s*같|"
            r"죽일\s*것\s*같"
            r")"
            r"|"
            r"(?:곧|당장)"
            r".{0,12}"
            r"(?:"
            r"해버릴\s*것\s*같|"
            r"실행할\s*것\s*같"
            r")"
        ),
    ),

    CrisisPattern(
        signal="IMMEDIATE_HARM_TO_OTHERS",
        pattern=re.compile(
            r"(?:지금|오늘|당장|곧)"
            r".{0,15}"
            r"(?:"
            r"누군가|"
            r"사람|"
            r"걔|"
            r"그\s*사람|"
            r"가족"
            r")"
            r".{0,15}"
            r"(?:"
            r"죽일|"
            r"죽이려고|"
            r"해칠|"
            r"공격할|"
            r"때릴"
            r")"
            r".{0,10}"
            r"(?:"
            r"거야|"
            r"겠다|"
            r"려고"
            r")"
        ),
    ),
)


# 부정 표현을 HIGH로 잘못 읽지 않도록 제외
NEGATION_PATTERN = re.compile(
    r"(?:"
    r"죽고\s*싶(?:"
    r"지\s*않"
    r"|은\s*(?:건|것은)\s*아니"
    r")"
    r"|"
    r"자살(?:"
    r"하고\s*싶지\s*않"
    r"|할\s*생각(?:은|이)?\s*없"
    r"|할\s*(?:건|것은)\s*아니"
    r")"
    r"|"
    r"해칠\s*생각(?:은|이)?\s*없"
    r"|"
    r"죽을\s*생각(?:은|이)?\s*없"
    r")"
)


# 본인 현재 상태가 아닌 인용·과거·제3자 표현은
# 1차에서 즉시 HIGH로 확정하지 않고
# 2차 Gemini 문맥 판단으로 넘긴다.
NON_CURRENT_CONTEXT_PATTERN = re.compile(
    r"(?:"
    r"영화|"
    r"드라마|"
    r"뉴스|"
    r"소설|"
    r"노래\s*가사|"
    r"친구가|"
    r"지인이|"
    r"다른\s*사람이|"
    r"예전에|"
    r"과거에|"
    r"작년에|"
    r"몇\s*년\s*전"
    r")"
)


def normalize_crisis_text(
    value: str,
) -> str:
    return re.sub(
        r"\s+",
        " ",
        value.strip().lower(),
    )


def is_excluded_context(
    *,
    text: str,
    start: int,
    end: int,
) -> bool:
    context_window = text[
        max(0, start - 20):
        min(len(text), end + 20)
    ]

    if NEGATION_PATTERN.search(
        context_window
    ):
        return True

    prefix = text[
        max(0, start - 18):
        start
    ]

    if NON_CURRENT_CONTEXT_PATTERN.search(
        prefix
    ):
        return True

    return False


def detect_rule_based_high_risk(
    text: str,
) -> RuleBasedCrisisResult:
    """
    명시적이고 현재적인 급성 위험 표현을
    1차 규칙으로 확인한다.

    모호한 절망감이나 간접 표현은
    여기서 HIGH로 확정하지 않고
    Gemini의 2차 문맥 평가로 넘긴다.
    """

    normalized_text = (
        normalize_crisis_text(
            text
        )
    )

    if not normalized_text:
        return RuleBasedCrisisResult(
            is_high=False
        )

    matched_signals: list[str] = []
    matched_phrases: list[str] = []

    for crisis_pattern in CRISIS_PATTERNS:
        for match in (
            crisis_pattern
            .pattern
            .finditer(normalized_text)
        ):
            if is_excluded_context(
                text=normalized_text,
                start=match.start(),
                end=match.end(),
            ):
                continue

            matched_signals.append(
                crisis_pattern.signal
            )

            matched_phrases.append(
                match.group().strip()
            )

    unique_signals = tuple(
        dict.fromkeys(
            matched_signals
        )
    )

    unique_phrases = tuple(
        dict.fromkeys(
            matched_phrases
        )
    )

    if not unique_signals:
        return RuleBasedCrisisResult(
            is_high=False
        )

    return RuleBasedCrisisResult(
        is_high=True,
        signals=unique_signals,
        matched_phrases=unique_phrases,
        reason=(
            "현재의 자살·자해, 준비 행동, "
            "안전 유지 불가능 또는 즉각적인 "
            "위해 가능성을 나타내는 명시적 "
            "표현이 감지되었습니다."
        ),
    )


# =========================================================
# 긴급 지원 화면 정보
# =========================================================

def format_phone_number(
    phone: str,
) -> str:
    digits = re.sub(
        r"\D",
        "",
        phone,
    )

    if len(digits) == 11:
        return (
            f"{digits[:3]}-"
            f"{digits[3:7]}-"
            f"{digits[7:]}"
        )

    if (
        digits.startswith("02")
        and len(digits) == 10
    ):
        return (
            f"{digits[:2]}-"
            f"{digits[2:6]}-"
            f"{digits[6:]}"
        )

    if len(digits) == 10:
        return (
            f"{digits[:3]}-"
            f"{digits[3:6]}-"
            f"{digits[6:]}"
        )

    return digits


def build_crisis_contact(
    *,
    contact_type: str,
    label: str,
    phone: str,
) -> dict:
    return {
        "contact_type": contact_type,
        "label": label,
        "phone": phone,
        "display_phone": (
            format_phone_number(
                phone
            )
        ),
        "phone_uri": (
            f"tel:{phone}"
        ),
    }


def build_crisis_support(
    user: User,
) -> dict:
    """
    등록된 보호자 연락처가 있으면
    해당 번호를 1순위로 반환한다.

    연락처가 없으면 109를 1순위로 반환하고,
    주변 병원 검색 버튼을 활성화한다.

    서버가 자동으로 전화하거나 문자를 보내지는 않는다.
    """

    registered_phone = (
        user.guardian_phone.strip()
        if user.guardian_phone
        else None
    )

    if registered_phone:
        primary_contact = (
            build_crisis_contact(
                contact_type=(
                    "REGISTERED_GUARDIAN"
                ),
                label=(
                    "보호자 및 주치의"
                ),
                phone=registered_phone,
            )
        )

        secondary_contacts = [
            build_crisis_contact(
                contact_type=(
                    "SUICIDE_HOTLINE"
                ),
                label=(
                    "자살예방 상담전화"
                ),
                phone="109",
            ),
            build_crisis_contact(
                contact_type=(
                    "POLICE_EMERGENCY"
                ),
                label="경찰 긴급신고",
                phone="112",
            ),
            build_crisis_contact(
                contact_type=(
                    "MEDICAL_EMERGENCY"
                ),
                label="구급·응급신고",
                phone="119",
            ),
        ]

    else:
        primary_contact = (
            build_crisis_contact(
                contact_type=(
                    "SUICIDE_HOTLINE"
                ),
                label=(
                    "자살예방 상담전화"
                ),
                phone="109",
            )
        )

        secondary_contacts = [
            build_crisis_contact(
                contact_type=(
                    "POLICE_EMERGENCY"
                ),
                label="경찰 긴급신고",
                phone="112",
            ),
            build_crisis_contact(
                contact_type=(
                    "MEDICAL_EMERGENCY"
                ),
                label="구급·응급신고",
                phone="119",
            ),
        ]

    return {
        "title": "도움을 요청하세요",
        "message": (
            "지금 혼자 감당하지 말고 "
            "바로 연락 가능한 사람이나 "
            "전문 상담기관에 도움을 요청해주세요."
        ),
        "primary_contact": (
            primary_contact
        ),
        "secondary_contacts": (
            secondary_contacts
        ),
        "has_registered_contact": (
            registered_phone
            is not None
        ),
        "nearby_hospital_search_enabled": (
            registered_phone
            is None
        ),
        "tts_text": (
            "도움을 요청하세요. "
            "지금 혼자 있지 말고 "
            "화면의 연락처로 바로 "
            "도움을 요청해주세요. "
            "즉각적인 위험이 있다면 "
            "112 또는 119에 연락해주세요."
        ),
    }


def build_crisis_assistant_message() -> str:
    return (
        "지금 말씀해 주신 내용은 "
        "즉시 도움을 받아야 할 수 있는 "
        "신호예요. 혼자 있지 말고 "
        "화면에 표시된 연락처로 "
        "바로 도움을 요청해주세요. "
        "지금 당장 자신이나 다른 사람을 "
        "해칠 위험이 있다면 "
        "112 또는 119에 연락해주세요."
    )