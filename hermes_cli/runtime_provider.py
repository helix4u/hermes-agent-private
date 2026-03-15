"""Shared runtime provider resolution for CLI, gateway, cron, and helpers."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from hermes_cli import auth as auth_mod
from hermes_cli.auth import (
    AuthError,
    format_auth_error,
    resolve_provider,
    resolve_anthropic_runtime_credentials,
    resolve_nous_runtime_credentials,
    resolve_codex_runtime_credentials,
)
from hermes_cli.config import load_config
from hermes_constants import OPENROUTER_BASE_URL

CODEX_DEFAULT_MODEL = (os.getenv("CODEX_DEFAULT_MODEL") or "gpt-5.4").strip() or "gpt-5.4"


def _normalize_custom_provider_name(value: str) -> str:
    return value.strip().lower().replace(" ", "-")


def _get_model_config() -> Dict[str, Any]:
    config = load_config()
    model_cfg = config.get("model")
    if isinstance(model_cfg, dict):
        return dict(model_cfg)
    if isinstance(model_cfg, str) and model_cfg.strip():
        return {"default": model_cfg.strip()}
    return {}


def normalize_model_for_runtime(
    model: Optional[str],
    provider: Optional[str],
    default_model: Optional[str] = CODEX_DEFAULT_MODEL,
) -> str:
    """Normalize model names after provider resolution.

    OpenRouter-style provider-prefixed models are valid for chat-completions
    backends, but Codex Responses expects plain OpenAI model IDs.
    """
    model_name = model.strip() if isinstance(model, str) else ""
    provider_name = provider.strip().lower() if isinstance(provider, str) else ""
    fallback_model = (
        default_model.strip()
        if isinstance(default_model, str) and default_model.strip()
        else CODEX_DEFAULT_MODEL
    )

    if provider_name != "openai-codex":
        if provider_name == "anthropic":
            if model_name.lower().startswith("anthropic/"):
                return model_name.split("/", 1)[1]
            return model_name
        return model_name
    if not model_name:
        return fallback_model
    if model_name.lower().startswith("openai/"):
        return model_name.split("/", 1)[1]
    if "/" in model_name:
        return fallback_model
    return model_name


def resolve_requested_provider(requested: Optional[str] = None) -> str:
    """Resolve provider request from explicit arg, env, then config."""
    if requested and requested.strip():
        return requested.strip().lower()

    env_provider = os.getenv("HERMES_INFERENCE_PROVIDER", "").strip().lower()
    if env_provider:
        return env_provider

    model_cfg = _get_model_config()
    cfg_provider = model_cfg.get("provider")
    if isinstance(cfg_provider, str) and cfg_provider.strip():
        return cfg_provider.strip().lower()

    return "auto"


def _get_named_custom_provider(requested_provider: str) -> Optional[Dict[str, Any]]:
    requested_norm = _normalize_custom_provider_name(requested_provider or "")
    if not requested_norm or requested_norm == "custom":
        return None

    if requested_norm == "auto":
        return None
    if not requested_norm.startswith("custom:"):
        try:
            auth_mod.resolve_provider(requested_norm)
        except AuthError:
            pass
        else:
            return None

    config = load_config()
    custom_providers = config.get("custom_providers")
    if not isinstance(custom_providers, list):
        return None

    for entry in custom_providers:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        base_url = entry.get("base_url")
        if not isinstance(name, str) or not isinstance(base_url, str):
            continue
        name_norm = _normalize_custom_provider_name(name)
        menu_key = f"custom:{name_norm}"
        if requested_norm not in {name_norm, menu_key}:
            continue
        return {
            "name": name.strip(),
            "base_url": base_url.strip(),
            "api_key": str(entry.get("api_key", "") or "").strip(),
        }

    return None


def _resolve_named_custom_runtime(
    *,
    requested_provider: str,
    explicit_api_key: Optional[str] = None,
    explicit_base_url: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    custom_provider = _get_named_custom_provider(requested_provider)
    if not custom_provider:
        return None

    base_url = (
        (explicit_base_url or "").strip()
        or custom_provider.get("base_url", "")
    ).rstrip("/")
    if not base_url:
        return None

    api_key = (
        (explicit_api_key or "").strip()
        or custom_provider.get("api_key", "")
        or os.getenv("OPENAI_API_KEY", "").strip()
        or os.getenv("OPENROUTER_API_KEY", "").strip()
    )

    return {
        "provider": "openrouter",
        "api_mode": "chat_completions",
        "base_url": base_url,
        "api_key": api_key,
        "source": f"custom_provider:{custom_provider.get('name', requested_provider)}",
    }


def _resolve_openrouter_runtime(
    *,
    requested_provider: str,
    explicit_api_key: Optional[str] = None,
    explicit_base_url: Optional[str] = None,
) -> Dict[str, Any]:
    model_cfg = _get_model_config()
    cfg_base_url = model_cfg.get("base_url") if isinstance(model_cfg.get("base_url"), str) else ""
    cfg_provider = model_cfg.get("provider") if isinstance(model_cfg.get("provider"), str) else ""
    requested_norm = (requested_provider or "").strip().lower()
    cfg_provider = cfg_provider.strip().lower()

    env_openai_base_url = os.getenv("OPENAI_BASE_URL", "").strip()
    env_openrouter_base_url = os.getenv("OPENROUTER_BASE_URL", "").strip()

    use_config_base_url = False
    if cfg_base_url.strip() and not explicit_base_url and not env_openai_base_url:
        if requested_norm == "auto":
            if not cfg_provider or cfg_provider == "auto":
                use_config_base_url = True
        elif requested_norm == "custom":
            # Persisted custom endpoints store their base URL in config.yaml.
            # If OPENAI_BASE_URL is not currently set in the environment, keep
            # honoring that saved endpoint instead of falling back to OpenRouter.
            if cfg_provider == "custom":
                use_config_base_url = True

    base_url = (
        (explicit_base_url or "").strip()
        or env_openai_base_url
        or (cfg_base_url.strip() if use_config_base_url else "")
        or env_openrouter_base_url
        or OPENROUTER_BASE_URL
    ).rstrip("/")

    api_key = (
        explicit_api_key
        or os.getenv("OPENROUTER_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or ""
    )

    source = "explicit" if (explicit_api_key or explicit_base_url) else "env/config"

    return {
        "provider": "openrouter",
        "api_mode": "chat_completions",
        "base_url": base_url,
        "api_key": api_key,
        "source": source,
    }


def resolve_runtime_provider(
    *,
    requested: Optional[str] = None,
    explicit_api_key: Optional[str] = None,
    explicit_base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve runtime provider credentials for agent execution."""
    requested_provider = resolve_requested_provider(requested)

    custom_runtime = _resolve_named_custom_runtime(
        requested_provider=requested_provider,
        explicit_api_key=explicit_api_key,
        explicit_base_url=explicit_base_url,
    )
    if custom_runtime:
        custom_runtime["requested_provider"] = requested_provider
        return custom_runtime

    provider = resolve_provider(
        requested_provider,
        explicit_api_key=explicit_api_key,
        explicit_base_url=explicit_base_url,
    )

    if provider == "nous":
        creds = resolve_nous_runtime_credentials(
            min_key_ttl_seconds=max(60, int(os.getenv("HERMES_NOUS_MIN_KEY_TTL_SECONDS", "1800"))),
            timeout_seconds=float(os.getenv("HERMES_NOUS_TIMEOUT_SECONDS", "15")),
        )
        return {
            "provider": "nous",
            "api_mode": "chat_completions",
            "base_url": creds.get("base_url", "").rstrip("/"),
            "api_key": creds.get("api_key", ""),
            "source": creds.get("source", "portal"),
            "expires_at": creds.get("expires_at"),
            "requested_provider": requested_provider,
        }

    if provider == "openai-codex":
        creds = resolve_codex_runtime_credentials()
        return {
            "provider": "openai-codex",
            "api_mode": "codex_responses",
            "base_url": creds.get("base_url", "").rstrip("/"),
            "api_key": creds.get("api_key", ""),
            "source": creds.get("source", "hermes-auth-store"),
            "last_refresh": creds.get("last_refresh"),
            "requested_provider": requested_provider,
        }

    if provider == "anthropic":
        creds = resolve_anthropic_runtime_credentials()
        base_url = (
            explicit_base_url.strip().rstrip("/")
            if isinstance(explicit_base_url, str) and explicit_base_url.strip()
            else creds.get("base_url", "").rstrip("/")
        )
        api_key = (
            explicit_api_key.strip()
            if isinstance(explicit_api_key, str) and explicit_api_key.strip()
            else creds.get("api_key", "")
        )
        return {
            "provider": "anthropic",
            "api_mode": "anthropic_messages",
            "base_url": base_url,
            "api_key": api_key,
            "source": "explicit" if (explicit_api_key or explicit_base_url) else creds.get("source", "env"),
            "requested_provider": requested_provider,
        }

    runtime = _resolve_openrouter_runtime(
        requested_provider=requested_provider,
        explicit_api_key=explicit_api_key,
        explicit_base_url=explicit_base_url,
    )
    runtime["requested_provider"] = requested_provider
    return runtime


def format_runtime_provider_error(error: Exception) -> str:
    if isinstance(error, AuthError):
        return format_auth_error(error)
    return str(error)
