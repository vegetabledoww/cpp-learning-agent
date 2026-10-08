from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from cpp_learning_agent.config import ConfigurationError, Settings
from cpp_learning_agent.graph import CppLearningAgent
from cpp_learning_agent.model import OpenAIResponsesGateway
from cpp_learning_agent.tools.registry import ToolDispatcher, ToolPolicy
from cpp_learning_agent.tools.workspace import WorkspaceError, WorkspaceTools


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cpp-agent",
        description="面向 C++ 学习仓库的安全代码智能体。",
    )
    parser.add_argument("request", nargs="?", help="要交给智能体的中文任务。")
    parser.add_argument("--workspace", required=True, help="允许访问的代码仓库根目录。")
    parser.add_argument("--model", help="覆盖 CPP_AGENT_MODEL。")
    parser.add_argument("--base-url", help="覆盖 OPENAI_BASE_URL。")
    parser.add_argument("--max-iterations", type=int, default=12, help="最大模型调用轮数，默认 12。")
    parser.add_argument("--allow-write", action="store_true", help="允许模型请求精确文本替换。")
    parser.add_argument("--allow-compile", action="store_true", help="允许模型请求 g++ 语法编译。")
    parser.add_argument("--yes", action="store_true", help="跳过已明确开放能力的逐次确认。")
    parser.add_argument("--verbose", action="store_true", help="显示工具调用轨迹。")
    parser.add_argument("--doctor", action="store_true", help="只检查本机环境，不调用模型。")
    return parser


def _confirm(description: str) -> bool:
    answer = input(f"允许智能体执行：{description}？[y/N] ").strip().lower()
    return answer in {"y", "yes"}


def _configure_utf8_console() -> None:
    # Windows 的默认代码页可能不是 UTF-8，显式设置后中文提示在终端和重定向中一致。
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    _configure_utf8_console()
    args = build_parser().parse_args(argv)
    try:
        workspace = WorkspaceTools(Path(args.workspace))
    except WorkspaceError as exc:
        print(f"工作区错误：{exc}")
        return 2

    if args.doctor:
        report = workspace.doctor()
        report["api_key_configured"] = bool(os.getenv("OPENAI_API_KEY"))
        report["model"] = args.model or os.getenv("CPP_AGENT_MODEL", "gpt-5.5")
        report["base_url_configured"] = bool(args.base_url or os.getenv("OPENAI_BASE_URL"))
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if not args.request:
        print("缺少任务描述；使用 --doctor 时可以不提供任务。")
        return 2

    try:
        settings = Settings.from_environment(
            model=args.model,
            base_url=args.base_url,
            max_iterations=args.max_iterations,
        )
    except ConfigurationError as exc:
        print(f"配置错误：{exc}")
        return 2

    policy = ToolPolicy(
        allow_write=args.allow_write,
        allow_compile=args.allow_compile,
        auto_approve=args.yes,
    )
    dispatcher = ToolDispatcher(workspace, policy, confirm=_confirm)
    model = OpenAIResponsesGateway(settings)
    agent = CppLearningAgent(model, dispatcher, max_iterations=settings.max_iterations)
    state = agent.run(args.request)

    if args.verbose and state["trace"]:
        print("\n===== 工具轨迹 =====")
        for event in state["trace"]:
            print(f"- {event}")

    print("\n===== 最终回答 =====")
    print(state["final_answer"])
    return 1 if state["error"] else 0
