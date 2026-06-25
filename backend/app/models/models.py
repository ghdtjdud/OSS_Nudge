from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
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

    user_missions = relationship(
        "UserMission",
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

    # =====================================================
    # 수면 루틴
    # =====================================================

    # 최근 주로 잠드는 시간
    sleep_bedtime = Column(
        String(30),
        nullable=False,
    )

    # 최근 평균 수면 시간
    sleep_duration = Column(
        String(30),
        nullable=False,
    )

    # =====================================================
    # 식사 루틴
    # =====================================================

    # 식사를 얼마나 규칙적으로 챙기는지
    meal_regularity = Column(
        String(50),
        nullable=False,
    )

    # =====================================================
    # 복약 루틴
    # =====================================================

    # CURRENT / NONE / PAST
    medication_status = Column(
        String(20),
        nullable=False,
    )

    # ["MORNING", "LUNCH", "EVENING", "BEFORE_SLEEP"]
    # CURRENT일 때만 값이 저장됨
    medication_times = Column(
        JSON,
        nullable=True,
    )

    # =====================================================
    # 일상 활동 상태
    # =====================================================

    # 일상 활동을 시작하는 데 드는 어려움
    activity_start_difficulty = Column(
        String(40),
        nullable=False,
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


class Mission(Base):
    __tablename__ = "missions"

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        index=True,
    )

    # 프론트·Gemini·백엔드가 공통으로 사용하는 고정 코드
    code = Column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )

    title = Column(
        String(100),
        nullable=False,
    )

    description = Column(
        String(255),
        nullable=False,
    )

    category = Column(
        String(30),
        nullable=False,
    )

    difficulty = Column(
        Integer,
        nullable=False,
        default=1,
    )

    # YOLO 인증에서 확인해야 할 객체 유형
    verification_code = Column(
        String(50),
        nullable=False,
    )

    # 현재 복약 중인 사용자에게만 노출할지 여부
    requires_current_medication = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    user_missions = relationship(
        "UserMission",
        back_populates="mission",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class UserMission(Base):
    __tablename__ = "user_missions"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "mission_id",
            "assigned_date",
            "instance_key",
            name="uq_user_mission_instance",
        ),
    )

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

    mission_id = Column(
        BigInteger,
        ForeignKey(
            "missions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # ASSIGNED / IN_PROGRESS / COMPLETED / FAILED
    status = Column(
        String(20),
        nullable=False,
        default="ASSIGNED",
    )

    recommended_reason = Column(
        Text,
        nullable=True,
    )

    instance_key = Column(
        String(60),
        nullable=False,
        default="GENERAL",
    )

    assigned_date = Column(
        Date,
        nullable=False,
        default=date.today,
        index=True,
    )

    assigned_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    completed_at = Column(
        DateTime,
        nullable=True,
    )

    user = relationship(
        "User",
        back_populates="user_missions",
    )

    mission = relationship(
        "Mission",
        back_populates="user_missions",
    )


class MedicationCheckLog(Base):
    __tablename__ = "medication_check_logs"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "check_date",
            "time_slot",
            name="uq_medication_check_per_slot",
        ),
    )

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

    check_date = Column(
        Date,
        nullable=False,
        index=True,
    )

    time_slot = Column(
        String(30),
        nullable=False,
    )

    # ASKED / TAKEN / NOT_TAKEN
    status = Column(
        String(20),
        nullable=False,
        default="ASKED",
    )

    asked_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    answered_at = Column(
        DateTime,
        nullable=True,
    )

class RevokedAccessToken(Base):
    __tablename__ = (
        "revoked_access_tokens"
    )

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

    # JWT 원문은 저장하지 않고
    # SHA-256 해시만 저장한다.
    token_hash = Column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    expires_at = Column(
        DateTime,
        nullable=False,
        index=True,
    )

    revoked_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )