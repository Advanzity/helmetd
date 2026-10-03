"""Explicit provider selection; no automatic cross-provider fallback."""

import math
import os
from dataclasses import dataclass, field
from typing import Literal

Provider = Literal["openai", "google", "anthropic"]
PROVIDERS = {"openai": "OPENAI", "google": "GOOGLE", "anthropic": "ANTHROPIC"}


@dataclass(frozen=True)
class Settings:
    provider: Provider
    model: str
    api_key: str = field(repr=False)
    max_tokens: int = 512
    timeout: float = 60

    def __post_init__(self):
        if self.provider not in PROVIDERS:
            raise ValueError("Provider must be openai, google, or anthropic")
        if not self.model.strip() or not self.api_key.strip():
            raise ValueError("A model ID and API key are required for the selected provider")
        if not 1 <= self.max_tokens <= 8192:
            raise ValueError("HELMETD_LLM_MAX_TOKENS must be between 1 and 8192")
        if not math.isfinite(self.timeout) or self.timeout <= 0:
            raise ValueError("HELMETD_LLM_TIMEOUT_SECONDS must be a positive finite number")

    @classmethod
    def from_env(cls, provider: str | None = None, model: str | None = None):
        provider = provider or os.getenv("HELMETD_LLM_PROVIDER", "openai")
        if provider not in PROVIDERS:
            raise ValueError("HELMETD_LLM_PROVIDER must be openai, google, or anthropic")
        prefix = PROVIDERS[provider]
        selected_model = model or os.getenv(f"{prefix}_MODEL", "")
        key = os.getenv(f"{prefix}_API_KEY", "")
        if not selected_model.strip():
            raise ValueError(f"Set {prefix}_MODEL to a model ID available in your account")
        if not key.strip():
            raise ValueError(f"Set {prefix}_API_KEY in your environment or local .env")
        return cls(
            provider=provider,
            model=selected_model,
            api_key=key,
            max_tokens=int(os.getenv("HELMETD_LLM_MAX_TOKENS", "512")),
            timeout=float(os.getenv("HELMETD_LLM_TIMEOUT_SECONDS", "60")),
        )
