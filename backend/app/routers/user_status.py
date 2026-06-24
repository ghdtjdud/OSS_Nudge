from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.models import (
    User,
    UserRoutineProfile,
)
from backend.app.schemas.schemas import (
    UserRoutineRequest,
    UserRoutineResponse,
)
from backend.app.services.auth_service import (
    get_current_user,
)


router = APIRouter(
    prefix="/api/v1/users",
    tags=["User Status"],
)


def build_routine_response(
    profile: UserRoutineProfile,
) -> UserRoutineResponse:
    return UserRoutineResponse(
        user_id=profile.user_id,
        sleep_bedtime=profile.sleep_bedtime,
        sleep_duration=profile.sleep_duration,
        meal_regularity=profile.meal_regularity,
        medication_status=profile.medication_status,
        medication_times=profile.medication_times,
        activity_start_difficulty=(
            profile.activity_start_difficulty
        ),
        onboarding_completed=True,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.put(
    "/me/status",
    response_model=UserRoutineResponse,
    status_code=status.HTTP_200_OK,
)
def save_user_status(
    request: UserRoutineRequest,
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

    # Enum을 JSON에 저장할 수 있는 문자열 값으로 변환
    request_data = request.model_dump(
        mode="json"
    )

    if profile is None:
        profile = UserRoutineProfile(
            user_id=current_user.id,
            **request_data,
        )
        db.add(profile)

    else:
        for field_name, value in (
            request_data.items()
        ):
            setattr(
                profile,
                field_name,
                value,
            )

    try:
        db.commit()
        db.refresh(profile)

    except SQLAlchemyError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "사용자 상태정보 저장 중 "
                "오류가 발생했습니다."
            ),
        ) from exc

    return build_routine_response(profile)


@router.get(
    "/me/status",
    response_model=UserRoutineResponse,
)
def get_user_status(
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
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "아직 사용자 상태정보를 "
                "입력하지 않았습니다."
            ),
        )

    return build_routine_response(profile)