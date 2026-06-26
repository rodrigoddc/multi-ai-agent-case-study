"""Infrastructure adapters — concrete implementations of application ports.

Provides LLM adapters, database adapters, and other infrastructure components.
"""

from src.app.infrastructure.adapters.llamacpp_adapter import LlamaCppAdapter
from src.app.infrastructure.adapters.llm_provider_router import LLMProviderRouter
from src.app.infrastructure.adapters.open_meteo_adapter import OpenMeteoAdapter
from src.app.infrastructure.adapters.openrouter_adapter import OpenRouterAdapter

__all__ = [
    "LlamaCppAdapter",
    "LLMProviderRouter",
    "OpenMeteoAdapter",
    "OpenRouterAdapter",
]
