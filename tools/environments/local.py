"""Local execution environment with interrupt support and non-blocking I/O."""

import os
import platform
import shutil
import signal
import subprocess
import threading
import time

_IS_WINDOWS = platform.system() == "Windows"
_HERMES_PROVIDER_ENV_FORCE_PREFIX = "_HERMES_FORCE_"

from tools.environments.base import BaseEnvironment
from tools.environments.shell_utils import (
    build_local_subprocess_invocation,
    terminate_process_tree,
)

# Unique marker to isolate real command output from shell init/exit noise.
# printf (no trailing newline) keeps the boundaries clean for splitting.
_OUTPUT_FENCE = "__HERMES_FENCE_a9f7b3__"

# Noise lines emitted by interactive shells when stdin is not a terminal.
# Used as a fallback when output fence markers are missing.
_SHELL_NOISE_SUBSTRINGS = (
    # bash
    "bash: cannot set terminal process group",
    "bash: no job control in this shell",
    "no job control in this shell",
    "cannot set terminal process group",
    "tcsetattr: Inappropriate ioctl for device",
    # zsh / oh-my-zsh / macOS terminal session
    "Restored session:",
    "Saving session...",
    "Last login:",
    "command not found:",
    "Oh My Zsh",
    "compinit:",
)


def _build_provider_env_blocklist() -> frozenset[str]:
    """Derive the blocklist from provider, tool, and gateway config."""
    blocked: set[str] = set()

    try:
        from hermes_cli.auth import PROVIDER_REGISTRY

        for provider in PROVIDER_REGISTRY.values():
            blocked.update(env_var for env_var in provider.api_key_env_vars if env_var)
            if provider.base_url_env_var:
                blocked.add(provider.base_url_env_var)
    except ImportError:
        pass

    try:
        from hermes_cli.config import OPTIONAL_ENV_VARS

        for name, metadata in OPTIONAL_ENV_VARS.items():
            category = metadata.get("category")
            if category in {"tool", "messaging"}:
                blocked.add(name)
            elif category == "setting" and metadata.get("password"):
                blocked.add(name)
    except ImportError:
        pass

    blocked.update(
        {
            "OPENAI_BASE_URL",
            "OPENAI_API_KEY",
            "OPENROUTER_API_KEY",
            "NOUS_API_KEY",
            "NOUS_BASE_URL",
            "FIREWORKS_API_KEY",
            "XAI_API_KEY",
            "HELICONE_API_KEY",
            "TELEGRAM_HOME_CHANNEL",
            "TELEGRAM_HOME_CHANNEL_NAME",
            "DISCORD_HOME_CHANNEL",
            "DISCORD_HOME_CHANNEL_NAME",
            "DISCORD_REQUIRE_MENTION",
            "DISCORD_FREE_RESPONSE_CHANNELS",
            "DISCORD_AUTO_THREAD",
            "SLACK_HOME_CHANNEL",
            "SLACK_HOME_CHANNEL_NAME",
            "SLACK_ALLOWED_USERS",
            "WHATSAPP_ENABLED",
            "WHATSAPP_MODE",
            "WHATSAPP_ALLOWED_USERS",
            "SIGNAL_HTTP_URL",
            "SIGNAL_ACCOUNT",
            "SIGNAL_ALLOWED_USERS",
            "SIGNAL_GROUP_ALLOWED_USERS",
            "SIGNAL_HOME_CHANNEL",
            "SIGNAL_HOME_CHANNEL_NAME",
            "SIGNAL_IGNORE_STORIES",
            "HASS_TOKEN",
            "HASS_URL",
            "EMAIL_ADDRESS",
            "EMAIL_PASSWORD",
            "EMAIL_IMAP_HOST",
            "EMAIL_SMTP_HOST",
            "EMAIL_HOME_ADDRESS",
            "EMAIL_HOME_ADDRESS_NAME",
            "GATEWAY_ALLOWED_USERS",
            "GH_TOKEN",
            "GITHUB_APP_ID",
            "GITHUB_APP_PRIVATE_KEY_PATH",
            "GITHUB_APP_INSTALLATION_ID",
        }
    )
    return frozenset(blocked)


_HERMES_PROVIDER_ENV_BLOCKLIST = _build_provider_env_blocklist()


def _sanitize_subprocess_env(base_env: dict | None, extra_env: dict | None = None) -> dict:
    """Filter Hermes-managed secrets from a subprocess environment."""
    sanitized: dict[str, str] = {}

    for key, value in (base_env or {}).items():
        if key.startswith(_HERMES_PROVIDER_ENV_FORCE_PREFIX):
            continue
        if key not in _HERMES_PROVIDER_ENV_BLOCKLIST:
            sanitized[key] = value

    for key, value in (extra_env or {}).items():
        if key.startswith(_HERMES_PROVIDER_ENV_FORCE_PREFIX):
            real_key = key[len(_HERMES_PROVIDER_ENV_FORCE_PREFIX):]
            sanitized[real_key] = value
        elif key not in _HERMES_PROVIDER_ENV_BLOCKLIST:
            sanitized[key] = value

    return sanitized


