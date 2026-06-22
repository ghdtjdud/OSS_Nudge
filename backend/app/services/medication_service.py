import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from sqlalchemy.orm import Session

from backend.app.models.models import (
    MedicationCheckLog,
    UserRoutineProfile,
)


load_dotenv()


APP_TIMEZONE = os.getenv(
    "APP_TIMEZONE",
    "Asia/Seoul",
)

LOCAL_TIMEZONE = ZoneInfo(
    APP_TIMEZONE
)


SLOT_LABELS = {
    "MORNING": "아침",
    "LUNCH": "점심",
    "EVENING": "저녁",
    "BEFORE_SLEEP": "자기 전",
}


def get_local_now() -> datetime:
    return datetime.now(
        LOCAL_TIMEZONE
    )


def get_current_time_slot(
    now: datetime | None = None,
) -> str:
    """
    현재 시간을 네 개의 복약 슬롯으로 분류한다.

    MORNING:      05:00 ~ 10:59
    LUNCH:        11:00 ~ 15:59
    EVENING:      16:00 ~ 20:59
    BEFORE_SLEEP: 21:00 ~ 04:59
    """

    current = now or get_local_now()
    hour = current.hour

    if 5 <= hour < 11:
        return "MORNING"

    if 11 <= hour < 16:
        return "LUNCH"

    if 16 <= hour < 21:
        return "EVENING"

    return "BEFORE_SLEEP"


def get_due_medication_slot(
    profile: UserRoutineProfile | None,
    now: datetime | None = None,
) -> str | None:
    """
    아래 조건을 모두 충족할 때만
    현재 복약 슬롯을 반환한다.

    1. 사용자 상태정보가 존재함
    2. medication_status가 CURRENT임
    3. 현재 슬롯이 medication_times에 포함됨
    """

    if profile is None:
        return None

    if (
        profile.medication_status
        != "CURRENT"
    ):
        return None

    medication_times = (
        profile.medication_times or []
    )

    current_slot = (
        get_current_time_slot(now)
    )

    if (
        current_slot
        not in medication_times
    ):
        return None

    return current_slot


def get_slot_label(
    slot: str,
) -> str:
    return SLOT_LABELS.get(
        slot,
        slot,
    )


def get_existing_slot_check(
    *,
    db: Session,
    user_id: int,
    check_date,
    time_slot: str,
) -> MedicationCheckLog | None:
    return (
        db.query(MedicationCheckLog)
        .filter(
            MedicationCheckLog.user_id
            == user_id,
            MedicationCheckLog.check_date
            == check_date,
            MedicationCheckLog.time_slot
            == time_slot,
        )
        .first()
    )


def get_pending_medication_check(
    *,
    db: Session,
    user_id: int,
) -> MedicationCheckLog | None:
    """
    최근 12시간 안에 질문했지만
    아직 답하지 않은 복약 확인을 조회한다.

    자기 전 질문 이후 자정이 지나는 경우를 고려하여
    check_date를 오늘 날짜로만 제한하지 않는다.
    """

    stale_threshold = (
        datetime.utcnow()
        - timedelta(hours=12)
    )

    return (
        db.query(MedicationCheckLog)
        .filter(
            MedicationCheckLog.user_id
            == user_id,
            MedicationCheckLog.status
            == "ASKED",
            MedicationCheckLog.asked_at
            >= stale_threshold,
        )
        .order_by(
            MedicationCheckLog
            .asked_at.desc(),
            MedicationCheckLog
            .id.desc(),
        )
        .first()
    )


def create_medication_check(
    *,
    db: Session,
    user_id: int,
    check_date,
    time_slot: str,
) -> MedicationCheckLog:
    check = MedicationCheckLog(
        user_id=user_id,
        check_date=check_date,
        time_slot=time_slot,
        status="ASKED",
    )

    db.add(check)
    db.flush()

    return check