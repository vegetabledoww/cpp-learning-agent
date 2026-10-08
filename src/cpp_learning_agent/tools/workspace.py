from __future__ import annotations

import fnmatch
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterator


class WorkspaceError(ValueError):
    """Raised when a requested operation escapes or violates the workspace."""


class WorkspaceTools:
    IGNORED_DIRECTORIES = {".git", ".venv", "__pycache__", "build", "node_modules"}
    MAX_TEXT_BYTES = 1_000_000
    MAX_DIFF_CHARS = 20_000

    def __init__(self, root: Path) -> None:
        resolved = root.expanduser().resolve()
        if not resolved.is_dir():
            raise WorkspaceError(f"工作区不存在或不是目录：{resolved}")
        self.root = resolved

    def _resolve(self, relative_path: str, *, must_exist: bool = True) -> Path:
        raw = Path(relative_path)
        if raw.is_absolute():
            raise WorkspaceError("工具参数必须使用工作区内的相对路径。")
        candidate = (self.root / raw).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceError("路径超出了允许的工作区。") from exc
        if must_exist and not candidate.exists():
            raise WorkspaceError(f"路径不存在：{relative_path}")
        return candidate

    def _relative(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def _iter_files(self, relative_path: str, pattern: str) -> Iterator[Path]:
        base = self._resolve(relative_path or ".")
        if not base.is_dir():
            raise WorkspaceError("列举和搜索的起点必须是目录。")

        for current_root, directory_names, file_names in os.walk(base):
            directory_names[:] = sorted(
                name for name in directory_names if name.casefold() not in self.IGNORED_DIRECTORIES
            )
            for file_name in sorted(file_names):
                path = Path(current_root) / file_name
                relative_text = self._relative(path)
                if fnmatch.fnmatch(path.name, pattern) or fnmatch.fnmatch(relative_text, pattern):
                    yield path

    @staticmethod
    def _read_text(path: Path) -> tuple[str, str]:
        raw = path.read_bytes()
        if len(raw) > WorkspaceTools.MAX_TEXT_BYTES:
            raise WorkspaceError("文件超过 1 MB，本学习版拒绝直接载入。")
        if b"\x00" in raw:
            raise WorkspaceError("目标看起来是二进制文件。")

        if raw.startswith(b"\xef\xbb\xbf"):
            return raw.decode("utf-8-sig"), "utf-8-sig"
        try:
            return raw.decode("utf-8"), "utf-8"
        except UnicodeDecodeError:
            try:
                return raw.decode("gb18030"), "gb18030"
            except UnicodeDecodeError as exc:
                raise WorkspaceError("文件不是支持的 UTF-8 或 GB18030 文本。") from exc

    def list_files(self, relative_path: str, pattern: str, max_results: int) -> dict[str, Any]:
        if max_results < 1 or max_results > 500:
            raise WorkspaceError("max_results 必须在 1 到 500 之间。")
        files: list[str] = []
        truncated = False
        for path in self._iter_files(relative_path, pattern or "*"):
            if len(files) >= max_results:
                truncated = True
                break
            files.append(self._relative(path))
        files.sort()
        return {"ok": True, "files": files, "truncated": truncated}

    def search_code(self, query: str, file_pattern: str, max_results: int) -> dict[str, Any]:
        if not query:
            raise WorkspaceError("搜索词不能为空。")
        if max_results < 1 or max_results > 200:
            raise WorkspaceError("max_results 必须在 1 到 200 之间。")

        needle = query.casefold()
        matches: list[dict[str, Any]] = []
        truncated = False
        for path in self._iter_files(".", file_pattern or "*"):
            try:
                text, _ = self._read_text(path)
            except WorkspaceError:
                continue
            for line_number, line in enumerate(text.splitlines(), start=1):
                column = line.casefold().find(needle)
                if column == -1:
                    continue
                if len(matches) >= max_results:
                    truncated = True
                    break
                matches.append(
                    {
                        "path": self._relative(path),
                        "line": line_number,
                        "column": column + 1,
                        "text": line[:500],
                    }
                )
            if truncated:
                break
        return {"ok": True, "matches": matches, "truncated": truncated}

    def read_file(self, path: str, start_line: int, end_line: int) -> dict[str, Any]:
        if start_line < 1 or end_line < start_line:
            raise WorkspaceError("行号范围无效。")
        if end_line - start_line + 1 > 400:
            raise WorkspaceError("单次最多读取 400 行。")
        resolved = self._resolve(path)
        if not resolved.is_file():
            raise WorkspaceError("read_file 只能读取文件。")
        text, encoding = self._read_text(resolved)
        lines = text.splitlines()
        selected = [
            {"line": number, "text": lines[number - 1]}
            for number in range(start_line, min(end_line, len(lines)) + 1)
        ]
        return {
            "ok": True,
            "path": self._relative(resolved),
            "encoding": encoding,
            "total_lines": len(lines),
            "lines": selected,
        }

    def git_status(self) -> dict[str, Any]:
        return self._run_git(["status", "--short"])

    def git_diff(self, path: str | None) -> dict[str, Any]:
        arguments = ["diff", "--"]
        if path:
            resolved = self._resolve(path)
            arguments.append(self._relative(resolved))
        return self._run_git(arguments)

    def _run_git(self, arguments: list[str]) -> dict[str, Any]:
        if not (self.root / ".git").exists():
            raise WorkspaceError("目标工作区不是 Git 仓库。")
        completed = subprocess.run(
            ["git", "-C", str(self.root), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
        output = (completed.stdout + completed.stderr)[: self.MAX_DIFF_CHARS]
        return {"ok": completed.returncode == 0, "exit_code": completed.returncode, "output": output}

    def compile_cpp(self, path: str) -> dict[str, Any]:
        compiler = shutil.which("g++")
        if compiler is None:
            raise WorkspaceError("系统中找不到 g++。")
        resolved = self._resolve(path)
        if resolved.suffix.lower() != ".cpp":
            raise WorkspaceError("compile_cpp 只接受 .cpp 文件。")
        completed = subprocess.run(
            [compiler, "-std=c++17", "-Wall", "-Wextra", "-pedantic", "-fsyntax-only", str(resolved)],
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        return {
            "ok": completed.returncode == 0,
            "exit_code": completed.returncode,
            "output": (completed.stdout + completed.stderr)[: self.MAX_DIFF_CHARS],
        }

    def replace_text(
        self,
        path: str,
        old_text: str,
        new_text: str,
        expected_count: int,
    ) -> dict[str, Any]:
        if not old_text:
            raise WorkspaceError("old_text 不能为空。")
        if expected_count < 1:
            raise WorkspaceError("expected_count 必须大于 0。")
        resolved = self._resolve(path)
        if not resolved.is_file():
            raise WorkspaceError("replace_text 只能修改已有文件。")
        text, encoding = self._read_text(resolved)
        actual_count = text.count(old_text)
        if actual_count != expected_count:
            raise WorkspaceError(
                f"旧文本实际出现 {actual_count} 次，与 expected_count={expected_count} 不一致，未修改文件。"
            )

        updated = text.replace(old_text, new_text)
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding=encoding,
                newline="",
                dir=resolved.parent,
                prefix=f".{resolved.name}.",
                suffix=".cpp-agent.tmp",
                delete=False,
            ) as temporary:
                temporary.write(updated)
                temporary_path = temporary.name
            os.replace(temporary_path, resolved)
        finally:
            if temporary_path and os.path.exists(temporary_path):
                os.remove(temporary_path)

        return {
            "ok": True,
            "path": self._relative(resolved),
            "replacements": actual_count,
        }

    def doctor(self) -> dict[str, Any]:
        return {
            "workspace": str(self.root),
            "is_git_repository": (self.root / ".git").is_dir(),
            "git": shutil.which("git"),
            "g++": shutil.which("g++"),
            "rg": shutil.which("rg"),
        }
