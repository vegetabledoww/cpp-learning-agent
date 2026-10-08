from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any, Callable

from cpp_learning_agent.tools.workspace import WorkspaceError, WorkspaceTools


@dataclass(frozen=True)
class ToolPolicy:
    allow_write: bool = False
    allow_compile: bool = False
    auto_approve: bool = False


def _function_tool(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str],
) -> dict[str, Any]:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
        "strict": True,
    }


def build_tool_definitions(policy: ToolPolicy) -> list[dict[str, Any]]:
    definitions = [
        _function_tool(
            "list_files",
            "列出工作区指定目录下的文件。relative_path 使用相对路径，根目录写点号。",
            {
                "relative_path": {"type": "string"},
                "pattern": {"type": "string", "description": "文件 glob，例如 *.cpp 或 *。"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 500},
            },
            ["relative_path", "pattern", "max_results"],
        ),
        _function_tool(
            "search_code",
            "在工作区文本文件中进行不区分大小写的字面量搜索。",
            {
                "query": {"type": "string"},
                "file_pattern": {"type": "string", "description": "例如 *.cpp、*.md 或 *。"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 200},
            },
            ["query", "file_pattern", "max_results"],
        ),
        _function_tool(
            "read_file",
            "按行读取工作区中的文本文件，单次最多 400 行。",
            {
                "path": {"type": "string"},
                "start_line": {"type": "integer", "minimum": 1},
                "end_line": {"type": "integer", "minimum": 1},
            },
            ["path", "start_line", "end_line"],
        ),
        _function_tool("git_status", "读取当前工作区的 Git 简短状态。", {}, []),
        _function_tool(
            "git_diff",
            "读取未暂存 Git diff。path 为 null 时读取整个工作区。",
            {"path": {"type": ["string", "null"]}},
            ["path"],
        ),
    ]

    if policy.allow_compile:
        definitions.append(
            _function_tool(
                "compile_cpp",
                "使用 C++17、Wall、Wextra、pedantic 和 fsyntax-only 编译一个 cpp 文件。",
                {"path": {"type": "string"}},
                ["path"],
            )
        )
    if policy.allow_write:
        definitions.append(
            _function_tool(
                "replace_text",
                "在已有文本文件中执行精确替换。出现次数不符时不会修改。",
                {
                    "path": {"type": "string"},
                    "old_text": {"type": "string"},
                    "new_text": {"type": "string"},
                    "expected_count": {"type": "integer", "minimum": 1},
                },
                ["path", "old_text", "new_text", "expected_count"],
            )
        )
    return definitions


class ToolDispatcher:
    def __init__(
        self,
        workspace: WorkspaceTools,
        policy: ToolPolicy,
        confirm: Callable[[str], bool] | None = None,
    ) -> None:
        self._workspace = workspace
        self._policy = policy
        self._confirm = confirm or (lambda _: False)
        self.definitions = build_tool_definitions(policy)

    def _approved(self, description: str) -> bool:
        return self._policy.auto_approve or self._confirm(description)

    def execute(self, name: str, arguments: dict[str, Any]) -> str:
        try:
            if name == "list_files":
                result = self._workspace.list_files(**arguments)
            elif name == "search_code":
                result = self._workspace.search_code(**arguments)
            elif name == "read_file":
                result = self._workspace.read_file(**arguments)
            elif name == "git_status":
                result = self._workspace.git_status()
            elif name == "git_diff":
                result = self._workspace.git_diff(**arguments)
            elif name == "compile_cpp":
                if not self._policy.allow_compile:
                    raise WorkspaceError("当前会话没有开启编译权限。")
                if not self._approved(f"编译 {arguments.get('path', '')}"):
                    raise WorkspaceError("用户拒绝了本次编译。")
                result = self._workspace.compile_cpp(**arguments)
            elif name == "replace_text":
                if not self._policy.allow_write:
                    raise WorkspaceError("当前会话没有开启写入权限。")
                if not self._approved(f"修改 {arguments.get('path', '')}"):
                    raise WorkspaceError("用户拒绝了本次修改。")
                result = self._workspace.replace_text(**arguments)
            else:
                raise WorkspaceError(f"未知工具：{name}")
        except (WorkspaceError, TypeError, subprocess.SubprocessError) as exc:
            result = {"ok": False, "error": str(exc)}
        except Exception as exc:  # Keep tool failures inside the agent loop.
            result = {"ok": False, "error": f"工具执行异常：{exc}"}
        return json.dumps(result, ensure_ascii=False)
