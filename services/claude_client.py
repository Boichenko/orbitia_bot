"""Вызов Claude API для интерпретации соляра."""

import os

from anthropic import AsyncAnthropic

_client: AsyncAnthropic | None = None

DEFAULT_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

MAX_TOKENS = 32000


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY не задан в .env")
        _client = AsyncAnthropic(api_key=api_key)
    return _client


async def interpret_solar_chart(prompt: str, model: str | None = None) -> tuple[str, str]:
    """
    Запрашивает разбор у Клода (через стриминг — иначе при таком объёме ответа
    запрос может упереться в таймаут). Возвращает (текст, stop_reason).
    stop_reason == "max_tokens" значит ответ обрезался по лимиту — это НЕ ошибка,
    Anthropic не считает это исключением, поэтому проверяем явно.
    """
    client = _get_client()
    async with client.messages.stream(
        model=model or DEFAULT_MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        async for _ in stream.text_stream:
            pass
        final_message = await stream.get_final_message()

    text = "".join(block.text for block in final_message.content if block.type == "text")
    return text, final_message.stop_reason
