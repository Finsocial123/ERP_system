import httpx

from app.core.config import settings


class TelegramNotConfiguredError(RuntimeError):
    pass


def _telegram_ready() -> bool:
    return bool(settings.TELEGRAM_BOT_TOKEN)


def _chunks(text: str, limit: int = 3900) -> list[str]:
    """Telegram supports 4096 chars; keep a small safety margin."""
    clean = text.strip()
    if not clean:
        return []
    return [clean[i : i + limit] for i in range(0, len(clean), limit)]


async def send_telegram_message(chat_id: str, text: str) -> int:
    """Send one or more plain-text Telegram messages. Returns sent count."""
    if not _telegram_ready():
        raise TelegramNotConfiguredError("Telegram bot is not configured. Add TELEGRAM_BOT_TOKEN in backend/.env")

    target = str(chat_id or settings.TELEGRAM_DEFAULT_CHAT_ID).strip()
    if not target:
        raise TelegramNotConfiguredError("Telegram chat id is missing. Provide chat_id or set TELEGRAM_DEFAULT_CHAT_ID in backend/.env")

    parts = _chunks(text)
    if not parts:
        return 0

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    sent = 0
    async with httpx.AsyncClient(timeout=12.0) as http:
        for part in parts:
            response = await http.post(
                url,
                json={
                    "chat_id": target,
                    "text": part,
                    "disable_web_page_preview": True,
                },
            )
            if response.status_code >= 400:
                detail = response.text[:300]
                raise RuntimeError(f"Telegram send failed: {detail}")
            sent += 1
    return sent
