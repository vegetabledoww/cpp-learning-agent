from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from cpp_learning_agent.model import ModelGateway
from cpp_learning_agent.state import AgentState
from cpp_learning_agent.tools.registry import ToolDispatcher


class CppLearningAgent:
    def __init__(
        self,
        model: ModelGateway,
        tools: ToolDispatcher,
        *,
        max_iterations: int = 12,
    ) -> None:
        self._model = model
        self._tools = tools
        self._max_iterations = max_iterations
        self._graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(AgentState)
        builder.add_node("model", self._model_node)
        builder.add_node("tools", self._tools_node)
        builder.add_edge(START, "model")
        builder.add_conditional_edges(
            "model",
            self._route_after_model,
            {"tools": "tools", "end": END},
        )
        builder.add_edge("tools", "model")
        return builder.compile()

    def _model_node(self, state: AgentState) -> dict[str, Any]:
        if state["iterations"] >= self._max_iterations:
            return {
                "pending_calls": [],
                "final_answer": "已达到最大工具调用轮数，任务停止。请缩小问题范围后重试。",
                "error": "达到最大迭代次数",
            }

        try:
            turn = self._model.create_turn(state["input_items"], self._tools.definitions)
        except Exception as exc:  # API and provider errors are reported to the CLI.
            return {
                "pending_calls": [],
                "final_answer": f"模型调用失败：{exc}",
                "error": str(exc),
                "iterations": state["iterations"] + 1,
            }

        pending_calls = [
            {
                "call_id": call.call_id,
                "name": call.name,
                "arguments": call.arguments,
            }
            for call in turn.function_calls
        ]
        trace = list(state["trace"])
        if pending_calls:
            trace.extend(f"模型请求工具：{call['name']}" for call in pending_calls)

        final_answer = "" if pending_calls else turn.output_text.strip()
        if not pending_calls and not final_answer:
            final_answer = "模型没有返回文本，也没有请求工具。"

        return {
            "input_items": [*state["input_items"], *turn.output_items],
            "pending_calls": pending_calls,
            "final_answer": final_answer,
            "iterations": state["iterations"] + 1,
            "trace": trace,
            "error": "",
        }

    def _tools_node(self, state: AgentState) -> dict[str, Any]:
        input_items = list(state["input_items"])
        trace = list(state["trace"])

        for call in state["pending_calls"]:
            output = self._tools.execute(call["name"], call["arguments"])
            input_items.append(
                {
                    "type": "function_call_output",
                    "call_id": call["call_id"],
                    "output": output,
                }
            )
            trace.append(f"工具完成：{call['name']}")

        return {
            "input_items": input_items,
            "pending_calls": [],
            "trace": trace,
        }

    @staticmethod
    def _route_after_model(state: AgentState) -> Literal["tools", "end"]:
        return "tools" if state["pending_calls"] else "end"

    def run(self, request: str) -> AgentState:
        initial: AgentState = {
            "input_items": [{"role": "user", "content": request}],
            "pending_calls": [],
            "final_answer": "",
            "iterations": 0,
            "trace": [],
            "error": "",
        }
        return self._graph.invoke(initial)
