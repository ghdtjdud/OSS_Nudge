from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.exc import (
    IntegrityError,
    SQLAlchemyError,
)
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.models import (
    ChatMessage,
    ChatSession,
    Mission,
    User,
    UserMission,
    UserRoutineProfile,
)
from backend.app.schemas.schemas import (
    MissionRecommendationResponse,
    MissionResponse,
)
from backend.app.services.auth_service import (
    get_current_user,
)
from backend.app.services.gemini_service import (
    GeminiServiceError,
    recommend_mission_with_gemini,
)


router = APIRouter(
    prefix="/api/v1/missions",
    tags=["Missions"],
)


def get_recent_messages(
    *,
    user_id: int,
    db: Session,
    limit: int = 10,
) -> list[dict[str, str]]:
    messages = (
        db.query(ChatMessage)
        .join(
            ChatSession,
            ChatMessage.session_id
            == ChatSession.id,
        )
        .filter(
            ChatSession.user_id == user_id
        )
        .order_by(
            ChatMessage.created_at.desc(),
            ChatMessage.id.desc(),
        )
        .limit(limit)
        .all()
    )

    messages.reverse()

    return [
        {
            "role": message.role,
            "content": message.content,
        }
        for message in messages
    ]


def build_user_profile(
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


@router.get(
    "",
    response_model=list[MissionResponse],
)
def get_available_missions(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    return (
        db.query(Mission)
        .filter(
            Mission.is_active.is_(True),
            Mission.code != "TAKE_MEDICATION",
        )
        .order_by(
            Mission.id.asc()
        )
        .all()
    )


@router.post(
    "/recommend",
    response_model=MissionRecommendationResponse,
    status_code=status.HTTP_201_CREATED,
)
def recommend_mission(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    profile = (
        db.query(UserRoutineProfile)
        .filter(
            UserRoutineProfile.user_id
            == current_user.id
        )
        .first()
    )

    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "미션 추천 전에 사용자 상태정보를 "
                "입력해야 합니다."
            ),
        )

    # 아직 진행 중인 오늘 미션이 있으면
    # 새 미션을 중복 추천하지 않음
    existing_user_mission = (
        db.query(UserMission)
        .filter(
            UserMission.user_id
            == current_user.id,
            UserMission.assigned_date
            == date.today(),
            UserMission.status.in_(
                [
                    "ASSIGNED",
                    "IN_PROGRESS",
                ]
            ),
        )
        .order_by(
            UserMission.assigned_at.desc()
        )
        .first()
    )

    if existing_user_mission is not None:
        return {
            "message": (
                "오늘 진행 중인 미션이 있습니다."
            ),
            "user_mission": (
                existing_user_mission
            ),
        }

    mission_query = db.query(Mission).filter(
        Mission.is_active.is_(True),
        Mission.code != "TAKE_MEDICATION",
    )

    # 오늘 이미 추천된 미션은 제외
    today_mission_ids = [
        mission_id
        for (mission_id,) in (
            db.query(UserMission.mission_id)
            .filter(
                UserMission.user_id
                == current_user.id,
                UserMission.assigned_date
                == date.today(),
            )
            .all()
        )
    ]

    if today_mission_ids:
        mission_query = mission_query.filter(
            Mission.id.notin_(
                today_mission_ids
            )
        )

    available_missions = (
        mission_query
        .order_by(Mission.id.asc())
        .all()
    )

    if not available_missions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "오늘 추천할 수 있는 미션이 "
                "더 이상 없습니다."
            ),
        )

    available_mission_payload = [
        {
            "mission_code": mission.code,
            "title": mission.title,
            "description": mission.description,
            "category": mission.category,
            "difficulty": mission.difficulty,
        }
        for mission in available_missions
    ]

    try:
        gemini_result = (
            recommend_mission_with_gemini(
                user_profile=build_user_profile(
                    profile
                ),
                recent_messages=(
                    get_recent_messages(
                        user_id=current_user.id,
                        db=db,
                    )
                ),
                available_missions=(
                    available_mission_payload
                ),
            )
        )

    except GeminiServiceError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=str(exc),
        ) from exc

    mission_by_code = {
        mission.code: mission
        for mission in available_missions
    }

    selected_mission = mission_by_code.get(
        gemini_result.mission_code
    )

    # Gemini가 후보에 없는 코드를 반환한 경우
    if selected_mission is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Gemini가 유효하지 않은 "
                "미션 코드를 반환했습니다."
            ),
        )

    user_mission = UserMission(
        user_id=current_user.id,
        mission_id=selected_mission.id,
        status="ASSIGNED",
        recommended_reason=(
            gemini_result.reason
        ),
        assigned_date=date.today(),
    )

    try:
        db.add(user_mission)
        db.commit()
        db.refresh(user_mission)

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "동일한 미션이 이미 "
                "오늘 배정되었습니다."
            ),
        ) from exc

    except SQLAlchemyError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail="미션 저장에 실패했습니다.",
        ) from exc

    return {
        "message": "새로운 미션을 추천했습니다.",
        "user_mission": user_mission,
    }


@router.get(
    "/me/today",
    response_model=list[
        MissionRecommendationResponse
    ],
)
def get_today_missions(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    user_missions = (
        db.query(UserMission)
        .filter(
            UserMission.user_id
            == current_user.id,
            UserMission.assigned_date
            == date.today(),
        )
        .order_by(
            UserMission.assigned_at.desc()
        )
        .all()
    )

    return [
        {
            "message": "오늘의 미션",
            "user_mission": user_mission,
        }
        for user_mission in user_missions
    ]