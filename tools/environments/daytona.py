"""Daytona cloud execution environment.

Uses the Daytona Python SDK to run commands in cloud sandboxes.
Supports persistent sandboxes: when enabled, sandboxes are stopped on cleanup
and resumed on next creation, preserving the filesystem across sessions.
"""

import logging
import math
import shlex
import threading
import uuid
import warnings
from typing import Optional

from tools.environments.base import BaseEnvironment
from tools.interrupt import is_interrupted

logger = logging.getLogger(__name__)


class DaytonaEnvironment(BaseEnvironment):
    """Daytona cloud sandbox execution backend."""

    def __init__(
        self,
        image: str,
        cwd: str = "/home/daytona",
        timeout: int = 60,
        cpu: int = 1,
        memory: int = 5120,
        disk: int = 10240,
        persistent_filesystem: bool = True,
        task_id: str = "default",
    ):
        self._requested_cwd = cwd
        super().__init__(cwd=cwd, timeout=timeout)

        from daytona import (
            CreateSandboxFromImageParams,
            Daytona,
            DaytonaError,
            Resources,
            SandboxState,
        )

        self._persistent = persistent_filesystem
        self._task_id = task_id
        self._daytona_error_type = DaytonaError
        self._sandbox_state = SandboxState
        self._daytona = Daytona()
        self._sandbox = None
        self._lock = threading.Lock()

        memory_gib = max(1, math.ceil(memory / 1024))
        disk_gib = max(1, math.ceil(disk / 1024))
        if disk_gib > 10:
            warnings.warn(
                (
                    f"Daytona: requested disk ({disk_gib}GB) exceeds platform limit (10GB). "
                    "Capping to 10GB. Set container_disk: 10240 in config to silence this."
                ),
                stacklevel=2,
            )
            disk_gib = 10

        resources = Resources(cpu=cpu, memory=memory_gib, disk=disk_gib)
        labels = {"hermes_task_id": task_id}

        if self._persistent:
            try:
                self._sandbox = self._daytona.find_one(labels=labels)
                self._sandbox.start()
                logger.info(
                    "Daytona: resumed sandbox %s for task %s",
                    self._sandbox.id,
                    task_id,
                )
            except DaytonaError:
                self._sandbox = None
            except Exception as exc:
                logger.warning(
                    "Daytona: failed to resume sandbox for task %s: %s",
                    task_id,
                    exc,
                )
                self._sandbox = None

        if self._sandbox is None:
            self._sandbox = self._daytona.create(
                CreateSandboxFromImageParams(
                    image=image,
                    labels=labels,
                    auto_stop_interval=0,
                    resources=resources,
                )
            )
            logger.info(
                "Daytona: created sandbox %s for task %s",
                self._sandbox.id,
                task_id,
            )

        if self._requested_cwd in ("~", "/home/daytona"):
            try:
                home = self._sandbox.process.exec("echo $HOME").result.strip()
                if home:
                    self.cwd = home
            except Exception:
                pass
            logger.info("Daytona: resolved cwd to %s", self.cwd)

    def _ensure_sandbox_ready(self) -> None:
        """Restart sandbox if it was previously stopped."""
        self._sandbox.refresh_data()
        if self._sandbox.state in (self._sandbox_state.STOPPED, self._sandbox_state.ARCHIVED):
            self._sandbox.start()
            logger.info("Daytona: restarted sandbox %s", self._sandbox.id)

    def _exec_in_thread(self, exec_command: str, cwd: Optional[str], timeout: int) -> dict:
        """Run exec in a background thread with interrupt polling."""
        timed_command = f"timeout {timeout} sh -c {shlex.quote(exec_command)}"
        result_holder: dict = {"value": None, "error": None}

        def _run() -> None:
            try:
                response = self._sandbox.process.exec(timed_command, cwd=cwd)
                result_holder["value"] = {
                    "output": response.result or "",
                    "returncode": response.exit_code,
                }
            except Exception as exc:
                result_holder["error"] = exc

        worker = threading.Thread(target=_run, daemon=True)
        worker.start()

        deadline = timeout + 10
        while worker.is_alive():
            worker.join(timeout=0.2)
            deadline -= 0.2
            if is_interrupted():
                with self._lock:
                    try:
                        self._sandbox.stop()
                    except Exception:
                        pass
                return {
                    "output": "[Command interrupted - Daytona sandbox stopped]",
                    "returncode": 130,
                }
            if deadline <= 0:
                with self._lock:
                    try:
                        self._sandbox.stop()
                    except Exception:
                        pass
                return self._timeout_result(timeout)

        if result_holder["error"] is not None:
            return {"error": result_holder["error"]}
        return result_holder["value"]

    def execute(
        self,
        command: str,
        cwd: str = "",
        *,
        timeout: Optional[int] = None,
        stdin_data: Optional[str] = None,
    ) -> dict:
        with self._lock:
            self._ensure_sandbox_ready()

        if stdin_data is not None:
            marker = f"HERMES_EOF_{uuid.uuid4().hex[:8]}"
            while marker in stdin_data:
                marker = f"HERMES_EOF_{uuid.uuid4().hex[:8]}"
            command = f"{command} << '{marker}'\n{stdin_data}\n{marker}"

        exec_command = self._prepare_command(command)
        effective_cwd = cwd or self.cwd or None
        effective_timeout = timeout or self.timeout

        result = self._exec_in_thread(exec_command, effective_cwd, effective_timeout)
        if "error" in result:
            err = result["error"]
            if isinstance(err, self._daytona_error_type):
                with self._lock:
                    try:
                        self._ensure_sandbox_ready()
                    except Exception:
                        return {
                            "output": f"Daytona execution error: {err}",
                            "returncode": 1,
                        }
                result = self._exec_in_thread(exec_command, effective_cwd, effective_timeout)
                if "error" not in result:
                    return result
            return {"output": f"Daytona execution error: {err}", "returncode": 1}

        return result

    def cleanup(self) -> None:
        with self._lock:
            if self._sandbox is None:
                return
            try:
                if self._persistent:
                    self._sandbox.stop()
                    logger.info(
                        "Daytona: stopped sandbox %s (filesystem preserved)",
                        self._sandbox.id,
                    )
                else:
                    self._daytona.delete(self._sandbox)
                    logger.info("Daytona: deleted sandbox %s", self._sandbox.id)
            except Exception as exc:
                logger.warning("Daytona: cleanup failed: %s", exc)
            self._sandbox = None
