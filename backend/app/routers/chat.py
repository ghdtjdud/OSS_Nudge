from datetime import datetime

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
    ChatMessage,
    ChatSession,
    User,
    UserMission,
    UserRoutineProfile,
)
from backend.app.schemas.schemas import (
    ChatHistoryResponse,
    ChatMessageRequest,
    ChatReplyResponse,
    ChatSessionResponse,
)
from backend.app.services.auth_service import (
    get_current_user,
)
from backend.app.services.gemini_service import (
    GeminiServiceError,
    classify_medication_answer,
    generate_chat_response_with_gemini,
)
from backend.app.services.medication_service import (
    create_medication_check,
    get_due_medication_slot,
    get_existing_slot_check,
    get_local_now,
    get_pending_medication_check,
    get_slot_label,
)
from backend.app.services.mission_service import (
    assign_medication_mission,
    recommend_general_mission,
)


router = APIRouter(
    prefix="/api/v1/chat",
    tags=["Chat"],
)


def get_owned_chat_session(
    *,
    session_id: int,
    user_id: int,
    db: Session,
) -> ChatSession:
    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
        .first()
    )

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="채팅 세션을 찾을 수 없습니다.",
        )

    return session


def build_recent_chat_history(
    *,
    session_id: int,
    db: Session,
    limit: int = 20,
) -> list[dict[str, str]]:
    messages = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.session_id
            == session_id
        )
        .order_by(
            ChatMessage.created_at.desc(),
            ChatMessage.id.desc(),
        )
        .limit(limit)
        .all()
    )

    messages.reverse()

    return [
        {
            "role": message.role,
            "content": message.content,
        }
        for message in messages
    ]


def build_chat_profile(
    profile: UserRoutineProfile | None,
) -> dict | None:
    if profile is None:
        return None

    return {
        "sleep_bedtime": profile.sleep_bedtime,
        "sleep_duration": profile.sleep_duration,
        "sleep_condition": profile.sleep_condition,
        "breakfast_frequency": (
            profile.breakfast_frequency
        ),
        "lunch_dinner_pattern": (
            profile.lunch_dinner_pattern
        ),
        "appetite_change": (
            profile.appetite_change
        ),
        "medication_status": (
            profile.medication_status
        ),
        "medication_times": (
            profile.medication_times
        ),
        "medication_forget_frequency": (
            profile.medication_forget_frequency
        ),
    }


def create_chat_messages(
    *,
    db: Session,
    session_id: int,
    user_content: str,
    user_input_type: str,
    assistant_content: str,
):
    user_message = ChatMessage(
        session_id=session_id,
        role="user",
        content=user_content,
        input_type=user_input_type,
    )

    assistant_message = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=assistant_content,
        input_type="text",
    )

    db.add_all([
        user_message,
        assistant_message,
    ])

    db.flush()

    return user_message, assistant_message


def build_mission_card(
    user_mission: UserMission | None,
) -> dict | None:
    if user_mission is None:
        return None

    mission = user_mission.mission

    return {
        "user_mission_id": user_mission.id,
        "mission_code": mission.code,
        "title": mission.title,
        "description": mission.description,
        "reason": (
            user_mission.recommended_reason
        ),
        "status": user_mission.status,
        "verification_code": (
            mission.verification_code
        ),
        "instance_key": (
            user_mission.instance_key
        ),
    }


@router.post(
    "/sessions",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_chat_session(
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
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "채팅 전에 사용자 상태정보를 "
                "입력해야 합니다."
            ),
        )

    chat_session = ChatSession(
        user_id=current_user.id
    )

    try:
        db.add(chat_session)
        db.commit()
        db.refresh(chat_session)

    except SQLAlchemyError as exc:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="채팅 세션 생성에 실패했습니다.",
        ) from exc

    return chat_session


