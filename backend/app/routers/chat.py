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
    ChatSessionCreateResponse,
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
from backend.app.services.chat_service import (
    build_initial_greeting,
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
    build_mission_ui_texts,
    get_active_user_mission,
    recommend_general_mission,
)


router = APIRouter(
    prefix="/api/v1/chat",
    tags=["Chat"],
)


# Gemini 판단이 흔들리더라도
# 아래 표현은 일반 미션 추천을 보장한다.
LOW_ENERGY_TRIGGERS = (
    "기운이 없어",
    "기운 없어",
    "힘이 없어",
    "힘 없어",
    "축 처져",
    "무기력",
    "아무것도 하기 싫",
)


MISSION_REFUSAL_TRIGGERS = (
    "미션 싫",
    "미션은 싫",
    "추천하지 마",
    "추천하지마",
    "미션 하지 않을",
)


def should_force_general_mission(
    user_message: str,
) -> bool:
    normalized = (
        user_message
        .strip()
        .lower()
    )

    if any(
        trigger in normalized
        for trigger
        in MISSION_REFUSAL_TRIGGERS
    ):
        return False

    return any(
        trigger in normalized
        for trigger
        in LOW_ENERGY_TRIGGERS
    )


def combine_assistant_and_mission_text(
    *,
    assistant_content: str,
    recommendation_text: str,
) -> str:
    """
    공감 답변과 미션 추천 이유를
    하나의 AI 말풍선으로 합친다.
    """

    normalized_assistant = (
        assistant_content.strip()
    )

    normalized_recommendation = (
        recommendation_text.strip()
    )

    if not normalized_recommendation:
        return normalized_assistant

    # Gemini 답변에 같은 추천 문구가 이미 포함된 경우
    # 중복으로 붙이지 않는다.
    if (
        normalized_recommendation
        in normalized_assistant
    ):
        return normalized_assistant

    return (
        f"{normalized_assistant}\n\n"
        f"{normalized_recommendation}"
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
            ChatSession.id
            == session_id,
            ChatSession.user_id
            == user_id,
        )
        .first()
    )

    if session is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "채팅 세션을 찾을 수 없습니다."
            ),
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
        "sleep_bedtime": (
            profile.sleep_bedtime
        ),
        "sleep_duration": (
            profile.sleep_duration
        ),
        "meal_regularity": (
            profile.meal_regularity
        ),
        "medication_status": (
            profile.medication_status
        ),
        "medication_times": (
            profile.medication_times or []
        ),
        "activity_start_difficulty": (
            profile
            .activity_start_difficulty
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
    """
    사용자 메시지 한 개와
    AI 메시지 한 개만 저장한다.

    미션 추천 이유도 assistant_content 안에
    함께 포함한다.
    """

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

    return (
        user_message,
        assistant_message,
    )


def build_mission_card(
    user_mission: UserMission | None,
) -> dict | None:
    if user_mission is None:
        return None

    mission = user_mission.mission

    ui_texts = build_mission_ui_texts(
        mission.code
    )

    return {
        "user_mission_id": (
            user_mission.id
        ),
        "mission_code": mission.code,
        "mission_type": (
            "MEDICATION"
            if mission.code
            == "TAKE_MEDICATION"
            else "GENERAL"
        ),
        "title": mission.title,
        "description": (
            mission.description
        ),
        "reason": (
            user_mission
            .recommended_reason
        ),
        "status": (
            user_mission.status
        ),
        "verification_code": (
            mission.verification_code
        ),
        "instance_key": (
            user_mission.instance_key
        ),

        # 미션 카드 전체 화면 문구
        "card_title": (
            ui_texts["card_title"]
        ),
        "card_subtitle": (
            ui_texts["card_subtitle"]
        ),

        # 카메라 인증 준비 화면 문구
        "verification_title": (
            ui_texts[
                "verification_title"
            ]
        ),
        "verification_subtitle": (
            ui_texts[
                "verification_subtitle"
            ]
        ),
    }


def save_and_build_response(
    *,
    db: Session,
    session_id: int,
    request: ChatMessageRequest,
    assistant_content: str,
    action: str,
    medication_check_slot: (
        str | None
    ),
    should_recommend_mission: bool,
    mission_context: str | None,
    risk_level,
    recommended_mission: (
        UserMission | None
    ),
) -> dict:
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

    should_navigate = (
        action
        == "OPEN_MISSION_VERIFICATION"
        and recommended_mission
        is not None
    )

    return {
        "session_id": session_id,
        "user_message": user_message,
        "assistant_message": (
            assistant_message
        ),
        "action": action,
        "medication_check_slot": (
            medication_check_slot
        ),
        "should_recommend_mission": (
            should_recommend_mission
        ),
        "mission_context": (
            mission_context
        ),
        "risk_level": risk_level,
        "should_navigate_to_mission": (
            should_navigate
        ),
        "next_screen": (
            "MISSION_VERIFICATION"
            if should_navigate
            else None
        ),
        "recommended_mission": (
            build_mission_card(
                recommended_mission
            )
        ),
    }


@router.post(
    "/sessions",
    response_model=ChatSessionCreateResponse,
    status_code=(
        status.HTTP_201_CREATED
    ),
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
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "채팅 전에 사용자 상태정보를 "
                "입력해야 합니다."
            ),
        )

    chat_session = ChatSession(
        user_id=current_user.id
    )

    try:
        # 세션 ID를 먼저 생성한다.
        db.add(chat_session)
        db.flush()

        # 새 세션의 첫 AI 인사말을 생성한다.
        initial_message = ChatMessage(
            session_id=chat_session.id,
            role="assistant",
            content=build_initial_greeting(
                current_user.name
            ),
            input_type="text",
        )

        db.add(initial_message)

        # 세션과 첫 메시지를 한 번에 저장한다.
        db.commit()

        db.refresh(chat_session)
        db.refresh(initial_message)

    except SQLAlchemyError as exc:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "채팅 세션 생성에 실패했습니다."
            ),
        ) from exc

    return {
        "id": chat_session.id,
        "user_id": chat_session.user_id,
        "created_at": (
            chat_session.created_at
        ),
        "initial_message": (
            initial_message
        ),
    }


