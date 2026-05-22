import httpx

from app.config import settings

# AI/free-text calls can be slow (LLM round-trip), so allow a generous read
# timeout but keep connect short. On any network failure we degrade to a
# friendly message instead of letting the handler raise.
COMMAND_TIMEOUT = httpx.Timeout(90.0, connect=10.0)
LINK_TIMEOUT = httpx.Timeout(20.0, connect=10.0)
ACTION_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

_NETWORK_ERROR = {
    "text": (
        "⏳ Сервис временно не отвечает (таймаут или сетевая ошибка). "
        "Попробуйте ещё раз через минуту."
    ),
    "buttons": [],
}


class BackendClient:
    def __init__(self):
        self.base_url = settings.BACKEND_URL.rstrip("/")
        self.headers = {"X-Telegram-Internal-Token": settings.TELEGRAM_INTERNAL_TOKEN}

    async def _post(self, path: str, payload: dict, timeout: httpx.Timeout) -> dict:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(f"{self.base_url}{path}", json=payload, headers=self.headers)
        except (httpx.TimeoutException, httpx.TransportError):
            return dict(_NETWORK_ERROR)
        return self._safe_json(response)

    async def link(self, telegram_user, code: str) -> dict:
        payload = {
            "telegram_user_id": telegram_user.id,
            "username": telegram_user.username,
            "first_name": telegram_user.first_name,
            "last_name": telegram_user.last_name,
            "code": code,
        }
        return await self._post("/api/telegram/link/confirm", payload, LINK_TIMEOUT)

    async def command(self, telegram_user_id: int, message: str) -> dict:
        payload = {"telegram_user_id": telegram_user_id, "message": message}
        return await self._post("/api/telegram/command", payload, COMMAND_TIMEOUT)

    async def confirm_action(self, telegram_user_id: int, callback_data: str) -> dict:
        payload = {"telegram_user_id": telegram_user_id, "callback_data": callback_data}
        return await self._post("/api/telegram/confirm-action", payload, ACTION_TIMEOUT)

    @staticmethod
    def _safe_json(response: httpx.Response) -> dict:
        try:
            data = response.json()
        except ValueError:
            data = {"detail": response.text}
        if response.status_code >= 400:
            detail = data.get("detail") if isinstance(data, dict) else None
            return {"text": f"⚠️ Ошибка сервиса: {detail or response.status_code}", "buttons": []}
        return data
