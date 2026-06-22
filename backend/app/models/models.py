from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    String,
)

from backend.app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        index=True,
    )

    email = Column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    password_hash = Column(
        String(255),
        nullable=False,
    )

    name = Column(
        String(100),
        nullable=False,
    )

    phone = Column(
        String(30),
        unique=True,
        index=True,
        nullable=False,
    )

    # 회원가입 화면의
    # '보호자 및 주치의 연락처'를 임시로 저장
    guardian_phone = Column(
        String(30),
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )