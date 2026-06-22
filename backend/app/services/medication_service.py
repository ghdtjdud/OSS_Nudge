import os
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from sqlalchemy.orm import Session

from backend.app.models.models import (
    MedicationCheckLog,
    UserRoutineProfile,
)


APP_TIMEZONE = os.getenv(
    "APP_TIMEZONE",
    "Asia/Seoul",
)

LOCAL_TIMEZONE = ZoneInfo(APP_TIMEZONE)


SLOT_LABELS = {
    "MORNING": "아침",
    "LUNCH": "점심",
    "EVENING": "저녁",
    "BEFORE_SLEEP": "취침 전",
}


def get_local_now() -> datetime:
    return datetime.now(LOCAL_TIMEZONE)


def get_current_time_slot(
    now: datetime | None = None,
) -> str:
    """
    한국 시각을 네 시간대로 분류한다.

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
    if profile is None:
        return None

    if profile.medication_status != "CURRENT":
        return None

    medication_times = (
        profile.medication_times or []
    )

    current_slot = get_current_time_slot(now)

    if current_slot in medication_times:
        return current_slot

    return None


def get_slot_label(slot: str) -> str:
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
    check_date,
) -> MedicationCheckLog | None:
    return (
        db.query(MedicationCheckLog)
        .filter(
            MedicationCheckLog.user_id
            == user_id,
            MedicationCheckLog.check_date
            == check_date,
            MedicationCheckLog.status
            == "ASKED",
        )
        .order_by(
            MedicationCheckLog.asked_at.desc()
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