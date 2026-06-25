import re
from datetime import datetime

from sqlalchemy.orm import (
    Session,
    joinedload,
)

from backend.app.models.models import (
    Mission,
    UserMission,
    UserRoutineProfile,
)
from backend.app.services.gemini_service import (
    GeminiServiceError,
    recommend_mission_with_gemini,
)
from backend.app.services.medication_service import (
    get_current_time_slot,
)


ACTIVE_MISSION_STATUSES = (
    "ASSIGNED",
    "IN_PROGRESS",
)

# =========================================================
# Gemini 장애 시 사용할 일반 미션 fallback 규칙
# =========================================================

FALLBACK_MISSION_PATTERNS = {
    "DRINK_WATER": (
        re.compile(
            r"(?:"
            r"물을\s*(?:안|못|거의|별로|조금도)?\s*"
            r"(?:마시|먹|챙기)"
            r"|"
            r"물\s*(?:안|못|거의|별로)\s*마시"
            r"|"
            r"물\s*한\s*잔"
            r"|"
            r"수분"
            r"|"
            r"목\s*말"
            r"|"
            r"목마르"
            r"|"
            r"갈증"
            r"|"
            r"입(?:안)?이\s*마르"
            r"|"
            r"입이\s*바짝"
            r")"
        ),
    ),

    "BRUSH_TEETH": (
        re.compile(
            r"(?:"
            r"양치"
            r"|"
            r"칫솔"
            r"|"
            r"치약"
            r"|"
            r"이(?:를)?\s*(?:안|못)\s*닦"
            r"|"
            r"이\s*닦"
            r"|"
            r"입안이\s*찝찝"
            r"|"
            r"입\s*냄새"
            r"|"
            r"씻(?:기|는|을|지)"
            r"|"
            r"안\s*씻"
            r"|"
            r"못\s*씻"
            r"|"
            r"세수"
            r"|"
            r"샤워"
            r"|"
            r"세면"
            r"|"
            r"위생"
            r")"
        ),
    ),

    "EAT_MEAL": (
        re.compile(
            r"(?:"
            r"밥"
            r"|"
            r"식사"
            r"|"
            r"끼니"
            r"|"
            r"아침밥"
            r"|"
            r"점심밥"
            r"|"
            r"저녁밥"
            r"|"
            r"배고프"
            r"|"
            r"배가\s*고프"
            r"|"
            r"허기"
            r"|"
            r"굶"
            r"|"
            r"공복"
            r"|"
            r"식욕"
            r"|"
            r"아무것도\s*못\s*먹"
            r"|"
            r"제대로\s*못\s*먹"
            r"|"
            r"먹을\s*게\s*없"
            r"|"
            r"한\s*끼"
            r")"
        ),
    ),
}


# 구체적인 물·양치·식사 단서가 없더라도
# 작은 생활 행동이 필요하다고 보는 문맥
FALLBACK_GENERAL_NEED_PATTERNS = (
    re.compile(
        r"(?:"
        r"기운이?\s*없"
        r"|"
        r"힘이?\s*없"
        r"|"
        r"무기력"
        r"|"
        r"아무것도\s*하기\s*싫"
        r"|"
        r"아무것도\s*못\s*하"
        r"|"
        r"귀찮"
        r"|"
        r"지쳤"
        r"|"
        r"지쳐"
        r"|"
        r"피곤"
        r"|"
        r"축\s*처"
        r"|"
        r"몸이\s*무거"
        r"|"
        r"일어나기\s*힘"
        r"|"
        r"누워만"
        r"|"
        r"계속\s*누워"
        r"|"
        r"챙기기\s*힘"
        r"|"
        r"시작하기\s*힘"
        r"|"
        r"손\s*하나\s*까딱"
        r"|"
        r"멍하"
        r"|"
        r"버겁"
        r")"
    ),
)


