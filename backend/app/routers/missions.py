from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.exc import (
    IntegrityError,
    SQLAlchemyError,
)
from sqlalchemy.orm import (
    Session,
    joinedload,
)

from backend.app.database import get_db
from backend.app.models.models import (
    ChatMessage,
    ChatSession,
    Mission,
    User,
    UserMission,
    UserRoutineProfile,
)
from backend.app.schemas.schemas import (
    MissionFrameVerificationResponse,
    MissionRecommendationResponse,
    MissionResponse,
    MissionResultScreenResponse,
)
from backend.app.services.auth_service import (
    get_current_user,
)
from backend.app.services.gemini_service import (
    GeminiServiceError,
    generate_mission_completion_feedback,
)
from backend.app.services.medication_service import (
    get_local_now,
)
from backend.app.services.mission_service import (
    build_mission_result_ui,
    get_active_user_mission,
    recommend_general_mission,
)
from backend.app.services.mission_verification_service import (
    MissionVerificationConfigError,
    MissionVerificationInferenceError,
    MissionVerificationValidationError,
    reset_verification_progress,
    verify_mission_frame,
)
from starlette.concurrency import (
    run_in_threadpool,
)

router = APIRouter(
    prefix="/api/v1/missions",
    tags=["Missions"],
)

def get_owned_user_mission(
    *,
    user_mission_id: int,
    user_id: int,
    db: Session,
) -> UserMission:
    """
    현재 로그인한 사용자의 미션을 조회한다.
    다른 사용자의 미션에는 접근할 수 없다.
    """

    user_mission = (
        db.query(UserMission)
        .options(
            joinedload(
                UserMission.mission
            )
        )
        .filter(
            UserMission.id
            == user_mission_id,
            UserMission.user_id
            == user_id,
        )
        .first()
    )

    if user_mission is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "사용자 미션을 "
                "찾을 수 없습니다."
            ),
        )

    return user_mission

def get_recent_messages(
    *,
    user_id: int,
    db: Session,
    limit: int = 10,
) -> list[dict[str, str]]:
    messages = (
        db.query(ChatMessage)
        .join(
            ChatSession,
            ChatMessage.session_id
            == ChatSession.id,
        )
        .filter(
            ChatSession.user_id
            == user_id
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


@router.get(
    "",
    response_model=list[
        MissionResponse
    ],
)
def get_available_missions(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    """
    일반 미션 목록만 반환한다.

    TAKE_MEDICATION은 채팅에서
    복약 여부를 확인한 뒤에만 배정한다.
    """

    return (
        db.query(Mission)
        .filter(
            Mission.is_active.is_(True),
            Mission
            .requires_current_medication
            .is_(False),
            Mission.code
            != "TAKE_MEDICATION",
        )
        .order_by(
            Mission.id.asc()
        )
        .all()
    )


@router.post(
    "/recommend",
    response_model=(
        MissionRecommendationResponse
    ),
    status_code=(
        status.HTTP_201_CREATED
    ),
)
def recommend_mission(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    """
    수동 일반 미션 추천 API.

    복약 미션은 절대 추천하지 않는다.
    진행 중인 미션이 있으면 기존 미션을 반환한다.
    """

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
                "미션 추천 전에 사용자 "
                "상태정보를 입력해야 합니다."
            ),
        )

    active_mission = (
        get_active_user_mission(
            db=db,
            user_id=current_user.id,
        )
    )

    if active_mission is not None:
        return {
            "message": (
                "현재 진행 중인 미션이 있습니다."
            ),
            "user_mission": (
                active_mission
            ),
        }

    today_local = (
        get_local_now().date()
    )

    try:
        user_mission = (
            recommend_general_mission(
                db=db,
                user_id=current_user.id,
                profile=profile,
                recent_messages=(
                    get_recent_messages(
                        user_id=(
                            current_user.id
                        ),
                        db=db,
                    )
                ),
                assigned_date=(
                    today_local
                ),
            )
        )

        if user_mission is None:
            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "현재 추천할 수 있는 "
                    "새 일반 미션이 없습니다."
                ),
            )

        db.commit()
        db.refresh(user_mission)

    except HTTPException:
        db.rollback()
        raise

    except GeminiServiceError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status
                .HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=str(exc),
        ) from exc

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "동일한 미션이 이미 "
                "오늘 배정되었습니다."
            ),
        ) from exc

    except SQLAlchemyError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status
                .HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "미션 저장에 실패했습니다."
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

    return {
        "message": (
            "새로운 미션을 추천했습니다."
        ),
        "user_mission": user_mission,
    }


