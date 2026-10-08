# C++ Learning Agent

一个面向 C++ 学习仓库的命令行智能体。它会先读取真实代码、搜索相关位置，再通过 OpenAI Responses API 和 LangGraph 完成分析、编译检查或经过确认的局部修改。

它适合这些场景：

- 检查一道 C++ 题目的正确性和边界条件；
- 解释陌生的 STL、数据结构或算法代码；
- 在回答中给出真实的文件路径和行号；
- 使用 `g++` 进行 C++17 严格语法检查；
- 保留原有结构，对已有文件做小范围修改。

> 当前版本是仓库级命令行助手，不是 IDE 中的实时补全插件。

## 核心特性

- **基于证据回答**：先调用本地工具读取文件，再给出分析结论。
- **工作区隔离**：只能访问 `--workspace` 指定的目录，拒绝绝对路径和 `..` 越界。
- **默认只读**：不加参数时只能列举、搜索和读取文件，以及查看 Git 状态与差异。
- **权限显式开放**：编译和写入分别需要 `--allow-compile`、`--allow-write`。
- **操作逐次确认**：即使开放权限，执行前仍会询问；只有显式使用 `--yes` 才跳过确认。
- **修改范围受控**：只支持对已有文件进行指定次数的精确文本替换。
- **无任意命令执行**：不能执行任意 Shell、删除文件、创建提交或推送代码。
- **兼容中文源码**：支持 UTF-8、带 BOM 的 UTF-8 和 GB18030 文本。

## 工作流程

```text
用户请求
   |
   v
模型判断需要哪些证据
   |
   v
list_files / search_code / read_file / git_diff
   |
   v
本地执行受控工具并返回结果
   |
   v
模型继续搜索、分析，或生成最终回答
```

LangGraph 负责模型与工具之间的循环。模型发出的 `function_call` 会在本地执行，执行结果再以相同 `call_id` 的 `function_call_output` 返回模型。

## 环境要求

- Python 3.11 或更高版本；
- Git；
- OpenAI API，或兼容 Responses API 与 function calling 的服务；
- `g++`（可选，仅在使用编译检查时需要）。

## 安装

### Windows PowerShell

```powershell
git clone https://github.com/vegetabledoww/cpp-learning-agent.git
cd cpp-learning-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

### macOS / Linux

```bash
git clone https://github.com/vegetabledoww/cpp-learning-agent.git
cd cpp-learning-agent
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## 配置

至少需要设置 API 密钥和模型名称：

```powershell
$env:OPENAI_API_KEY = "你的密钥"
$env:CPP_AGENT_MODEL = "你的模型名"
```

使用兼容服务时，再设置它的 API 地址：

```powershell
$env:OPENAI_BASE_URL = "服务地址"
```

macOS 或 Linux 使用 `export`：

```bash
export OPENAI_API_KEY="你的密钥"
export CPP_AGENT_MODEL="你的模型名"
export OPENAI_BASE_URL="服务地址"
```

可以参考 [.env.example](./.env.example)，但程序不会自动读取 `.env`。不要把真实密钥写入源码或提交到 Git。

## 快速开始

先运行不调用模型的环境检查：

```powershell
cpp-agent --workspace D:\path\to\your-cpp-repo --doctor
```

### 只读分析

```powershell
cpp-agent --workspace D:\path\to\your-cpp-repo "检查资源分发题的正确性，先不考虑性能"
```

显示智能体实际调用过的工具：

```powershell
cpp-agent --workspace D:\path\to\your-cpp-repo --verbose "解释 lower_bound 在这道题中的作用"
```

### 允许编译检查

```powershell
cpp-agent --workspace D:\path\to\your-cpp-repo --allow-compile "编译并检查指定题目"
```

编译使用以下约束：

```text
g++ -std=c++17 -Wall -Wextra -pedantic -fsyntax-only
```

它只检查语法和编译警告，不运行生成的程序。

### 允许修改已有文件

```powershell
cpp-agent --workspace D:\path\to\your-cpp-repo --allow-write --allow-compile "保留原结构修复问题，并在修改处添加中文注释"
```

默认每次编译或修改都会询问确认。确定要自动批准已开放的能力时，可以加上 `--yes`：

```powershell
cpp-agent --workspace D:\path\to\your-cpp-repo --allow-write --allow-compile --yes "修复指定文件并编译检查"
```

`--yes` 不会额外开放删除、Shell、Git 提交或推送等能力。

## 命令参数

| 参数 | 作用 |
| --- | --- |
| `--workspace PATH` | 指定唯一允许访问的代码仓库根目录 |
| `--model MODEL` | 覆盖 `CPP_AGENT_MODEL` |
| `--base-url URL` | 覆盖 `OPENAI_BASE_URL` |
| `--max-iterations N` | 设置最大模型调用轮数，默认 12 |
| `--allow-compile` | 向模型开放 C++17 语法编译工具 |
| `--allow-write` | 向模型开放精确文本替换工具 |
| `--yes` | 跳过已开放操作的逐次确认 |
| `--verbose` | 显示工具调用轨迹 |
| `--doctor` | 只检查本机环境，不调用模型 |

查看完整帮助：

```powershell
cpp-agent --help
```

## 项目结构

```text
src/cpp_learning_agent/
├─ cli.py              命令行入口和人工确认
├─ config.py           环境变量配置
├─ graph.py            LangGraph 智能体循环
├─ model.py            Responses API 适配层
├─ prompts.py          C++ 学习助手规则
├─ state.py            Graph State
└─ tools/
   ├─ registry.py      严格工具 Schema 与权限调度
   └─ workspace.py     路径隔离和本地工具实现

tests/
├─ test_graph.py       模型与工具循环测试
├─ test_registry.py    权限和工具注册测试
└─ test_workspace.py   路径、搜索、读取和写入测试
```

## 开发与测试

```powershell
python -m pytest
python -m compileall -q src tests
python -m pip check
```

测试不会调用真实模型，覆盖以下行为：

- 工作区越界保护；
- 文件搜索、编码和行号；
- 精确文本替换；
- 编译与写入权限；
- 一次完整的“模型调用工具后继续回答”循环。

## 安全说明

- 模型读取到的必要代码片段会发送给你配置的 API 服务；使用第三方服务前请确认其数据处理规则。
- 不要在目标仓库中保存 API 密钥、令牌或其他敏感信息。
- 对重要仓库启用写入前，建议先检查 Git 状态并保留可恢复的提交。
- 本项目使用 `store=False` 请求模型服务不存储响应，但第三方兼容服务是否遵守该参数，需要以其自身说明为准。

## 设计参考

- [OpenAI Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI Responses API](https://developers.openai.com/api/reference/responses/overview)
- [LangGraph documentation](https://docs.langchain.com/oss/python/langgraph/overview)