# 현재 메시지에서 아래 표현이 확인되면
# 과거 문맥이 남아 있더라도 새 미션을 추천하지 않는다.
FALLBACK_MISSION_REFUSAL_PATTERNS = (
    re.compile(
        r"(?:"
        r"미션.*싫"
        r"|"
        r"미션.*안\s*할"
        r"|"
        r"미션.*하지\s*마"
        r"|"
        r"추천하지\s*마"
        r"|"
        r"추천하지마"
        r"|"
        r"그만\s*추천"
        r"|"
        r"필요\s*없"
        r"|"
        r"지금은\s*괜찮"
        r"|"
        r"이제\s*괜찮"
        r"|"
        r"괜찮아졌"
        r"|"
        r"해결됐"
        r")"
    ),
)


# 사용자가 이미 해당 행동을 했다고 말한 경우
# 그 미션을 키워드만 보고 다시 추천하지 않는다.
FALLBACK_MISSION_DONE_PATTERNS = {
    "DRINK_WATER": (
        re.compile(
            r"(?:"
            r"물.*(?:마셨어|마셨|먹었|챙겼)"
            r"|"
            r"수분.*챙겼"
            r")"
        ),
    ),

    "BRUSH_TEETH": (
        re.compile(
            r"(?:"
            r"양치.*(?:했어|했지|끝냈|완료)"
            r"|"
            r"이.*닦았"
            r"|"
            r"씻었"
            r"|"
            r"샤워했"
            r"|"
            r"세수했"
            r")"
        ),
    ),

    "EAT_MEAL": (
        re.compile(
            r"(?:"
            r"밥.*(?:먹었|챙겼)"
            r"|"
            r"식사.*(?:했어|했지|끝냈|챙겼)"
            r"|"
            r"끼니.*챙겼"
            r")"
        ),
    ),
}


FALLBACK_MISSION_REASONS = {
    "DRINK_WATER": (
        "최근 대화에서 수분 섭취가 부족하거나 "
        "기운이 떨어진 상태가 확인되어 "
        "물 한 잔 미션을 추천했어요."
    ),
    "BRUSH_TEETH": (
        "최근 대화에서 씻기나 위생관리를 "
        "시작하기 어려운 상태가 확인되어 "
        "양치하기 미션을 추천했어요."
    ),
    "EAT_MEAL": (
        "최근 대화에서 식사나 끼니를 "
        "제대로 챙기기 어려운 상태가 확인되어 "
        "식사하기 미션을 추천했어요."
    ),
}


# 직접적인 단서가 없을 때의 부담도 순서
FALLBACK_DEFAULT_PRIORITY = (
    "DRINK_WATER",
    "BRUSH_TEETH",
    "EAT_MEAL",
)

def normalize_fallback_text(
    value: str,
) -> str:
    return re.sub(
        r"\s+",
        " ",
        value.strip().lower(),
    )


def get_recent_user_texts(
    recent_messages: list[
        dict[str, str]
    ],
    limit: int = 6,
) -> list[str]:
    """
    최근 대화 중 사용자 메시지만 가져온다.

    assistant 메시지에 포함된 미션명 때문에
    fallback이 잘못 실행되는 것을 막는다.
    """

    user_texts = [
        normalize_fallback_text(
            str(message.get(
                "content",
                "",
            ))
        )
        for message in recent_messages
        if (
            message.get("role")
            == "user"
            and str(
                message.get(
                    "content",
                    "",
                )
            ).strip()
        )
    ]

    return user_texts[-limit:]


def current_message_refuses_mission(
    recent_messages: list[
        dict[str, str]
    ],
) -> bool:
    user_texts = get_recent_user_texts(
        recent_messages
    )

    if not user_texts:
        return False

    current_text = user_texts[-1]

    return any(
        pattern.search(current_text)
        for pattern
        in FALLBACK_MISSION_REFUSAL_PATTERNS
    )


