import os
import tempfile
import threading
from pathlib import Path

from dotenv import load_dotenv
from faster_whisper import WhisperModel


load_dotenv()


WHISPER_MODEL_SIZE = os.getenv(
    "WHISPER_MODEL_SIZE",
    "base",
)

WHISPER_DEVICE = os.getenv(
    "WHISPER_DEVICE",
    "cpu",
)

WHISPER_COMPUTE_TYPE = os.getenv(
    "WHISPER_COMPUTE_TYPE",
    "int8",
)

WHISPER_CPU_THREADS = int(
    os.getenv(
        "WHISPER_CPU_THREADS",
        "4",
    )
)

WHISPER_NUM_WORKERS = int(
    os.getenv(
        "WHISPER_NUM_WORKERS",
        "1",
    )
)

WHISPER_LANGUAGE = os.getenv(
    "WHISPER_LANGUAGE",
    "ko",
)

WHISPER_MAX_AUDIO_MB = int(
    os.getenv(
        "WHISPER_MAX_AUDIO_MB",
        "10",
    )
)

MAX_AUDIO_BYTES = (
    WHISPER_MAX_AUDIO_MB
    * 1024
    * 1024
)


ALLOWED_AUDIO_EXTENSIONS = {
    ".webm",
    ".wav",
    ".mp3",
    ".mp4",
    ".m4a",
    ".mpeg",
    ".mpga",
    ".ogg",
}


class SpeechValidationError(Exception):
    """
    음성 파일 자체가 잘못된 경우.
    """


class SpeechServiceError(Exception):
    """
    Whisper 모델 로딩 또는
    음성 인식 처리에 실패한 경우.
    """


_whisper_model: WhisperModel | None = None

# 여러 요청이 동시에 모델을 생성하지 않도록 보호
_model_load_lock = threading.Lock()

# CPU에서 여러 음성 전사가 동시에 실행되어
# 서버 자원을 독점하지 않도록 보호
_transcription_lock = threading.Lock()


def get_whisper_model() -> WhisperModel:
    """
    Whisper 모델을 최초 한 번만 로드하고
    이후 요청에서는 재사용한다.
    """

    global _whisper_model

    if _whisper_model is not None:
        return _whisper_model

    with _model_load_lock:
        if _whisper_model is None:
            try:
                _whisper_model = WhisperModel(
                    WHISPER_MODEL_SIZE,
                    device=WHISPER_DEVICE,
                    compute_type=(
                        WHISPER_COMPUTE_TYPE
                    ),
                    cpu_threads=(
                        WHISPER_CPU_THREADS
                    ),
                    num_workers=(
                        WHISPER_NUM_WORKERS
                    ),
                )

            except Exception as exc:
                raise SpeechServiceError(
                    "Whisper 모델을 "
                    "불러오지 못했습니다: "
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ) from exc

    return _whisper_model


def validate_audio(
    *,
    audio_bytes: bytes,
    filename: str,
) -> str:
    """
    음성 데이터와 확장자를 검사하고
    임시 파일에 사용할 확장자를 반환한다.
    """

    if not audio_bytes:
        raise SpeechValidationError(
            "전달된 음성 데이터가 없습니다."
        )

    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise SpeechValidationError(
            "음성 데이터는 "
            f"{WHISPER_MAX_AUDIO_MB}MB "
            "이하여야 합니다."
        )

    normalized_filename = (
        filename.strip()
        if filename
        else "recording.webm"
    )

    extension = (
        Path(normalized_filename)
        .suffix
        .lower()
    )

    if not extension:
        extension = ".webm"

    if (
        extension
        not in ALLOWED_AUDIO_EXTENSIONS
    ):
        raise SpeechValidationError(
            "지원하지 않는 음성 형식입니다. "
            "webm, wav, mp3, mp4, m4a, "
            "mpeg, ogg 형식을 사용해주세요."
        )

    return extension


def transcribe_audio(
    *,
    audio_bytes: bytes,
    filename: str,
) -> str:
    """
    음성 데이터를 로컬 faster-whisper로
    한국어 텍스트로 변환한다.
    """

    extension = validate_audio(
        audio_bytes=audio_bytes,
        filename=filename,
    )

    temp_path: str | None = None

    try:
        # Whisper가 안정적으로 읽을 수 있도록
        # 음성을 임시 파일로 저장한다.
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=extension,
            delete=False,
        ) as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name

        model = get_whisper_model()

        # segments는 generator이므로
        # 반복문이 끝날 때까지 lock이 유지되어야 한다.
        with _transcription_lock:
            segments, _ = model.transcribe(
                temp_path,
                language=WHISPER_LANGUAGE,
                task="transcribe",
                beam_size=5,
                vad_filter=True,
                condition_on_previous_text=False,
                initial_prompt=(
                    "한국어 정서지원 채팅입니다. "
                    "수면, 식사, 복약, 미션, "
                    "기분과 관련된 표현을 "
                    "자연스럽고 정확하게 "
                    "전사해주세요."
                ),
            )

            transcript_parts = [
                segment.text.strip()
                for segment in segments
                if segment.text.strip()
            ]

        transcript = " ".join(
            transcript_parts
        ).strip()

        if not transcript:
            raise SpeechValidationError(
                "음성에서 텍스트를 "
                "인식하지 못했습니다."
            )

        return transcript

    except SpeechValidationError:
        raise

    except SpeechServiceError:
        raise

    except Exception as exc:
        raise SpeechServiceError(
            "음성 인식 처리에 실패했습니다: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    finally:
        if (
            temp_path is not None
            and os.path.exists(temp_path)
        ):
            try:
                os.remove(temp_path)

            except OSError:
                pass