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
    """
    사용자 상태정보 최초 저장 및 재수정 API.

    상태정보가 없으면 새로 생성하고,
    이미 있으면 기존 정보를 덮어쓴다.
    """

    routine_profile = (
        db.query(UserRoutineProfile)
        .filter(
            UserRoutineProfile.user_id
            == current_user.id
        )
        .first()
    )

    # Enum 객체를 실제 문자열로 변환
    request_data = request.model_dump(
        mode="json"
    )

    if routine_profile is None:
        routine_profile = UserRoutineProfile(
            user_id=current_user.id,
            **request_data,
        )

        db.add(routine_profile)

    else:
        for field_name, value in request_data.items():
            setattr(
                routine_profile,
                field_name,
                value,
            )

    try:
        db.commit()
        db.refresh(routine_profile)

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

    return UserRoutineResponse(
        user_id=routine_profile.user_id,
        sleep_bedtime=(
            routine_profile.sleep_bedtime
        ),
        sleep_duration=(
            routine_profile.sleep_duration
        ),
        sleep_condition=(
            routine_profile.sleep_condition
        ),
        breakfast_frequency=(
            routine_profile.breakfast_frequency
        ),
        lunch_dinner_pattern=(
            routine_profile.lunch_dinner_pattern
        ),
        appetite_change=(
            routine_profile.appetite_change
        ),
        medication_status=(
            routine_profile.medication_status
        ),
        medication_timing=(
            routine_profile.medication_timing
        ),
        medication_forget_frequency=(
            routine_profile
            .medication_forget_frequency
        ),
        onboarding_completed=True,
        created_at=routine_profile.created_at,
        updated_at=routine_profile.updated_at,
    )


@router.get(
    "/me/status",
    response_model=UserRoutineResponse,
    status_code=status.HTTP_200_OK,
)
def get_user_status(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    """
    로그인한 사용자의 상태정보 조회 API.
    """

    routine_profile = (
        db.query(UserRoutineProfile)
        .filter(
            UserRoutineProfile.user_id
            == current_user.id
        )
        .first()
    )

    if routine_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "아직 사용자 상태정보를 "
                "입력하지 않았습니다."
            ),
        )

    return UserRoutineResponse(
        user_id=routine_profile.user_id,
        sleep_bedtime=(
            routine_profile.sleep_bedtime
        ),
        sleep_duration=(
            routine_profile.sleep_duration
        ),
        sleep_condition=(
            routine_profile.sleep_condition
        ),
        breakfast_frequency=(
            routine_profile.breakfast_frequency
        ),
        lunch_dinner_pattern=(
            routine_profile.lunch_dinner_pattern
        ),
        appetite_change=(
            routine_profile.appetite_change
        ),
        medication_status=(
            routine_profile.medication_status
        ),
        medication_timing=(
            routine_profile.medication_timing
        ),
        medication_forget_frequency=(
            routine_profile
            .medication_forget_frequency
        ),
        onboarding_completed=True,
        created_at=routine_profile.created_at,
        updated_at=routine_profile.updated_at,
    )