def has_fallback_general_mission_need(
    recent_messages: list[
        dict[str, str]
    ],
) -> bool:
    """
    현재 메시지뿐 아니라 최근 사용자 대화 문맥에서
    일반 미션 필요성이 확인되는지 판단한다.
    """

    user_texts = get_recent_user_texts(
        recent_messages
    )

    if not user_texts:
        return False

    if current_message_refuses_mission(
        recent_messages
    ):
        return False

    combined_text = " ".join(
        user_texts
    )

    has_specific_mission_signal = any(
        pattern.search(combined_text)
        for patterns
        in FALLBACK_MISSION_PATTERNS.values()
        for pattern in patterns
    )

    has_general_need_signal = any(
        pattern.search(combined_text)
        for pattern
        in FALLBACK_GENERAL_NEED_PATTERNS
    )

    return (
        has_specific_mission_signal
        or has_general_need_signal
    )


def select_fallback_general_mission(
    *,
    candidates: list[Mission],
    recent_messages: list[
        dict[str, str]
    ],
) -> tuple[
    Mission | None,
    str | None,
]:
    """
    Gemini 호출 실패 시 최근 사용자 대화를
    시간 순서대로 점수화하여 미션을 선택한다.

    최근 메시지일수록 높은 점수를 받으며,
    candidates에 없는 미션은 절대 선택하지 않는다.
    """

    if not candidates:
        return None, None

    user_texts = get_recent_user_texts(
        recent_messages
    )

    if not user_texts:
        return None, None

    if current_message_refuses_mission(
        recent_messages
    ):
        return None, None

    current_text = user_texts[-1]

    blocked_codes: set[str] = set()

    # 현재 메시지에서 이미 수행했다고 말한 미션은 제외
    for mission_code, patterns in (
        FALLBACK_MISSION_DONE_PATTERNS.items()
    ):
        if any(
            pattern.search(current_text)
            for pattern in patterns
        ):
            blocked_codes.add(
                mission_code
            )

    available_by_code = {
        mission.code: mission
        for mission in candidates
        if mission.code
        not in blocked_codes
    }

    if not available_by_code:
        return None, None

    scores = {
        mission_code: 0
        for mission_code
        in available_by_code
    }

    # 오래된 메시지는 낮은 점수,
    # 최근 메시지는 높은 점수
    for index, text in enumerate(
        user_texts,
        start=1,
    ):
        recency_weight = index

        for mission_code, patterns in (
            FALLBACK_MISSION_PATTERNS.items()
        ):
            if (
                mission_code
                not in available_by_code
            ):
                continue

            matched_count = sum(
                1
                for pattern in patterns
                if pattern.search(text)
            )

            if matched_count > 0:
                scores[mission_code] += (
                    recency_weight
                    * matched_count
                    * 10
                )

    positive_codes = [
        mission_code
        for mission_code, score
        in scores.items()
        if score > 0
    ]

    # 직접적인 단서가 있는 미션 선택
    if positive_codes:
        priority_rank = {
            mission_code: (
                len(
                    FALLBACK_DEFAULT_PRIORITY
                )
                - index
            )
            for index, mission_code
            in enumerate(
                FALLBACK_DEFAULT_PRIORITY
            )
        }

        selected_code = max(
            positive_codes,
            key=lambda code: (
                scores[code],
                priority_rank.get(
                    code,
                    0,
                ),
            ),
        )

    # 직접 단서는 없지만 무기력 문맥이 있는 경우
    else:
        combined_text = " ".join(
            user_texts
        )

        has_general_need = any(
            pattern.search(
                combined_text
            )
            for pattern
            in FALLBACK_GENERAL_NEED_PATTERNS
        )

        if not has_general_need:
            return None, None

        selected_code = next(
            (
                mission_code
                for mission_code
                in FALLBACK_DEFAULT_PRIORITY
                if mission_code
                in available_by_code
            ),
            None,
        )

        if selected_code is None:
            return None, None

    selected = available_by_code[
        selected_code
    ]

    reason = (
        FALLBACK_MISSION_REASONS[
            selected_code
        ]
    )

    return selected, reason