@router.get(
    "/sessions",
    response_model=list[
        ChatSessionResponse
    ],
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
            ChatSession
            .created_at.desc()
        )
        .all()
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ChatReplyResponse,
    status_code=(
        status.HTTP_201_CREATED
    ),
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

    recent_messages = (
        build_recent_chat_history(
            session_id=session_id,
            db=db,
        )
    )

    now_local = get_local_now()
    today_local = now_local.date()

    try:
        # =============================================
        # 1. 이전 복약 질문에 대한 답변 처리
        # =============================================
        pending_check = (
            get_pending_medication_check(
                db=db,
                user_id=current_user.id,
            )
        )

        if pending_check is not None:
            classification = (
                classify_medication_answer(
                    request.content
                )
            )

            slot_label = get_slot_label(
                pending_check.time_slot
            )

            # -----------------------------------------
            # 약을 이미 먹었다고 답함
            # -----------------------------------------
            if (
                classification.answer.value
                == "TAKEN"
            ):
                pending_check.status = "TAKEN"
                pending_check.answered_at = (
                    datetime.utcnow()
                )

                return save_and_build_response(
                    db=db,
                    session_id=session_id,
                    request=request,
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

            # -----------------------------------------
            # 약을 아직 먹지 않았다고 답함
            # -----------------------------------------
            if (
                classification.answer.value
                == "NOT_TAKEN"
            ):
                pending_check.status = (
                    "NOT_TAKEN"
                )
                pending_check.answered_at = (
                    datetime.utcnow()
                )

                active_before_assignment = (
                    get_active_user_mission(
                        db=db,
                        user_id=current_user.id,
                    )
                )

                recommended_mission = (
                    assign_medication_mission(
                        db=db,
                        user_id=(
                            current_user.id
                        ),
                        profile=profile,
                        assigned_date=(
                            today_local
                        ),
                        time_slot=(
                            pending_check
                            .time_slot
                        ),
                        now=now_local,
                    )
                )

                if (
                    recommended_mission
                    is not None
                ):
                    medication_ui_texts = (
                        build_mission_ui_texts(
                            recommended_mission
                            .mission.code
                        )
                    )

                    recommendation_text = (
                        recommended_mission
                        .recommended_reason
                        or medication_ui_texts[
                            "recommendation_message"
                        ]
                    )

                    combined_content = (
                        combine_assistant_and_mission_text(
                            assistant_content=(
                                f"아직 {slot_label} 약을 "
                                "복용하지 않으셨군요."
                            ),
                            recommendation_text=(
                                recommendation_text
                            ),
                        )
                    )

                    return save_and_build_response(
                        db=db,
                        session_id=session_id,
                        request=request,
                        assistant_content=(
                            combined_content
                        ),
                        action=(
                            "OPEN_MISSION_VERIFICATION"
                        ),
                        medication_check_slot=(
                            pending_check
                            .time_slot
                        ),
                        should_recommend_mission=True,
                        mission_context=(
                            "설정한 복약 시간대이며 "
                            "아직 복용하지 않음"
                        ),
                        risk_level="LOW",
                        recommended_mission=(
                            recommended_mission
                        ),
                    )

                current_due_slot = (
                    get_due_medication_slot(
                        profile=profile,
                        now=now_local,
                    )
                )

                if (
                    active_before_assignment
                    is not None
                ):
                    assistant_content = (
                        "복약하지 않은 상태는 "
                        "확인했어요. "
                        "다만 현재 진행 중인 미션이 "
                        "있어 새 복약 미션은 "
                        "추가하지 않았어요."
                    )

                elif (
                    current_due_slot
                    != pending_check.time_slot
                ):
                    assistant_content = (
                        "복약하지 않은 상태는 "
                        "확인했어요. "
                        "현재는 설정한 복약 시간대를 "
                        "벗어나 있어 새 복약 미션은 "
                        "생성하지 않았어요."
                    )

                else:
                    assistant_content = (
                        "복약하지 않은 상태는 "
                        "확인했어요. "
                        "지금은 새 미션을 "
                        "생성할 수 없어요."
                    )

                return save_and_build_response(
                    db=db,
                    session_id=session_id,
                    request=request,
                    assistant_content=(
                        assistant_content
                    ),
                    action="CHAT",
                    medication_check_slot=(
                        pending_check.time_slot
                    ),
                    should_recommend_mission=False,
                    mission_context=None,
                    risk_level="LOW",
                    recommended_mission=None,
                )

            # -----------------------------------------
            # 복약 여부 답변이 불분명함
            # -----------------------------------------
            normal_result = (
                generate_chat_response_with_gemini(
                    user_message=(
                        request.content
                    ),
                    user_profile=(
                        build_chat_profile(
                            profile
                        )
                    ),
                    recent_messages=(
                        recent_messages
                    ),
                    current_time_context={
                        "timezone": (
                            "Asia/Seoul"
                        ),
                        "datetime": (
                            now_local
                            .isoformat()
                        ),
                        "time_slot": (
                            pending_check
                            .time_slot
                        ),
                        "medication_check_required": (
                            True
                        ),
                    },
                )
            )

            assistant_content = (
                normal_result.reply
                + "\n\n그리고 복약 여부도 "
                "확인할게요. "
                f"오늘 {slot_label} 약은 "
                "드셨나요?"
            )

            return save_and_build_response(
                db=db,
                session_id=session_id,
                request=request,
                assistant_content=(
                    assistant_content
                ),
                action=(
                    "MEDICATION_CHECK_REQUIRED"
                ),
                medication_check_slot=(
                    pending_check.time_slot
                ),
                should_recommend_mission=False,
                mission_context=None,
                risk_level=(
                    normal_result.risk_level
                ),
                recommended_mission=None,
            )

        # =============================================
        # 2. 활성 미션 및 현재 복약 시간대 확인
        # =============================================
        active_mission = (
            get_active_user_mission(
                db=db,
                user_id=current_user.id,
            )
        )

        due_slot = (
            get_due_medication_slot(
                profile=profile,
                now=now_local,
            )
        )

        existing_check = None

        if due_slot is not None:
            existing_check = (
                get_existing_slot_check(
                    db=db,
                    user_id=current_user.id,
                    check_date=today_local,
                    time_slot=due_slot,
                )
            )

        should_ask_medication = (
            active_mission is None
            and due_slot is not None
            and existing_check is None
        )

        # =============================================
        # 3. 사용자의 현재 메시지에 AI가 먼저 답변
        # =============================================
        gemini_result = (
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
                        due_slot or "NONE"
                    ),
                    "medication_check_required": (
                        should_ask_medication
                    ),
                },
            )
        )

        assistant_content = (
            gemini_result.reply
        )

        # =============================================
        # 4. 현재가 선택한 복약 시간대이면
        #    AI 답변 뒤 복약 여부 확인
        # =============================================
        if (
            should_ask_medication
            and gemini_result
            .risk_level.value
            != "HIGH"
        ):
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
                assistant_content
                + "\n\n그리고 지금은 "
                "설정하신 "
                f"{slot_label} 복약 "
                "시간대예요. "
                "오늘 약은 드셨나요?"
            )

            return save_and_build_response(
                db=db,
                session_id=session_id,
                request=request,
                assistant_content=(
                    assistant_content
                ),
                action=(
                    "MEDICATION_CHECK_REQUIRED"
                ),
                medication_check_slot=(
                    due_slot
                ),
                should_recommend_mission=False,
                mission_context=None,
                risk_level=(
                    gemini_result.risk_level
                ),
                recommended_mission=None,
            )

        # =============================================
        # 5. 일반 미션 추천
        # =============================================
        recommended_mission = None

        force_general_mission = (
            should_force_general_mission(
                request.content
            )
        )

        if (
            active_mission is None
            and (
                gemini_result
                .should_recommend_mission
                or force_general_mission
            )
            and gemini_result
            .risk_level.value
            == "LOW"
        ):
            mission_messages = (
                recent_messages
                + [
                    {
                        "role": "user",
                        "content": (
                            request.content
                        ),
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
                    assigned_date=(
                        today_local
                    ),
                )
            )

        # ---------------------------------------------
        # 추천 성공:
        # 공감 답변과 추천 이유를 한 말풍선으로 합침
        # ---------------------------------------------
        if recommended_mission is not None:
            mission_ui_texts = (
                build_mission_ui_texts(
                    recommended_mission
                    .mission.code
                )
            )

            recommendation_text = (
                recommended_mission
                .recommended_reason
                or mission_ui_texts[
                    "recommendation_message"
                ]
            )

            combined_content = (
                combine_assistant_and_mission_text(
                    assistant_content=(
                        assistant_content
                    ),
                    recommendation_text=(
                        recommendation_text
                    ),
                )
            )

            return save_and_build_response(
                db=db,
                session_id=session_id,
                request=request,
                assistant_content=(
                    combined_content
                ),
                action=(
                    "OPEN_MISSION_VERIFICATION"
                ),
                medication_check_slot=None,
                should_recommend_mission=True,
                mission_context=(
                    gemini_result
                    .mission_context
                    or (
                        "사용자가 기운 저하를 "
                        "직접 표현함"
                        if force_general_mission
                        else None
                    )
                ),
                risk_level=(
                    gemini_result.risk_level
                ),
                recommended_mission=(
                    recommended_mission
                ),
            )

        # ---------------------------------------------
        # 추천 없음: 일반 채팅 응답
        # ---------------------------------------------
        return save_and_build_response(
            db=db,
            session_id=session_id,
            request=request,
            assistant_content=(
                assistant_content
            ),
            action="CHAT",
            medication_check_slot=None,
            should_recommend_mission=False,
            mission_context=None,
            risk_level=(
                gemini_result.risk_level
            ),
            recommended_mission=None,
        )

    except GeminiServiceError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status
                .HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=str(exc),
        ) from exc

    except SQLAlchemyError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status
                .HTTP_500_INTERNAL_SERVER_ERROR
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