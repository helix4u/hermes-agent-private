"""Shared auxiliary OpenAI client for cheap/fast side tasks.

Provides a single resolution chain so every consumer (context compression,
session search, web extraction, vision analysis, browser vision) picks up
the best available backend without duplicating fallback logic.

Resolution order for text tasks:
  1. Runtime-selected provider (env/config/active auth provider)
  2. OpenRouter  (OPENROUTER_API_KEY)
  3. Nous Portal (~/.hermes/auth.json active provider)
  4. Custom endpoint (OPENAI_BASE_URL + OPENAI_API_KEY)
  5. Codex OAuth (Responses API via chatgpt.com,
     wrapped to look like a chat.completions client)
  6. None

Resolution order for vision/multimodal tasks:
  1. Runtime-selected provider (env/config/active auth provider)
  2. OpenRouter
  3. Nous Portal
  4. Codex OAuth (Responses API with multimodal input)
  5. None  (custom endpoints still can't substitute for multimodal support)
"""

import json
import logging
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

from hermes_constants import OPENROUTER_BASE_URL

logger = logging.getLogger(__name__)

# OpenRouter app attribution headers
_OR_HEADERS = {
    "HTTP-Referer": "https://github.com/NousResearch/hermes-agent",
    "X-OpenRouter-Title": "Hermes Agent",
    "X-OpenRouter-Categories": "productivity,cli-agent",
}

# Nous Portal extra_body for product attribution.
# Callers should pass this as extra_body in chat.completions.create()
# when the auxiliary client is backed by Nous Portal.
NOUS_EXTRA_BODY = {"tags": ["product=hermes-agent"]}

# Set at resolve time — True if the auxiliary client points to Nous Portal
auxiliary_is_nous: bool = False

# Default auxiliary models per provider
_OPENROUTER_MODEL = "google/gemini-3-flash-preview"
_NOUS_MODEL = "gemini-3-flash"
_NOUS_DEFAULT_BASE_URL = "https://inference-api.nousresearch.com/v1"
_AUTH_JSON_PATH = Path.home() / ".hermes" / "auth.json"
_AUX_PROVIDER_ENV = "CONTEXT_COMPRESSION_PROVIDER"
_CONFIG_YAML_PATH = Path.home() / ".hermes" / "config.yaml"

# Codex fallback: uses the Responses API (the only endpoint the Codex
# OAuth token can access) with a fast model for auxiliary tasks.
_CODEX_AUX_MODEL = "gpt-5.4"
_CODEX_AUX_BASE_URL = "https://chatgpt.com/backend-api/codex"
_PROVIDER_ALIASES = {
    "codex": "openai-codex",
    "openai_codex": "openai-codex",
}


def _load_auxiliary_config() -> Dict[str, Any]:
    """Read auxiliary config from ~/.hermes/config.yaml."""
    try:
        if not _CONFIG_YAML_PATH.is_file():
            return {}
        import yaml

        data = yaml.safe_load(_CONFIG_YAML_PATH.read_text(encoding="utf-8")) or {}
        auxiliary_cfg = data.get("auxiliary", {})
        return auxiliary_cfg if isinstance(auxiliary_cfg, dict) else {}
    except Exception as exc:
        logger.debug("Could not read auxiliary config: %s", exc)
        return {}


def _get_auxiliary_overrides(kind: str) -> Dict[str, str]:
    """Return normalized auxiliary overrides for a task kind."""
    auxiliary_cfg = _load_auxiliary_config()
    task_cfg = auxiliary_cfg.get(kind, {})
    if not isinstance(task_cfg, dict):
        return {}
    overrides: Dict[str, str] = {}
    for key in ("provider", "model", "base_url", "api_key"):
        value = task_cfg.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            overrides[key] = text
    return overrides


def _get_auxiliary_env_override(task: str, suffix: str) -> Optional[str]:
    """Read task-specific auxiliary overrides from AUXILIARY_/CONTEXT_ env vars."""
    if not task:
        return None
    task_name = task.strip().upper().replace("-", "_")
    if not task_name:
        return None
    for prefix in ("AUXILIARY_", "CONTEXT_"):
        value = os.getenv(f"{prefix}{task_name}_{suffix}", "").strip()
        if value:
            return value
    return None


def _get_task_auxiliary_overrides(task: Optional[str], task_kind: str) -> Dict[str, str]:
    """Merge task-specific overrides with the text/vision task-kind defaults."""
    merged: Dict[str, str] = {}
    merged.update(_get_auxiliary_overrides(task_kind))

    task_name = (task or "").strip().lower()
    if task_name and task_name != task_kind:
        merged.update(_get_auxiliary_overrides(task_name))

    env_task_names: List[str] = []
    if task_name:
        env_task_names.append(task_name)
    if task_kind not in env_task_names:
        env_task_names.append(task_kind)

    for env_task in env_task_names:
        for key, suffix in (
            ("provider", "PROVIDER"),
            ("model", "MODEL"),
            ("base_url", "BASE_URL"),
            ("api_key", "API_KEY"),
        ):
            value = _get_auxiliary_env_override(env_task, suffix)
            if value:
                merged[key] = value

    return merged


