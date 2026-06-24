from collections import defaultdict
from datetime import (
    date,
    datetime,
    timezone,
)

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.exc import (
    SQLAlchemyError,
)
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.models import (
    Mission,
    User,
    UserMission,
)
from backend.app.schemas.schemas import (
    DashboardCalendarResponse,
)
from backend.app.services.auth_service import (
    get_current_user,
)
from backend.app.services.medication_service import (
    LOCAL_TIMEZONE,
)


router = APIRouter(
    prefix="/api/v1/dashboard",
    tags=["Dashboard"],
)


# 대시보드 성취도에 포함되는
# 네 가지 미션 종류
DASHBOARD_MISSION_CODES = {
    "DRINK_WATER",
    "BRUSH_TEETH",
    "EAT_MEAL",
    "TAKE_MEDICATION",
}


STICKER_BY_COMPLETED_COUNT = {
    1: "STICKER_1",
    2: "STICKER_2",
    3: "STICKER_3",
    4: "STICKER_4",
}


def get_month_utc_range(
    *,
    year: int,
    month: int,
) -> tuple[datetime, datetime]:
    """
    사용자가 선택한 현지 월의 시작과 끝을
    DB 조회에 사용할 UTC naive datetime으로 변환한다.

    UserMission.completed_at은 현재
    datetime.utcnow()으로 저장되고 있다.
    """

    month_start_local = datetime(
        year,
        month,
        1,
        tzinfo=LOCAL_TIMEZONE,
    )

    if month == 12:
        next_month_start_local = datetime(
            year + 1,
            1,
            1,
            tzinfo=LOCAL_TIMEZONE,
        )

    else:
        next_month_start_local = datetime(
            year,
            month + 1,
            1,
            tzinfo=LOCAL_TIMEZONE,
        )

    month_start_utc = (
        month_start_local
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )

    next_month_start_utc = (
        next_month_start_local
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )

    return (
        month_start_utc,
        next_month_start_utc,
    )


def get_local_completion_date(
    completed_at: datetime,
) -> date:
    """
    DB의 UTC 완료시간을
    앱 현지 날짜로 변환한다.
    """

    if completed_at.tzinfo is None:
        completed_at_utc = (
            completed_at.replace(
                tzinfo=timezone.utc
            )
        )

    else:
        completed_at_utc = (
            completed_at.astimezone(
                timezone.utc
            )
        )

    return (
        completed_at_utc
        .astimezone(LOCAL_TIMEZONE)
        .date()
    )


@router.get(
    "/calendar",
    response_model=(
        DashboardCalendarResponse
    ),
)
def get_dashboard_calendar(
    year: int = Query(
        ...,
        ge=2000,
        le=2100,
    ),
    month: int = Query(
        ...,
        ge=1,
        le=12,
    ),
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    """
    선택한 월에 미션을 완료한 날짜와
    해당 날짜의 스티커 단계만 반환한다.

    ASSIGNED, IN_PROGRESS, FAILED 미션은
    대시보드 스티커에 포함하지 않는다.

    동일한 미션 코드를 여러 번 완료해도
    해당 날짜에는 한 종류로만 계산한다.
    """

    (
        month_start_utc,
        next_month_start_utc,
    ) = get_month_utc_range(
        year=year,
        month=month,
    )

    try:
        completed_rows = (
            db.query(
                UserMission.completed_at,
                Mission.code,
            )
            .join(
                Mission,
                UserMission.mission_id
                == Mission.id,
            )
            .filter(
                UserMission.user_id
                == current_user.id,

                UserMission.status
                == "COMPLETED",

                UserMission.completed_at
                .isnot(None),

                UserMission.completed_at
                >= month_start_utc,

                UserMission.completed_at
                < next_month_start_utc,

                Mission.code.in_(
                    DASHBOARD_MISSION_CODES
                ),
            )
            .order_by(
                UserMission.completed_at.asc()
            )
            .all()
        )

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=(
                status
                .HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "대시보드 기록 조회 중 "
                "오류가 발생했습니다."
            ),
        ) from exc

    # 날짜별로 완료한 미션 코드를
    # set으로 저장해 중복을 제거한다.
    mission_codes_by_date: dict[
        date,
        set[str],
    ] = defaultdict(set)

    for (
        completed_at,
        mission_code,
    ) in completed_rows:
        if completed_at is None:
            continue

        completion_date = (
            get_local_completion_date(
                completed_at
            )
        )

        mission_codes_by_date[
            completion_date
        ].add(
            mission_code
        )

    stickers = []

    for completion_date in sorted(
        mission_codes_by_date.keys()
    ):
        completed_count = min(
            len(
                mission_codes_by_date[
                    completion_date
                ]
            ),
            4,
        )

        # 완료된 미션이 없는 날짜는
        # 응답에 포함하지 않는다.
        if completed_count == 0:
            continue

        stickers.append({
            "date": completion_date,
            "completed_count": (
                completed_count
            ),
            "sticker_type": (
                STICKER_BY_COMPLETED_COUNT[
                    completed_count
                ]
            ),
        })

    return {
        "year": year,
        "month": month,
        "stickers": stickers,
    }