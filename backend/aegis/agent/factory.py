"""Select the LLM provider from settings.

`replay` (the default) and `mock` never require an API key, which is what
lets `docker compose up` and CI run the whole suite offline. `live` requires
`AEGIS_GEMINI_API_KEY` and fails loudly at startup if it is missing, rather
than silently degrading to a mode the operator did not ask for.
"""

from __future__ import annotations

from functools import lru_cache

from aegis.agent.provider import LLMProvider
from aegis.config import Settings, get_settings


def build_provider(settings: Settings) -> LLMProvider:
    if settings.llm_mode == "mock":
        from aegis.agent.mock import MockProvider

        return MockProvider()

    if settings.llm_mode == "replay":
        from aegis.agent.replay import ReplayProvider

        return ReplayProvider()

    if settings.llm_mode == "live":
        if not settings.gemini_api_key:
            raise RuntimeError("AEGIS_LLM_MODE=live requires AEGIS_GEMINI_API_KEY to be set.")
        from aegis.agent.gemini import GeminiProvider

        return GeminiProvider(api_key=settings.gemini_api_key)

    raise ValueError(f"Unknown AEGIS_LLM_MODE: {settings.llm_mode!r}")


@lru_cache
def get_provider() -> LLMProvider:
    return build_provider(get_settings())
