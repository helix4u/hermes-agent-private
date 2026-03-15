"""Anthropic Messages API adapter for Hermes Agent.

This module keeps native Anthropic provider logic isolated from the main
agent loop by translating between Hermes's internal OpenAI-style message
format and Anthropic's Messages API.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

try:
    import anthropic as _anthropic_sdk
except ImportError:
    _anthropic_sdk = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com"
THINKING_BUDGET = {"xhigh": 32000, "high": 16000, "medium": 8000, "low": 4000}
ADAPTIVE_EFFORT_MAP = {
    "xhigh": "max",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "minimal": "low",
}

_COMMON_BETAS = [
    "interleaved-thinking-2025-05-14",
    "fine-grained-tool-streaming-2025-05-14",
]
_OAUTH_ONLY_BETAS = [
    "claude-code-20250219",
    "oauth-2025-04-20",
]


def _supports_adaptive_thinking(model: str) -> bool:
    return any(v in model for v in ("4-6", "4.6"))


def _is_oauth_token(key: str) -> bool:
    if not key:
        return False
    if key.startswith("sk-ant-api"):
        return False
    return True


def build_anthropic_client(api_key: str, base_url: str | None = None):
    """Create an Anthropic client, handling API-key vs OAuth token auth."""
    if _anthropic_sdk is None:
        raise ImportError(
            "The 'anthropic' package is required for the native Anthropic provider. "
            "Install it with: pip install anthropic>=0.39.0"
        )

    from httpx import Timeout

    kwargs: Dict[str, Any] = {
        "timeout": Timeout(timeout=900.0, connect=10.0),
    }
    if base_url:
        kwargs["base_url"] = base_url.rstrip("/")

    if _is_oauth_token(api_key):
        kwargs["auth_token"] = api_key
        kwargs["default_headers"] = {"anthropic-beta": ",".join(_COMMON_BETAS + _OAUTH_ONLY_BETAS)}
    else:
        kwargs["api_key"] = api_key
        kwargs["default_headers"] = {"anthropic-beta": ",".join(_COMMON_BETAS)}

    return _anthropic_sdk.Anthropic(**kwargs)


def read_claude_code_credentials() -> Optional[Dict[str, Any]]:
    """Read refreshable Claude Code OAuth credentials from ~/.claude/.credentials.json."""
    cred_path = Path.home() / ".claude" / ".credentials.json"
    if not cred_path.exists():
        return None
    try:
        data = json.loads(cred_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, IOError) as exc:
        logger.debug("Failed to read Claude Code credentials: %s", exc)
        return None

    oauth_data = data.get("claudeAiOauth")
    if not isinstance(oauth_data, dict):
        return None
    access_token = str(oauth_data.get("accessToken") or "").strip()
    if not access_token:
        return None
    return {
        "accessToken": access_token,
        "refreshToken": str(oauth_data.get("refreshToken") or "").strip(),
        "expiresAt": oauth_data.get("expiresAt", 0),
        "source": "claude_code_credentials_file",
    }


def read_claude_managed_key() -> Optional[str]:
    """Read Claude's native managed key from ~/.claude.json for diagnostics only."""
    claude_json = Path.home() / ".claude.json"
    if not claude_json.exists():
        return None
    try:
        data = json.loads(claude_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, IOError) as exc:
        logger.debug("Failed to read ~/.claude.json: %s", exc)
        return None
    primary_key = data.get("primaryApiKey", "")
    if isinstance(primary_key, str) and primary_key.strip():
        return primary_key.strip()
    return None


def is_claude_code_token_valid(creds: Dict[str, Any]) -> bool:
    import time

    expires_at = creds.get("expiresAt", 0)
    if not expires_at:
        return bool(creds.get("accessToken"))

    now_ms = int(time.time() * 1000)
    return now_ms < (int(expires_at) - 60_000)


