def build_initial_greeting(
    user_name: str,
) -> str:
    """
    새 채팅 세션을 생성할 때 저장하는
    AI의 첫 인사말을 반환한다.
    """

    normalized_name = user_name.strip()

    if not normalized_name:
        return (
            "오늘은 어떠세요? "
            "편하게 이야기해 주세요."
        )

    return (
        f"{normalized_name}님, 오늘은 어떠세요? "
        "편하게 이야기해 주세요."
    )