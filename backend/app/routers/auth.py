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
from backend.app.models.models import User
from backend.app.schemas.schemas import (
    LoginRequest,
    SignupRequest,
    SignupResponse,
    TokenResponse,
    UserResponse,
)
from backend.app.services.auth_service import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)


router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Auth"],
)


@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
)
def signup(
    request: SignupRequest,
    db: Session = Depends(get_db),
):
    # 1. 이메일 중복 확인
    existing_email_user = (
        db.query(User)
        .filter(User.email == request.email)
        .first()
    )

    if existing_email_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 가입된 이메일입니다.",
        )

    # 2. 전화번호 중복 확인
    existing_phone_user = (
        db.query(User)
        .filter(User.phone == request.phone)
        .first()
    )

    if existing_phone_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 가입된 전화번호입니다.",
        )

    # 3. 사용자 생성
    new_user = User(
        name=request.name,
        email=request.email,
        password_hash=hash_password(
            request.password
        ),
        phone=request.phone,
        guardian_phone=request.guardian_phone,
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "이미 사용 중인 이메일 또는 "
                "전화번호입니다."
            ),
        ) from exc

    except SQLAlchemyError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "회원가입 처리 중 "
                "오류가 발생했습니다."
            ),
        ) from exc

    # 회원가입 단계에서는 JWT를 발급하지 않음
    return {
        "message": (
            "회원가입이 완료되었습니다. "
            "로그인해주세요."
        ),
        "user": new_user,
    }


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.email == request.email)
        .first()
    )

    # 가입되지 않은 사용자이거나
    # 비밀번호가 틀렸다면 로그인 차단
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "이메일 또는 비밀번호가 "
                "올바르지 않습니다."
            ),
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    if not verify_password(
        request.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "이메일 또는 비밀번호가 "
                "올바르지 않습니다."
            ),
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    access_token = create_access_token(
        data={
            "sub": str(user.id),
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
    }


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    current_user: User = Depends(
        get_current_user
    ),
):
    return current_user