def _write_claude_code_credentials(access_token: str, refresh_token: str, expires_at_ms: int) -> None:
    cred_path = Path.home() / ".claude" / ".credentials.json"
    try:
        existing: Dict[str, Any] = {}
        if cred_path.exists():
            existing = json.loads(cred_path.read_text(encoding="utf-8"))
        existing["claudeAiOauth"] = {
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "expiresAt": expires_at_ms,
        }
        cred_path.parent.mkdir(parents=True, exist_ok=True)
        cred_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        cred_path.chmod(0o600)
    except (OSError, IOError) as exc:
        logger.debug("Failed to persist refreshed Claude Code credentials: %s", exc)


def _refresh_oauth_token(creds: Dict[str, Any]) -> Optional[str]:
    """Refresh an expired Claude Code OAuth token if a refresh token is present."""
    import urllib.parse
    import urllib.request

    refresh_token = str(creds.get("refreshToken") or "").strip()
    if not refresh_token:
        return None

    client_id = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
    data = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        }
    ).encode()
    request = urllib.request.Request(
        "https://console.anthropic.com/v1/oauth/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        logger.debug("Failed to refresh Claude Code token: %s", exc)
        return None

    access_token = str(payload.get("access_token") or "").strip()
    if not access_token:
        return None

    import time

    refresh_out = str(payload.get("refresh_token") or refresh_token).strip()
    expires_in = int(payload.get("expires_in") or 3600)
    expires_at_ms = int(time.time() * 1000) + expires_in * 1000
    _write_claude_code_credentials(access_token, refresh_out, expires_at_ms)
    return access_token


def _resolve_claude_code_token_from_credentials(creds: Optional[Dict[str, Any]] = None) -> Optional[str]:
    creds = creds or read_claude_code_credentials()
    if creds and is_claude_code_token_valid(creds):
        return creds["accessToken"]
    if creds:
        return _refresh_oauth_token(creds)
    return None


def _prefer_refreshable_claude_code_token(env_token: str, creds: Optional[Dict[str, Any]]) -> Optional[str]:
    """Prefer refreshable Claude Code creds over static env OAuth tokens."""
    if not env_token or not _is_oauth_token(env_token) or not isinstance(creds, dict):
        return None
    if not creds.get("refreshToken"):
        return None
    resolved = _resolve_claude_code_token_from_credentials(creds)
    if resolved and resolved != env_token:
        logger.debug(
            "Preferring Claude Code credential file over static env OAuth token so refresh can proceed"
        )
        return resolved
    return None


def get_anthropic_token_source(token: Optional[str] = None) -> str:
    token = (token or "").strip()
    if not token:
        return "none"

    env_token = os.getenv("ANTHROPIC_TOKEN", "").strip()
    if env_token and env_token == token:
        return "anthropic_token_env"

    cc_env_token = os.getenv("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    if cc_env_token and cc_env_token == token:
        return "claude_code_oauth_token_env"

    creds = read_claude_code_credentials()
    if creds and creds.get("accessToken") == token:
        return str(creds.get("source") or "claude_code_credentials")

    managed_key = read_claude_managed_key()
    if managed_key and managed_key == token:
        return "claude_json_primary_api_key"

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if api_key and api_key == token:
        return "anthropic_api_key_env"

    return "unknown"


def resolve_anthropic_token() -> Optional[str]:
    """Resolve an Anthropic token from env vars and Claude Code credentials."""
    creds = read_claude_code_credentials()

    token = os.getenv("ANTHROPIC_TOKEN", "").strip()
    if token:
        preferred = _prefer_refreshable_claude_code_token(token, creds)
        return preferred or token

    cc_token = os.getenv("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    if cc_token:
        preferred = _prefer_refreshable_claude_code_token(cc_token, creds)
        return preferred or cc_token

    resolved = _resolve_claude_code_token_from_credentials(creds)
    if resolved:
        return resolved

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if api_key:
        return api_key

    return None


def normalize_model_name(model: str) -> str:
    lower = model.lower()
    if lower.startswith("anthropic/"):
        model = model.split("/", 1)[1]
    return model.replace(".", "-")


def _sanitize_tool_id(tool_id: str) -> str:
    import re

    if not tool_id:
        return "tool_0"
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", tool_id)
    return sanitized or "tool_0"


def _image_source_from_openai_url(url: str) -> Dict[str, str]:
    url = str(url or "").strip()
    if not url:
        return {"type": "url", "url": ""}
    if url.startswith("data:"):
        header, _, data = url.partition(",")
        media_type = "image/jpeg"
        if header.startswith("data:"):
            mime_part = header[len("data:") :].split(";", 1)[0].strip()
            if mime_part.startswith("image/"):
                media_type = mime_part
        return {"type": "base64", "media_type": media_type, "data": data}
    return {"type": "url", "url": url}


def _convert_content_part_to_anthropic(part: Any) -> Optional[Dict[str, Any]]:
    if part is None:
        return None
    if isinstance(part, str):
        return {"type": "text", "text": part}
    if not isinstance(part, dict):
        return {"type": "text", "text": str(part)}

    ptype = part.get("type")
    if ptype in {"text", "input_text"}:
        block: Dict[str, Any] = {"type": "text", "text": part.get("text", "")}
    elif ptype in {"image_url", "input_image"}:
        image_value = part.get("image_url", {})
        url = image_value.get("url", "") if isinstance(image_value, dict) else str(image_value or "")
        block = {"type": "image", "source": _image_source_from_openai_url(url)}
    elif ptype == "image" and part.get("source"):
        block = dict(part)
    else:
        block = dict(part)

    if isinstance(part.get("cache_control"), dict) and "cache_control" not in block:
        block["cache_control"] = dict(part["cache_control"])
    return block


def _convert_content_to_anthropic(content: Any) -> Any:
    if not isinstance(content, list):
        return content
    converted = []
    for part in content:
        block = _convert_content_part_to_anthropic(part)
        if block is not None:
            converted.append(block)
    return converted


def convert_tools_to_anthropic(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = []
    for tool in tools or []:
        fn = tool.get("function", {})
        result.append(
            {
                "name": fn.get("name", ""),
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
            }
        )
    return result


def convert_messages_to_anthropic(messages: List[Dict[str, Any]]) -> Tuple[Optional[Any], List[Dict[str, Any]]]:
    system = None
    result: List[Dict[str, Any]] = []

    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")

        if role == "system":
            if isinstance(content, list):
                has_cache = any(p.get("cache_control") for p in content if isinstance(p, dict))
                if has_cache:
                    system = [p for p in content if isinstance(p, dict)]
                else:
                    system = "\n".join(
                        p["text"] for p in content if isinstance(p, dict) and p.get("type") == "text"
                    )
            else:
                system = content
            continue

        if role == "assistant":
            blocks = []
            if content:
                if isinstance(content, list):
                    converted = _convert_content_to_anthropic(content)
                    if isinstance(converted, list):
                        blocks.extend(converted)
                else:
                    blocks.append({"type": "text", "text": str(content)})
            for tool_call in message.get("tool_calls", []):
                fn = tool_call.get("function", {})
                args = fn.get("arguments", "{}")
                try:
                    parsed_args = json.loads(args) if isinstance(args, str) else args
                except (json.JSONDecodeError, ValueError):
                    parsed_args = {}
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": _sanitize_tool_id(tool_call.get("id", "")),
                        "name": fn.get("name", ""),
                        "input": parsed_args,
                    }
                )
            result.append({"role": "assistant", "content": blocks or [{"type": "text", "text": "(empty)"}]})
            continue

        if role == "tool":
            result_content = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
            if not result_content:
                result_content = "(no output)"
            block = {
                "type": "tool_result",
                "tool_use_id": _sanitize_tool_id(message.get("tool_call_id", "")),
                "content": result_content,
            }
            if result and result[-1]["role"] == "user" and isinstance(result[-1]["content"], list):
                result[-1]["content"].append(block)
            else:
                result.append({"role": "user", "content": [block]})
            continue

        if isinstance(content, list):
            converted = _convert_content_to_anthropic(content)
            result.append({"role": "user", "content": converted or [{"type": "text", "text": ""}]})
        else:
            result.append({"role": "user", "content": content})

    return system, result


def build_anthropic_kwargs(
    model: str,
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]],
    max_tokens: Optional[int],
    reasoning_config: Optional[Dict[str, Any]],
    tool_choice: Optional[str] = None,
) -> Dict[str, Any]:
    system, anthropic_messages = convert_messages_to_anthropic(messages)
    anthropic_tools = convert_tools_to_anthropic(tools or [])

    model = normalize_model_name(model)
    effective_max_tokens = max_tokens or 16384

    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": anthropic_messages,
        "max_tokens": effective_max_tokens,
    }
    if system:
        kwargs["system"] = system
    if anthropic_tools:
        kwargs["tools"] = anthropic_tools
        if tool_choice in {None, "auto"}:
            kwargs["tool_choice"] = {"type": "auto"}
        elif tool_choice == "required":
            kwargs["tool_choice"] = {"type": "any"}
        elif tool_choice not in {"none", ""}:
            kwargs["tool_choice"] = {"type": "tool", "name": tool_choice}

    if reasoning_config and isinstance(reasoning_config, dict):
        if reasoning_config.get("enabled") is not False and "haiku" not in model.lower():
            effort = str(reasoning_config.get("effort", "medium")).lower()
            budget = THINKING_BUDGET.get(effort, 8000)
            if _supports_adaptive_thinking(model):
                kwargs["thinking"] = {"type": "adaptive"}
                kwargs["output_config"] = {"effort": ADAPTIVE_EFFORT_MAP.get(effort, "medium")}
            else:
                kwargs["thinking"] = {"type": "enabled", "budget_tokens": budget}
                kwargs["temperature"] = 1
                kwargs["max_tokens"] = max(effective_max_tokens, budget + 4096)

    return kwargs


