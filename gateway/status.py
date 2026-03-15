"""
Gateway runtime status helpers.

Provides PID-file based detection of whether the gateway daemon is running,
plus a lightweight persisted runtime-health record used by `hermes gateway status`.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_HERMES_HOME = Path(os.getenv("HERMES_HOME", Path.home() / ".hermes"))
_PID_FILE = _HERMES_HOME / "gateway.pid"
_RUNTIME_STATUS_FILE = _HERMES_HOME / "gateway_state.json"
_GATEWAY_KIND = "hermes-gateway"

if sys.platform == "win32":
    import ctypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pid_exists(pid: int) -> bool:
    """Cross-platform process existence check."""
    if sys.platform == "win32":
        return _pid_exists_windows(pid)

    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False


def _pid_exists_windows(pid: int) -> bool:
    """Return True if a Windows PID appears to refer to a live process."""
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False

    try:
        exit_code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def _get_process_start_time(pid: int) -> Optional[int]:
    """Return a process start-time marker when it is available."""
    if sys.platform == "win32":
        return None

    stat_path = Path(f"/proc/{pid}/stat")
    try:
        # Field 22 is process start time in clock ticks.
        return int(stat_path.read_text(encoding="utf-8", errors="replace").split()[21])
    except (FileNotFoundError, IndexError, PermissionError, ValueError, OSError):
        return None


def _read_process_cmdline(pid: int) -> Optional[str]:
    """Return the process command line when it can be inspected."""
    if sys.platform == "win32":
        return None

    cmdline_path = Path(f"/proc/{pid}/cmdline")
    try:
        raw = cmdline_path.read_bytes()
    except (FileNotFoundError, PermissionError, OSError):
        return None

    if not raw:
        return None
    return raw.replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()


def _looks_like_gateway_process(pid: int) -> bool:
    """Return True when a live PID still appears to belong to Hermes gateway."""
    cmdline = _read_process_cmdline(pid)
    if not cmdline:
        return True

    patterns = (
        "hermes_cli.main gateway",
        "hermes gateway",
        "gateway/run.py",
    )
    return any(pattern in cmdline for pattern in patterns)


def _read_json_file(path: Path) -> Optional[dict[str, Any]]:
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
        errors="replace",
        newline="",
    )


def _build_pid_record() -> dict[str, Any]:
    return {
        "pid": os.getpid(),
        "kind": _GATEWAY_KIND,
        "argv": list(sys.argv),
        "start_time": _get_process_start_time(os.getpid()),
    }


def _read_pid_record() -> Optional[dict[str, Any]]:
    if not _PID_FILE.exists():
        return None
    try:
        raw = _PID_FILE.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    if not raw:
        return None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        try:
            return {"pid": int(raw)}
        except ValueError:
            return None

    if isinstance(payload, int):
        return {"pid": payload}
    if isinstance(payload, dict):
        return payload
    return None


def _build_runtime_status_record() -> dict[str, Any]:
    return {
        "pid": os.getpid(),
        "gateway_state": "starting",
        "exit_reason": None,
        "platforms": {},
        "updated_at": _utc_now_iso(),
    }


def write_pid_file() -> None:
    """Write the current process PID and lightweight metadata."""
    _PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PID_FILE.write_text(
        json.dumps(_build_pid_record(), ensure_ascii=False),
        encoding="utf-8",
        errors="replace",
        newline="",
    )


def write_runtime_status(
    *,
    gateway_state: Optional[str] = None,
    exit_reason: Optional[str] = None,
    platform: Optional[str] = None,
    platform_state: Optional[str] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """Persist gateway runtime health information for diagnostics/status."""
    payload = _read_json_file(_RUNTIME_STATUS_FILE) or _build_runtime_status_record()
    payload.setdefault("platforms", {})
    payload["pid"] = os.getpid()
    payload["updated_at"] = _utc_now_iso()

    if gateway_state is not None:
        payload["gateway_state"] = gateway_state
    if exit_reason is not None:
        payload["exit_reason"] = exit_reason

    if platform is not None:
        platform_payload = payload["platforms"].get(platform, {})
        if platform_state is not None:
            platform_payload["state"] = platform_state
        if error_code is not None:
            platform_payload["error_code"] = error_code
        if error_message is not None:
            platform_payload["error_message"] = error_message
        platform_payload["updated_at"] = _utc_now_iso()
        payload["platforms"][platform] = platform_payload

    _write_json_file(_RUNTIME_STATUS_FILE, payload)


def read_runtime_status() -> Optional[dict[str, Any]]:
    """Read the persisted gateway runtime health/status information."""
    return _read_json_file(_RUNTIME_STATUS_FILE)


def remove_pid_file() -> None:
    """Remove the gateway PID file if it exists."""
    try:
        _PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def get_gateway_pid() -> int | None:
    """Return the gateway PID when the pid file still points to the real gateway."""
    record = _read_pid_record()
    if not record:
        remove_pid_file()
        return None

    try:
        pid = int(record["pid"])
    except (KeyError, TypeError, ValueError):
        remove_pid_file()
        return None

    if not _pid_exists(pid):
        remove_pid_file()
        return None

    recorded_start = record.get("start_time")
    current_start = _get_process_start_time(pid)
    if recorded_start is not None and current_start is not None and current_start != recorded_start:
        remove_pid_file()
        return None

    if not _looks_like_gateway_process(pid):
        remove_pid_file()
        return None

    return pid


def is_gateway_running() -> bool:
    """Check if the gateway daemon is currently running."""
    return get_gateway_pid() is not None