def _clean_shell_noise(output: str) -> str:
    """Strip shell startup/exit warnings that leak when using -i without a TTY.

    Removes lines matching known noise patterns from both the beginning
    and end of the output.  Lines in the middle are left untouched.
    """

    def _is_noise(line: str) -> bool:
        return any(noise in line for noise in _SHELL_NOISE_SUBSTRINGS)

    lines = output.split("\n")

    # Strip leading noise
    while lines and _is_noise(lines[0]):
        lines.pop(0)

    # Strip trailing noise (walk backwards, skip empty lines from split)
    end = len(lines) - 1
    while end >= 0 and (not lines[end] or _is_noise(lines[end])):
        end -= 1

    if end < 0:
        return ""

    cleaned = lines[: end + 1]
    result = "\n".join(cleaned)

    # Preserve trailing newline if original had one
    if output.endswith("\n") and result and not result.endswith("\n"):
        result += "\n"
    return result


def _extract_fenced_output(raw: str) -> str:
    """Extract real command output from between fence markers.

    The execute() method wraps each command with printf(FENCE) markers.
    This function finds the first and last fence and returns only the
    content between them, which is the actual command output free of
    any shell init/exit noise.

    Falls back to pattern-based _clean_shell_noise if fences are missing.
    """
    first = raw.find(_OUTPUT_FENCE)
    if first == -1:
        return _clean_shell_noise(raw)

    start = first + len(_OUTPUT_FENCE)
    last = raw.rfind(_OUTPUT_FENCE)

    if last <= first:
        # Only start fence found (e.g. user command called `exit`)
        return _clean_shell_noise(raw[start:])

    return raw[start:last]


class LocalEnvironment(BaseEnvironment):
    """Run commands directly on the host machine.

    Features:
    - Popen + polling for interrupt support (user can cancel mid-command)
    - Background stdout drain thread to prevent pipe buffer deadlocks
    - stdin_data support for piping content (bypasses ARG_MAX limits)
    - sudo -S transform via SUDO_PASSWORD env var
    - Uses interactive login shell so full user env is available
    """

    def __init__(self, cwd: str = "", timeout: int = 60, env: dict = None):
        super().__init__(cwd=cwd or os.getcwd(), timeout=timeout, env=env)

    def execute(self, command: str, cwd: str = "", *,
                timeout: int | None = None,
                stdin_data: str | None = None) -> dict:
        from tools.terminal_tool import _interrupt_event

        work_dir = cwd or self.cwd or os.getcwd()
        effective_timeout = timeout or self.timeout
        exec_command = self._prepare_command(command)

        try:
            shell_command = exec_command
            # On POSIX and WSL, wrap commands with output fences so shell
            # startup/exit chatter does not leak into the real command output.
            popen_args, popen_platform_kwargs, shell_mode = build_local_subprocess_invocation(
                shell_command, work_dir
            )
            if shell_mode in {"posix", "wsl"}:
                shell_command = (
                    f"printf '{_OUTPUT_FENCE}';"
                    f" {exec_command};"
                    f" __hermes_rc=$?;"
                    f" printf '{_OUTPUT_FENCE}';"
                    f" exit $__hermes_rc"
                )
                popen_args, popen_platform_kwargs, shell_mode = build_local_subprocess_invocation(
                    shell_command, work_dir
                )
            proc = subprocess.Popen(
                popen_args,
                text=True,
                env=_sanitize_subprocess_env(os.environ, self.env),
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE if stdin_data is not None else subprocess.DEVNULL,
                **popen_platform_kwargs,
            )

            if stdin_data is not None:
                def _write_stdin():
                    try:
                        proc.stdin.write(stdin_data)
                        proc.stdin.close()
                    except (BrokenPipeError, OSError):
                        pass
                threading.Thread(target=_write_stdin, daemon=True).start()

            _output_chunks: list[str] = []

            def _drain_stdout():
                try:
                    for line in proc.stdout:
                        _output_chunks.append(line)
                except ValueError:
                    pass
                finally:
                    try:
                        proc.stdout.close()
                    except Exception:
                        pass

            reader = threading.Thread(target=_drain_stdout, daemon=True)
            reader.start()
            deadline = time.monotonic() + effective_timeout

            while proc.poll() is None:
                if _interrupt_event.is_set():
                    terminate_process_tree(proc, force=False)
                    try:
                        proc.wait(timeout=1.0)
                    except subprocess.TimeoutExpired:
                        terminate_process_tree(proc, force=True)
                    reader.join(timeout=2)
                    return {
                        "output": "".join(_output_chunks) + "\n[Command interrupted — user sent a new message]",
                        "returncode": 130,
                    }
                if time.monotonic() > deadline:
                    terminate_process_tree(proc, force=False)
                    try:
                        proc.wait(timeout=1.0)
                    except subprocess.TimeoutExpired:
                        terminate_process_tree(proc, force=True)
                    reader.join(timeout=2)
                    return self._timeout_result(effective_timeout)
                time.sleep(0.2)

            reader.join(timeout=5)
            output = _extract_fenced_output("".join(_output_chunks))
            return {"output": output, "returncode": proc.returncode}

        except Exception as e:
            return {"output": f"Execution error: {str(e)}", "returncode": 1}

    def cleanup(self):
        pass
