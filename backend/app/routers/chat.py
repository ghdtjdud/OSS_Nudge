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
from backend.app.services.chat_service import (
    generate_temporary_ai_response,
)


router = APIRouter(
    prefix="/api/v1/chat",
    tags=["Chat"],
)


def get_owned_chat_session(
    session_id: int,
    user_id: int,
    db: Session,
) -> ChatSession:
    """
    채팅방이 존재하며 현재 사용자의 채팅방인지 검사한다.
    """

    chat_session = (
        db.query(ChatSession)
        .filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
        .first()
    )

    if chat_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="채팅 세션을 찾을 수 없습니다.",
        )

    return chat_session


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
    """
    새로운 채팅 세션을 생성한다.

    사용자 상태정보를 입력하지 않은 사용자는
    채팅 세션을 생성할 수 없다.
    """

    routine_profile = (
        db.query(UserRoutineProfile)
        .filter(
            UserRoutineProfile.user_id
            == current_user.id
        )
        .first()
    )

    if routine_profile is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "채팅을 시작하기 전에 "
                "사용자 상태정보를 입력해야 합니다."
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
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
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
    """
    현재 사용자의 전체 채팅 세션을 조회한다.
    """

    chat_sessions = (
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

    return chat_sessions


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
    """
    사용자 메시지를 저장하고
    임시 AI 응답을 생성해 함께 저장한다.
    """

    get_owned_chat_session(
        session_id=session_id,
        user_id=current_user.id,
        db=db,
    )

    user_message = ChatMessage(
        session_id=session_id,
        role="user",
        content=request.content,
        input_type=request.input_type.value,
    )

    assistant_content = (
        generate_temporary_ai_response(
            request.content
        )
    )

    assistant_message = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=assistant_content,
        input_type="text",
    )

    try:
        db.add(user_message)
        db.add(assistant_message)
        db.commit()

        db.refresh(user_message)
        db.refresh(assistant_message)

    except SQLAlchemyError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail="채팅 메시지 저장에 실패했습니다.",
        ) from exc

    return {
        "session_id": session_id,
        "user_message": user_message,
        "assistant_message": assistant_message,
    }


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
    """
    특정 채팅 세션의 전체 메시지를 조회한다.
    """

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