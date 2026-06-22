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
)
from backend.app.services.medication_service import (
    get_local_now,
)
from backend.app.services.mission_service import (
    get_active_user_mission,
    recommend_general_mission,
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
            ChatSession.user_id
            == user_id
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


@router.get(
    "",
    response_model=list[
        MissionResponse
    ],
)
def get_available_missions(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    """
    일반 미션 목록만 반환한다.

    TAKE_MEDICATION은 채팅에서
    복약 여부를 확인한 뒤에만 배정한다.
    """

    return (
        db.query(Mission)
        .filter(
            Mission.is_active.is_(True),
            Mission
            .requires_current_medication
            .is_(False),
            Mission.code
            != "TAKE_MEDICATION",
        )
        .order_by(
            Mission.id.asc()
        )
        .all()
    )


@router.post(
    "/recommend",
    response_model=(
        MissionRecommendationResponse
    ),
    status_code=(
        status.HTTP_201_CREATED
    ),
)
def recommend_mission(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    """
    수동 일반 미션 추천 API.

    복약 미션은 절대 추천하지 않는다.
    진행 중인 미션이 있으면 기존 미션을 반환한다.
    """

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
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "미션 추천 전에 사용자 "
                "상태정보를 입력해야 합니다."
            ),
        )

    active_mission = (
        get_active_user_mission(
            db=db,
            user_id=current_user.id,
        )
    )

    if active_mission is not None:
        return {
            "message": (
                "현재 진행 중인 미션이 있습니다."
            ),
            "user_mission": (
                active_mission
            ),
        }

    today_local = (
        get_local_now().date()
    )

    try:
        user_mission = (
            recommend_general_mission(
                db=db,
                user_id=current_user.id,
                profile=profile,
                recent_messages=(
                    get_recent_messages(
                        user_id=(
                            current_user.id
                        ),
                        db=db,
                    )
                ),
                assigned_date=(
                    today_local
                ),
            )
        )

        if user_mission is None:
            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "현재 추천할 수 있는 "
                    "새 일반 미션이 없습니다."
                ),
            )

        db.commit()
        db.refresh(user_mission)

    except HTTPException:
        db.rollback()
        raise

    except GeminiServiceError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status
                .HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=str(exc),
        ) from exc

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "동일한 미션이 이미 "
                "오늘 배정되었습니다."
            ),
        ) from exc

    except SQLAlchemyError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status
                .HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "미션 저장에 실패했습니다."
            ),
        ) from exc

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=str(exc),
        ) from exc

    return {
        "message": (
            "새로운 미션을 추천했습니다."
        ),
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
    today_local = (
        get_local_now().date()
    )

    user_missions = (
        db.query(UserMission)
        .filter(
            UserMission.user_id
            == current_user.id,
            UserMission.assigned_date
            == today_local,
        )
        .order_by(
            UserMission
            .assigned_at.desc()
        )
        .all()
    )

    return [
        {
            "message": "오늘의 미션",
            "user_mission": (
                user_mission
            ),
        }
        for user_mission
        in user_missions
    ]