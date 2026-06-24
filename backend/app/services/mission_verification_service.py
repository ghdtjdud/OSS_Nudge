import os
import threading
import time
import cv2
import numpy as np

from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from ultralytics import YOLO


load_dotenv()


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)


YOLO_MODEL_PATH_VALUE = os.getenv(
    "YOLO_MODEL_PATH",
    "backend/app/weights/best.pt",
)

YOLO_MODEL_PATH = Path(
    YOLO_MODEL_PATH_VALUE
)

if not YOLO_MODEL_PATH.is_absolute():
    YOLO_MODEL_PATH = (
        PROJECT_ROOT
        / YOLO_MODEL_PATH
    )


YOLO_DEVICE = os.getenv(
    "YOLO_DEVICE",
    "cpu",
)

# 특정 클래스 설정이 없을 때 사용하는
# 최종 매칭 기본 confidence
YOLO_CONFIDENCE = float(
    os.getenv(
        "YOLO_CONFIDENCE",
        "0.45",
    )
)


# 모델에서 탐지 결과를 받아오기 위한
# 낮은 1차 confidence
#
# 이 값보다 낮으면 detected_objects에도 나오지 않는다.
YOLO_INFERENCE_CONFIDENCE = float(
    os.getenv(
        "YOLO_INFERENCE_CONFIDENCE",
        "0.15",
    )
)


# 클래스별 최종 성공 판정 confidence
YOLO_CLASS_CONFIDENCE = {
    # 컵은 현재 잘 인식되므로
    # 비교적 높은 기준을 유지
    "cup": float(
        os.getenv(
            "YOLO_CUP_CONFIDENCE",
            "0.55",
        )
    ),

    # 칫솔은 가늘고 작아서 기준을 낮춤
    "toothbrush": float(
        os.getenv(
            "YOLO_TOOTHBRUSH_CONFIDENCE",
            "0.25",
        )
    ),

    # 밥그릇
    "bowl": float(
        os.getenv(
            "YOLO_BOWL_CONFIDENCE",
            "0.30",
        )
    ),

    # 숟가락·젓가락 등은 작고 가늘기 때문에
    # 가장 낮은 기준 적용
    "utensil": float(
        os.getenv(
            "YOLO_UTENSIL_CONFIDENCE",
            "0.20",
        )
    ),

    # 약은 오탐 위험이 있으므로
    # 너무 낮추지 않음
    "pill": float(
        os.getenv(
            "YOLO_PILL_CONFIDENCE",
            "0.45",
        )
    ),
}

YOLO_IMAGE_SIZE = int(
    os.getenv(
        "YOLO_IMAGE_SIZE",
        "640",
    )
)

YOLO_REQUIRED_SECONDS = float(
    os.getenv(
        "YOLO_REQUIRED_SECONDS",
        "3.0",
    )
)

YOLO_DETECTION_GAP_TOLERANCE = float(
    os.getenv(
        "YOLO_DETECTION_GAP_TOLERANCE",
        "2.5",
    )
)

YOLO_MAX_IMAGE_MB = int(
    os.getenv(
        "YOLO_MAX_IMAGE_MB",
        "5",
    )
)

MAX_IMAGE_BYTES = (
    YOLO_MAX_IMAGE_MB
    * 1024
    * 1024
)

VERIFICATION_CLASS_MAP = {
    # 물 마시기
    "WATER_CONTAINER": {
        "cup",
    },

    # 양치하기
    "TOOTHBRUSH": {
        "toothbrush",
    },

    # 식사하기
    "FOOD": {
        "bowl",
        "utensil",
    },

    # 약 복용하기
    "MEDICATION_PACKAGE": {
        "pill",
    },
}


class MissionVerificationError(
    Exception
):
    pass


class MissionVerificationValidationError(
    MissionVerificationError
):
    pass


class MissionVerificationConfigError(
    MissionVerificationError
):
    pass


class MissionVerificationInferenceError(
    MissionVerificationError
):
    pass


@dataclass
class VerificationProgress:
    started_at: float
    last_detected_at: float


_yolo_model: YOLO | None = None

_model_load_lock = threading.Lock()
_inference_lock = threading.Lock()
_progress_lock = threading.Lock()