def build_mission_ui_texts(
    mission_code: str,
) -> dict[str, str]:
    """
    미션 코드에 따라 채팅 추천 기본 문구,
    미션 카드 문구, 인증 준비 문구를 반환한다.
    """

    mission_ui_texts = {
        "DRINK_WATER": {
            "recommendation_message": (
                "지금은 부담 없이 물 한 잔부터 "
                "천천히 마셔보세요."
            ),
            "card_title": (
                "지금 자리에서 일어나서 "
                "물 한 잔을 마셔보세요"
            ),
            "card_subtitle": (
                "잠시 후 카메라가 활성화됩니다"
            ),
            "verification_title": (
                "물 마시기 미션을 인증할게요"
            ),
            "verification_subtitle": (
                "물컵이나 물병이 카메라 화면에 "
                "잘 보이도록 준비해주세요"
            ),
        },

        "BRUSH_TEETH": {
            "recommendation_message": (
                "지금은 세면대로 가서 "
                "가볍게 양치부터 시작해보세요."
            ),
            "card_title": (
                "지금 세면대로 가서 "
                "가볍게 양치해보세요"
            ),
            "card_subtitle": (
                "잠시 후 카메라가 활성화됩니다"
            ),
            "verification_title": (
                "양치하기 미션을 인증할게요"
            ),
            "verification_subtitle": (
                "칫솔이 카메라 화면에 "
                "잘 보이도록 준비해주세요"
            ),
        },

        "EAT_MEAL": {
            "recommendation_message": (
                "지금은 부담되지 않는 음식을 "
                "조금이라도 챙겨보세요."
            ),
            "card_title": (
                "부담되지 않는 식사를 "
                "조금이라도 챙겨보세요"
            ),
            "card_subtitle": (
                "잠시 후 카메라가 활성화됩니다"
            ),
            "verification_title": (
                "식사하기 미션을 인증할게요"
            ),
            "verification_subtitle": (
                "준비한 음식이 카메라 화면에 "
                "잘 보이도록 놓아주세요"
            ),
        },

        "TAKE_MEDICATION": {
            "recommendation_message": (
                "지금은 설정해 둔 복약 시간대예요. "
                "처방받은 방법대로 약을 챙겨보세요."
            ),
            "card_title": (
                "처방받은 약을 정해진 방법대로 "
                "챙겨 드세요"
            ),
            "card_subtitle": (
                "잠시 후 카메라가 활성화됩니다"
            ),
            "verification_title": (
                "약 먹기 미션을 인증할게요"
            ),
            "verification_subtitle": (
                "약 포장이나 약통이 카메라 화면에 "
                "잘 보이도록 준비해주세요"
            ),
        },
    }

    return mission_ui_texts.get(
        mission_code,
        {
            "recommendation_message": (
                "지금은 부담 없는 작은 행동부터 "
                "천천히 시작해보세요."
            ),
            "card_title": (
                "지금 작은 행동부터 시작해보세요"
            ),
            "card_subtitle": (
                "잠시 후 카메라가 활성화됩니다"
            ),
            "verification_title": (
                "미션 인증을 준비하고 있어요"
            ),
            "verification_subtitle": (
                "인증할 물건이 카메라 화면에 "
                "잘 보이도록 준비해주세요"
            ),
        },
    )

