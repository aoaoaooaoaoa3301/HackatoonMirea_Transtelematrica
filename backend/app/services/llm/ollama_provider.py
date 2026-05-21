import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class OllamaProvider:
    def __init__(self, base_url: str, model: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def generate(
        self,
        prompt: str,
        system: str = "",
        json_mode: bool = False,
        temperature: float = 0.2,
    ) -> Optional[str]:
        body = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if json_mode:
            body["format"] = "json"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}/api/generate", json=body)
            if resp.status_code == 200:
                return (resp.json().get("response") or "").strip() or None
            logger.warning("Ollama returned status %d: %s", resp.status_code, resp.text[:500])
        except Exception as exc:
            logger.warning("Ollama call failed: %s", exc)
        return None
