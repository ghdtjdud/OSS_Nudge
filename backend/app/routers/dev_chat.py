import os
from datetime import datetime
from uuid import uuid4

from dotenv import load_dotenv
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
    Mission,
    User,
    UserMission,
    UserRoutineProfile,
)
from backend.app.routers.chat import (
    combine_assistant_and_mission_text,
    get_owned_chat_session,
    save_and_build_response,
    save_crisis_response,
)
from backend.app.schemas.schemas import (
    ChatMessageRequest,
    ChatReplyResponse,
    DevChatMessageRequest,
    DevChatScenario,
)
from backend.app.services.auth_service import (
    get_current_user,
)
from backend.app.services.medication_service import (
    create_medication_check,
    get_current_time_slot,
    get_existing_slot_check,
    get_local_now,
    get_pending_medication_check,
    get_slot_label,
)
from backend.app.services.mission_service import (
    build_mission_ui_texts,
    get_active_user_mission,
)


load_dotenv()


router = APIRouter(
    prefix="/api/v1/dev/chat",
    tags=["Dev Chat"],
)


DEV_CHAT_ENABLED = (
    os.getenv(
        "DEV_CHAT_ENABLED",
        "false",
    )
    .strip()
    .lower()
    == "true"
)

DEV_CHAT_ALLOWED_USER_IDS = {
    int(value.strip())
    for value in os.getenv(
        "DEV_CHAT_ALLOWED_USER_IDS",
        "",
    ).split(",")
    if value.strip().isdigit()
}


GENERAL_MISSION_CODES = {
    "DRINK_WATER",
    "BRUSH_TEETH",
    "EAT_MEAL",
}

MEDICATION_TIME_SLOTS = {
    "MORNING",
    "LUNCH",
    "EVENING",
    "BEFORE_SLEEP",
}


def ensure_dev_chat_access(
    current_user: User,
) -> None:
    if not DEV_CHAT_ENABLED:
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "프론트 개발용 채팅 API가 "
                "비활성화되어 있습니다."
            ),
        )

    if (
        DEV_CHAT_ALLOWED_USER_IDS
        and current_user.id
        not in DEV_CHAT_ALLOWED_USER_IDS
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "이 사용자는 프론트 개발용 "
                "채팅 API를 사용할 수 없습니다."
            ),
        )


def create_dev_user_mission(
    *,
    db: Session,
    user_id: int,
    mission_code: str,
    assigned_date,
) -> UserMission:
    normalized_code = (
        mission_code.strip().upper()
    )

    allowed_codes = (
        GENERAL_MISSION_CODES
        | {"TAKE_MEDICATION"}
    )

    if normalized_code not in allowed_codes:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "지원하지 않는 개발용 "
                "미션 코드입니다."
            ),
        )

    active_mission = (
        get_active_user_mission(
            db=db,
            user_id=user_id,
        )
    )

    if active_mission is not None:
        if (
            active_mission.instance_key
            .startswith("DEV_TEST:")
        ):
            active_mission.status = "FAILED"
        else:
            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "실제 진행 중인 미션이 있어 "
                    "개발용 미션을 생성할 수 없습니다. "
                    "기존 미션을 먼저 완료하거나 "
                    "테스트 전용 계정을 사용해주세요."
                ),
            )

    mission_query = (
        db.query(Mission)
        .filter(
            Mission.code == normalized_code,
            Mission.is_active.is_(True),
        )
    )

    if normalized_code == "TAKE_MEDICATION":
        mission_query = mission_query.filter(
            Mission
            .requires_current_medication
            .is_(True)
        )
    else:
        mission_query = mission_query.filter(
            Mission
            .requires_current_medication
            .is_(False)
        )

    mission = mission_query.first()

    if mission is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                f"{normalized_code} 미션이 "
                "DB에 없거나 비활성 상태입니다."
            ),
        )

    ui_texts = build_mission_ui_texts(
        normalized_code
    )

    user_mission = UserMission(
        user_id=user_id,
        mission_id=mission.id,
        mission=mission,
        status="ASSIGNED",
        recommended_reason=(
            ui_texts[
                "recommendation_message"
            ]
        ),
        instance_key=(
            f"DEV_TEST:{normalized_code}:"
            f"{uuid4().hex[:12]}"
        ),
        assigned_date=assigned_date,
    )

    db.add(user_mission)
    db.flush()

    return user_mission


