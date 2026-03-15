"""
Timezone-aware clock helpers for Hermes.

Resolution order:
1. ``HERMES_TIMEZONE`` environment variable
2. ``timezone`` key in ``~/.hermes/config.yaml``
3. Server-local timezone via ``datetime.now().astimezone()``
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]


_cached_tz: Optional[ZoneInfo] = None
_cached_tz_name: Optional[str] = None
_cache_resolved = False


def _resolve_timezone_name() -> str:
    tz_env = os.getenv("HERMES_TIMEZONE", "").strip()
    if tz_env:
        return tz_env

    try:
        hermes_home = Path(os.getenv("HERMES_HOME", Path.home() / ".hermes"))
        config_path = hermes_home / "config.yaml"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8", errors="replace") as handle:
                cfg = yaml.safe_load(handle) or {}
            tz_cfg = cfg.get("timezone", "")
            if isinstance(tz_cfg, str) and tz_cfg.strip():
                return tz_cfg.strip()
    except Exception:
        pass

    return ""


def _get_zoneinfo(name: str) -> Optional[ZoneInfo]:
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except Exception as exc:
        logger.warning(
            "Invalid timezone '%s': %s. Falling back to server-local time.",
            name,
            exc,
        )
        return None


def get_timezone() -> Optional[ZoneInfo]:
    global _cached_tz, _cached_tz_name, _cache_resolved
    if not _cache_resolved:
        _cached_tz_name = _resolve_timezone_name()
        _cached_tz = _get_zoneinfo(_cached_tz_name)
        _cache_resolved = True
    return _cached_tz


def get_timezone_name() -> str:
    global _cached_tz_name, _cache_resolved
    if not _cache_resolved:
        get_timezone()
    return _cached_tz_name or ""


def now() -> datetime:
    tz = get_timezone()
    if tz is not None:
        return datetime.now(tz)
    return datetime.now().astimezone()


def reset_cache() -> None:
    global _cached_tz, _cached_tz_name, _cache_resolved
    _cached_tz = None
    _cached_tz_name = None
    _cache_resolved = False
