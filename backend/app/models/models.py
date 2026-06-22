from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import relationship

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

    guardian_phone = Column(
        String(30),
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # UserRoutineProfile.user와 연결되는 반대편 속성
    routine_profile = relationship(
        "UserRoutineProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    chat_sessions = relationship(
        "ChatSession",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class UserRoutineProfile(Base):
    __tablename__ = "user_routine_profiles"

    user_id = Column(
        BigInteger,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    # 수면 루틴
    sleep_bedtime = Column(
        String(30),
        nullable=False,
    )

    sleep_duration = Column(
        String(30),
        nullable=False,
    )

    sleep_condition = Column(
        String(50),
        nullable=False,
    )

    # 식사 루틴
    breakfast_frequency = Column(
        String(30),
        nullable=False,
    )

    lunch_dinner_pattern = Column(
        String(40),
        nullable=False,
    )

    appetite_change = Column(
        String(30),
        nullable=False,
    )

    # 복약 루틴
    medication_status = Column(
        String(20),
        nullable=False,
    )

    medication_timing = Column(
        String(30),
        nullable=True,
    )

    medication_forget_frequency = Column(
        String(30),
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    user = relationship(
        "User",
        back_populates="routine_profile",
    )

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        index=True,
    )

    user_id = Column(
        BigInteger,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    user = relationship(
        "User",
        back_populates="chat_sessions",
    )

    messages = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ChatMessage.created_at",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        index=True,
    )

    session_id = Column(
        BigInteger,
        ForeignKey(
            "chat_sessions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # user 또는 assistant
    role = Column(
        String(20),
        nullable=False,
    )

    content = Column(
        Text,
        nullable=False,
    )

    # text 또는 voice
    input_type = Column(
        String(20),
        nullable=False,
        default="text",
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    session = relationship(
        "ChatSession",
        back_populates="messages",
    )

    