def get_or_reset_dev_medication_check(
    *,
    db: Session,
    user_id: int,
    check_date,
    time_slot: str,
):
    normalized_slot = (
        time_slot.strip().upper()
    )

    if (
        normalized_slot
        not in MEDICATION_TIME_SLOTS
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "복약 시간대는 MORNING, LUNCH, "
                "EVENING, BEFORE_SLEEP 중 "
                "하나여야 합니다."
            ),
        )

    check = get_existing_slot_check(
        db=db,
        user_id=user_id,
        check_date=check_date,
        time_slot=normalized_slot,
    )

    if check is None:
        return create_medication_check(
            db=db,
            user_id=user_id,
            check_date=check_date,
            time_slot=normalized_slot,
        )

    check.status = "ASKED"
    check.asked_at = datetime.utcnow()
    check.answered_at = None

    db.flush()

    return check


def get_dev_pending_check(
    *,
    db: Session,
    user_id: int,
    check_date,
    requested_slot: str | None,
):
    pending_check = (
        get_pending_medication_check(
            db=db,
            user_id=user_id,
        )
    )

    if pending_check is not None:
        return pending_check

    slot = (
        requested_slot
        or get_current_time_slot()
    )

    return get_or_reset_dev_medication_check(
        db=db,
        user_id=user_id,
        check_date=check_date,
        time_slot=slot,
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ChatReplyResponse,
    status_code=(
        status.HTTP_201_CREATED
    ),
)
def send_dev_chat_message(
    session_id: int,
    request: DevChatMessageRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    """
    프론트 화면 연동 전용 채팅 API.

    Gemini를 호출하지 않지만,
    실제 채팅 메시지와 UserMission을 DB에 저장하고
    운영 채팅 API와 동일한 ChatReplyResponse를 반환한다.
    """

    ensure_dev_chat_access(
        current_user
    )

    get_owned_chat_session(
        session_id=session_id,
        user_id=current_user.id,
        db=db,
    )

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
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "채팅 전에 사용자 상태정보를 "
                "입력해야 합니다."
            ),
        )

    now_local = get_local_now()
    today_local = now_local.date()

    chat_request = ChatMessageRequest(
        content=request.content,
        input_type=request.input_type,
    )

    try:
        if (
            request.scenario
            == DevChatScenario.CHAT_LOW
        ):
            return save_and_build_response(
                db=db,
                session_id=session_id,
                request=chat_request,
                assistant_content=(
                    "말씀해 주셔서 고마워요. "
                    "지금 느끼는 마음을 "
                    "천천히 이야기해도 괜찮아요."
                ),
                action="CHAT",
                medication_check_slot=None,
                should_recommend_mission=False,
                mission_context=None,
                risk_level="LOW",
                recommended_mission=None,
            )

        if (
            request.scenario
            == DevChatScenario
            .MEDIUM_SAFETY_CHECK
        ):
            return save_and_build_response(
                db=db,
                session_id=session_id,
                request=chat_request,
                assistant_content=(
                    "많이 힘들고 희망이 없다고 "
                    "느끼시는군요. "
                    "혹시 지금 자신을 해치거나 "
                    "구체적인 계획을 가지고 "
                    "있지는 않으신가요?"
                ),
                action="CHAT",
                medication_check_slot=None,
                should_recommend_mission=False,
                mission_context=None,
                risk_level="MEDIUM",
                recommended_mission=None,
            )

        if (
            request.scenario
            == DevChatScenario.CRISIS_HIGH
        ):
            return save_crisis_response(
                db=db,
                session_id=session_id,
                request=chat_request,
                current_user=current_user,
                detection_stage="DEV_TEST",
                crisis_signals=[
                    "SUICIDE_PLAN_OR_PREPARATION",
                ],
                crisis_reason=(
                    "프론트 위기지원 화면 연동을 "
                    "확인하기 위한 개발용 응답입니다."
                ),
            )

        if (
            request.scenario
            == DevChatScenario.GENERAL_MISSION
        ):
            user_mission = (
                create_dev_user_mission(
                    db=db,
                    user_id=current_user.id,
                    mission_code=(
                        request.mission_code
                    ),
                    assigned_date=(
                        today_local
                    ),
                )
            )

            recommendation_text = (
                user_mission
                .recommended_reason
                or build_mission_ui_texts(
                    user_mission.mission.code
                )[
                    "recommendation_message"
                ]
            )

            assistant_content = (
                combine_assistant_and_mission_text(
                    assistant_content=(
                        "지금은 부담이 적은 "
                        "작은 행동부터 시작해보면 "
                        "좋겠어요."
                    ),
                    recommendation_text=(
                        recommendation_text
                    ),
                )
            )

            return save_and_build_response(
                db=db,
                session_id=session_id,
                request=chat_request,
                assistant_content=(
                    assistant_content
                ),
                action=(
                    "OPEN_MISSION_VERIFICATION"
                ),
                medication_check_slot=None,
                should_recommend_mission=True,
                mission_context=(
                    "DEV_GENERAL_MISSION"
                ),
                risk_level="LOW",
                recommended_mission=(
                    user_mission
                ),
            )

        if (
            request.scenario
            == DevChatScenario
            .MEDICATION_CHECK_REQUIRED
        ):
            slot = (
                request.medication_check_slot
                or get_current_time_slot(
                    now_local
                )
            )

            check = (
                get_or_reset_dev_medication_check(
                    db=db,
                    user_id=current_user.id,
                    check_date=today_local,
                    time_slot=slot,
                )
            )

            slot_label = get_slot_label(
                check.time_slot
            )

            return save_and_build_response(
                db=db,
                session_id=session_id,
                request=chat_request,
                assistant_content=(
                    "지금은 설정하신 "
                    f"{slot_label} 복약 시간대예요. "
                    "오늘 약은 드셨나요?"
                ),
                action=(
                    "MEDICATION_CHECK_REQUIRED"
                ),
                medication_check_slot=(
                    check.time_slot
                ),
                should_recommend_mission=False,
                mission_context=None,
                risk_level="LOW",
                recommended_mission=None,
            )

        if (
            request.scenario
            == DevChatScenario.MEDICATION_TAKEN
        ):
            pending_check = (
                get_dev_pending_check(
                    db=db,
                    user_id=current_user.id,
                    check_date=today_local,
                    requested_slot=(
                        request
                        .medication_check_slot
                    ),
                )
            )

            pending_check.status = "TAKEN"
            pending_check.answered_at = (
                datetime.utcnow()
            )

            return save_and_build_response(
                db=db,
                session_id=session_id,
                request=chat_request,
                assistant_content=(
                    "잘 챙겨 드셨군요. "
                    "복약 여부를 확인했어요."
                ),
                action=(
                    "MEDICATION_CONFIRMED"
                ),
                medication_check_slot=(
                    pending_check.time_slot
                ),
                should_recommend_mission=False,
                mission_context=None,
                risk_level="LOW",
                recommended_mission=None,
            )

        if (
            request.scenario
            == DevChatScenario
            .MEDICATION_NOT_TAKEN
        ):
            pending_check = (
                get_dev_pending_check(
                    db=db,
                    user_id=current_user.id,
                    check_date=today_local,
                    requested_slot=(
                        request
                        .medication_check_slot
                    ),
                )
            )

            pending_check.status = "NOT_TAKEN"
            pending_check.answered_at = (
                datetime.utcnow()
            )

            user_mission = (
                create_dev_user_mission(
                    db=db,
                    user_id=current_user.id,
                    mission_code=(
                        "TAKE_MEDICATION"
                    ),
                    assigned_date=(
                        today_local
                    ),
                )
            )

            slot_label = get_slot_label(
                pending_check.time_slot
            )

            assistant_content = (
                combine_assistant_and_mission_text(
                    assistant_content=(
                        f"아직 {slot_label} 약을 "
                        "복용하지 않으셨군요."
                    ),
                    recommendation_text=(
                        user_mission
                        .recommended_reason
                        or ""
                    ),
                )
            )

            return save_and_build_response(
                db=db,
                session_id=session_id,
                request=chat_request,
                assistant_content=(
                    assistant_content
                ),
                action=(
                    "OPEN_MISSION_VERIFICATION"
                ),
                medication_check_slot=(
                    pending_check.time_slot
                ),
                should_recommend_mission=True,
                mission_context=(
                    "DEV_MEDICATION_NOT_TAKEN"
                ),
                risk_level="LOW",
                recommended_mission=(
                    user_mission
                ),
            )

        if (
            request.scenario
            == DevChatScenario.MEDICATION_MISSION
        ):
            user_mission = (
                create_dev_user_mission(
                    db=db,
                    user_id=current_user.id,
                    mission_code=(
                        "TAKE_MEDICATION"
                    ),
                    assigned_date=(
                        today_local
                    ),
                )
            )

            return save_and_build_response(
                db=db,
                session_id=session_id,
                request=chat_request,
                assistant_content=(
                    user_mission
                    .recommended_reason
                    or (
                        "지금은 설정해 둔 복약 "
                        "시간대예요. 처방받은 "
                        "방법대로 약을 챙겨보세요."
                    )
                ),
                action=(
                    "OPEN_MISSION_VERIFICATION"
                ),
                medication_check_slot=(
                    request.medication_check_slot
                ),
                should_recommend_mission=True,
                mission_context=(
                    "DEV_MEDICATION_MISSION"
                ),
                risk_level="LOW",
                recommended_mission=(
                    user_mission
                ),
            )

        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "지원하지 않는 개발용 "
                "채팅 시나리오입니다."
            ),
        )

    except HTTPException:
        db.rollback()
        raise

    except SQLAlchemyError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status
                .HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "개발용 채팅 응답 저장 중 "
                "오류가 발생했습니다."
            ),
        ) from exc
