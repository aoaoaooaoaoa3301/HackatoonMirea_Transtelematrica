from app.core.config import settings
from app.services.llm.base import LLMProvider, NullLLMProvider
from app.services.llm.ollama_provider import OllamaProvider
from app.services.llm.openai_compatible_provider import OpenAICompatibleProvider


def _docker_model_base_url(raw_url: str) -> str:
    base = raw_url.rstrip("/")
    return base if base.endswith("/v1") else f"{base}/v1"


def get_llm_provider() -> LLMProvider:
    provider = (settings.LLM_PROVIDER or "none").lower()

    if provider == "ollama":
        return OllamaProvider(
            base_url=settings.OLLAMA_URL,
            model=settings.OLLAMA_MODEL,
            timeout=settings.OLLAMA_TIMEOUT,
        )

    if provider == "openai_compatible":
        return OpenAICompatibleProvider(
            base_url=settings.OPENAI_COMPATIBLE_BASE_URL,
            api_key=settings.OPENAI_COMPATIBLE_API_KEY,
            model=settings.OPENAI_COMPATIBLE_MODEL,
            timeout=settings.OPENAI_COMPATIBLE_TIMEOUT,
            referer=settings.OPENAI_COMPATIBLE_REFERER,
            app_title=settings.OPENAI_COMPATIBLE_APP_TITLE,
            provider_order=settings.OPENAI_COMPATIBLE_PROVIDER_ORDER,
        )

    if provider == "docker_model":
        return OpenAICompatibleProvider(
            base_url=_docker_model_base_url(settings.DOCKER_MODEL_URL),
            api_key="",
            model=settings.OLLAMA_MODEL,
            timeout=settings.OLLAMA_TIMEOUT,
        )

    return NullLLMProvider()