@router.get(
    "/me/today",
    response_model=list[
        MissionRecommendationResponse
    ],
)
def get_today_missions(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    today_local = (
        get_local_now().date()
    )

    user_missions = (
        db.query(UserMission)
        .filter(
            UserMission.user_id
            == current_user.id,
            UserMission.assigned_date
            == today_local,
        )
        .order_by(
            UserMission
            .assigned_at.desc()
        )
        .all()
    )

    return [
        {
            "message": "오늘의 미션",
            "user_mission": (
                user_mission
            ),
        }
        for user_mission
        in user_missions
    ]

@router.patch(
    "/{user_mission_id}/start",
    response_model=(
        MissionRecommendationResponse
    ),
)
def start_user_mission(
    user_mission_id: int,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    """
    배정된 미션을 시작한다.

    ASSIGNED → IN_PROGRESS
    """

    user_mission = (
        get_owned_user_mission(
            user_mission_id=(
                user_mission_id
            ),
            user_id=current_user.id,
            db=db,
        )
    )

    # 이미 시작한 경우에는 중복 오류 대신
    # 현재 상태를 그대로 반환한다.
    if (
        user_mission.status
        == "IN_PROGRESS"
    ):
        return {
            "message": (
                "이미 진행 중인 미션입니다."
            ),
            "user_mission": user_mission,
        }

    if (
        user_mission.status
        == "COMPLETED"
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "이미 완료한 미션입니다."
            ),
        )

    if (
        user_mission.status
        == "FAILED"
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "종료된 미션은 "
                "다시 시작할 수 없습니다."
            ),
        )

    if (
        user_mission.status
        != "ASSIGNED"
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "현재 상태에서는 "
                "미션을 시작할 수 없습니다."
            ),
        )

    try:
        user_mission.status = (
            "IN_PROGRESS"
        )

        db.commit()
        db.refresh(user_mission)

    except SQLAlchemyError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status
                .HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "미션 시작 처리 중 "
                "오류가 발생했습니다."
            ),
        ) from exc

    return {
        "message": "미션을 시작했습니다.",
        "user_mission": user_mission,
    }

