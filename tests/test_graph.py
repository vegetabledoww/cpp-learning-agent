from pathlib import Path
from typing import Any

from cpp_learning_agent.graph import CppLearningAgent
from cpp_learning_agent.model import FunctionCall, ModelTurn
from cpp_learning_agent.tools.registry import ToolDispatcher, ToolPolicy
from cpp_learning_agent.tools.workspace import WorkspaceTools


class FakeModel:
    def __init__(self) -> None:
        self.turns = 0
        self.received_inputs: list[list[Any]] = []

    def create_turn(self, input_items: list[Any], tools: list[dict[str, Any]]) -> ModelTurn:
        self.received_inputs.append(list(input_items))
        self.turns += 1
        if self.turns == 1:
            return ModelTurn(
                output_items=[
                    {
                        "type": "function_call",
                        "call_id": "call_1",
                        "name": "search_code",
                        "arguments": '{"query":"main","file_pattern":"*.cpp","max_results":10}',
                    }
                ],
                function_calls=[
                    FunctionCall(
                        call_id="call_1",
                        name="search_code",
                        arguments={"query": "main", "file_pattern": "*.cpp", "max_results": 10},
                    )
                ],
                output_text="",
            )
        return ModelTurn(
            output_items=[{"type": "message", "content": "找到 main。"}],
            function_calls=[],
            output_text="找到 main，位于 demo.cpp:1。",
        )


def test_graph_executes_tool_then_returns_final_answer(tmp_path: Path) -> None:
    (tmp_path / "demo.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")
    model = FakeModel()
    dispatcher = ToolDispatcher(WorkspaceTools(tmp_path), ToolPolicy())
    agent = CppLearningAgent(model, dispatcher, max_iterations=4)

    result = agent.run("main 在哪里？")

    assert result["final_answer"] == "找到 main，位于 demo.cpp:1。"
    assert model.turns == 2
    assert any(item.get("type") == "function_call_output" for item in model.received_inputs[1])
    assert result["trace"] == ["模型请求工具：search_code", "工具完成：search_code"]