@router.get(
    "/sessions",
    response_model=list[ChatSessionResponse],
)
def get_chat_sessions(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    return (
        db.query(ChatSession)
        .filter(
            ChatSession.user_id
            == current_user.id
        )
        .order_by(
            ChatSession.created_at.desc()
        )
        .all()
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ChatReplyResponse,
    status_code=status.HTTP_201_CREATED,
)
def send_chat_message(
    session_id: int,
    request: ChatMessageRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
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

    recent_messages = (
        build_recent_chat_history(
            session_id=session_id,
            db=db,
        )
    )

    now_local = get_local_now()
    today_local = now_local.date()

    try:
        # =================================================
        # 1. 직전 복약 질문에 대한 사용자 답변 처리
        # =================================================
        pending_check = (
            get_pending_medication_check(
                db=db,
                user_id=current_user.id,
                check_date=today_local,
            )
        )

        if pending_check is not None:
            classification = (
                classify_medication_answer(
                    request.content
                )
            )

            medication_slot_label = (
                get_slot_label(
                    pending_check.time_slot
                )
            )

            recommended_mission = None

            if classification.answer.value == "TAKEN":
                pending_check.status = "TAKEN"
                pending_check.answered_at = (
                    datetime.utcnow()
                )

                assistant_content = (
                    "잘 챙겨 드셨군요. "
                    "복약 여부를 확인했어요. "
                    "이제 방금 나누던 이야기를 "
                    "계속해도 좋아요."
                )

                action = (
                    "MEDICATION_CONFIRMED"
                )

            elif (
                classification.answer.value
                == "NOT_TAKEN"
            ):
                pending_check.status = "NOT_TAKEN"
                pending_check.answered_at = (
                    datetime.utcnow()
                )

                recommended_mission = (
                    assign_medication_mission(
                        db=db,
                        user_id=current_user.id,
                        assigned_date=today_local,
                        time_slot=(
                            pending_check.time_slot
                        ),
                    )
                )

                assistant_content = (
                    f"아직 {medication_slot_label} 약을 "
                    "복용하지 않으셨군요. "
                    "처방받은 방법대로 약을 "
                    "챙길 수 있도록 "
                    "'약 먹기' 미션을 추천했어요."
                )

                action = (
                    "MEDICATION_MISSION_ASSIGNED"
                )

            else:
                normal_result = (
                    generate_chat_response_with_gemini(
                        user_message=request.content,
                        user_profile=(
                            build_chat_profile(
                                profile
                            )
                        ),
                        recent_messages=(
                            recent_messages
                        ),
                        current_time_context={
                            "timezone": "Asia/Seoul",
                            "datetime": (
                                now_local.isoformat()
                            ),
                            "time_slot": (
                                pending_check
                                .time_slot
                            ),
                        },
                    )
                )

                assistant_content = (
                    normal_result.reply
                    + "\n\n그리고 복약 여부도 "
                    "확인하고 싶어요. "
                    f"오늘 {medication_slot_label} 약은 "
                    "드셨나요?"
                )

                action = (
                    "MEDICATION_CHECK_PENDING"
                )

            user_message, assistant_message = (
                create_chat_messages(
                    db=db,
                    session_id=session_id,
                    user_content=request.content,
                    user_input_type=(
                        request.input_type.value
                    ),
                    assistant_content=(
                        assistant_content
                    ),
                )
            )

            db.commit()
            db.refresh(user_message)
            db.refresh(assistant_message)

            return {
                "session_id": session_id,
                "user_message": user_message,
                "assistant_message": assistant_message,
                "action": action,
                "medication_check_slot": (
                    pending_check.time_slot
                ),
                "should_recommend_mission": (
                    recommended_mission
                    is not None
                ),
                "mission_context": (
                    "복약 시간대에 아직 "
                    "약을 복용하지 않음"
                    if recommended_mission
                    else None
                ),
                "risk_level": "LOW",
                "recommended_mission": (
                    build_mission_card(
                        recommended_mission
                    )
                ),
            }

        # =================================================
        # 2. 현재 복약 시간대이면 복약 여부 먼저 질문
        # =================================================
        due_slot = get_due_medication_slot(
            profile=profile,
            now=now_local,
        )

        if due_slot is not None:
            existing_check = (
                get_existing_slot_check(
                    db=db,
                    user_id=current_user.id,
                    check_date=today_local,
                    time_slot=due_slot,
                )
            )

            if existing_check is None:
                create_medication_check(
                    db=db,
                    user_id=current_user.id,
                    check_date=today_local,
                    time_slot=due_slot,
                )

                slot_label = get_slot_label(
                    due_slot
                )

                assistant_content = (
                    "먼저 복약 여부를 확인할게요. "
                    f"지금은 설정하신 {slot_label} "
                    "복약 시간대예요. "
                    "오늘 약은 드셨나요? "
                    "답해주시면 방금 하신 이야기도 "
                    "계속 함께 나눌게요."
                )

                (
                    user_message,
                    assistant_message,
                ) = create_chat_messages(
                    db=db,
                    session_id=session_id,
                    user_content=request.content,
                    user_input_type=(
                        request.input_type.value
                    ),
                    assistant_content=(
                        assistant_content
                    ),
                )

                db.commit()
                db.refresh(user_message)
                db.refresh(assistant_message)

                return {
                    "session_id": session_id,
                    "user_message": user_message,
                    "assistant_message": assistant_message,
                    "action": "MEDICATION_CHECK",
                    "medication_check_slot": (
                        due_slot
                    ),
                    "should_recommend_mission": False,
                    "mission_context": None,
                    "risk_level": "LOW",
                    "recommended_mission": None,
                }

        # =================================================
        # 3. 일반 Gemini 채팅
        # =================================================
        gemini_result = (
            generate_chat_response_with_gemini(
                user_message=request.content,
                user_profile=(
                    build_chat_profile(profile)
                ),
                recent_messages=recent_messages,
                current_time_context={
                    "timezone": "Asia/Seoul",
                    "datetime": (
                        now_local.isoformat()
                    ),
                    "time_slot": (
                        due_slot or "NONE"
                    ),
                },
            )
        )

        recommended_mission = None

        # LOW일 때만 일반 미션 자동 추천
        if (
            gemini_result
            .should_recommend_mission
            and gemini_result
            .risk_level.value == "LOW"
            and profile is not None
        ):
            mission_messages = (
                recent_messages
                + [
                    {
                        "role": "user",
                        "content": request.content,
                    }
                ]
            )

            recommended_mission = (
                recommend_general_mission(
                    db=db,
                    user_id=current_user.id,
                    profile=profile,
                    recent_messages=(
                        mission_messages
                    ),
                    assigned_date=today_local,
                )
            )

        (
            user_message,
            assistant_message,
        ) = create_chat_messages(
            db=db,
            session_id=session_id,
            user_content=request.content,
            user_input_type=(
                request.input_type.value
            ),
            assistant_content=(
                gemini_result.reply
            ),
        )

        db.commit()
        db.refresh(user_message)
        db.refresh(assistant_message)

        return {
            "session_id": session_id,
            "user_message": user_message,
            "assistant_message": assistant_message,
            "action": (
                "MISSION_ASSIGNED"
                if recommended_mission
                else "CHAT"
            ),
            "medication_check_slot": None,
            "should_recommend_mission": (
                recommended_mission is not None
            ),
            "mission_context": (
                gemini_result.mission_context
            ),
            "risk_level": (
                gemini_result.risk_level
            ),
            "recommended_mission": (
                build_mission_card(
                    recommended_mission
                )
            ),
        }

    except GeminiServiceError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=str(exc),
        ) from exc

    except SQLAlchemyError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "채팅 또는 미션 저장 중 "
                "오류가 발생했습니다."
            ),
        ) from exc

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=str(exc),
        ) from exc


@router.get(
    "/sessions/{session_id}/messages",
    response_model=ChatHistoryResponse,
)
def get_chat_messages(
    session_id: int,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    get_owned_chat_session(
        session_id=session_id,
        user_id=current_user.id,
        db=db,
    )

    messages = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.session_id
            == session_id
        )
        .order_by(
            ChatMessage.created_at.asc(),
            ChatMessage.id.asc(),
        )
        .all()
    )

    return {
        "session_id": session_id,
        "messages": messages,
    }