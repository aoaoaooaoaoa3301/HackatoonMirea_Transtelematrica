from typing import Optional, Protocol


class LLMProvider(Protocol):
    async def generate(
        self,
        prompt: str,
        system: str = "",
        json_mode: bool = False,
        temperature: float = 0.2,
    ) -> Optional[str]:
        ...


class NullLLMProvider:
    async def generate(
        self,
        prompt: str,
        system: str = "",
        json_mode: bool = False,
        temperature: float = 0.2,
    ) -> Optional[str]:
        return None
