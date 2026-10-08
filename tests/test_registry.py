import json
from pathlib import Path

from cpp_learning_agent.tools.registry import ToolDispatcher, ToolPolicy, build_tool_definitions
from cpp_learning_agent.tools.workspace import WorkspaceTools


def tool_names(policy: ToolPolicy) -> set[str]:
    return {tool["name"] for tool in build_tool_definitions(policy)}


def test_sensitive_tools_are_hidden_by_default() -> None:
    names = tool_names(ToolPolicy())
    assert "compile_cpp" not in names
    assert "replace_text" not in names


def test_sensitive_tools_require_explicit_policy() -> None:
    names = tool_names(ToolPolicy(allow_write=True, allow_compile=True))
    assert {"compile_cpp", "replace_text"}.issubset(names)


def test_denied_write_does_not_change_file(tmp_path: Path) -> None:
    source = tmp_path / "demo.cpp"
    source.write_text("int value = 1;\n", encoding="utf-8")
    dispatcher = ToolDispatcher(
        WorkspaceTools(tmp_path),
        ToolPolicy(allow_write=True),
        confirm=lambda _: False,
    )
    output = dispatcher.execute(
        "replace_text",
        {"path": "demo.cpp", "old_text": "1", "new_text": "2", "expected_count": 1},
    )
    assert json.loads(output)["ok"] is False
    assert source.read_text(encoding="utf-8") == "int value = 1;\n"
