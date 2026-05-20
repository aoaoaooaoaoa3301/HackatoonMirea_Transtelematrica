import httpx

from app.config import settings


class BackendClient:
    def __init__(self):
        self.base_url = settings.BACKEND_URL.rstrip("/")
        self.headers = {"X-Telegram-Internal-Token": settings.TELEGRAM_INTERNAL_TOKEN}

    async def link(self, telegram_user, code: str) -> dict:
        payload = {
            "telegram_user_id": telegram_user.id,
            "username": telegram_user.username,
            "first_name": telegram_user.first_name,
            "last_name": telegram_user.last_name,
            "code": code,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(f"{self.base_url}/api/telegram/link/confirm", json=payload, headers=self.headers)
        return self._safe_json(response)

    async def command(self, telegram_user_id: int, message: str) -> dict:
        payload = {"telegram_user_id": telegram_user_id, "message": message}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{self.base_url}/api/telegram/command", json=payload, headers=self.headers)
        return self._safe_json(response)

    async def confirm_action(self, telegram_user_id: int, callback_data: str) -> dict:
        payload = {"telegram_user_id": telegram_user_id, "callback_data": callback_data}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{self.base_url}/api/telegram/confirm-action", json=payload, headers=self.headers)
        return self._safe_json(response)

    @staticmethod
    def _safe_json(response: httpx.Response) -> dict:
        try:
            data = response.json()
        except ValueError:
            data = {"detail": response.text}
        if response.status_code >= 400:
            detail = data.get("detail") if isinstance(data, dict) else None
            return {"text": f"Ошибка backend: {detail or response.status_code}", "buttons": []}
        return data
