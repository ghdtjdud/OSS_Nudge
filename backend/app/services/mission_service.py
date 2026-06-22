# mission_service.py
'''추천 후보 미션 조회
Gemini 미션 추천 함수 호출
반환된 ID 검증
user_missions 저장'''

from sqlalchemy.orm import Session

from backend.app.models.models import (
    Mission,
    UserMission,
    UserRoutineProfile,
)
from backend.app.services.gemini_service import (
    recommend_mission_with_gemini,
)


def build_user_profile_payload(
    profile: UserRoutineProfile,
) -> dict:
    return {
        "sleep_bedtime": profile.sleep_bedtime,
        "sleep_duration": profile.sleep_duration,
        "sleep_condition": profile.sleep_condition,
        "breakfast_frequency": (
            profile.breakfast_frequency
        ),
        "lunch_dinner_pattern": (
            profile.lunch_dinner_pattern
        ),
        "appetite_change": (
            profile.appetite_change
        ),
        "medication_status": (
            profile.medication_status
        ),
        "medication_times": (
            profile.medication_times
        ),
        "medication_forget_frequency": (
            profile.medication_forget_frequency
        ),
    }


def recommend_general_mission(
    *,
    db: Session,
    user_id: int,
    profile: UserRoutineProfile,
    recent_messages: list[dict[str, str]],
    assigned_date,
) -> UserMission | None:
    """
    물·양치·식사 중 하나를 Gemini가 선택한다.

    약 미션은 이 함수에서 절대 추천하지 않는다.
    """

    active_general = (
        db.query(UserMission)
        .join(
            Mission,
            UserMission.mission_id
            == Mission.id,
        )
        .filter(
            UserMission.user_id == user_id,
            UserMission.assigned_date
            == assigned_date,
            UserMission.status.in_(
                ["ASSIGNED", "IN_PROGRESS"]
            ),
            Mission.code
            != "TAKE_MEDICATION",
        )
        .first()
    )

    if active_general is not None:
        return None

    already_assigned_ids = [
        mission_id
        for (mission_id,) in (
            db.query(UserMission.mission_id)
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
                Mission.code
                != "TAKE_MEDICATION",
            )
            .all()
        )
    ]

    query = db.query(Mission).filter(
        Mission.is_active.is_(True),
        Mission.code != "TAKE_MEDICATION",
    )

    if already_assigned_ids:
        query = query.filter(
            Mission.id.notin_(
                already_assigned_ids
            )
        )

    candidates = query.order_by(
        Mission.id.asc()
    ).all()

    if not candidates:
        return None

    candidate_payload = [
        {
            "mission_code": mission.code,
            "title": mission.title,
            "description": mission.description,
            "category": mission.category,
            "difficulty": mission.difficulty,
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
            recent_messages=recent_messages,
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
    assigned_date,
    time_slot: str,
) -> UserMission:
    """
    사용자가 복약하지 않았다고 답한 경우에만 호출한다.
    """

    mission = (
        db.query(Mission)
        .filter(
            Mission.code
            == "TAKE_MEDICATION",
            Mission.is_active.is_(True),
        )
        .first()
    )

    if mission is None:
        raise ValueError(
            "TAKE_MEDICATION 미션이 "
            "DB에 없습니다."
        )

    instance_key = (
        f"MEDICATION:{time_slot}"
    )

    existing = (
        db.query(UserMission)
        .filter(
            UserMission.user_id == user_id,
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
        return existing

    user_mission = UserMission(
        user_id=user_id,
        mission_id=mission.id,
        mission=mission,
        status="ASSIGNED",
        recommended_reason=(
            "설정한 복약 시간대에 아직 "
            "약을 복용하지 않았다고 답해 "
            "추천된 미션입니다."
        ),
        instance_key=instance_key,
        assigned_date=assigned_date,
    )

    db.add(user_mission)
    db.flush()

    return user_mission