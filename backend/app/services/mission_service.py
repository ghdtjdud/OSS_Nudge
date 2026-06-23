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
    recommend_mission_with_gemini,
)
from backend.app.services.medication_service import (
    get_current_time_slot,
)


ACTIVE_MISSION_STATUSES = (
    "ASSIGNED",
    "IN_PROGRESS",
)

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

    mission_by_code = {
        mission.code: mission
        for mission in candidates
    }

    selected = mission_by_code.get(
        gemini_result.mission_code
    )

    if selected is None:
        raise ValueError(
            "Gemini가 후보에 없는 "
            "미션 코드를 반환했습니다."
        )

    user_mission = UserMission(
        user_id=user_id,
        mission_id=selected.id,
        mission=selected,
        status="ASSIGNED",
        recommended_reason=(
            gemini_result.reason
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