def normalize_anthropic_response(response) -> Tuple[SimpleNamespace, str]:
    text_parts = []
    reasoning_parts = []
    tool_calls = []

    for block in getattr(response, "content", []) or []:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "thinking":
            reasoning_parts.append(getattr(block, "thinking", ""))
        elif block.type == "tool_use":
            tool_calls.append(
                SimpleNamespace(
                    id=block.id,
                    type="function",
                    function=SimpleNamespace(
                        name=block.name,
                        arguments=json.dumps(block.input, ensure_ascii=False),
                    ),
                )
            )

    stop_reason_map = {
        "end_turn": "stop",
        "tool_use": "tool_calls",
        "max_tokens": "length",
        "stop_sequence": "stop",
    }
    finish_reason = stop_reason_map.get(getattr(response, "stop_reason", None), "stop")
    assistant_message = SimpleNamespace(
        content="\n".join(text_parts) if text_parts else None,
        tool_calls=tool_calls or None,
        reasoning="\n\n".join(p for p in reasoning_parts if p) or None,
        reasoning_content=None,
        reasoning_details=None,
    )
    return assistant_message, finish_reason


def wrap_anthropic_response(response):
    """Wrap an Anthropic response in an OpenAI-like shape for the agent loop."""
    assistant_message, finish_reason = normalize_anthropic_response(response)
    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "input_tokens", 0) or 0
    completion_tokens = getattr(usage, "output_tokens", 0) or 0
    total_tokens = prompt_tokens + completion_tokens

    wrapped_usage = SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        prompt_tokens_details=SimpleNamespace(cached_tokens=0, cache_write_tokens=0),
    )
    wrapped_choice = SimpleNamespace(message=assistant_message, finish_reason=finish_reason)
    return SimpleNamespace(
        choices=[wrapped_choice],
        usage=wrapped_usage,
        model=getattr(response, "model", None),
        raw_response=response,
    )
