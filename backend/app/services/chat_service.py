# chat_service.py
'''대화 내역 조회
Gemini 채팅 함수 호출
사용자/AI 메시지 DB 저장'''

def generate_temporary_ai_response(
    user_message: str,
) -> str:
    """
    실제 AI 서버 연결 전까지 사용하는 임시 응답 함수.

    이후 이 함수 내부를 AI 서버 호출 코드로 교체한다.
    """

    normalized_message = user_message.strip()

    if not normalized_message:
        return "말씀해주신 내용을 확인하지 못했어요."

    return (
        "말씀해주셔서 고마워요. "
        f"오늘은 '{normalized_message}'라고 느끼셨군요. "
        "조금 더 이야기해주실 수 있을까요?"
    )