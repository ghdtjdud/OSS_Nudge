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
    MedicationCheckLog,
    User,
    UserRoutineProfile,
)
from backend.app.schemas.schemas import (
    AccountDeleteRequest,
    AccountDeleteResponse,
    MyPageResponse,
    MyPageUpdateRequest,
    PasswordChangeRequest,
    PasswordChangeResponse,
    UserRoutineRequest,
    UserRoutineResponse,
)
from backend.app.services.auth_service import (
    get_current_user,
    hash_password,
    verify_password,
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

@router.get(
    "/me",
    response_model=MyPageResponse,
)
def get_my_page(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    """
    마이페이지에서 사용할
    기본 회원정보와 상태정보를 반환한다.
    """

    profile = (
        db.query(UserRoutineProfile)
        .filter(
            UserRoutineProfile.user_id
            == current_user.id
        )
        .first()
    )

    return {
        "user": current_user,
        "routine_profile": (
            build_routine_response(
                profile
            )
            if profile is not None
            else None
        ),
    }

@router.patch(
    "/me",
    response_model=MyPageResponse,
)
def update_my_page(
    request: MyPageUpdateRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    """
    이름, 이메일, 전화번호,
    보호자 또는 주치의 연락처를 수정한다.

    이메일 변경 시에는
    현재 비밀번호 확인이 필요하다.
    """

    update_data = request.model_dump(
        exclude_unset=True,
        exclude={
            "current_password",
        },
    )

    new_email = update_data.get(
        "email"
    )

    new_phone = update_data.get(
        "phone"
    )

    # 이메일 변경 시 현재 비밀번호 확인
    if (
        new_email is not None
        and new_email
        != current_user.email
    ):
        if (
            request.current_password
            is None
            or not verify_password(
                request.current_password,
                current_user.password_hash,
            )
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_401_UNAUTHORIZED
                ),
                detail=(
                    "이메일 변경을 위해서는 "
                    "현재 비밀번호 확인이 "
                    "필요합니다."
                ),
            )

        duplicate_email_user = (
            db.query(User)
            .filter(
                User.email == new_email,
                User.id != current_user.id,
            )
            .first()
        )

        if (
            duplicate_email_user
            is not None
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "이미 사용 중인 "
                    "이메일입니다."
                ),
            )

    # 전화번호 중복 확인
    if (
        new_phone is not None
        and new_phone
        != current_user.phone
    ):
        duplicate_phone_user = (
            db.query(User)
            .filter(
                User.phone == new_phone,
                User.id != current_user.id,
            )
            .first()
        )

        if (
            duplicate_phone_user
            is not None
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "이미 사용 중인 "
                    "전화번호입니다."
                ),
            )

    for field_name, value in (
        update_data.items()
    ):
        setattr(
            current_user,
            field_name,
            value,
        )

    try:
        db.commit()
        db.refresh(current_user)

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "이미 사용 중인 이메일 또는 "
                "전화번호입니다."
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
                "회원정보 수정 중 "
                "오류가 발생했습니다."
            ),
        ) from exc

    profile = (
        db.query(UserRoutineProfile)
        .filter(
            UserRoutineProfile.user_id
            == current_user.id
        )
        .first()
    )

    return {
        "user": current_user,
        "routine_profile": (
            build_routine_response(
                profile
            )
            if profile is not None
            else None
        ),
    }

@router.patch(
    "/me/password",
    response_model=(
        PasswordChangeResponse
    ),
)
def change_my_password(
    request: PasswordChangeRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    """
    현재 비밀번호를 확인한 뒤
    새 비밀번호 해시를 저장한다.
    """

    if not verify_password(
        request.current_password,
        current_user.password_hash,
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "현재 비밀번호가 "
                "올바르지 않습니다."
            ),
        )

    current_user.password_hash = (
        hash_password(
            request.new_password
        )
    )

    try:
        db.commit()
        db.refresh(current_user)

    except SQLAlchemyError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status
                .HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "비밀번호 변경 중 "
                "오류가 발생했습니다."
            ),
        ) from exc

    return {
        "message": (
            "비밀번호가 변경되었습니다."
        )
    }

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

@router.delete(
    "/me",
    response_model=(
        AccountDeleteResponse
    ),
)
def delete_my_account(
    request: AccountDeleteRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    """
    현재 비밀번호를 확인한 뒤
    사용자 계정과 관련 데이터를 삭제한다.
    """

    if not verify_password(
        request.current_password,
        current_user.password_hash,
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "현재 비밀번호가 "
                "올바르지 않습니다."
            ),
        )

    user_id = current_user.id

    try:
        # User에 ORM relationship이 없는
        # 복약 확인 로그는 명시적으로 삭제한다.
        db.query(
            MedicationCheckLog
        ).filter(
            MedicationCheckLog.user_id
            == user_id
        ).delete(
            synchronize_session=False
        )

        db.delete(current_user)
        db.commit()

    except SQLAlchemyError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status
                .HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "회원 탈퇴 처리 중 "
                "오류가 발생했습니다."
            ),
        ) from exc

    return {
        "message": (
            "회원 탈퇴가 완료되었습니다."
        )
    }