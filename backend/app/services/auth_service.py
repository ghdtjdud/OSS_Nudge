import hashlib
import os
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.models import (
    RevokedAccessToken,
    User,
)


load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY 환경변수가 설정되지 않았습니다.")

ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto"
)

security = HTTPBearer()

def hash_access_token(
    token: str,
) -> str:
    """
    JWT 원문을 DB에 저장하지 않도록
    SHA-256 해시로 변환한다.
    """

    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

def revoke_access_token(
    *,
    token: str,
    user_id: int,
    db: Session,
) -> None:
    """
    현재 JWT를 로그아웃 토큰 목록에 추가한다.
    """

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        expiration_timestamp = (
            payload.get("exp")
        )

        if expiration_timestamp is None:
            raise HTTPException(
                status_code=(
                    status.HTTP_401_UNAUTHORIZED
                ),
                detail=(
                    "토큰 만료 정보가 없습니다."
                ),
            )

        expires_at = (
            datetime.utcfromtimestamp(
                expiration_timestamp
            )
        )

    except JWTError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "인증 정보가 유효하지 않습니다."
            ),
            headers={
                "WWW-Authenticate": "Bearer",
            },
        ) from exc

    token_hash = hash_access_token(
        token
    )

    # 이미 로그아웃 처리된 토큰이면
    # 중복 레코드를 생성하지 않는다.
    existing_revoked_token = (
        db.query(RevokedAccessToken)
        .filter(
            RevokedAccessToken.token_hash
            == token_hash
        )
        .first()
    )

    if existing_revoked_token is not None:
        return

    # 만료된 폐기 토큰을 정리한다.
    db.query(
        RevokedAccessToken
    ).filter(
        RevokedAccessToken.expires_at
        < datetime.utcnow()
    ).delete(
        synchronize_session=False
    )

    revoked_token = RevokedAccessToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )

    db.add(revoked_token)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    to_encode = data.copy()

    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증 정보가 유효하지 않습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials

    token_hash = hash_access_token(
        token
    )

    revoked_token = (
        db.query(RevokedAccessToken)
        .filter(
            RevokedAccessToken.token_hash
            == token_hash
        )
        .first()
    )

    if revoked_token is not None:
        raise credentials_exception

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")

        if user_id is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()

    if user is None:
        raise credentials_exception

    return user