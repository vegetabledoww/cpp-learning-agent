from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from openai import OpenAI

from cpp_learning_agent.config import Settings
from cpp_learning_agent.prompts import SYSTEM_PROMPT


@dataclass(frozen=True)
class FunctionCall:
    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ModelTurn:
    output_items: list[Any]
    function_calls: list[FunctionCall]
    output_text: str


class ModelGateway(Protocol):
    def create_turn(self, input_items: list[Any], tools: list[dict[str, Any]]) -> ModelTurn:
        """Call the model once and normalize its output."""


class OpenAIResponsesGateway:
    def __init__(self, settings: Settings) -> None:
        client_kwargs: dict[str, Any] = {"api_key": settings.api_key}
        if settings.base_url:
            client_kwargs["base_url"] = settings.base_url
        self._client = OpenAI(**client_kwargs)
        self._settings = settings

    def create_turn(self, input_items: list[Any], tools: list[dict[str, Any]]) -> ModelTurn:
        request: dict[str, Any] = {
            "model": self._settings.model,
            "instructions": SYSTEM_PROMPT,
            "input": input_items,
            "tools": tools,
            "parallel_tool_calls": False,
            "store": False,
        }
        if self._settings.reasoning_effort:
            request["reasoning"] = {"effort": self._settings.reasoning_effort}

        response = self._client.responses.create(**request)
        calls: list[FunctionCall] = []
        for item in response.output:
            if getattr(item, "type", None) != "function_call":
                continue
            try:
                arguments = json.loads(item.arguments)
            except json.JSONDecodeError as exc:
                raise ValueError(f"工具 {item.name} 返回了无效 JSON 参数。") from exc
            if not isinstance(arguments, dict):
                raise ValueError(f"工具 {item.name} 的参数必须是 JSON 对象。")
            calls.append(
                FunctionCall(
                    call_id=item.call_id,
                    name=item.name,
                    arguments=arguments,
                )
            )

        return ModelTurn(
            output_items=list(response.output),
            function_calls=calls,
            output_text=response.output_text or "",
        )