def build_mission_result_ui(
    *,
    success: bool,
) -> dict[str, str | None]:
    """
    미션 인증 결과 화면에 표시할
    기본 문구와 이동 정보를 반환한다.

    성공 문구는 Gemini 호출 실패 시
    fallback 문구로 사용한다.
    """

    if success:
        fallback_message = (
            "오늘의 Nudge로 천천히 "
            "한걸음씩 나아가요!"
        )

        return {
            "result_type": "SUCCESS",

            # 화면 표시용 제목
            "result_title": (
                "오늘의 Nudge 성공🎉"
            ),

            # Gemini 실패 시 사용할 기본 문구
            "result_message": (
                fallback_message
            ),

            # TTS에서는 이모지를 제외한 제목 사용
            "tts_title": (
                "오늘의 Nudge 성공"
            ),

            # Gemini 성공 시 AI 문구로 교체됨
            "tts_text": (
                fallback_message
            ),

            "button_text": (
                "대시보드로 이동"
            ),
            "next_screen": "DASHBOARD",
        }

    return {
        "result_type": "FAILURE",
        "result_title": (
            "미션 확인이 어려워요"
        ),
        "result_message": (
            "다시 한번 미션을 수행해주세요"
        ),

        # 현재는 성공 화면만 TTS 재생
        "tts_title": None,
        "tts_text": None,

        "button_text": (
            "미션카드로 이동"
        ),
        "next_screen": "MISSION_CARD",
    }

def build_user_profile_payload(
    profile: UserRoutineProfile,
) -> dict:
    return {
        "sleep_bedtime": (
            profile.sleep_bedtime
        ),
        "sleep_duration": (
            profile.sleep_duration
        ),
        "meal_regularity": (
            profile.meal_regularity
        ),
        "medication_status": (
            profile.medication_status
        ),
        "medication_times": (
            profile.medication_times or []
        ),
        "activity_start_difficulty": (
            profile
            .activity_start_difficulty
        ),
    }


def get_active_user_mission(
    *,
    db: Session,
    user_id: int,
) -> UserMission | None:
    """
    일반 미션과 복약 미션을 구분하지 않고
    현재 진행 중인 미션 하나를 조회한다.
    """

    return (
        db.query(UserMission)
        .options(
            joinedload(
                UserMission.mission
            )
        )
        .filter(
            UserMission.user_id
            == user_id,
            UserMission.status.in_(
                ACTIVE_MISSION_STATUSES
            ),
        )
        .order_by(
            UserMission
            .assigned_at.desc(),
            UserMission.id.desc(),
        )
        .first()
    )


def recommend_general_mission(
    *,
    db: Session,
    user_id: int,
    profile: UserRoutineProfile,
    recent_messages: list[
        dict[str, str]
    ],
    assigned_date,
) -> UserMission | None:
    """
    일반 생활 미션 중 하나를 추천한다.

    복약 미션은 후보에서 제외한다.
    이미 진행 중인 미션이 있으면
    새로운 미션을 만들지 않는다.
    """

    active_mission = (
        get_active_user_mission(
            db=db,
            user_id=user_id,
        )
    )

    if active_mission is not None:
        return None

    already_assigned_ids = [
        mission_id
        for (mission_id,) in (
            db.query(
                UserMission.mission_id
            )
            .join(
                Mission,
                UserMission.mission_id
                == Mission.id,
            )
            .filter(
                UserMission.user_id
                == user_id,
                UserMission.assigned_date
                == assigned_date,
                Mission
                .requires_current_medication
                .is_(False),
            )
            .all()
        )
    ]

    query = (
        db.query(Mission)
        .filter(
            Mission.is_active.is_(True),
            Mission
            .requires_current_medication
            .is_(False),
            Mission.code
            != "TAKE_MEDICATION",
        )
    )

    if already_assigned_ids:
        query = query.filter(
            Mission.id.notin_(
                already_assigned_ids
            )
        )

    candidates = (
        query
        .order_by(
            Mission.id.asc()
        )
        .all()
    )

    if not candidates:
        return None

    candidate_payload = [
        {
            "mission_code": mission.code,
            "title": mission.title,
            "description": (
                mission.description
            ),
            "category": mission.category,
            "difficulty": (
                mission.difficulty
            ),
        }
        for mission in candidates
    ]

    mission_by_code = {
        mission.code: mission
        for mission in candidates
    }

    selected = None
    selected_reason = None

    try:
        gemini_result = (
            recommend_mission_with_gemini(
                user_profile=(
                    build_user_profile_payload(
                        profile
                    )
                ),
                recent_messages=(
                    recent_messages
                ),
                available_missions=(
                    candidate_payload
                ),
            )
        )

        selected = mission_by_code.get(
            gemini_result.mission_code
        )

        if selected is None:
            raise ValueError(
                "Gemini가 후보에 없는 "
                "미션 코드를 반환했습니다."
            )

        selected_reason = (
            gemini_result.reason
        )

        print(
            "[AI SOURCE] MISSION=GEMINI",
            f"selected={selected.code}",
        )

    except (
        GeminiServiceError,
        ValueError,
    ) as exc:
        (
            selected,
            selected_reason,
        ) = select_fallback_general_mission(
            candidates=candidates,
            recent_messages=(
                recent_messages
            ),
        )

        print(
            "[AI SOURCE] MISSION=FALLBACK",
            f"selected={(
                selected.code
                if selected is not None
                else None
            )}",
            f"error={type(exc).__name__}",
        )

        if selected is None:
            return None

    user_mission = UserMission(
        user_id=user_id,
        mission_id=selected.id,
        mission=selected,
        status="ASSIGNED",
        recommended_reason=(
            selected_reason
        ),
        instance_key=(
            f"GENERAL:{selected.code}"
        ),
        assigned_date=assigned_date,
    )

    db.add(user_mission)
    db.flush()

    return user_mission