@router.post(
    "/{user_mission_id}/verify-frame",
    response_model=(
        MissionFrameVerificationResponse
    ),
)
async def verify_user_mission_frame(
    user_mission_id: int,
    image: UploadFile = File(...),
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    """
    웹캠의 현재 프레임을 YOLO로 분석한다.

    대상 객체가 약 3초 동안 안정적으로
    탐지되면 미션을 COMPLETED로 변경한다.
    """

    user_mission = (
        get_owned_user_mission(
            user_mission_id=(
                user_mission_id
            ),
            user_id=current_user.id,
            db=db,
        )
    )

    if (
        user_mission.status
        == "ASSIGNED"
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "미션을 먼저 시작해주세요."
            ),
        )

    if (
        user_mission.status
        == "COMPLETED"
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "이미 완료된 미션입니다."
            ),
        )

    if (
        user_mission.status
        != "IN_PROGRESS"
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "현재 상태에서는 "
                "미션 인증을 진행할 수 없습니다."
            ),
        )

    content_type = (
        image.content_type or ""
    )

    if not content_type.startswith(
        "image/"
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "이미지 파일만 전송할 수 있습니다."
            ),
        )

    try:
        image_bytes = await image.read()

        verification_result = (
            await run_in_threadpool(
                verify_mission_frame,
                user_mission_id=(
                    user_mission.id
                ),
                verification_code=(
                    user_mission
                    .mission
                    .verification_code
                ),
                image_bytes=image_bytes,
            )
        )

        result_screen = None

        if verification_result[
            "completed"
        ]:
            # =============================================
            # 1. 미션 완료 상태를 먼저 DB에 저장
            # =============================================
            user_mission.status = (
                "COMPLETED"
            )

            user_mission.completed_at = (
                datetime.utcnow()
            )

            db.commit()
            db.refresh(user_mission)

            # =============================================
            # 2. 기본 성공 화면 문구 준비
            # Gemini 실패 시 fallback으로 사용
            # =============================================
            result_ui = (
                build_mission_result_ui(
                    success=True
                )
            )

            fallback_feedback = str(
                result_ui[
                    "result_message"
                ]
            )

            # =============================================
            # 3. Gemini 미션 완료 피드백 생성
            # =============================================
            try:
                ai_feedback = (
                    await run_in_threadpool(
                        generate_mission_completion_feedback,
                        user_name=(
                            current_user.name
                        ),
                        mission_code=(
                            user_mission
                            .mission
                            .code
                        ),
                        mission_title=(
                            user_mission
                            .mission
                            .title
                        ),
                    )
                )

            except GeminiServiceError as exc:
                # Gemini가 실패하더라도
                # 미션 완료 결과는 정상 반환한다.
                print(
                    "[Mission Completion Feedback] "
                    "Gemini 호출 실패, fallback 사용:",
                    exc,
                )

                ai_feedback = (
                    fallback_feedback
                )

            # =============================================
            # 4. 화면 표시 문구와 TTS 문구에
            # Gemini 피드백 적용
            # =============================================
            result_ui[
                "result_message"
            ] = ai_feedback

            result_ui[
                "tts_text"
            ] = ai_feedback

            # tts_title은 build_mission_result_ui에서
            # "오늘의 Nudge 성공"으로 고정됨

            result_screen = {
                "user_mission_id": (
                    user_mission.id
                ),
                "mission_code": (
                    user_mission
                    .mission
                    .code
                ),
                "status": (
                    user_mission.status
                ),
                **result_ui,
            }

        return {
            "user_mission_id": (
                user_mission.id
            ),
            "mission_code": (
                user_mission.mission.code
            ),
            "verification_code": (
                user_mission
                .mission
                .verification_code
            ),
            "detected": (
                verification_result[
                    "detected"
                ]
            ),
            "expected_classes": (
                verification_result[
                    "expected_classes"
                ]
            ),
            "detected_objects": (
                verification_result[
                    "detected_objects"
                ]
            ),
            "stable_seconds": (
                verification_result[
                    "stable_seconds"
                ]
            ),
            "required_seconds": (
                verification_result[
                    "required_seconds"
                ]
            ),
            "progress_percent": (
                verification_result[
                    "progress_percent"
                ]
            ),
            "completed": (
                verification_result[
                    "completed"
                ]
            ),
            "status": user_mission.status,

            "should_stop_camera": (
                verification_result[
                    "completed"
                ]
            ),
            "result_screen": (
                result_screen
            ),
        }

    except (
        MissionVerificationValidationError
    ) as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(exc),
        ) from exc

    except MissionVerificationConfigError as exc:
        raise HTTPException(
            status_code=(
                status
                .HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=str(exc),
        ) from exc

    except (
        MissionVerificationInferenceError
    ) as exc:
        raise HTTPException(
            status_code=(
                status
                .HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=str(exc),
        ) from exc

    except SQLAlchemyError as exc:
        db.rollback()

        reset_verification_progress(
            user_mission_id
        )

        raise HTTPException(
            status_code=(
                status
                .HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "미션 완료 처리 중 "
                "오류가 발생했습니다."
            ),
        ) from exc

    finally:
        await image.close()

@router.post(
    "/{user_mission_id}"
    "/verification-attempt/reset",
    response_model=(
        MissionResultScreenResponse
    ),
)
def reset_user_mission_verification(
    user_mission_id: int,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    """
    한 번의 미션 인증 시도를 종료하고
    연속 탐지 진행 시간을 초기화한다.

    미션 자체는 실패 처리하지 않으며,
    IN_PROGRESS 상태를 유지하여
    사용자가 다시 시도할 수 있게 한다.
    """

    user_mission = (
        get_owned_user_mission(
            user_mission_id=(
                user_mission_id
            ),
            user_id=current_user.id,
            db=db,
        )
    )

    if (
        user_mission.status
        == "COMPLETED"
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "이미 완료된 미션입니다."
            ),
        )

    if (
        user_mission.status
        != "IN_PROGRESS"
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "진행 중인 미션만 "
                "인증을 다시 시도할 수 있습니다."
            ),
        )

    reset_verification_progress(
        user_mission.id
    )

    result_ui = (
        build_mission_result_ui(
            success=False
        )
    )

    return {
        "user_mission_id": (
            user_mission.id
        ),
        "mission_code": (
            user_mission.mission.code
        ),
        "status": (
            user_mission.status
        ),
        **result_ui,
    }