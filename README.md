# C++ Learning Agent

一个独立的、面向 C++ 学习仓库的命令行智能体。它使用 LangGraph 管理“模型调用 -> 本地工具 -> 模型继续判断”的循环，通过 OpenAI Responses API 的 function calling 访问代码仓库。

本仓库与 `D:\Code\C++code` 完全分离。目标代码仓只通过 `--workspace` 参数访问，默认只读。

## 第一版能力

- 列出指定工作区中的源码和文档；
- 按关键词搜索代码，不依赖系统必须安装 `rg`；
- 按行读取文件，并在回答中引用 `相对路径:行号`；
- 查看 Git 状态和 diff；
- 可选执行 `g++ -fsyntax-only` 严格语法编译；
- 可选对已有文件执行“精确文本替换”；
- 编译和写文件默认关闭，开启后仍会逐次询问确认；
- 所有路径都必须解析到工作区内部，拒绝 `..` 越界和绝对路径逃逸。

当前版本不执行任意 Shell 命令、不删除文件、不提交或 push，也不实现未经确认的自动修改。

## 安装

```powershell
cd D:\Code\cpp-learning-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

设置环境变量。不要把真实密钥写入源码或提交到 Git：

```powershell
$env:OPENAI_API_KEY = "你的密钥"
$env:CPP_AGENT_MODEL = "你的模型名"

# 使用兼容服务时再设置；该服务必须支持 Responses API 和 function calling。
$env:OPENAI_BASE_URL = "服务地址"
```

也可以参考 [.env.example](./.env.example)，但本项目不会自动读取 `.env`，避免不明确地加载密钥。

## 使用

先做无需 API 的环境检查：

```powershell
cpp-agent --workspace D:\Code\C++code --doctor
```

默认只读分析：

```powershell
cpp-agent --workspace D:\Code\C++code "检查 05_design_problems 中资源分发题的正确性，先不考虑性能"
```

显示 Agent 实际调用过的工具：

```powershell
cpp-agent --workspace D:\Code\C++code --verbose "解释 lower_bound 在资源分发题中的作用"
```

允许请求严格语法编译：

```powershell
cpp-agent --workspace D:\Code\C++code --allow-compile "编译并检查资源分发题"
```

允许修改已有文件：

```powershell
cpp-agent --workspace D:\Code\C++code --allow-write --allow-compile "保留原结构修复问题，并在修改处写中文注释"
```

`--yes` 只会跳过已经通过 `--allow-write` 或 `--allow-compile` 明确开启的逐次确认，不会额外开放其他能力。

## 执行流程

```text
用户请求
   ↓
模型判断需要什么证据
   ↓
调用 list_files / search_code / read_file / git_diff
   ↓
本地执行受控工具并返回结果
   ↓
模型继续搜索、分析，或给出最终答案
```

启用写入或编译后，相应工具才会出现在模型可见的工具列表中。模型不能调用没有开放的能力。

## 项目结构

```text
src/cpp_learning_agent/
├─ cli.py              命令行入口和人工确认
├─ config.py           环境变量配置
├─ graph.py            LangGraph Agent 循环
├─ model.py            Responses API 适配层
├─ prompts.py          C++ 学习助手规则
├─ state.py            Graph State
└─ tools/
   ├─ registry.py      严格工具 Schema 与调度
   └─ workspace.py     路径隔离和实际工具实现
```

## 设计依据

OpenAI 官方 function calling 流程要求应用接收 `function_call`、在本地执行函数，再以带相同 `call_id` 的 `function_call_output` 返回模型。本项目把这个循环放进 LangGraph，并采用严格 JSON Schema：

- [OpenAI Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI Responses API](https://developers.openai.com/api/reference/responses/overview)

## 测试

```powershell
python -m pytest
```

测试不调用真实模型，覆盖工作区越界保护、搜索和行号、精确替换、工具权限以及一次完整的“模型调用工具后再回答”循环。
