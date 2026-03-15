"""Shared Hermes entrypoint env loading helpers.

Prefer importing low-level decode helpers from `agent.env_loader`.
Use `load_hermes_dotenv(...)` for consistent entrypoint startup behavior.
"""

from __future__ import annotations

import os
from pathlib import Path

from agent.env_loader import (  # noqa: F401
    DEFAULT_DOTENV_ENCODINGS,
    load_dotenv_with_fallback,
    read_env_text_with_fallback,
    read_text_with_fallback,
)


def load_hermes_dotenv(
    *,
    hermes_home: str | os.PathLike | None = None,
    project_env: str | os.PathLike | None = None,
    logger=None,
) -> list[Path]:
    """Load Hermes .env files with user config taking precedence.

    Behavior:
    - `~/.hermes/.env` overrides stale shell-exported values when present.
    - project `.env` acts as a dev fallback and only fills missing values when
      the user env exists.
    - if no user env exists, the project `.env` also overrides stale shell vars.
    """
    loaded: list[Path] = []

    home_path = Path(hermes_home or os.getenv("HERMES_HOME", Path.home() / ".hermes"))
    user_env = home_path / ".env"
    project_env_path = Path(project_env) if project_env else None

    if user_env.exists():
        load_dotenv_with_fallback(user_env, override=True, logger=logger)
        loaded.append(user_env)

    if project_env_path and project_env_path.exists():
        load_dotenv_with_fallback(project_env_path, override=not loaded, logger=logger)
        loaded.append(project_env_path)

    return loaded
