from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigurationError(ValueError):
    """Raised when required runtime configuration is missing."""


@dataclass(frozen=True)
class Settings:
    api_key: str
    model: str
    base_url: str | None = None
    reasoning_effort: str | None = None
    max_iterations: int = 12

    @classmethod
    def from_environment(
        cls,
        *,
        model: str | None = None,
        base_url: str | None = None,
        max_iterations: int = 12,
    ) -> "Settings":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ConfigurationError("缺少环境变量 OPENAI_API_KEY。")

        selected_model = (model or os.getenv("CPP_AGENT_MODEL", "gpt-5.5")).strip()
        if not selected_model:
            raise ConfigurationError("模型名称不能为空。")

        selected_base_url = base_url or os.getenv("OPENAI_BASE_URL")
        if selected_base_url:
            selected_base_url = selected_base_url.strip().rstrip("/")

        reasoning_effort = os.getenv("CPP_AGENT_REASONING_EFFORT", "").strip() or None
        if max_iterations < 1 or max_iterations > 50:
            raise ConfigurationError("max_iterations 必须在 1 到 50 之间。")

        return cls(
            api_key=api_key,
            model=selected_model,
            base_url=selected_base_url,
            reasoning_effort=reasoning_effort,
            max_iterations=max_iterations,
        )