_verification_progress: dict[
    int,
    VerificationProgress,
] = {}


def normalize_class_name(
    value: str,
) -> str:
    return (
        value
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )


def get_expected_classes(
    verification_code: str,
) -> set[str]:
    expected_classes = (
        VERIFICATION_CLASS_MAP.get(
            verification_code
        )
    )

    if not expected_classes:
        raise (
            MissionVerificationConfigError(
                "지원하지 않는 인증 코드입니다: "
                f"{verification_code}"
            )
        )

    return {
        normalize_class_name(
            class_name
        )
        for class_name
        in expected_classes
    }


def get_yolo_model() -> YOLO:
    """
    YOLO 모델을 최초 한 번만 로드하고
    이후 요청에서는 재사용한다.
    """

    global _yolo_model

    if _yolo_model is not None:
        return _yolo_model

    with _model_load_lock:
        if _yolo_model is not None:
            return _yolo_model

        if not YOLO_MODEL_PATH.exists():
            raise (
                MissionVerificationConfigError(
                    "YOLO 모델 파일을 "
                    "찾을 수 없습니다: "
                    f"{YOLO_MODEL_PATH}"
                )
            )

        try:
            _yolo_model = YOLO(
                str(YOLO_MODEL_PATH)
            )

            print(
                "[YOLO] model loaded:",
                YOLO_MODEL_PATH,
            )

            print(
                "[YOLO] classes:",
                _yolo_model.names,
            )

        except Exception as exc:
            raise (
                MissionVerificationConfigError(
                    "YOLO 모델 로딩 실패: "
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )
            ) from exc

    return _yolo_model


def decode_image(
    image_bytes: bytes,
) -> np.ndarray:
    if not image_bytes:
        raise MissionVerificationValidationError(
            "전달된 이미지가 없습니다."
        )

    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise MissionVerificationValidationError(
            f"이미지는 {YOLO_MAX_IMAGE_MB}MB 이하여야 합니다."
        )

    try:
        image_array = np.frombuffer(
            image_bytes,
            dtype=np.uint8,
        )

        image = cv2.imdecode(
            image_array,
            cv2.IMREAD_COLOR,
        )

        if image is None:
            raise MissionVerificationValidationError(
                "올바른 이미지 파일이 아닙니다."
            )

        return image

    except MissionVerificationValidationError:
        raise

    except Exception as exc:
        raise MissionVerificationValidationError(
            "이미지를 읽지 못했습니다: "
            f"{type(exc).__name__}: {exc}"
        ) from exc


def run_detection(
    *,
    image: np.ndarray,
    verification_code: str,
) -> dict:
    model = get_yolo_model()

    expected_classes = (
        get_expected_classes(
            verification_code
        )
    )

    try:
        # 한 프로세스에서 여러 YOLO 추론이
        # 동시에 CPU를 독점하지 않도록 제한한다.
        with _inference_lock:
            prediction_results = (
                model.predict(
                    source=image,
                    conf=YOLO_INFERENCE_CONFIDENCE,
                    imgsz=YOLO_IMAGE_SIZE,
                    device=YOLO_DEVICE,
                    verbose=False,
                )
            )

    except Exception as exc:
        raise (
            MissionVerificationInferenceError(
                "YOLO 객체 탐지 실패: "
                f"{type(exc).__name__}: "
                f"{exc}"
            )
        ) from exc

    if not prediction_results:
        return {
            "detected": False,
            "expected_classes": sorted(
                expected_classes
            ),
            "detected_objects": [],
        }

    result = prediction_results[0]
    boxes = result.boxes

    if boxes is None:
        return {
            "detected": False,
            "expected_classes": sorted(
                expected_classes
            ),
            "detected_objects": [],
        }

    class_ids = (
        boxes.cls
        .int()
        .cpu()
        .tolist()
    )

    confidence_values = (
        boxes.conf
        .cpu()
        .tolist()
    )

    coordinate_values = (
        boxes.xyxy
        .cpu()
        .tolist()
    )

    model_names = result.names

    detected_objects = []
    matched = False

    for (
        class_id,
        confidence,
        coordinates,
    ) in zip(
        class_ids,
        confidence_values,
        coordinate_values,
    ):
        raw_class_name = str(
            model_names[class_id]
        )

        normalized_class_name = (
            normalize_class_name(
                raw_class_name
            )
        )

        confidence_value = float(
            confidence
        )

        required_confidence = (
            YOLO_CLASS_CONFIDENCE.get(
                normalized_class_name,
                YOLO_CONFIDENCE,
            )
        )

        is_expected = (
            normalized_class_name
            in expected_classes
            and confidence_value
            >= required_confidence
        )

        if is_expected:
            matched = True

        detected_objects.append({
            "class_id": class_id,
            "class_name": raw_class_name,
            "confidence": round(
                confidence_value,
                4,
            ),
            "matched": is_expected,
            "bounding_box": {
                "x1": round(
                    float(coordinates[0]),
                    2,
                ),
                "y1": round(
                    float(coordinates[1]),
                    2,
                ),
                "x2": round(
                    float(coordinates[2]),
                    2,
                ),
                "y2": round(
                    float(coordinates[3]),
                    2,
                ),
            },
        })

    return {
        "detected": matched,
        "expected_classes": sorted(
            expected_classes
        ),
        "detected_objects": (
            detected_objects
        ),
    }


