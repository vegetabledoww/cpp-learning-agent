from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict):
    input_items: list[Any]
    pending_calls: list[dict[str, Any]]
    final_answer: str
    iterations: int
    trace: list[str]
    error: str
