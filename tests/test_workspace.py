from pathlib import Path

import pytest

from cpp_learning_agent.tools.workspace import WorkspaceError, WorkspaceTools


def make_workspace(tmp_path: Path) -> WorkspaceTools:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "demo.cpp").write_text(
        "#include <iostream>\nint main() {\n    return 0;\n}\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("demo project\n", encoding="utf-8")
    return WorkspaceTools(tmp_path)


def test_path_cannot_escape_workspace(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    with pytest.raises(WorkspaceError, match="超出"):
        workspace.read_file("../outside.txt", 1, 1)


def test_search_and_read_include_line_numbers(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    result = workspace.search_code("return", "*.cpp", 10)
    assert result["matches"] == [
        {"path": "src/demo.cpp", "line": 3, "column": 5, "text": "    return 0;"}
    ]

    content = workspace.read_file("src/demo.cpp", 2, 3)
    assert content["lines"] == [
        {"line": 2, "text": "int main() {"},
        {"line": 3, "text": "    return 0;"},
    ]


def test_list_files_is_sorted_and_ignores_build_directories(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    (tmp_path / "a.cpp").write_text("int a;\n", encoding="utf-8")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "generated.cpp").write_text("int generated;\n", encoding="utf-8")

    result = workspace.list_files(".", "*.cpp", 10)

    assert result["files"] == ["a.cpp", "src/demo.cpp"]


def test_replace_text_requires_exact_count(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    with pytest.raises(WorkspaceError, match="实际出现 1 次"):
        workspace.replace_text("src/demo.cpp", "return 0;", "return 1;", 2)

    result = workspace.replace_text("src/demo.cpp", "return 0;", "return 1;", 1)
    assert result["replacements"] == 1
    assert "return 1;" in (tmp_path / "src" / "demo.cpp").read_text(encoding="utf-8")