def update_verification_progress(
    *,
    user_mission_id: int,
    detected: bool,
) -> tuple[float, bool]:
    """
    대상 객체가 안정적으로 탐지된 시간을 계산한다.

    프론트가 약 0.5초 간격으로 요청한다고 가정하며,
    잠깐 한 프레임을 놓친 경우에는
    gap tolerance 범위 안에서 진행 시간을 유지한다.
    """

    current_time = time.monotonic()

    with _progress_lock:
        progress = (
            _verification_progress.get(
                user_mission_id
            )
        )

        if detected:
            if (
                progress is None
                or (
                    current_time
                    - progress.last_detected_at
                    > YOLO_DETECTION_GAP_TOLERANCE
                )
            ):
                progress = VerificationProgress(
                    started_at=current_time,
                    last_detected_at=(
                        current_time
                    ),
                )

                _verification_progress[
                    user_mission_id
                ] = progress

            else:
                progress.last_detected_at = (
                    current_time
                )

            stable_seconds = (
                current_time
                - progress.started_at
            )

        else:
            if progress is None:
                stable_seconds = 0.0

            elif (
                current_time
                - progress.last_detected_at
                <= YOLO_DETECTION_GAP_TOLERANCE
            ):
                # 한 번 정도의 순간적인 미탐지는
                # 허용하되 완료 판정은 하지 않는다.
                stable_seconds = (
                    current_time
                    - progress.started_at
                )

            else:
                _verification_progress.pop(
                    user_mission_id,
                    None,
                )

                stable_seconds = 0.0

        completed = (
            detected
            and stable_seconds
            >= YOLO_REQUIRED_SECONDS
        )

        if completed:
            _verification_progress.pop(
                user_mission_id,
                None,
            )

    return (
        min(
            stable_seconds,
            YOLO_REQUIRED_SECONDS,
        ),
        completed,
    )


def reset_verification_progress(
    user_mission_id: int,
) -> None:
    with _progress_lock:
        _verification_progress.pop(
            user_mission_id,
            None,
        )


def verify_mission_frame(
    *,
    user_mission_id: int,
    verification_code: str,
    image_bytes: bytes,
) -> dict:
    image = decode_image(
        image_bytes
    )

    detection_result = run_detection(
        image=image,
        verification_code=(
            verification_code
        ),
    )

    (
        stable_seconds,
        completed,
    ) = update_verification_progress(
        user_mission_id=(
            user_mission_id
        ),
        detected=(
            detection_result[
                "detected"
            ]
        ),
    )

    progress_percent = int(
        min(
            100,
            (
                stable_seconds
                / YOLO_REQUIRED_SECONDS
            )
            * 100,
        )
    )

    return {
        **detection_result,
        "stable_seconds": round(
            stable_seconds,
            2,
        ),
        "required_seconds": (
            YOLO_REQUIRED_SECONDS
        ),
        "progress_percent": (
            progress_percent
        ),
        "completed": completed,
    }