def assign_medication_mission(
    *,
    db: Session,
    user_id: int,
    profile: (
        UserRoutineProfile | None
    ),
    assigned_date,
    time_slot: str,
    now: datetime,
) -> UserMission | None:
    """
    아래 조건을 모두 충족할 때만
    복약 미션을 배정한다.

    1. medication_status가 CURRENT
    2. 해당 슬롯을 사용자가 선택함
    3. 현재 실제 시간대가 해당 슬롯임
    4. 다른 진행 중 미션이 없음
    """

    if profile is None:
        return None

    if (
        profile.medication_status
        != "CURRENT"
    ):
        return None

    medication_times = (
        profile.medication_times or []
    )

    if time_slot not in medication_times:
        return None

    current_slot = (
        get_current_time_slot(now)
    )

    if current_slot != time_slot:
        return None

    mission = (
        db.query(Mission)
        .filter(
            Mission.code
            == "TAKE_MEDICATION",
            Mission.is_active.is_(True),
            Mission
            .requires_current_medication
            .is_(True),
        )
        .first()
    )

    if mission is None:
        raise ValueError(
            "TAKE_MEDICATION 미션이 "
            "DB에 없거나 복약 전용 미션으로 "
            "설정되지 않았습니다."
        )

    instance_key = (
        f"MEDICATION:{time_slot}"
    )

    existing = (
        db.query(UserMission)
        .options(
            joinedload(
                UserMission.mission
            )
        )
        .filter(
            UserMission.user_id
            == user_id,
            UserMission.mission_id
            == mission.id,
            UserMission.assigned_date
            == assigned_date,
            UserMission.instance_key
            == instance_key,
        )
        .first()
    )

    if existing is not None:
        if (
            existing.status
            in ACTIVE_MISSION_STATUSES
        ):
            return existing

        return None

    active_mission = (
        get_active_user_mission(
            db=db,
            user_id=user_id,
        )
    )

    if active_mission is not None:
        return None

    user_mission = UserMission(
        user_id=user_id,
        mission_id=mission.id,
        mission=mission,
        status="ASSIGNED",
        recommended_reason=(
            "지금은 설정해 둔 복약 시간대예요. "
            "처방받은 방법대로 약을 챙겨보세요."
        ),
        instance_key=instance_key,
        assigned_date=assigned_date,
    )

    db.add(user_mission)
    db.flush()

    return user_mission