def _resolve_auxiliary_direct_credentials(overrides: Dict[str, str]) -> Tuple[str, str]:
    """Resolve explicit direct endpoint credentials from config/env."""
    base_url = overrides.get("base_url", "").strip()
    api_key = overrides.get("api_key", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()
    return base_url, api_key


def _build_custom_auxiliary_client(
    base_url: str,
    api_key: str,
    model: Optional[str] = None,
) -> Tuple[Optional[OpenAI], Optional[str]]:
    """Build a direct OpenAI-compatible auxiliary client."""
    if not (base_url and api_key):
        return None, None
    resolved_model = model or os.getenv("OPENAI_MODEL") or os.getenv("LLM_MODEL") or "gpt-4o-mini"
    return OpenAI(api_key=api_key, base_url=base_url), resolved_model


def _chat_content_to_text(content: Any) -> str:
    """Extract text from chat.completions-style message content."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content or "")

    parts: List[str] = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
            continue
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type in {"text", "input_text", "output_text"}:
            text = item.get("text")
            if isinstance(text, str) and text:
                parts.append(text)
    return "\n".join(part for part in parts if part).strip()


def _chat_content_to_responses_content(content: Any) -> Any:
    """Convert chat.completions content into Responses input content."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        text = str(content or "")
        return text if text else ""

    converted: List[Dict[str, Any]] = []
    for item in content:
        if isinstance(item, str):
            if item:
                converted.append({"type": "input_text", "text": item})
            continue
        if not isinstance(item, dict):
            continue

        item_type = item.get("type")
        if item_type in {"text", "input_text", "output_text"}:
            text = item.get("text")
            if isinstance(text, str) and text:
                converted.append({"type": "input_text", "text": text})
            continue

        if item_type in {"image_url", "input_image"}:
            image_url = item.get("image_url")
            detail = item.get("detail")
            if isinstance(image_url, dict):
                detail = image_url.get("detail", detail)
                image_url = image_url.get("url") or image_url.get("image_url")
            if isinstance(image_url, str) and image_url:
                payload: Dict[str, Any] = {
                    "type": "input_image",
                    "image_url": image_url,
                }
                if isinstance(detail, str) and detail:
                    payload["detail"] = detail
                converted.append(payload)

    if not converted:
        return _chat_content_to_text(content)
    return converted


# ── Codex Responses → chat.completions adapter ─────────────────────────────
# All auxiliary consumers call client.chat.completions.create(**kwargs) and
# read response.choices[0].message.content. This adapter translates those
# calls to the Codex Responses API so callers don't need any changes.

class _CodexCompletionsAdapter:
    """Drop-in shim that accepts chat.completions.create() kwargs and
    routes them through the Codex Responses streaming API."""

    def __init__(self, real_client: OpenAI, model: str):
        self._client = real_client
        self._model = model

    def create(self, **kwargs) -> Any:
        messages = kwargs.get("messages", [])
        model = kwargs.get("model", self._model)

        # Separate system/instructions from conversation messages
        instructions = "You are a helpful assistant."
        input_msgs: List[Dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content") or ""
            if role == "system":
                instructions = _chat_content_to_text(content) or instructions
            else:
                input_msgs.append({
                    "role": role,
                    "content": _chat_content_to_responses_content(content),
                })

        resp_kwargs: Dict[str, Any] = {
            "model": model,
            "instructions": instructions,
            "input": input_msgs or [{"role": "user", "content": ""}],
            "store": False,
        }

        # Tools support for flush_memories and similar callers
        tools = kwargs.get("tools")
        if tools:
            converted = []
            for t in tools:
                fn = t.get("function", {}) if isinstance(t, dict) else {}
                name = fn.get("name")
                if not name:
                    continue
                converted.append({
                    "type": "function",
                    "name": name,
                    "description": fn.get("description", ""),
                    "parameters": fn.get("parameters", {}),
                })
            if converted:
                resp_kwargs["tools"] = converted

        # Stream and collect the response
        text_parts: List[str] = []
        tool_calls_raw: List[Any] = []
        usage = None

        try:
            with self._client.responses.stream(**resp_kwargs) as stream:
                for _event in stream:
                    pass
                final = stream.get_final_response()

            # Extract text and tool calls from the Responses output
            for item in getattr(final, "output", []):
                item_type = getattr(item, "type", None)
                if item_type == "message":
                    for part in getattr(item, "content", []):
                        ptype = getattr(part, "type", None)
                        if ptype in ("output_text", "text"):
                            text_parts.append(getattr(part, "text", ""))
                elif item_type == "function_call":
                    tool_calls_raw.append(SimpleNamespace(
                        id=getattr(item, "call_id", ""),
                        type="function",
                        function=SimpleNamespace(
                            name=getattr(item, "name", ""),
                            arguments=getattr(item, "arguments", "{}"),
                        ),
                    ))

            resp_usage = getattr(final, "usage", None)
            if resp_usage:
                usage = SimpleNamespace(
                    prompt_tokens=getattr(resp_usage, "input_tokens", 0),
                    completion_tokens=getattr(resp_usage, "output_tokens", 0),
                    total_tokens=getattr(resp_usage, "total_tokens", 0),
                )
        except Exception as exc:
            logger.debug("Codex auxiliary Responses API call failed: %s", exc)
            raise

        content = "".join(text_parts).strip() or None

        # Build a response that looks like chat.completions
        message = SimpleNamespace(
            role="assistant",
            content=content,
            tool_calls=tool_calls_raw or None,
        )
        choice = SimpleNamespace(
            index=0,
            message=message,
            finish_reason="stop" if not tool_calls_raw else "tool_calls",
        )
        return SimpleNamespace(
            choices=[choice],
            model=model,
            usage=usage,
        )


class _CodexChatShim:
    """Wraps the adapter to provide client.chat.completions.create()."""

    def __init__(self, adapter: _CodexCompletionsAdapter):
        self.completions = adapter


class CodexAuxiliaryClient:
    """OpenAI-client-compatible wrapper that routes through Codex Responses API.

    Consumers can call client.chat.completions.create(**kwargs) as normal.
    Also exposes .api_key and .base_url for introspection by async wrappers.
    """

    def __init__(self, real_client: OpenAI, model: str):
        self._real_client = real_client
        adapter = _CodexCompletionsAdapter(real_client, model)
        self.chat = _CodexChatShim(adapter)
        self.api_key = real_client.api_key
        self.base_url = real_client.base_url

    def close(self):
        self._real_client.close()


class _AsyncCodexCompletionsAdapter:
    """Async version of the Codex Responses adapter.

    Wraps the sync adapter via asyncio.to_thread() so async consumers
    (web_tools, session_search) can await it as normal.
    """

    def __init__(self, sync_adapter: _CodexCompletionsAdapter):
        self._sync = sync_adapter

    async def create(self, **kwargs) -> Any:
        import asyncio
        return await asyncio.to_thread(self._sync.create, **kwargs)


class _AsyncCodexChatShim:
    def __init__(self, adapter: _AsyncCodexCompletionsAdapter):
        self.completions = adapter


class AsyncCodexAuxiliaryClient:
    """Async-compatible wrapper matching AsyncOpenAI.chat.completions.create()."""

    def __init__(self, sync_wrapper: "CodexAuxiliaryClient"):
        sync_adapter = sync_wrapper.chat.completions
        async_adapter = _AsyncCodexCompletionsAdapter(sync_adapter)
        self.chat = _AsyncCodexChatShim(async_adapter)
        self.api_key = sync_wrapper.api_key
        self.base_url = sync_wrapper.base_url


def _read_nous_auth() -> Optional[dict]:
    """Read and validate ~/.hermes/auth.json for an active Nous provider.

    Returns the provider state dict if Nous is active with tokens,
    otherwise None.
    """
    try:
        if not _AUTH_JSON_PATH.is_file():
            return None
        data = json.loads(_AUTH_JSON_PATH.read_text())
        if data.get("active_provider") != "nous":
            return None
        provider = data.get("providers", {}).get("nous", {})
        # Must have at least an access_token or agent_key
        if not provider.get("agent_key") and not provider.get("access_token"):
            return None
        return provider
    except Exception as exc:
        logger.debug("Could not read Nous auth: %s", exc)
        return None


def _nous_api_key(provider: dict) -> str:
    """Extract the best API key from a Nous provider state dict."""
    return provider.get("agent_key") or provider.get("access_token", "")


def _nous_base_url() -> str:
    """Resolve the Nous inference base URL from env or default."""
    return os.getenv("NOUS_INFERENCE_BASE_URL", _NOUS_DEFAULT_BASE_URL)


def _read_codex_access_token() -> Optional[str]:
    """Read a usable Codex OAuth access token from Hermes auth store."""
    try:
        from hermes_cli.auth import resolve_codex_runtime_credentials

        data = resolve_codex_runtime_credentials()
        access_token = data.get("api_key")
        if isinstance(access_token, str) and access_token.strip():
            return access_token.strip()
        return None
    except Exception as exc:
        logger.debug("Could not read Codex auth for auxiliary client: %s", exc)
        return None


def _normalize_provider_name(value: str) -> str:
    raw = (value or "").strip().lower()
    return _PROVIDER_ALIASES.get(raw, raw)


def _resolve_auto_provider_preference() -> str:
    """Best-effort provider hint for auto mode.

    Priority:
    1. HERMES_INFERENCE_PROVIDER env var
    2. ~/.hermes/config.yaml -> model.provider
    3. ~/.hermes/auth.json -> active_provider
    """
    env_pref = _normalize_provider_name(os.getenv("HERMES_INFERENCE_PROVIDER", ""))
    if env_pref and env_pref != "auto":
        return env_pref

    try:
        if _CONFIG_YAML_PATH.is_file():
            import yaml

            data = yaml.safe_load(_CONFIG_YAML_PATH.read_text(encoding="utf-8")) or {}
            model_cfg = data.get("model", {})
            if isinstance(model_cfg, dict):
                cfg_pref = _normalize_provider_name(str(model_cfg.get("provider", "")))
                if cfg_pref and cfg_pref != "auto":
                    return cfg_pref
    except Exception as exc:
        logger.debug("Could not read model.provider from config for auxiliary client: %s", exc)

    try:
        from hermes_cli.auth import get_active_provider

        active_provider = _normalize_provider_name(get_active_provider() or "")
        if active_provider and active_provider != "auto":
            return active_provider
    except Exception as exc:
        logger.debug("Could not read active_provider for auxiliary client: %s", exc)

    return "auto"


def _to_async_client(sync_client: Any, model: Optional[str]):
    """Convert a sync auxiliary client to its async counterpart."""
    from openai import AsyncOpenAI

    if isinstance(sync_client, CodexAuxiliaryClient):
        return AsyncCodexAuxiliaryClient(sync_client), model

    async_kwargs = {
        "api_key": sync_client.api_key,
        "base_url": str(sync_client.base_url),
    }
    base_lower = str(sync_client.base_url).lower()
    if "openrouter" in base_lower:
        async_kwargs["default_headers"] = dict(_OR_HEADERS)
    return AsyncOpenAI(**async_kwargs), model


def _infer_task_kind(task: Optional[str]) -> str:
    """Return 'vision' for multimodal tasks, else 'text'."""
    task_name = (task or "").strip().lower()
    if task_name in {"vision", "browser_vision", "browser-vision"}:
        return "vision"
    return "text"


def _resolve_task_provider_model(
    task: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Tuple[str, Optional[str], str, Optional[str], Optional[str]]:
    """Resolve provider/model intent for a task without creating a client."""
    task_kind = _infer_task_kind(task)
    overrides = _get_task_auxiliary_overrides(task, task_kind)

    if base_url:
        return "custom", model or overrides.get("model"), task_kind, base_url, api_key
    if provider:
        return _normalize_provider_name(provider), model or overrides.get("model"), task_kind, None, None

    cfg_provider = _normalize_provider_name(overrides.get("provider", ""))
    cfg_model = overrides.get("model") or model
    cfg_base_url = overrides.get("base_url")
    cfg_api_key = overrides.get("api_key")
    if cfg_base_url:
        return "custom", cfg_model, task_kind, cfg_base_url, cfg_api_key
    if cfg_provider and cfg_provider != "auto":
        return cfg_provider, cfg_model, task_kind, None, None

    env_provider = _normalize_provider_name(os.getenv(_AUX_PROVIDER_ENV, "auto"))
    if env_provider and env_provider != "auto":
        return env_provider, cfg_model, task_kind, None, None

    preferred = _resolve_auto_provider_preference()
    return preferred or "auto", cfg_model, task_kind, None, None


def resolve_provider_client(
    provider: str,
    model: Optional[str] = None,
    async_mode: bool = False,
    raw_codex: bool = False,
    task_kind: str = "text",
    task: Optional[str] = None,
    explicit_base_url: Optional[str] = None,
    explicit_api_key: Optional[str] = None,
) -> Tuple[Optional[Any], Optional[str]]:
    """Central entry point for provider-specific auxiliary client resolution.

    This Stage 1 wrapper preserves the existing local provider behavior while
    giving consumers a single place to ask for a configured client.
    """
    normalized_provider = _normalize_provider_name(provider or "auto")
    task_kind = "vision" if task_kind == "vision" else "text"
    overrides = _get_task_auxiliary_overrides(task, task_kind)

    if normalized_provider == "auto":
        if explicit_base_url:
            client, resolved_model = _build_custom_auxiliary_client(
                explicit_base_url,
                (explicit_api_key or "").strip() or os.getenv("OPENAI_API_KEY", "").strip(),
                model or overrides.get("model"),
            )
            if client is None:
                return None, None
            final_model = model or resolved_model
            return _to_async_client(client, final_model) if async_mode else (client, final_model)
        if task_kind == "vision":
            client, resolved_model = get_vision_auxiliary_client(task or task_kind)
        else:
            client, resolved_model = get_text_auxiliary_client(task or task_kind)
        if client is None:
            return None, None
        final_model = model or resolved_model
        return _to_async_client(client, final_model) if async_mode else (client, final_model)

    if normalized_provider == "openrouter":
        or_key = os.getenv("OPENROUTER_API_KEY")
        if not or_key:
            return None, None
        resolved_model = model or overrides.get("model") or _OPENROUTER_MODEL
        client = OpenAI(
            api_key=or_key,
            base_url=OPENROUTER_BASE_URL,
            default_headers=_OR_HEADERS,
        )
        return _to_async_client(client, resolved_model) if async_mode else (client, resolved_model)

    if normalized_provider == "nous":
        global auxiliary_is_nous
        nous = _read_nous_auth()
        if not nous:
            return None, None
        auxiliary_is_nous = True
        resolved_model = model or overrides.get("model") or _NOUS_MODEL
        client = OpenAI(api_key=_nous_api_key(nous), base_url=_nous_base_url())
        return _to_async_client(client, resolved_model) if async_mode else (client, resolved_model)

    if normalized_provider == "custom":
        base_url = (explicit_base_url or "").strip()
        api_key = (explicit_api_key or "").strip()
        if not base_url:
            base_url, api_key = _resolve_auxiliary_direct_credentials(overrides)
        if not base_url:
            base_url = os.getenv("OPENAI_BASE_URL", "").strip()
        client, resolved_model = _build_custom_auxiliary_client(
            base_url,
            api_key,
            model or overrides.get("model"),
        )
        if client is None:
            return None, None
        return _to_async_client(client, resolved_model) if async_mode else (client, resolved_model)

    if normalized_provider == "openai-codex":
        codex_token = _read_codex_access_token()
        if not codex_token:
            return None, None
        resolved_model = model or _CODEX_AUX_MODEL
        real_client = OpenAI(api_key=codex_token, base_url=_CODEX_AUX_BASE_URL)
        if raw_codex:
            return real_client, resolved_model
        wrapped = CodexAuxiliaryClient(real_client, resolved_model)
        return _to_async_client(wrapped, resolved_model) if async_mode else (wrapped, resolved_model)

    logger.warning("resolve_provider_client: unknown provider %r", provider)
    return None, None


def _build_llm_call_kwargs(
    client: Any,
    model: str,
    messages: list,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    tools: Optional[list] = None,
    timeout: float = 30.0,
    extra_body: Optional[dict] = None,
    base_url: Optional[str] = None,
) -> dict:
    """Build provider-aware kwargs for chat.completions.create()."""
    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "timeout": timeout,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        base_lower = str(base_url or getattr(client, "base_url", "")).lower()
        if "api.openai.com" in base_lower:
            kwargs["max_completion_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = max_tokens
    if tools:
        kwargs["tools"] = tools

    merged_extra = dict(extra_body or {})
    if auxiliary_is_nous:
        existing_tags = merged_extra.get("tags")
        if isinstance(existing_tags, list):
            if "product=hermes-agent" not in existing_tags:
                existing_tags.append("product=hermes-agent")
        elif not merged_extra:
            merged_extra = dict(NOUS_EXTRA_BODY)
        else:
            merged_extra["tags"] = ["product=hermes-agent"]
    if merged_extra:
        kwargs["extra_body"] = merged_extra
    return kwargs


def call_llm(
    task: Optional[str] = None,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    messages: list,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    tools: Optional[list] = None,
    timeout: float = 30.0,
    extra_body: Optional[dict] = None,
) -> Any:
    """Centralized synchronous auxiliary LLM call."""
    resolved_provider, resolved_model, task_kind, resolved_base_url, resolved_api_key = _resolve_task_provider_model(
        task=task,
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
    )
    client, final_model = resolve_provider_client(
        resolved_provider,
        model=resolved_model,
        async_mode=False,
        task_kind=task_kind,
        task=task,
        explicit_base_url=resolved_base_url,
        explicit_api_key=resolved_api_key,
    )
    if client is None or final_model is None:
        raise RuntimeError(
            f"No LLM provider configured for task={task or task_kind} provider={resolved_provider}. "
            "Run: hermes setup"
        )

    kwargs = _build_llm_call_kwargs(
        client,
        final_model,
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        tools=tools,
        timeout=timeout,
        extra_body=extra_body,
        base_url=resolved_base_url,
    )
    return client.chat.completions.create(**kwargs)


async def async_call_llm(
    task: Optional[str] = None,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    messages: list,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    tools: Optional[list] = None,
    timeout: float = 30.0,
    extra_body: Optional[dict] = None,
) -> Any:
    """Centralized asynchronous auxiliary LLM call."""
    resolved_provider, resolved_model, task_kind, resolved_base_url, resolved_api_key = _resolve_task_provider_model(
        task=task,
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
    )
    client, final_model = resolve_provider_client(
        resolved_provider,
        model=resolved_model,
        async_mode=True,
        task_kind=task_kind,
        task=task,
        explicit_base_url=resolved_base_url,
        explicit_api_key=resolved_api_key,
    )
    if client is None or final_model is None:
        raise RuntimeError(
            f"No LLM provider configured for task={task or task_kind} provider={resolved_provider}. "
            "Run: hermes setup"
        )

    kwargs = _build_llm_call_kwargs(
        client,
        final_model,
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        tools=tools,
        timeout=timeout,
        extra_body=extra_body,
        base_url=resolved_base_url,
    )
    return await client.chat.completions.create(**kwargs)


# ── Public API ──────────────────────────────────────────────────────────────

def get_text_auxiliary_client(task: str = "text") -> Tuple[Optional[OpenAI], Optional[str]]:
    """Return (client, model_slug) for text-only auxiliary tasks.

    Falls through OpenRouter -> Nous Portal -> custom endpoint -> Codex OAuth -> (None, None).
    """
    global auxiliary_is_nous
    auxiliary_is_nous = False

    text_overrides = _get_task_auxiliary_overrides(task, "text")
    forced_provider_raw = text_overrides.get("provider") or os.getenv(_AUX_PROVIDER_ENV, "auto").strip().lower()
    forced_provider = _normalize_provider_name(forced_provider_raw)
    valid_providers = {"auto", "openrouter", "nous", "custom", "openai-codex"}
    if forced_provider not in valid_providers:
        logger.warning(
            "Unknown %s value '%s'; using auto auxiliary provider selection",
            _AUX_PROVIDER_ENV,
            forced_provider_raw,
        )
        forced_provider = "auto"

    if forced_provider == "auto":
        override_base_url, override_api_key = _resolve_auxiliary_direct_credentials(text_overrides)
        if override_base_url:
            client, model = _build_custom_auxiliary_client(
                override_base_url,
                override_api_key,
                text_overrides.get("model"),
            )
            if client is None:
                logger.warning(
                    "auxiliary.text.base_url is set but no API key is available "
                    "(set auxiliary.text.api_key or OPENAI_API_KEY)"
                )
                return None, None
            logger.debug("Auxiliary text client: direct override (%s)", model)
            return client, model

    # Explicit provider selection (strict): if a forced provider is selected
    # but not configured, return no client rather than silently falling through.
    if forced_provider == "openrouter":
        or_key = os.getenv("OPENROUTER_API_KEY")
        if not or_key:
            logger.warning("%s=openrouter but OPENROUTER_API_KEY is not set", _AUX_PROVIDER_ENV)
            return None, None
        logger.debug("Auxiliary text client: OpenRouter (forced)")
        return (
            OpenAI(api_key=or_key, base_url=OPENROUTER_BASE_URL, default_headers=_OR_HEADERS),
            _OPENROUTER_MODEL,
        )
    if forced_provider == "nous":
        nous = _read_nous_auth()
        if not nous:
            logger.warning("%s=nous but no active Nous auth was found", _AUX_PROVIDER_ENV)
            return None, None
        auxiliary_is_nous = True
        logger.debug("Auxiliary text client: Nous Portal (forced)")
        return (
            OpenAI(api_key=_nous_api_key(nous), base_url=_nous_base_url()),
            _NOUS_MODEL,
        )
    if forced_provider == "custom":
        custom_base = os.getenv("OPENAI_BASE_URL")
        custom_key = os.getenv("OPENAI_API_KEY")
        if not (custom_base and custom_key):
            logger.warning(
                "%s=custom but OPENAI_BASE_URL/OPENAI_API_KEY are not fully configured",
                _AUX_PROVIDER_ENV,
            )
            return None, None
        model = text_overrides.get("model") or os.getenv("OPENAI_MODEL") or os.getenv("LLM_MODEL") or "gpt-4o-mini"
        logger.debug("Auxiliary text client: custom endpoint (%s, forced)", model)
        return OpenAI(api_key=custom_key, base_url=custom_base), model
    if forced_provider == "openai-codex":
        codex_token = _read_codex_access_token()
        if not codex_token:
            logger.warning("%s=openai-codex but no Codex token was found", _AUX_PROVIDER_ENV)
            return None, None
        logger.debug("Auxiliary text client: Codex OAuth (%s, forced)", _CODEX_AUX_MODEL)
        real_client = OpenAI(api_key=codex_token, base_url=_CODEX_AUX_BASE_URL)
        return CodexAuxiliaryClient(real_client, _CODEX_AUX_MODEL), _CODEX_AUX_MODEL

    # Auto mode: if the runtime provider is explicitly selected, keep using it.
    if forced_provider == "auto":
        preferred_provider = _normalize_provider_name(text_overrides.get("provider", ""))
        if not preferred_provider:
            preferred_provider = _resolve_auto_provider_preference()
        if preferred_provider == "openai-codex":
            codex_token = _read_codex_access_token()
            if codex_token:
                logger.debug(
                    "Auxiliary text client: Codex OAuth (%s via runtime provider preference)",
                    _CODEX_AUX_MODEL,
                )
                real_client = OpenAI(api_key=codex_token, base_url=_CODEX_AUX_BASE_URL)
                return CodexAuxiliaryClient(real_client, _CODEX_AUX_MODEL), _CODEX_AUX_MODEL
            return None, None
        if preferred_provider == "openrouter":
            or_key = os.getenv("OPENROUTER_API_KEY")
            if not or_key:
                return None, None
            logger.debug("Auxiliary text client: OpenRouter (via runtime provider preference)")
            return (
                OpenAI(api_key=or_key, base_url=OPENROUTER_BASE_URL, default_headers=_OR_HEADERS),
                text_overrides.get("model") or _OPENROUTER_MODEL,
            )
        if preferred_provider == "nous":
            nous = _read_nous_auth()
            if not nous:
                return None, None
            auxiliary_is_nous = True
            logger.debug("Auxiliary text client: Nous Portal (via runtime provider preference)")
            return (
                OpenAI(api_key=_nous_api_key(nous), base_url=_nous_base_url()),
                text_overrides.get("model") or _NOUS_MODEL,
            )
        if preferred_provider == "custom":
            custom_base = os.getenv("OPENAI_BASE_URL")
            custom_key = os.getenv("OPENAI_API_KEY")
            if not (custom_base and custom_key):
                return None, None
            model = text_overrides.get("model") or os.getenv("OPENAI_MODEL") or os.getenv("LLM_MODEL") or "gpt-4o-mini"
            logger.debug("Auxiliary text client: custom endpoint (%s via runtime provider preference)", model)
            return OpenAI(api_key=custom_key, base_url=custom_base), model

    # 1. OpenRouter
    or_key = os.getenv("OPENROUTER_API_KEY")
    if or_key:
        logger.debug("Auxiliary text client: OpenRouter")
        return OpenAI(api_key=or_key, base_url=OPENROUTER_BASE_URL,
                       default_headers=_OR_HEADERS), text_overrides.get("model") or _OPENROUTER_MODEL

    # 2. Nous Portal
    nous = _read_nous_auth()
    if nous:
        auxiliary_is_nous = True
        logger.debug("Auxiliary text client: Nous Portal")
        return (
            OpenAI(api_key=_nous_api_key(nous), base_url=_nous_base_url()),
            text_overrides.get("model") or _NOUS_MODEL,
        )

    # 3. Custom endpoint (both base URL and key must be set)
    custom_base = os.getenv("OPENAI_BASE_URL")
    custom_key = os.getenv("OPENAI_API_KEY")
    if custom_base and custom_key:
        model = text_overrides.get("model") or os.getenv("OPENAI_MODEL") or os.getenv("LLM_MODEL") or "gpt-4o-mini"
        logger.debug("Auxiliary text client: custom endpoint (%s)", model)
        return OpenAI(api_key=custom_key, base_url=custom_base), model

    # 4. Codex OAuth -- uses the Responses API (only endpoint the token
    # can access), wrapped to look like a chat.completions client.
    codex_token = _read_codex_access_token()
    if codex_token:
        logger.debug("Auxiliary text client: Codex OAuth (%s via Responses API)", _CODEX_AUX_MODEL)
        real_client = OpenAI(api_key=codex_token, base_url=_CODEX_AUX_BASE_URL)
        return CodexAuxiliaryClient(real_client, _CODEX_AUX_MODEL), _CODEX_AUX_MODEL

    # 5. Nothing available
    logger.debug("Auxiliary text client: none available")
    return None, None


def get_async_text_auxiliary_client(task: str = "text"):
    """Return (async_client, model_slug) for async consumers.

    For standard providers returns (AsyncOpenAI, model). For Codex returns
    (AsyncCodexAuxiliaryClient, model) which wraps the Responses API.
    Returns (None, None) when no provider is available.
    """
    from openai import AsyncOpenAI

    sync_client, model = get_text_auxiliary_client(task)
    if sync_client is None:
        return None, None

    if isinstance(sync_client, CodexAuxiliaryClient):
        return AsyncCodexAuxiliaryClient(sync_client), model

    async_kwargs = {
        "api_key": sync_client.api_key,
        "base_url": str(sync_client.base_url),
    }
    if "openrouter" in str(sync_client.base_url).lower():
        async_kwargs["default_headers"] = dict(_OR_HEADERS)
    return AsyncOpenAI(**async_kwargs), model


def get_vision_auxiliary_client(task: str = "vision") -> Tuple[Optional[OpenAI], Optional[str]]:
    """Return (client, model_slug) for vision/multimodal auxiliary tasks.

    Falls through OpenRouter -> Nous Portal -> Codex OAuth -> (None, None).
    Custom endpoints are not assumed to provide multimodal compatibility.
    """
    vision_overrides = _get_task_auxiliary_overrides(task, "vision")
    forced_provider_raw = vision_overrides.get("provider") or os.getenv(_AUX_PROVIDER_ENV, "auto").strip().lower()
    forced_provider = _normalize_provider_name(forced_provider_raw)
    valid_providers = {"auto", "openrouter", "nous", "custom", "openai-codex"}
    if forced_provider not in valid_providers:
        logger.warning(
            "Unknown %s value '%s'; using auto auxiliary provider selection",
            _AUX_PROVIDER_ENV,
            forced_provider_raw,
        )
        forced_provider = "auto"

    if forced_provider == "auto":
        override_base_url, override_api_key = _resolve_auxiliary_direct_credentials(vision_overrides)
        if override_base_url:
            client, model = _build_custom_auxiliary_client(
                override_base_url,
                override_api_key,
                vision_overrides.get("model"),
            )
            if client is None:
                logger.warning(
                    "auxiliary.vision.base_url is set but no API key is available "
                    "(set auxiliary.vision.api_key or OPENAI_API_KEY)"
                )
                return None, None
            logger.debug("Auxiliary vision client: direct override (%s)", model)
            return client, model

    if forced_provider == "openrouter":
        or_key = os.getenv("OPENROUTER_API_KEY")
        if not or_key:
            logger.warning("%s=openrouter but OPENROUTER_API_KEY is not set", _AUX_PROVIDER_ENV)
            return None, None
        logger.debug("Auxiliary vision client: OpenRouter (forced)")
        return OpenAI(api_key=or_key, base_url=OPENROUTER_BASE_URL,
                      default_headers=_OR_HEADERS), vision_overrides.get("model") or _OPENROUTER_MODEL

    if forced_provider == "nous":
        nous = _read_nous_auth()
        if not nous:
            logger.warning("%s=nous but no active Nous auth was found", _AUX_PROVIDER_ENV)
            return None, None
        logger.debug("Auxiliary vision client: Nous Portal (forced)")
        return OpenAI(api_key=_nous_api_key(nous), base_url=_nous_base_url()), vision_overrides.get("model") or _NOUS_MODEL

    if forced_provider == "custom":
        custom_base = os.getenv("OPENAI_BASE_URL")
        custom_key = os.getenv("OPENAI_API_KEY")
        client, model = _build_custom_auxiliary_client(
            custom_base,
            custom_key,
            vision_overrides.get("model"),
        )
        if client is None:
            logger.warning(
                "%s=custom but OPENAI_BASE_URL/OPENAI_API_KEY are not fully configured",
                _AUX_PROVIDER_ENV,
            )
            return None, None
        logger.debug("Auxiliary vision client: custom endpoint (%s, forced)", model)
        return client, model

    if forced_provider == "openai-codex":
        codex_token = _read_codex_access_token()
        if not codex_token:
            logger.warning("%s=openai-codex but no Codex token was found", _AUX_PROVIDER_ENV)
            return None, None
        logger.debug("Auxiliary vision client: Codex OAuth (%s, forced)", _CODEX_AUX_MODEL)
        real_client = OpenAI(api_key=codex_token, base_url=_CODEX_AUX_BASE_URL)
        return CodexAuxiliaryClient(real_client, _CODEX_AUX_MODEL), _CODEX_AUX_MODEL

    if forced_provider == "auto":
        preferred_provider = _normalize_provider_name(vision_overrides.get("provider", ""))
        if not preferred_provider:
            preferred_provider = _resolve_auto_provider_preference()
        if preferred_provider == "openai-codex":
            codex_token = _read_codex_access_token()
            if codex_token:
                logger.debug(
                    "Auxiliary vision client: Codex OAuth (%s via runtime provider preference)",
                    _CODEX_AUX_MODEL,
                )
                real_client = OpenAI(api_key=codex_token, base_url=_CODEX_AUX_BASE_URL)
                return CodexAuxiliaryClient(real_client, _CODEX_AUX_MODEL), _CODEX_AUX_MODEL
            return None, None
        if preferred_provider == "openrouter":
            or_key = os.getenv("OPENROUTER_API_KEY")
            if not or_key:
                return None, None
            logger.debug("Auxiliary vision client: OpenRouter (via runtime provider preference)")
            return OpenAI(api_key=or_key, base_url=OPENROUTER_BASE_URL,
                          default_headers=_OR_HEADERS), vision_overrides.get("model") or _OPENROUTER_MODEL
        if preferred_provider == "nous":
            nous = _read_nous_auth()
            if not nous:
                return None, None
            logger.debug("Auxiliary vision client: Nous Portal (via runtime provider preference)")
            return OpenAI(api_key=_nous_api_key(nous), base_url=_nous_base_url()), vision_overrides.get("model") or _NOUS_MODEL
        if preferred_provider == "custom":
            custom_base = os.getenv("OPENAI_BASE_URL")
            custom_key = os.getenv("OPENAI_API_KEY")
            client, model = _build_custom_auxiliary_client(
                custom_base,
                custom_key,
                vision_overrides.get("model"),
            )
            return client, model

    # 1. OpenRouter
    or_key = os.getenv("OPENROUTER_API_KEY")
    if or_key:
        logger.debug("Auxiliary vision client: OpenRouter")
        return OpenAI(api_key=or_key, base_url=OPENROUTER_BASE_URL,
                       default_headers=_OR_HEADERS), vision_overrides.get("model") or _OPENROUTER_MODEL

    # 2. Nous Portal
    nous = _read_nous_auth()
    if nous:
        logger.debug("Auxiliary vision client: Nous Portal")
        return (
            OpenAI(api_key=_nous_api_key(nous), base_url=_nous_base_url()),
            vision_overrides.get("model") or _NOUS_MODEL,
        )

    # 3. Codex OAuth
    codex_token = _read_codex_access_token()
    if codex_token:
        logger.debug("Auxiliary vision client: Codex OAuth (%s via Responses API)", _CODEX_AUX_MODEL)
        real_client = OpenAI(api_key=codex_token, base_url=_CODEX_AUX_BASE_URL)
        return CodexAuxiliaryClient(real_client, _CODEX_AUX_MODEL), _CODEX_AUX_MODEL

    # 4. Nothing suitable
    logger.debug("Auxiliary vision client: none available")
    return None, None


def get_async_vision_auxiliary_client(task: str = "vision"):
    """Return (async_client, model_slug) for async multimodal auxiliary tasks."""
    from openai import AsyncOpenAI

    sync_client, model = get_vision_auxiliary_client(task)
    if sync_client is None:
        return None, None

    if isinstance(sync_client, CodexAuxiliaryClient):
        return AsyncCodexAuxiliaryClient(sync_client), model

    async_kwargs = {
        "api_key": sync_client.api_key,
        "base_url": str(sync_client.base_url),
    }
    if "openrouter" in str(sync_client.base_url).lower():
        async_kwargs["default_headers"] = dict(_OR_HEADERS)
    return AsyncOpenAI(**async_kwargs), model


def get_auxiliary_extra_body() -> dict:
    """Return extra_body kwargs for auxiliary API calls.

    Includes Nous Portal product tags when the auxiliary client is backed
    by Nous Portal. Returns empty dict otherwise.
    """
    return dict(NOUS_EXTRA_BODY) if auxiliary_is_nous else {}


def auxiliary_max_tokens_param(value: int) -> dict:
    """Return the correct max tokens kwarg for the auxiliary client's provider.

    OpenRouter and local models use 'max_tokens'. Direct OpenAI with newer
    models (gpt-4o, o-series, gpt-5+) requires 'max_completion_tokens'.
    The Codex adapter translates max_tokens internally, so we use max_tokens
    for it as well.
    """
    text_overrides = _get_auxiliary_overrides("text")
    custom_base = text_overrides.get("base_url") or os.getenv("OPENAI_BASE_URL", "")
    or_key = os.getenv("OPENROUTER_API_KEY")
    # Only use max_completion_tokens for direct OpenAI custom endpoints
    if (not or_key
            and _read_nous_auth() is None
            and "api.openai.com" in custom_base.lower()):
        return {"max_completion_tokens": value}
    return {"max_tokens": value}
