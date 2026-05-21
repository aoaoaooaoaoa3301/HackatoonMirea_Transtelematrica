import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: int = 60,
        referer: str = "",
        app_title: str = "",
        provider_order: str = "",
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.referer = referer
        self.app_title = app_title
        self.provider_order = [item.strip() for item in provider_order.split(",") if item.strip()]

    async def generate(
        self,
        prompt: str,
        system: str = "",
        json_mode: bool = False,
        temperature: float = 0.2,
    ) -> Optional[str]:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if self.provider_order:
            payload["provider"] = {"order": self.provider_order, "allow_fallbacks": True}

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.referer:
            headers["HTTP-Referer"] = self.referer
        if self.app_title:
            headers["X-Title"] = self.app_title

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            if resp.status_code == 200:
                choices = resp.json().get("choices") or []
                if choices:
                    return (choices[0].get("message", {}).get("content") or "").strip() or None
            logger.warning("OpenAI-compatible provider returned status %d: %s", resp.status_code, resp.text[:500])
        except Exception as exc:
            logger.warning("OpenAI-compatible call failed: %s", exc)
        return None
