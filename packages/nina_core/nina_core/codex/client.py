"""Codex CLI client used by the Nina daemon integration."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Health, Project


logger = logging.getLogger(__name__)


class CodexError(RuntimeError):
    """Raised for any Codex CLI execution failure."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        body: str | None = None,
        stdout: str | None = None,
        stderr: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body
        self.stdout = stdout
        self.stderr = stderr


@dataclass
class CodexExecResult:
    """Result of a single `codex exec` invocation."""

    exit_code: int
    stdout: str
    stderr: str
    json_payload: dict[str, Any] | list[Any] | None = None
    last_message: str | None = None


class CodexClient:
    """Thin wrapper around the `codex` binary."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        *,
        timeout: float = 5.0,
        binary_path: str | None = None,
    ) -> None:
        # These fields are kept for existing call-sites.
        del host, port, username, password
        self.binary_path = (binary_path or "").strip() or (shutil.which("codex") or "")
        self._timeout = timeout

    async def _run(
        self,
        args: list[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        log_path: Path | str | None = None,
    ) -> CodexExecResult:
        if not self.binary_path:
            raise CodexError("codex binary not found on PATH")
        command = [self.binary_path, *args]
        logged_args = args[:-1] if args and args[0] == "exec" else args
        logger.info(
            "nina.codex event=command_start binary=%s cwd=%s args=%s",
            self.binary_path,
            cwd or "",
            logged_args,
        )
        process_env = os.environ.copy()
        if env:
            process_env.update(env)
        try:
            process = await asyncio.to_thread(
                self._run_subprocess,
                command,
                cwd=cwd,
                env=process_env,
                log_path=Path(log_path) if log_path is not None else None,
            )
        except FileNotFoundError as exc:
            logger.error("nina.codex event=command_error binary=%s error=not_found", self.binary_path)
            raise CodexError(f"codex binary not found: {self.binary_path}") from exc
        except subprocess.TimeoutExpired as exc:
            logger.error("nina.codex event=command_timeout binary=%s timeout=%s", self.binary_path, self._timeout)
            raise CodexError(f"codex command timed out after {self._timeout}s", stderr=str(exc))

        stdout = process.stdout or ""
        stderr = process.stderr or ""
        logger.info(
            "nina.codex event=command_exit binary=%s exit_code=%s stdout_chars=%s stderr_chars=%s",
            self.binary_path,
            process.returncode,
            len(stdout),
            len(stderr),
        )
        return CodexExecResult(
            exit_code=process.returncode,
            stdout=stdout,
            stderr=stderr,
        )

    def _run_subprocess(
        self,
        command: list[str],
        *,
        cwd: str | None,
        env: dict[str, str],
        log_path: Path | None,
    ) -> subprocess.CompletedProcess[str]:
        log_handle = None
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_handle = log_path.open("a", encoding="utf-8", errors="replace")
            command_display = " ".join(command[:-1])
            log_handle.write(f"$ {command_display} <prompt>\n")
            if cwd:
                log_handle.write(f"cwd: {cwd}\n")
            log_handle.flush()

        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []

        def pump(stream: Any, chunks: list[str], label: str) -> None:
            try:
                for line in iter(stream.readline, ""):
                    chunks.append(line)
                    if log_handle is not None:
                        log_handle.write(f"[{label}] {line}")
                        log_handle.flush()
            finally:
                stream.close()

        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception:
            if log_handle is not None:
                log_handle.close()
            raise
        if process.stdout is None or process.stderr is None:
            if log_handle is not None:
                log_handle.close()
            raise RuntimeError("codex subprocess pipes were not created")
        stdout_thread = threading.Thread(
            target=pump,
            args=(process.stdout, stdout_chunks, "stdout"),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=pump,
            args=(process.stderr, stderr_chunks, "stderr"),
            daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()
        try:
            returncode = process.wait(timeout=self._timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            returncode = process.wait()
            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)
            if log_handle is not None:
                log_handle.write(f"\nexit_code: {returncode} (timeout after {self._timeout}s)\n")
                log_handle.close()
            raise
        stdout_thread.join()
        stderr_thread.join()
        stdout = "".join(stdout_chunks)
        stderr = "".join(stderr_chunks)
        if log_handle is not None:
            log_handle.write(f"\nexit_code: {returncode}\n")
            log_handle.close()
        return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr=stderr)

    @staticmethod
    def _extract_json_payload(text: str) -> dict[str, Any] | list[Any] | None:
        for line in reversed(text.strip().splitlines()):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, (dict, list)):
                return payload
        return None

    async def exec_task(
        self,
        prompt: str,
        *,
        cwd: str,
        env: dict[str, str],
        timeout: float = 1800.0,
        json_mode: bool = True,
        log_path: Path | str | None = None,
    ) -> CodexExecResult:
        previous_timeout = self._timeout
        self._timeout = timeout
        output_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(prefix="nina-codex-last-", suffix=".txt", delete=False) as handle:
                output_path = Path(handle.name)
            args: list[str] = [
                "exec",
                "--cd",
                cwd,
                "--skip-git-repo-check",
                "--dangerously-bypass-approvals-and-sandbox",
                "--dangerously-bypass-hook-trust",
                "--output-last-message",
                str(output_path),
            ]
            if json_mode:
                args.append("--json")
            args.append(prompt)
            result = await self._run(args, cwd=cwd, env=env, log_path=log_path)
            if output_path is not None and output_path.exists():
                result.last_message = output_path.read_text()
        finally:
            self._timeout = previous_timeout
            if output_path is not None:
                try:
                    output_path.unlink(missing_ok=True)
                except OSError:
                    pass

        if result.exit_code != 0:
            raise CodexError(
                "codex task exec failed",
                status_code=result.exit_code,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        if json_mode:
            result.json_payload = self._extract_json_payload(result.stdout)
        return result

    async def exec(
        self,
        prompt: str,
        *,
        json_mode: bool = False,
        timeout: float = 120.0,
        cwd: str | None = None,
        output_last_message: bool = False,
    ) -> CodexExecResult:
        previous_timeout = self._timeout
        self._timeout = timeout
        output_path: Path | None = None
        try:
            args: list[str] = ["exec"]
            if cwd:
                args.extend(["--cd", cwd])
            args.append("--skip-git-repo-check")
            if output_last_message:
                with tempfile.NamedTemporaryFile(prefix="nina-codex-llm-", suffix=".txt", delete=False) as handle:
                    output_path = Path(handle.name)
                args.extend(["--output-last-message", str(output_path)])
            if json_mode:
                args.append("--json")
            args.append(prompt)
            result = await self._run(args, cwd=cwd)
            if output_path is not None and output_path.exists():
                result.last_message = output_path.read_text()
        finally:
            self._timeout = previous_timeout
            if output_path is not None:
                try:
                    output_path.unlink(missing_ok=True)
                except OSError:
                    pass

        if result.exit_code != 0:
            raise CodexError(
                "codex exec failed",
                status_code=result.exit_code,
                stdout=result.stdout,
                stderr=result.stderr,
            )

        if json_mode:
            result.json_payload = self._extract_json_payload(result.stdout)
        return result

    async def health(self) -> Health:
        result = await self._run(["--version"])
        if result.exit_code != 0:
            raise CodexError(
                "codex failed to report version",
                status_code=result.exit_code,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        version: str | None = None
        for line in result.stdout.splitlines():
            line = line.strip()
            if line:
                version = line
                break
        return Health(healthy=True, version=version)

    async def list_projects(self) -> list[Project]:
        # Codex CLI does not expose a first-class `project` endpoint comparable
        # to the old API. Keep compatibility by returning an empty list.
        return []

    async def current_project(self) -> Project:
        # Kept for API compatibility only.
        raise CodexError(
            "codex CLI integration does not expose current project",
            status_code=501,
            body="not_supported",
        )

    async def __aenter__(self) -> "CodexClient":
        return self

    async def __aexit__(self, *_exc: object) -> None:  # noqa: ARG002
        return None

    async def aclose(self) -> None:
        return None
