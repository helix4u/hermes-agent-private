"""
Gateway runtime status helpers.

Provides PID-file based detection of whether the gateway daemon is running,
used by send_message's check_fn to gate availability in the CLI.
"""

import os
import sys
from pathlib import Path

_PID_FILE = Path.home() / ".hermes" / "gateway.pid"

if sys.platform == "win32":
    import ctypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259


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


def write_pid_file() -> None:
    """Write the current process PID to the gateway PID file."""
    _PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PID_FILE.write_text(str(os.getpid()))


def remove_pid_file() -> None:
    """Remove the gateway PID file if it exists."""
    try:
        _PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def get_gateway_pid() -> int | None:
    """Return the gateway PID from the pid file if it points to a live process."""
    if not _PID_FILE.exists():
        return None
    try:
        pid = int(_PID_FILE.read_text().strip())
        if _pid_exists(pid):
            return pid
        remove_pid_file()
        return None
    except ValueError:
        remove_pid_file()
        return None


def is_gateway_running() -> bool:
    """Check if the gateway daemon is currently running."""
    return get_gateway_pid() is not None
