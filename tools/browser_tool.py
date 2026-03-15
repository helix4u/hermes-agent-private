#!/usr/bin/env python3
"""
Browser Tool Module

This module provides browser automation tools using either a local Playwright
backend or the legacy Browserbase cloud backend. It enables AI agents to navigate websites,
interact with page elements, and extract information in a text-based format.

The tool uses agent-browser's accessibility tree (ariaSnapshot) for text-based
page representation, making it ideal for LLM agents without vision capabilities.

Features:
- Local Playwright execution by default with a persistent browser profile
- User-agent spoofing and anti-automation shims for common fingerprint checks
- Optional Browserbase fallback for cloud execution
- Session isolation per task ID
- Text-based page snapshots using accessibility tree
- Element interaction via ref selectors (@e1, @e2, etc.)
- Task-aware content extraction using LLM summarization
- Automatic cleanup of browser sessions

Environment Variables:
- BROWSER_BACKEND: `playwright` (default) or `browserbase`
- BROWSER_PROFILE_DIR: Persistent Playwright profile directory
- BROWSER_USER_AGENT: Override the Playwright user agent string
- BROWSER_HEADLESS: Run Playwright headless (`true`/`false`, default: `false`)
- BROWSER_TIMEZONE: Override the Playwright timezone fingerprint
- BROWSERBASE_API_KEY: API key for Browserbase (required)
- BROWSERBASE_PROJECT_ID: Project ID for Browserbase (required)
- BROWSER_NAVIGATE_TIMEOUT: Timeout for page navigation in seconds (default: "12")
- BROWSERBASE_PROXIES: Enable/disable residential proxies (default: "true")
- BROWSERBASE_ADVANCED_STEALTH: Enable advanced stealth mode with custom Chromium,
  requires Scale Plan (default: "false")
- BROWSERBASE_KEEP_ALIVE: Enable keepAlive for session reconnection after disconnects,
  requires paid plan (default: "true")
- BROWSERBASE_SESSION_TIMEOUT: Custom session timeout in milliseconds. Set to extend
  beyond project default. Common values: 600000 (10min), 1800000 (30min) (default: none)

Usage:
    from tools.browser_tool import browser_navigate, browser_snapshot, browser_click
    
    # Navigate to a page
    result = browser_navigate("https://example.com", task_id="task_123")
    
    # Get page snapshot
    snapshot = browser_snapshot(task_id="task_123")
    
    # Click an element
    browser_click("@e5", task_id="task_123")
"""

import atexit
import json
import logging
import os
import re
import signal
import subprocess
import shutil
import sys
import tempfile
import threading
import time
import requests
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
from agent.auxiliary_client import get_vision_auxiliary_client

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

# Default timeout for browser commands (seconds)
DEFAULT_COMMAND_TIMEOUT = 30

# Default timeout for browser navigation (seconds)
BROWSER_NAVIGATE_TIMEOUT = int(os.environ.get("BROWSER_NAVIGATE_TIMEOUT", "12"))

# Browser backend selection
BROWSER_BACKEND = os.environ.get("BROWSER_BACKEND", "playwright").strip().lower()
BROWSER_HEADLESS = os.environ.get("BROWSER_HEADLESS", "false").strip().lower() == "true"
BROWSER_PROFILE_DIR = os.environ.get(
    "BROWSER_PROFILE_DIR",
    str(Path.home() / ".hermes" / "browser-profile"),
)
BROWSER_USER_AGENT = os.environ.get(
    "BROWSER_USER_AGENT",
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
    ),
)
BROWSER_VIEWPORT_WIDTH = int(os.environ.get("BROWSER_VIEWPORT_WIDTH", "1440"))
BROWSER_VIEWPORT_HEIGHT = int(os.environ.get("BROWSER_VIEWPORT_HEIGHT", "960"))
BROWSER_SCREEN_WIDTH = int(os.environ.get("BROWSER_SCREEN_WIDTH", "1536"))
BROWSER_SCREEN_HEIGHT = int(os.environ.get("BROWSER_SCREEN_HEIGHT", "1024"))
BROWSER_DEVICE_SCALE_FACTOR = float(os.environ.get("BROWSER_DEVICE_SCALE_FACTOR", "1.25"))
BROWSER_HARDWARE_CONCURRENCY = int(os.environ.get("BROWSER_HARDWARE_CONCURRENCY", "8"))
BROWSER_DEVICE_MEMORY = int(os.environ.get("BROWSER_DEVICE_MEMORY", "8"))
BROWSER_MAX_TOUCH_POINTS = int(os.environ.get("BROWSER_MAX_TOUCH_POINTS", "0"))

# Default session timeout (seconds)
DEFAULT_SESSION_TIMEOUT = 300

# Max tokens for snapshot content before summarization
SNAPSHOT_SUMMARIZE_THRESHOLD = 8000

# Resolve vision auxiliary client for extraction/vision tasks
_aux_vision_client, EXTRACTION_MODEL = get_vision_auxiliary_client()


def _browser_screenshots_dir() -> Path:
    """Persistent screenshot cache used for browser_vision sharing."""
    hermes_home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    return hermes_home / "browser_screenshots"


def _cleanup_old_screenshots(screenshots_dir: Path, max_age_hours: int = 24) -> None:
    """Remove stale browser screenshots to avoid unbounded disk growth."""
    cutoff = time.time() - (max_age_hours * 3600)
    try:
        for entry in screenshots_dir.glob("browser_screenshot_*.png"):
            try:
                if entry.stat().st_mtime < cutoff:
                    entry.unlink()
            except Exception:
                logger.debug("Could not prune browser screenshot %s", entry, exc_info=True)
    except Exception:
        logger.debug("Could not prune browser screenshot directory %s", screenshots_dir, exc_info=True)

# Track active sessions per task
# Now stores tuple of (session_name, browserbase_session_id, cdp_url)
_active_sessions: Dict[str, Dict[str, str]] = {}  # task_id -> {session_name, bb_session_id, cdp_url}

# Flag to track if cleanup has been done
_cleanup_done = False

# =============================================================================
# Inactivity Timeout Configuration
# =============================================================================

# Session inactivity timeout (seconds) - cleanup if no activity for this long
# Default: 5 minutes. Needs headroom for LLM reasoning between browser commands,
# especially when subagents are doing multi-step browser tasks.
BROWSER_SESSION_INACTIVITY_TIMEOUT = int(os.environ.get("BROWSER_INACTIVITY_TIMEOUT", "300"))

# Track last activity time per session
_session_last_activity: Dict[str, float] = {}

# Background cleanup thread state
_cleanup_thread = None
_cleanup_running = False
# Protects _session_last_activity AND _active_sessions for thread safety
# (subagents run concurrently via ThreadPoolExecutor)
_cleanup_lock = threading.Lock()

# Local Playwright state
_playwright_runtime: Dict[str, Any] = {}
_local_browser_pages: Dict[str, Any] = {}
_local_ref_maps: Dict[str, Dict[str, str]] = {}


def _using_playwright_backend() -> bool:
    return BROWSER_BACKEND in {"playwright", "local"}


def _detect_browser_timezone() -> str:
    explicit = os.environ.get("BROWSER_TIMEZONE") or os.environ.get("TZ")
    if explicit:
        return explicit.strip()

    try:
        tzinfo = datetime.now().astimezone().tzinfo
        for attr in ("key", "zone"):
            value = getattr(tzinfo, attr, None)
            if value:
                return str(value)
    except Exception:
        pass

    return "UTC"


BROWSER_TIMEZONE = _detect_browser_timezone()


def _get_playwright_stealth_script() -> str:
    fingerprint = json.dumps({
        "timezone": BROWSER_TIMEZONE,
        "hardwareConcurrency": BROWSER_HARDWARE_CONCURRENCY,
        "deviceMemory": BROWSER_DEVICE_MEMORY,
        "maxTouchPoints": BROWSER_MAX_TOUCH_POINTS,
        "screenWidth": BROWSER_SCREEN_WIDTH,
        "screenHeight": BROWSER_SCREEN_HEIGHT,
        "availWidth": BROWSER_SCREEN_WIDTH,
        "availHeight": max(BROWSER_SCREEN_HEIGHT - 40, BROWSER_VIEWPORT_HEIGHT),
        "colorDepth": 24,
        "pixelDepth": 24,
        "devicePixelRatio": BROWSER_DEVICE_SCALE_FACTOR,
        "mediaDevices": [
            {"deviceId": "default-audio-in", "groupId": "grp-audio", "kind": "audioinput", "label": "Default Microphone"},
            {"deviceId": "default-audio-out", "groupId": "grp-audio", "kind": "audiooutput", "label": "Default Speakers"},
            {"deviceId": "default-video", "groupId": "grp-video", "kind": "videoinput", "label": "Integrated Camera"},
        ],
    })
    script = """
(() => {
  const cfg = __HERMES_FINGERPRINT__;
  const override = (obj, key, value) => {
    try {
      Object.defineProperty(obj, key, { get: () => value, configurable: true });
    } catch (_) {}
  };
  override(navigator, 'webdriver', undefined);
  override(navigator, 'languages', ['en-US', 'en']);
  override(navigator, 'platform', 'Win32');
  override(navigator, 'plugins', [1, 2, 3, 4, 5]);
  override(navigator, 'hardwareConcurrency', cfg.hardwareConcurrency);
  override(navigator, 'deviceMemory', cfg.deviceMemory);
  override(navigator, 'maxTouchPoints', cfg.maxTouchPoints);
  if (!window.chrome) {
    Object.defineProperty(window, 'chrome', {
      value: { runtime: {}, app: {}, webstore: {} },
      configurable: true,
    });
  }
  override(screen, 'width', cfg.screenWidth);
  override(screen, 'height', cfg.screenHeight);
  override(screen, 'availWidth', cfg.availWidth);
  override(screen, 'availHeight', cfg.availHeight);
  override(screen, 'colorDepth', cfg.colorDepth);
  override(screen, 'pixelDepth', cfg.pixelDepth);
  override(window, 'devicePixelRatio', cfg.devicePixelRatio);
  const originalResolvedOptions = Intl.DateTimeFormat.prototype.resolvedOptions;
  Intl.DateTimeFormat.prototype.resolvedOptions = function(...args) {
    const result = originalResolvedOptions.apply(this, args);
    return { ...result, timeZone: cfg.timezone };
  };
  const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
  if (originalQuery) {
    window.navigator.permissions.query = (parameters) => (
      parameters && parameters.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(parameters)
    );
  }
  if (!navigator.mediaDevices) {
    Object.defineProperty(navigator, 'mediaDevices', {
      value: {},
      configurable: true,
    });
  }
  if (navigator.mediaDevices) {
    navigator.mediaDevices.enumerateDevices = async () => cfg.mediaDevices;
    navigator.mediaDevices.getSupportedConstraints = () => ({
      width: true,
      height: true,
      aspectRatio: true,
      frameRate: true,
      facingMode: true,
      resizeMode: true,
    });
  }
  const originalMatchMedia = window.matchMedia;
  window.matchMedia = (query) => {
    if (query === '(prefers-color-scheme: dark)') {
      return { matches: false, media: query, onchange: null, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, dispatchEvent() { return false; } };
    }
    if (query === '(prefers-reduced-motion: reduce)') {
      return { matches: false, media: query, onchange: null, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, dispatchEvent() { return false; } };
    }
    return originalMatchMedia(query);
  };
})();
"""
    return script.replace("__HERMES_FINGERPRINT__", fingerprint)


def _ensure_playwright_runtime() -> Dict[str, Any]:
    if _playwright_runtime.get("context") is not None:
        return _playwright_runtime

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - import failure path
        raise RuntimeError(
            "Playwright backend requested but the Python Playwright package is unavailable. "
            "Install it with `pip install playwright` and `playwright install chromium`."
        ) from exc

    profile_dir = Path(BROWSER_PROFILE_DIR).expanduser()
    profile_dir.mkdir(parents=True, exist_ok=True)

    playwright = sync_playwright().start()
    context = playwright.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        headless=BROWSER_HEADLESS,
        user_agent=BROWSER_USER_AGENT,
        viewport={"width": BROWSER_VIEWPORT_WIDTH, "height": BROWSER_VIEWPORT_HEIGHT},
        screen={"width": BROWSER_SCREEN_WIDTH, "height": BROWSER_SCREEN_HEIGHT},
        device_scale_factor=BROWSER_DEVICE_SCALE_FACTOR,
        timezone_id=BROWSER_TIMEZONE,
        has_touch=BROWSER_MAX_TOUCH_POINTS > 0,
        is_mobile=False,
        locale="en-US",
        color_scheme="light",
        reduced_motion="no-preference",
        extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-default-browser-check",
            "--disable-features=IsolateOrigins,site-per-process",
        ],
    )
    context.add_init_script(_get_playwright_stealth_script())
    _playwright_runtime.update({
        "playwright": playwright,
        "context": context,
        "profile_dir": str(profile_dir),
    })
    return _playwright_runtime


def _shutdown_playwright_runtime() -> None:
    context = _playwright_runtime.get("context")
    playwright = _playwright_runtime.get("playwright")
    try:
        if context is not None:
            context.close()
    finally:
        if playwright is not None:
            playwright.stop()
        _playwright_runtime.clear()


def _ensure_local_page(task_id: str):
    runtime = _ensure_playwright_runtime()
    page = _local_browser_pages.get(task_id)
    if page is not None and not page.is_closed():
        return page

    page = runtime["context"].new_page()
    _local_browser_pages[task_id] = page
    with _cleanup_lock:
        _active_sessions[task_id] = {
            "session_name": f"playwright_{task_id}",
            "backend": "playwright",
            "profile_dir": runtime["profile_dir"],
        }
    return page


def _build_local_snapshot(page, full: bool) -> Dict[str, Any]:
    snapshot_js = """
({ full }) => {
  const normalize = (value, maxLen) => (value || "").replace(/\\s+/g, " ").trim().slice(0, maxLen);
  const isVisible = (el) => {
    if (!el) return false;
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style &&
      style.visibility !== "hidden" &&
      style.display !== "none" &&
      rect.width > 0 &&
      rect.height > 0;
  };
  const cssPath = (el) => {
    if (el.id) return `#${CSS.escape(el.id)}`;
    const parts = [];
    let current = el;
    while (current && current.nodeType === Node.ELEMENT_NODE && parts.length < 6) {
      let selector = current.nodeName.toLowerCase();
      if (current.classList && current.classList.length) {
        selector += "." + Array.from(current.classList).slice(0, 2).map((cls) => CSS.escape(cls)).join(".");
      }
      let sibling = current;
      let index = 1;
      while ((sibling = sibling.previousElementSibling)) {
        if (sibling.nodeName === current.nodeName) index += 1;
      }
      selector += `:nth-of-type(${index})`;
      parts.unshift(selector);
      current = current.parentElement;
    }
    return parts.join(" > ");
  };

  const selectors = [
    "a[href]",
    "button",
    "input",
    "textarea",
    "select",
    "[role='button']",
    "[role='link']",
    "[contenteditable='true']",
    "summary"
  ].join(",");
  const interactive = Array.from(document.querySelectorAll(selectors))
    .filter(isVisible)
    .slice(0, full ? 200 : 80)
    .map((el, index) => {
      const ref = `@e${index + 1}`;
      const label = normalize(
        el.getAttribute("aria-label") ||
        el.innerText ||
        el.textContent ||
        el.getAttribute("placeholder") ||
        el.getAttribute("name") ||
        el.getAttribute("title"),
        140
      );
      return {
        ref,
        selector: cssPath(el),
        tag: el.tagName.toLowerCase(),
        type: el.getAttribute("type") || "",
        label,
      };
    });

  const refs = {};
  interactive.forEach((item) => {
    refs[item.ref] = item.selector;
  });

  const bodyText = normalize(document.body ? document.body.innerText : "", full ? 12000 : 4000);
  const lines = [
    `Title: ${document.title || ""}`,
    `URL: ${location.href}`,
  ];
  if (bodyText) {
    lines.push("");
    lines.push("Visible text:");
    lines.push(bodyText);
  }
  if (interactive.length) {
    lines.push("");
    lines.push("Interactive elements:");
    interactive.forEach((item) => {
      const extras = [item.tag, item.type].filter(Boolean).join("/");
      lines.push(`${item.ref} ${extras}: ${item.label || "<no label>"}`);
    });
  }
  return { snapshot: lines.join("\\n"), refs };
}
"""
    return page.evaluate(snapshot_js, {"full": full})


def _lookup_local_selector(task_id: str, ref: str) -> str:
    ref_map = _local_ref_maps.get(task_id, {})
    selector = ref_map.get(ref)
    if selector:
        return selector
    raise RuntimeError(
        f"Unknown element ref {ref}. Snapshot refs go stale after navigation or DOM changes; run browser_snapshot again."
    )


def _run_playwright_command(
    task_id: str,
    command: str,
    args: Optional[List[str]] = None,
    timeout: int = DEFAULT_COMMAND_TIMEOUT,
) -> Dict[str, Any]:
    args = args or []
    _start_browser_cleanup_thread()
    _update_session_activity(task_id)

    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    except Exception:  # pragma: no cover - import already validated
        PlaywrightTimeoutError = TimeoutError

    try:
        if command == "close":
            page = _local_browser_pages.pop(task_id, None)
            _local_ref_maps.pop(task_id, None)
            with _cleanup_lock:
                _active_sessions.pop(task_id, None)
                _session_last_activity.pop(task_id, None)
            if page is not None and not page.is_closed():
                page.close()
            if not _local_browser_pages:
                _shutdown_playwright_runtime()
            return {"success": True, "data": {"closed": True}}

        page = _ensure_local_page(task_id)
        page.set_default_timeout(timeout * 1000)

        if command == "open":
            target = args[0]
            page.goto(target, wait_until="domcontentloaded", timeout=timeout * 1000)
            page.wait_for_timeout(350)
            return {
                "success": True,
                "data": {
                    "url": page.url,
                    "title": page.title(),
                }
            }
        if command == "snapshot":
            full = "-c" not in args
            data = _build_local_snapshot(page, full=full)
            _local_ref_maps[task_id] = data.get("refs", {})
            return {"success": True, "data": data}
        if command == "click":
            ref = args[0]
            selector = _lookup_local_selector(task_id, ref)
            page.locator(selector).first.click(timeout=timeout * 1000)
            return {"success": True, "data": {"clicked": ref}}
        if command == "fill":
            ref, text = args[0], args[1]
            selector = _lookup_local_selector(task_id, ref)
            page.locator(selector).first.fill(text, timeout=timeout * 1000)
            return {"success": True, "data": {"filled": ref}}
        if command == "scroll":
            direction = args[0]
            delta = 900 if direction == "down" else -900
            page.mouse.wheel(0, delta)
            page.wait_for_timeout(150)
            return {"success": True, "data": {"direction": direction}}
        if command == "back":
            page.go_back(wait_until="domcontentloaded", timeout=timeout * 1000)
            page.wait_for_timeout(200)
            return {"success": True, "data": {"url": page.url, "title": page.title()}}
        if command == "press":
            page.keyboard.press(args[0])
            return {"success": True, "data": {"pressed": args[0]}}
        if command == "eval":
            result = page.evaluate(args[0])
            return {"success": True, "data": {"result": result}}
        if command == "screenshot":
            path = args[0]
            page.screenshot(path=path, full_page=False)
            return {"success": True, "data": {"path": path}}

        return {"success": False, "error": f"Unsupported Playwright browser command: {command}"}

    except PlaywrightTimeoutError:
        if command == "open":
            target = args[0] if args else "<unknown url>"
            return {
                "success": False,
                "error": (
                    f"Navigation to {target} did not finish within {timeout} seconds under the Playwright backend. "
                    "The page may be slow, blocked, or stuck in client-side rendering."
                ),
            }
        return {
            "success": False,
            "error": f"Playwright browser command '{command}' timed out after {timeout} seconds.",
        }
    except Exception as exc:
        return {"success": False, "error": f"Playwright browser command '{command}' failed: {exc}"}


def _emergency_cleanup_all_sessions():
    """
    Emergency cleanup of all active browser sessions.
    Called on process exit or interrupt to prevent orphaned sessions.
    """
    global _cleanup_done
    if _cleanup_done:
        return
    _cleanup_done = True
    
    if not _active_sessions:
        return

    if _using_playwright_backend():
        try:
            for task_id in list(_local_browser_pages.keys()):
                try:
                    _run_playwright_command(task_id, "close", [], timeout=5)
                except Exception as exc:
                    logger.error("Error closing local Playwright page %s: %s", task_id, exc)
            _shutdown_playwright_runtime()
            _local_browser_pages.clear()
            _local_ref_maps.clear()
            _active_sessions.clear()
        except Exception as e:
            logger.error("Emergency Playwright cleanup error: %s", e)
        return
    
    logger.info("Emergency cleanup: closing %s active session(s)...", len(_active_sessions))

    try:
        cleanup_all_browsers()
    except Exception as e:
        logger.error("Emergency cleanup error: %s", e)
    finally:
        with _cleanup_lock:
            _active_sessions.clear()
            _session_last_activity.clear()
        _recording_sessions.clear()


def _signal_handler(signum, frame):
    """Handle interrupt signals to cleanup sessions before exit."""
    logger.warning("Received signal %s, cleaning up...", signum)
    _emergency_cleanup_all_sessions()
    sys.exit(128 + signum)


# Register cleanup handlers
atexit.register(_emergency_cleanup_all_sessions)

# Only register signal handlers in main process (not in multiprocessing workers)
try:
    if os.getpid() == os.getpgrp():  # Main process check
        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)
except (OSError, AttributeError):
    pass  # Signal handling not available (e.g., Windows or worker process)


# =============================================================================
# Inactivity Cleanup Functions
# =============================================================================

def _cleanup_inactive_browser_sessions():
    """
    Clean up browser sessions that have been inactive for longer than the timeout.
    
    This function is called periodically by the background cleanup thread to
    automatically close sessions that haven't been used recently, preventing
    orphaned Browserbase sessions from accumulating.
    """
    current_time = time.time()
    sessions_to_cleanup = []
    
    with _cleanup_lock:
        for task_id, last_time in list(_session_last_activity.items()):
            if current_time - last_time > BROWSER_SESSION_INACTIVITY_TIMEOUT:
                sessions_to_cleanup.append(task_id)
    
    for task_id in sessions_to_cleanup:
        try:
            elapsed = int(current_time - _session_last_activity.get(task_id, current_time))
            logger.info("Cleaning up inactive session for task: %s (inactive for %ss)", task_id, elapsed)
            cleanup_browser(task_id)
            with _cleanup_lock:
                if task_id in _session_last_activity:
                    del _session_last_activity[task_id]
        except Exception as e:
            logger.warning("Error cleaning up inactive session %s: %s", task_id, e)


def _browser_cleanup_thread_worker():
    """
    Background thread that periodically cleans up inactive browser sessions.
    
    Runs every 30 seconds and checks for sessions that haven't been used
    within the BROWSER_SESSION_INACTIVITY_TIMEOUT period.
    """
    global _cleanup_running
    
    while _cleanup_running:
        try:
            _cleanup_inactive_browser_sessions()
        except Exception as e:
            logger.warning("Cleanup thread error: %s", e)
        
        # Sleep in 1-second intervals so we can stop quickly if needed
        for _ in range(30):
            if not _cleanup_running:
                break
            time.sleep(1)


def _start_browser_cleanup_thread():
    """Start the background cleanup thread if not already running."""
    global _cleanup_thread, _cleanup_running
    
    with _cleanup_lock:
        if _cleanup_thread is None or not _cleanup_thread.is_alive():
            _cleanup_running = True
            _cleanup_thread = threading.Thread(
                target=_browser_cleanup_thread_worker,
                daemon=True,
                name="browser-cleanup"
            )
            _cleanup_thread.start()
            logger.info("Started inactivity cleanup thread (timeout: %ss)", BROWSER_SESSION_INACTIVITY_TIMEOUT)


def _stop_browser_cleanup_thread():
    """Stop the background cleanup thread."""
    global _cleanup_running
    _cleanup_running = False
    if _cleanup_thread is not None:
        _cleanup_thread.join(timeout=5)


def _update_session_activity(task_id: str):
    """Update the last activity timestamp for a session."""
    with _cleanup_lock:
        _session_last_activity[task_id] = time.time()


# Register cleanup thread stop on exit
atexit.register(_stop_browser_cleanup_thread)


# ============================================================================
# Tool Schemas
# ============================================================================

BROWSER_TOOL_SCHEMAS = [
    {
        "name": "browser_navigate",
        "description": "Navigate to a URL in the browser. Initializes the session and loads the page. Must be called before other browser tools. For simple information retrieval, prefer web_search or web_extract (faster, cheaper). Use browser tools when you need to interact with a page (click, fill forms, dynamic content).",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to navigate to (e.g., 'https://example.com')"
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "browser_snapshot",
        "description": "Get a text-based snapshot of the current page's accessibility tree. Returns interactive elements with ref IDs (like @e1, @e2) for browser_click and browser_type. full=false (default): compact view with interactive elements. full=true: complete page content. Snapshots over 8000 chars are truncated or LLM-summarized. Requires browser_navigate first.",
        "parameters": {
            "type": "object",
            "properties": {
                "full": {
                    "type": "boolean",
                    "description": "If true, returns complete page content. If false (default), returns compact view with interactive elements only.",
                    "default": False
                }
            },
            "required": []
        }
    },
    {
        "name": "browser_click",
        "description": "Click on an element identified by its ref ID from the snapshot (e.g., '@e5'). The ref IDs are shown in square brackets in the snapshot output. Requires browser_navigate and browser_snapshot to be called first.",
        "parameters": {
            "type": "object",
            "properties": {
                "ref": {
                    "type": "string",
                    "description": "The element reference from the snapshot (e.g., '@e5', '@e12')"
                }
            },
            "required": ["ref"]
        }
    },
    {
        "name": "browser_type",
        "description": "Type text into an input field identified by its ref ID. Clears the field first, then types the new text. Requires browser_navigate and browser_snapshot to be called first.",
        "parameters": {
            "type": "object",
            "properties": {
                "ref": {
                    "type": "string",
                    "description": "The element reference from the snapshot (e.g., '@e3')"
                },
                "text": {
                    "type": "string",
                    "description": "The text to type into the field"
                }
            },
            "required": ["ref", "text"]
        }
    },
    {
        "name": "browser_scroll",
        "description": "Scroll the page in a direction. Use this to reveal more content that may be below or above the current viewport. Requires browser_navigate to be called first.",
        "parameters": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["up", "down"],
                    "description": "Direction to scroll"
                }
            },
            "required": ["direction"]
        }
    },
    {
        "name": "browser_back",
        "description": "Navigate back to the previous page in browser history. Requires browser_navigate to be called first.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "browser_press",
        "description": "Press a keyboard key. Useful for submitting forms (Enter), navigating (Tab), or keyboard shortcuts. Requires browser_navigate to be called first.",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Key to press (e.g., 'Enter', 'Tab', 'Escape', 'ArrowDown')"
                }
            },
            "required": ["key"]
        }
    },
    {
        "name": "browser_close",
        "description": "Close the browser session and release resources. Call this when done with browser tasks to free up Browserbase session quota.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "browser_get_images",
        "description": "Get a list of all images on the current page with their URLs and alt text. Useful for finding images to analyze with the vision tool. Requires browser_navigate to be called first.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "browser_vision",
        "description": "Take a screenshot of the current page and analyze it with vision AI. Use this when you need to visually understand what's on the page - especially useful for CAPTCHAs, visual verification challenges, complex layouts, or when the text snapshot doesn't capture important visual information. Requires browser_navigate to be called first.",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "What you want to know about the page visually. Be specific about what you're looking for."
                }
            },
            "required": ["question"]
        }
    },
]


# ============================================================================
# Utility Functions
# ============================================================================

def _create_browserbase_session(task_id: str) -> Dict[str, str]:
    """
    Create a Browserbase session with stealth features.
    
    Browserbase Stealth Modes:
    - Basic Stealth: ALWAYS enabled automatically. Generates random fingerprints,
      viewports, and solves visual CAPTCHAs. No configuration needed.
    - Advanced Stealth: Uses custom Chromium build for better bot detection avoidance.
      Requires Scale Plan. Enable via BROWSERBASE_ADVANCED_STEALTH=true.
    
    Proxies are enabled by default to route traffic through residential IPs,
    which significantly improves CAPTCHA solving rates. Can be disabled via
    BROWSERBASE_PROXIES=false if needed.
    
    Args:
        task_id: Unique identifier for the task
        
    Returns:
        Dict with session_name, bb_session_id, cdp_url, and feature flags
    """
    import uuid
    import sys
    
    config = _get_browserbase_config()
    
    # Check for optional settings from environment
    # Proxies: enabled by default for better CAPTCHA solving
    enable_proxies = os.environ.get("BROWSERBASE_PROXIES", "true").lower() != "false"
    # Advanced Stealth: requires Scale Plan, disabled by default
    enable_advanced_stealth = os.environ.get("BROWSERBASE_ADVANCED_STEALTH", "false").lower() == "true"
    # keepAlive: enabled by default (requires paid plan) - allows reconnection after disconnects
    enable_keep_alive = os.environ.get("BROWSERBASE_KEEP_ALIVE", "true").lower() != "false"
    # Custom session timeout in milliseconds (optional) - extends session beyond project default
    custom_timeout_ms = os.environ.get("BROWSERBASE_SESSION_TIMEOUT")
    
    # Track which features are actually enabled for logging/debugging
    features_enabled = {
        "basic_stealth": True,  # Always on
        "proxies": False,
        "advanced_stealth": False,
        "keep_alive": False,
        "custom_timeout": False,
    }
    
    # Build session configuration
    # Note: Basic stealth mode is ALWAYS active - no configuration needed
    session_config = {
        "projectId": config["project_id"],
    }
    
    # Enable keepAlive for session reconnection (default: true, requires paid plan)
    # Allows reconnecting to the same session after network hiccups
    if enable_keep_alive:
        session_config["keepAlive"] = True
    
    # Add custom timeout if specified (in milliseconds)
    # This extends session duration beyond project's default timeout
    if custom_timeout_ms:
        try:
            timeout_val = int(custom_timeout_ms)
            if timeout_val > 0:
                session_config["timeout"] = timeout_val
        except ValueError:
            logger.warning("Invalid BROWSERBASE_SESSION_TIMEOUT value: %s", custom_timeout_ms)
    
    # Enable proxies for better CAPTCHA solving (default: true)
    # Routes traffic through residential IPs for more reliable access
    if enable_proxies:
        session_config["proxies"] = True
    
    # Add advanced stealth if enabled (requires Scale Plan)
    # Uses custom Chromium build to avoid bot detection altogether
    if enable_advanced_stealth:
        session_config["browserSettings"] = {
            "advancedStealth": True,
        }
    
    # Create session via Browserbase API
    response = requests.post(
        "https://api.browserbase.com/v1/sessions",
        headers={
            "Content-Type": "application/json",
            "X-BB-API-Key": config["api_key"],
        },
        json=session_config,
        timeout=30
    )
    
    # Track if we fell back from paid features
    proxies_fallback = False
    keepalive_fallback = False
    
    # Handle 402 Payment Required - likely paid features not available
    # Try to identify which feature caused the issue and retry without it
    if response.status_code == 402:
        # First try without keepAlive (most likely culprit for paid plan requirement)
        if enable_keep_alive:
            keepalive_fallback = True
            logger.warning("keepAlive may require paid plan (402), retrying without it. "
                          "Sessions may timeout during long operations.")
            session_config.pop("keepAlive", None)
            response = requests.post(
                "https://api.browserbase.com/v1/sessions",
                headers={
                    "Content-Type": "application/json",
                    "X-BB-API-Key": config["api_key"],
                },
                json=session_config,
                timeout=30
            )
        
        # If still 402, try without proxies too
        if response.status_code == 402 and enable_proxies:
            proxies_fallback = True
            logger.warning("Proxies unavailable (402), retrying without proxies. "
                          "Bot detection may be less effective.")
            session_config.pop("proxies", None)
            response = requests.post(
                "https://api.browserbase.com/v1/sessions",
                headers={
                    "Content-Type": "application/json",
                    "X-BB-API-Key": config["api_key"],
                },
                json=session_config,
                timeout=30
            )
    
    if not response.ok:
        raise RuntimeError(f"Failed to create Browserbase session: {response.status_code} {response.text}")
    
    session_data = response.json()
    session_name = f"hermes_{task_id}_{uuid.uuid4().hex[:8]}"
    
    # Update features based on what actually succeeded
    if enable_proxies and not proxies_fallback:
        features_enabled["proxies"] = True
    if enable_advanced_stealth:
        features_enabled["advanced_stealth"] = True
    if enable_keep_alive and not keepalive_fallback:
        features_enabled["keep_alive"] = True
    if custom_timeout_ms and "timeout" in session_config:
        features_enabled["custom_timeout"] = True
    
    # Log session info for debugging
    feature_str = ", ".join(k for k, v in features_enabled.items() if v)
    logger.info("Created session %s with features: %s", session_name, feature_str)
    
    return {
        "session_name": session_name,
        "bb_session_id": session_data["id"],
        "cdp_url": session_data["connectUrl"],
        "features": features_enabled,
    }


def _get_session_info(task_id: Optional[str] = None) -> Dict[str, str]:
    """
    Get or create session info for the given task.
    
    Creates a Browserbase session with proxies enabled if one doesn't exist.
    Also starts the inactivity cleanup thread and updates activity tracking.
    Thread-safe: multiple subagents can call this concurrently.
    
    Args:
        task_id: Unique identifier for the task
        
    Returns:
        Dict with session_name, bb_session_id, and cdp_url
    """
    if task_id is None:
        task_id = "default"

    if _using_playwright_backend():
        _start_browser_cleanup_thread()
        _update_session_activity(task_id)
        _ensure_local_page(task_id)
        with _cleanup_lock:
            return _active_sessions[task_id]
    
    # Start the cleanup thread if not running (handles inactivity timeouts)
    _start_browser_cleanup_thread()
    
    # Update activity timestamp for this session
    _update_session_activity(task_id)
    
    with _cleanup_lock:
        # Check if we already have a session for this task
        if task_id in _active_sessions:
            return _active_sessions[task_id]
    
    # Create session outside the lock (network call - don't hold lock during I/O)
    session_info = _create_browserbase_session(task_id)
    
    with _cleanup_lock:
        _active_sessions[task_id] = session_info
    
    return session_info


def _get_session_name(task_id: Optional[str] = None) -> str:
    """
    Get the session name for agent-browser CLI.
    
    Args:
        task_id: Unique identifier for the task
        
    Returns:
        Session name for agent-browser
    """
    session_info = _get_session_info(task_id)
    return session_info["session_name"]


def _get_browserbase_config() -> Dict[str, str]:
    """
    Get Browserbase configuration from environment.
    
    Returns:
        Dict with api_key and project_id
        
    Raises:
        ValueError: If required env vars are not set
    """
    api_key = os.environ.get("BROWSERBASE_API_KEY")
    project_id = os.environ.get("BROWSERBASE_PROJECT_ID")
    
    if not api_key or not project_id:
        raise ValueError(
            "BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID environment variables are required. "
            "Get your credentials at https://browserbase.com"
        )
    
    return {
        "api_key": api_key,
        "project_id": project_id
    }


def _find_agent_browser() -> List[str]:
    """
    Find the agent-browser CLI executable.
    
    Checks in order: PATH, local node_modules/.bin/, npx fallback.
    
    Returns:
        Command prefix for invoking agent-browser (argv list)
        
    Raises:
        FileNotFoundError: If agent-browser is not installed
    """
    is_windows = os.name == "nt"

    # Check if it's in PATH (global install)
    which_result = shutil.which("agent-browser.cmd" if is_windows else "agent-browser")
    if not which_result:
        which_result = shutil.which("agent-browser")
    if which_result:
        return [which_result]
    
    # Check local node_modules/.bin/ (npm install in repo root)
    repo_root = Path(__file__).parent.parent
    local_bin_dir = repo_root / "node_modules" / ".bin"
    if is_windows:
        local_cmd = local_bin_dir / "agent-browser.cmd"
        if local_cmd.exists():
            return [str(local_cmd)]
    local_bin = local_bin_dir / "agent-browser"
    if local_bin.exists():
        return [str(local_bin)]
    
    # Check common npx locations
    npx_path = shutil.which("npx.cmd" if is_windows else "npx")
    if not npx_path:
        npx_path = shutil.which("npx")
    if npx_path:
        return [npx_path, "agent-browser"]
    
    raise FileNotFoundError(
        "agent-browser CLI not found. Install it with: npm install -g agent-browser\n"
        "Or run 'npm install' in the repo root to install locally.\n"
        "Or ensure npx is available in your PATH."
    )


def _extract_screenshot_path_from_text(text: str) -> Optional[str]:
    """Extract a screenshot file path from agent-browser human-readable output."""
    if not text:
        return None

    patterns = [
        r"Screenshot saved to ['\"](?P<path>/[^'\"]+?\.png)['\"]",
        r"Screenshot saved to (?P<path>/\S+?\.png)(?:\s|$)",
        r"(?P<path>/\S+?\.png)(?:\s|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            path = match.group("path").strip().strip("'\"")
            if path:
                return path

    return None


def _run_browser_command(
    task_id: str,
    command: str,
    args: List[str] = None,
    timeout: int = DEFAULT_COMMAND_TIMEOUT
) -> Dict[str, Any]:
    """
    Run an agent-browser CLI command using our pre-created Browserbase session.
    
    Args:
        task_id: Task identifier to get the right session
        command: The command to run (e.g., "open", "click")
        args: Additional arguments for the command
        timeout: Command timeout in seconds
        
    Returns:
        Parsed JSON response from agent-browser
    """
    args = args or []

    if _using_playwright_backend():
        return _run_playwright_command(task_id, command, args, timeout)
    
    # Build the command
    try:
        browser_cmd = _find_agent_browser()
    except FileNotFoundError as e:
        return {"success": False, "error": str(e)}
    
    from tools.interrupt import is_interrupted
    if is_interrupted():
        return {"success": False, "error": "Interrupted"}

    # Get session info (creates Browserbase session with proxies if needed)
    try:
        session_info = _get_session_info(task_id)
    except Exception as e:
        return {"success": False, "error": f"Failed to create browser session: {str(e)}"}
    
    # Connect via CDP to our pre-created Browserbase session.
    # IMPORTANT: Do NOT use --session with --cdp. In agent-browser >=0.13,
    # --session creates a local browser instance and silently ignores --cdp.
    # Per-task isolation is handled by AGENT_BROWSER_SOCKET_DIR instead.
    cmd_parts = browser_cmd + [
        "--cdp", session_info["cdp_url"],
        "--json",
        command
    ] + args
    
    try:
        # Give each task its own socket directory to prevent concurrency conflicts.
        # Without this, parallel workers fight over the same default socket path,
        # causing "Failed to create socket directory: Permission denied" errors.
        task_socket_dir = os.path.join(
            tempfile.gettempdir(), 
            f"agent-browser-{session_info['session_name']}"
        )
        os.makedirs(task_socket_dir, exist_ok=True)
        
        browser_env = {**os.environ}
        hermes_home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
        hermes_node_bin = str(hermes_home / "node" / "bin")

        existing_path = browser_env.get("PATH", "")
        path_parts = [p for p in existing_path.split(":") if p]
        candidate_dirs = [hermes_node_bin] + [p for p in _SANE_PATH.split(":") if p]
        for part in reversed(candidate_dirs):
            if os.path.isdir(part) and part not in path_parts:
                path_parts.insert(0, part)

        browser_env["PATH"] = ":".join(path_parts)
        browser_env["AGENT_BROWSER_SOCKET_DIR"] = task_socket_dir
        
        result = subprocess.run(
            cmd_parts,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=browser_env,
        )
        
        # Log stderr for diagnostics (agent-browser may emit warnings there)
        if result.stderr and result.stderr.strip():
            logger.debug("stderr from '%s': %s", command, result.stderr.strip()[:200])
        
        stdout_text = result.stdout.strip()

        # Parse JSON output
        if stdout_text:
            try:
                parsed = json.loads(stdout_text)
                # Warn if snapshot came back empty (common sign of daemon/CDP issues)
                if command == "snapshot" and parsed.get("success"):
                    snap_data = parsed.get("data", {})
                    if not snap_data.get("snapshot") and not snap_data.get("refs"):
                        logger.warning("snapshot returned empty content. "
                                       "Possible stale daemon or CDP connection issue. "
                                       "returncode=%s", result.returncode)
                return parsed
            except json.JSONDecodeError:
                raw = stdout_text[:2000]
                logger.warning("browser '%s' returned non-JSON output (rc=%s): %s",
                               command, result.returncode, raw[:500])

                if command == "screenshot":
                    stderr_text = (result.stderr or "").strip()
                    combined_text = "\n".join(
                        part for part in [stdout_text, stderr_text] if part
                    )
                    recovered_path = _extract_screenshot_path_from_text(combined_text)

                    if recovered_path and Path(recovered_path).exists():
                        logger.info(
                            "browser 'screenshot' recovered file from non-JSON output: %s",
                            recovered_path,
                        )
                        return {
                            "success": True,
                            "data": {
                                "path": recovered_path,
                                "raw": raw,
                            },
                        }

                return {
                    "success": False,
                    "error": f"Non-JSON output from agent-browser for '{command}': {raw}"
                }
        
        # Check for errors
        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else f"Command failed with code {result.returncode}"
            command_label = f"browser {command}"
            if args:
                rendered_args = ", ".join(repr(str(arg)) for arg in args[:3])
                if len(args) > 3:
                    rendered_args += ", ..."
                command_label += f"({rendered_args})"
            return {"success": False, "error": f"{command_label} failed: {error_msg}"}
        
        return {"success": True, "data": {}}
        
    except subprocess.TimeoutExpired:
        if command == "open":
            target = args[0] if args else "<unknown url>"
            detail = (
                f"Navigation to {target} did not finish within {timeout} seconds. "
                "The site may be slow, blocking automation, or waiting on heavy client-side rendering."
            )
        elif command == "snapshot":
            detail = (
                f"Snapshot capture did not finish within {timeout} seconds. "
                "The page may be hung, the browser session may be stale, or the accessibility tree may be failing to render."
            )
        elif command == "screenshot":
            detail = (
                f"Screenshot capture did not finish within {timeout} seconds. "
                "The page may be hung or the browser session may be stale."
            )
        else:
            detail = f"Browser command '{command}' timed out after {timeout} seconds."
        return {"success": False, "error": detail}
    except Exception as e:
        return {"success": False, "error": f"Browser command '{command}' failed: {str(e)}"}


def _extract_relevant_content(
    snapshot_text: str,
    user_task: Optional[str] = None
) -> str:
    """Use LLM to extract relevant content from a snapshot based on the user's task.

    Falls back to simple truncation when no auxiliary vision model is configured.
    """
    if _aux_vision_client is None or EXTRACTION_MODEL is None:
        return _truncate_snapshot(snapshot_text)

    if user_task:
        extraction_prompt = (
            f"You are a content extractor for a browser automation agent.\n\n"
            f"The user's task is: {user_task}\n\n"
            f"Given the following page snapshot (accessibility tree representation), "
            f"extract and summarize the most relevant information for completing this task. Focus on:\n"
            f"1. Interactive elements (buttons, links, inputs) that might be needed\n"
            f"2. Text content relevant to the task (prices, descriptions, headings, important info)\n"
            f"3. Navigation structure if relevant\n\n"
            f"Keep ref IDs (like [ref=e5]) for interactive elements so the agent can use them.\n\n"
            f"Page Snapshot:\n{snapshot_text}\n\n"
            f"Provide a concise summary that preserves actionable information and relevant content."
        )
    else:
        extraction_prompt = (
            f"Summarize this page snapshot, preserving:\n"
            f"1. All interactive elements with their ref IDs (like [ref=e5])\n"
            f"2. Key text content and headings\n"
            f"3. Important information visible on the page\n\n"
            f"Page Snapshot:\n{snapshot_text}\n\n"
            f"Provide a concise summary focused on interactive elements and key content."
        )

    try:
        from agent.auxiliary_client import auxiliary_max_tokens_param
        response = _aux_vision_client.chat.completions.create(
            model=EXTRACTION_MODEL,
            messages=[{"role": "user", "content": extraction_prompt}],
            **auxiliary_max_tokens_param(4000),
            temperature=0.1,
        )
        return response.choices[0].message.content
    except Exception:
        return _truncate_snapshot(snapshot_text)


def _truncate_snapshot(snapshot_text: str, max_chars: int = 8000) -> str:
    """
    Simple truncation fallback for snapshots.
    
    Args:
        snapshot_text: The snapshot text to truncate
        max_chars: Maximum characters to keep
        
    Returns:
        Truncated text with indicator if truncated
    """
    if len(snapshot_text) <= max_chars:
        return snapshot_text
    
    return snapshot_text[:max_chars] + "\n\n[... content truncated ...]"


# ============================================================================
# Browser Tool Functions
# ============================================================================

def browser_navigate(url: str, task_id: Optional[str] = None) -> str:
    """
    Navigate to a URL in the browser.
    
    Args:
        url: The URL to navigate to
        task_id: Task identifier for session isolation
        
    Returns:
        JSON string with navigation result (includes stealth features info on first nav)
    """
    effective_task_id = task_id or "default"
    
    # Get session info to check if this is a new session
    # (will create one with features logged if not exists)
    session_info = _get_session_info(effective_task_id)
    is_first_nav = session_info.get("_first_nav", True)
    
    # Mark that we've done at least one navigation
    if is_first_nav:
        session_info["_first_nav"] = False
    
    result = _run_browser_command(
        effective_task_id,
        "open",
        [url],
        timeout=BROWSER_NAVIGATE_TIMEOUT,
    )
    
    if result.get("success"):
        data = result.get("data", {})
        title = data.get("title", "")
        final_url = data.get("url", url)
        
        response = {
            "success": True,
            "url": final_url,
            "title": title
        }
        
        # Detect common "blocked" page patterns from title/url
        blocked_patterns = [
            "access denied", "access to this page has been denied",
            "blocked", "bot detected", "verification required",
            "please verify", "are you a robot", "captcha",
            "cloudflare", "ddos protection", "checking your browser",
            "just a moment", "attention required"
        ]
        title_lower = title.lower()
        
        if any(pattern in title_lower for pattern in blocked_patterns):
            response["bot_detection_warning"] = (
                f"Page title '{title}' suggests bot detection. The site may have blocked this request. "
                "Options: 1) Try adding delays between actions, 2) Access different pages first, "
                "3) Enable advanced stealth (BROWSERBASE_ADVANCED_STEALTH=true, requires Scale plan), "
                "4) Some sites have very aggressive bot detection that may be unavoidable."
            )
        
        # Include feature info on first navigation so model knows what's active
        if is_first_nav and "features" in session_info:
            features = session_info["features"]
            active_features = [k for k, v in features.items() if v]
            if not features.get("proxies"):
                response["stealth_warning"] = (
                    "Running WITHOUT residential proxies. Bot detection may be more aggressive. "
                    "Consider upgrading Browserbase plan for proxy support."
                )
            response["stealth_features"] = active_features
        
        return json.dumps(response, ensure_ascii=False)
    else:
        return json.dumps({
            "success": False,
            "error": result.get("error", "Navigation failed")
        }, ensure_ascii=False)


def browser_snapshot(
    full: bool = False,
    task_id: Optional[str] = None,
    user_task: Optional[str] = None
) -> str:
    """
    Get a text-based snapshot of the current page's accessibility tree.
    
    Args:
        full: If True, return complete snapshot. If False, return compact view.
        task_id: Task identifier for session isolation
        user_task: The user's current task (for task-aware extraction)
        
    Returns:
        JSON string with page snapshot
    """
    effective_task_id = task_id or "default"
    
    # Build command args based on full flag
    args = []
    if not full:
        args.extend(["-c"])  # Compact mode
    
    result = _run_browser_command(effective_task_id, "snapshot", args)
    
    if result.get("success"):
        data = result.get("data", {})
        snapshot_text = data.get("snapshot", "")
        refs = data.get("refs", {})

        if not snapshot_text and not refs:
            return json.dumps({
                "success": False,
                "error": (
                    "Snapshot returned empty content. The page may be blank, login-gated, "
                    "bot-blocked, or the browser/CDP session may be stale."
                ),
                "details": {
                    "hint": "Try navigating again or re-opening the page before requesting a snapshot."
                }
            }, ensure_ascii=False)
        
        # Check if snapshot needs summarization
        if len(snapshot_text) > SNAPSHOT_SUMMARIZE_THRESHOLD and user_task:
            snapshot_text = _extract_relevant_content(snapshot_text, user_task)
        elif len(snapshot_text) > SNAPSHOT_SUMMARIZE_THRESHOLD:
            snapshot_text = _truncate_snapshot(snapshot_text)
        
        response = {
            "success": True,
            "snapshot": snapshot_text,
            "element_count": len(refs) if refs else 0
        }
        
        return json.dumps(response, ensure_ascii=False)
    else:
        return json.dumps({
            "success": False,
            "error": result.get("error", "Failed to get snapshot")
        }, ensure_ascii=False)


def browser_click(ref: str, task_id: Optional[str] = None) -> str:
    """
    Click on an element.
    
    Args:
        ref: Element reference (e.g., "@e5")
        task_id: Task identifier for session isolation
        
    Returns:
        JSON string with click result
    """
    effective_task_id = task_id or "default"
    
    # Ensure ref starts with @
    if not ref.startswith("@"):
        ref = f"@{ref}"
    
    result = _run_browser_command(effective_task_id, "click", [ref])
    
    if result.get("success"):
        return json.dumps({
            "success": True,
            "clicked": ref
        }, ensure_ascii=False)
    else:
        return json.dumps({
            "success": False,
            "error": result.get("error", f"Failed to click {ref}")
        }, ensure_ascii=False)


def browser_type(ref: str, text: str, task_id: Optional[str] = None) -> str:
    """
    Type text into an input field.
    
    Args:
        ref: Element reference (e.g., "@e3")
        text: Text to type
        task_id: Task identifier for session isolation
        
    Returns:
        JSON string with type result
    """
    effective_task_id = task_id or "default"
    
    # Ensure ref starts with @
    if not ref.startswith("@"):
        ref = f"@{ref}"
    
    # Use fill command (clears then types)
    result = _run_browser_command(effective_task_id, "fill", [ref, text])
    
    if result.get("success"):
        return json.dumps({
            "success": True,
            "typed": text,
            "element": ref
        }, ensure_ascii=False)
    else:
        return json.dumps({
            "success": False,
            "error": result.get("error", f"Failed to type into {ref}")
        }, ensure_ascii=False)


def browser_scroll(direction: str, task_id: Optional[str] = None) -> str:
    """
    Scroll the page.
    
    Args:
        direction: "up" or "down"
        task_id: Task identifier for session isolation
        
    Returns:
        JSON string with scroll result
    """
    effective_task_id = task_id or "default"
    
    # Validate direction
    if direction not in ["up", "down"]:
        return json.dumps({
            "success": False,
            "error": f"Invalid direction '{direction}'. Use 'up' or 'down'."
        }, ensure_ascii=False)
    
    result = _run_browser_command(effective_task_id, "scroll", [direction])
    
    if result.get("success"):
        return json.dumps({
            "success": True,
            "scrolled": direction
        }, ensure_ascii=False)
    else:
        return json.dumps({
            "success": False,
            "error": result.get("error", f"Failed to scroll {direction}")
        }, ensure_ascii=False)


def browser_back(task_id: Optional[str] = None) -> str:
    """
    Navigate back in browser history.
    
    Args:
        task_id: Task identifier for session isolation
        
    Returns:
        JSON string with navigation result
    """
    effective_task_id = task_id or "default"
    result = _run_browser_command(effective_task_id, "back", [])
    
    if result.get("success"):
        data = result.get("data", {})
        return json.dumps({
            "success": True,
            "url": data.get("url", "")
        }, ensure_ascii=False)
    else:
        return json.dumps({
            "success": False,
            "error": result.get("error", "Failed to go back")
        }, ensure_ascii=False)


def browser_press(key: str, task_id: Optional[str] = None) -> str:
    """
    Press a keyboard key.
    
    Args:
        key: Key to press (e.g., "Enter", "Tab")
        task_id: Task identifier for session isolation
        
    Returns:
        JSON string with key press result
    """
    effective_task_id = task_id or "default"
    result = _run_browser_command(effective_task_id, "press", [key])
    
    if result.get("success"):
        return json.dumps({
            "success": True,
            "pressed": key
        }, ensure_ascii=False)
    else:
        return json.dumps({
            "success": False,
            "error": result.get("error", f"Failed to press {key}")
        }, ensure_ascii=False)


def browser_close(task_id: Optional[str] = None) -> str:
    """
    Close the browser session.
    
    Args:
        task_id: Task identifier for session isolation
        
    Returns:
        JSON string with close result
    """
    effective_task_id = task_id or "default"
    with _cleanup_lock:
        had_session = effective_task_id in _active_sessions

    cleanup_browser(effective_task_id)

    response = {
        "success": True,
        "closed": True,
    }
    if not had_session:
        response["warning"] = "Session may not have been active"
    return json.dumps(response, ensure_ascii=False)


def browser_get_images(task_id: Optional[str] = None) -> str:
    """
    Get all images on the current page.
    
    Args:
        task_id: Task identifier for session isolation
        
    Returns:
        JSON string with list of images (src and alt)
    """
    effective_task_id = task_id or "default"
    
    # Use eval to run JavaScript that extracts images
    js_code = """JSON.stringify(
        [...document.images].map(img => ({
            src: img.src,
            alt: img.alt || '',
            width: img.naturalWidth,
            height: img.naturalHeight
        })).filter(img => img.src && !img.src.startsWith('data:'))
    )"""
    
    result = _run_browser_command(effective_task_id, "eval", [js_code])
    
    if result.get("success"):
        data = result.get("data", {})
        raw_result = data.get("result", "[]")
        
        try:
            # Parse the JSON string returned by JavaScript
            if isinstance(raw_result, str):
                images = json.loads(raw_result)
            else:
                images = raw_result
            
            return json.dumps({
                "success": True,
                "images": images,
                "count": len(images)
            }, ensure_ascii=False)
        except json.JSONDecodeError:
            return json.dumps({
                "success": True,
                "images": [],
                "count": 0,
                "warning": "Could not parse image data"
            }, ensure_ascii=False)
    else:
        return json.dumps({
            "success": False,
            "error": result.get("error", "Failed to get images")
        }, ensure_ascii=False)


def browser_vision(question: str, task_id: Optional[str] = None) -> str:
    """
    Take a screenshot of the current page and analyze it with vision AI.
    
    This tool captures what's visually displayed in the browser and sends it
    to Gemini for analysis. Useful for understanding visual content that the
    text-based snapshot may not capture (CAPTCHAs, verification challenges,
    images, complex layouts, etc.).
    
    Args:
        question: What you want to know about the page visually
        task_id: Task identifier for session isolation
        
    Returns:
        JSON string with vision analysis results and a persistent screenshot_path
    """
    import base64
    import uuid as uuid_mod
    
    effective_task_id = task_id or "default"
    
    # Check auxiliary vision client
    if _aux_vision_client is None or EXTRACTION_MODEL is None:
        return json.dumps({
            "success": False,
            "error": "Browser vision unavailable: no auxiliary vision model configured. "
                     "Set OPENROUTER_API_KEY, configure Nous Portal, or sign in to Codex to enable browser vision."
        }, ensure_ascii=False)
    
    screenshots_dir = _browser_screenshots_dir()
    screenshot_path = screenshots_dir / f"browser_screenshot_{uuid_mod.uuid4().hex}.png"
    
    try:
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        _cleanup_old_screenshots(screenshots_dir, max_age_hours=24)

        def _resolve_image_path(command_result: Dict[str, Any]) -> Path | None:
            candidates: list[Path] = [screenshot_path]
            data = command_result.get("data", {}) if isinstance(command_result, dict) else {}
            for key in ("path", "screenshot_path", "screenshotPath", "file", "file_path"):
                value = None
                if isinstance(command_result, dict):
                    value = command_result.get(key)
                if not value and isinstance(data, dict):
                    value = data.get(key)
                if value:
                    candidates.append(Path(str(value)))
            for candidate in candidates:
                if candidate.exists():
                    return candidate
            return None

        # Take screenshot using agent-browser (with one retry).
        result = None
        image_path: Path | None = None
        for _attempt in range(2):
            result = _run_browser_command(
                effective_task_id,
                "screenshot",
                [str(screenshot_path)],
                timeout=30
            )
            if not result.get("success"):
                continue
            image_path = _resolve_image_path(result)
            if image_path:
                break

        if not result or not result.get("success"):
            return json.dumps({
                "success": False,
                "error": f"Failed to take screenshot: {(result or {}).get('error', 'Unknown error')}"
            }, ensure_ascii=False)

        if not image_path:
            return json.dumps({
                "success": False,
                "error": "Screenshot file was not created",
                "details": result
            }, ensure_ascii=False)

        if image_path != screenshot_path:
            shutil.copy2(image_path, screenshot_path)
            try:
                image_path.unlink()
            except Exception:
                logger.debug("Could not remove temporary browser screenshot %s", image_path, exc_info=True)
            image_path = screenshot_path
        
        # Read and convert to base64
        image_data = image_path.read_bytes()
        image_base64 = base64.b64encode(image_data).decode("ascii")
        data_url = f"data:image/png;base64,{image_base64}"
        
        vision_prompt = (
            f"You are analyzing a screenshot of a web browser.\n\n"
            f"User's question: {question}\n\n"
            f"Provide a detailed and helpful answer based on what you see in the screenshot. "
            f"If there are interactive elements, describe them. If there are verification challenges "
            f"or CAPTCHAs, describe what type they are and what action might be needed. "
            f"Focus on answering the user's specific question."
        )

        # Use the sync auxiliary vision client directly
        from agent.auxiliary_client import auxiliary_max_tokens_param
        response = _aux_vision_client.chat.completions.create(
            model=EXTRACTION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": vision_prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            **auxiliary_max_tokens_param(2000),
            temperature=0.1,
        )
        
        analysis = response.choices[0].message.content
        return json.dumps({
            "success": True,
            "analysis": analysis,
            "screenshot_path": str(screenshot_path),
        }, ensure_ascii=False)
    
    except Exception as e:
        error_text = str(e)
        if "Insufficient credits" in error_text or "code': 402" in error_text or '"code": 402' in error_text:
            error_text = (
                "Vision analysis failed because the auxiliary vision provider reported insufficient credits "
                "(HTTP 402 from OpenRouter). Screenshot capture may have succeeded, but image analysis could not run."
            )
        else:
            error_text = f"Error during vision analysis: {error_text}"
        return json.dumps({
            "success": False,
            "error": error_text
        }, ensure_ascii=False)


# ============================================================================
# Cleanup and Management Functions
# ============================================================================

def _close_browserbase_session(session_id: str, api_key: str, project_id: str) -> bool:
    """
    Close a Browserbase session immediately via the API.
    
    Uses POST /v1/sessions/{id} with status=REQUEST_RELEASE to immediately
    terminate the session without waiting for keepAlive timeout.
    
    Args:
        session_id: The Browserbase session ID
        api_key: Browserbase API key
        project_id: Browserbase project ID
        
    Returns:
        True if session was successfully closed, False otherwise
    """
    try:
        # POST to update session status to REQUEST_RELEASE
        response = requests.post(
            f"https://api.browserbase.com/v1/sessions/{session_id}",
            headers={
                "X-BB-API-Key": api_key,
                "Content-Type": "application/json"
            },
            json={
                "projectId": project_id,
                "status": "REQUEST_RELEASE"
            },
            timeout=10
        )
        
        if response.status_code in (200, 201, 204):
            logger.debug("Successfully closed BrowserBase session %s", session_id)
            return True
        else:
            logger.warning("Failed to close session %s: HTTP %s - %s", session_id, response.status_code, response.text[:200])
            return False
                
    except Exception as e:
        logger.error("Exception closing session %s: %s", session_id, e)
        return False


def cleanup_browser(task_id: Optional[str] = None) -> None:
    """
    Clean up browser session for a task.
    
    Called automatically when a task completes or when inactivity timeout is reached.
    Closes both the agent-browser session and the Browserbase session.
    
    Args:
        task_id: Task identifier to clean up
    """
    if task_id is None:
        task_id = "default"
    
    logger.debug("cleanup_browser called for task_id: %s", task_id)
    logger.debug("Active sessions: %s", list(_active_sessions.keys()))

    if _using_playwright_backend():
        _run_playwright_command(task_id, "close", [], timeout=5)
        return
    
    # Check if session exists (under lock), but don't remove yet -
    # _run_browser_command needs it to build the close command.
    with _cleanup_lock:
        session_info = _active_sessions.get(task_id)
    
    if session_info:
        bb_session_id = session_info.get("bb_session_id", "unknown")
        logger.debug("Found session for task %s: bb_session_id=%s", task_id, bb_session_id)
        
        # Try to close via agent-browser first (needs session in _active_sessions)
        try:
            _run_browser_command(task_id, "close", [], timeout=10)
            logger.debug("agent-browser close command completed for task %s", task_id)
        except Exception as e:
            logger.warning("agent-browser close failed for task %s: %s", task_id, e)
        
        # Now remove from tracking under lock
        with _cleanup_lock:
            _active_sessions.pop(task_id, None)
            _session_last_activity.pop(task_id, None)
        
        # Close the Browserbase session immediately via API
        try:
            config = _get_browserbase_config()
            success = _close_browserbase_session(bb_session_id, config["api_key"], config["project_id"])
            if not success:
                logger.warning("Could not close BrowserBase session %s", bb_session_id)
        except Exception as e:
            logger.error("Exception during BrowserBase session close: %s", e)
        
        # Kill the daemon process and clean up socket directory
        session_name = session_info.get("session_name", "")
        if session_name:
            socket_dir = os.path.join(tempfile.gettempdir(), f"agent-browser-{session_name}")
            if os.path.exists(socket_dir):
                # agent-browser writes {session}.pid in the socket dir
                pid_file = os.path.join(socket_dir, f"{session_name}.pid")
                if os.path.isfile(pid_file):
                    try:
                        daemon_pid = int(open(pid_file, encoding="utf-8").read().strip())
                        os.kill(daemon_pid, signal.SIGTERM)
                        logger.debug("Killed daemon pid %s for %s", daemon_pid, session_name)
                    except (ProcessLookupError, ValueError, PermissionError, OSError):
                        pass
                shutil.rmtree(socket_dir, ignore_errors=True)
        
        logger.debug("Removed task %s from active sessions", task_id)
    else:
        logger.debug("No active session found for task_id: %s", task_id)


def cleanup_all_browsers() -> None:
    """
    Clean up all active browser sessions.
    
    Useful for cleanup on shutdown.
    """
    with _cleanup_lock:
        task_ids = list(_active_sessions.keys())
    for task_id in task_ids:
        cleanup_browser(task_id)


def get_active_browser_sessions() -> Dict[str, Dict[str, str]]:
    """
    Get information about active browser sessions.
    
    Returns:
        Dict mapping task_id to session info (session_name, bb_session_id, cdp_url)
    """
    with _cleanup_lock:
        return _active_sessions.copy()


# ============================================================================
# Requirements Check
# ============================================================================

def check_browser_requirements() -> bool:
    """
    Check if browser tool requirements are met.
    
    Returns:
        True if all requirements are met, False otherwise
    """
    if _using_playwright_backend():
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
            return True
        except Exception:
            return False

    # Check for Browserbase credentials
    api_key = os.environ.get("BROWSERBASE_API_KEY")
    project_id = os.environ.get("BROWSERBASE_PROJECT_ID")

    if not api_key or not project_id:
        return False

    # Check for agent-browser CLI
    try:
        _find_agent_browser()
        return True
    except FileNotFoundError:
        return False


# ============================================================================
# Module Test
# ============================================================================

if __name__ == "__main__":
    """
    Simple test/demo when run directly
    """
    print("🌐 Browser Tool Module")
    print("=" * 40)
    
    # Check requirements
    if check_browser_requirements():
        print("✅ All requirements met")
    else:
        print("❌ Missing requirements:")
        if not os.environ.get("BROWSERBASE_API_KEY"):
            print("   - BROWSERBASE_API_KEY not set")
        if not os.environ.get("BROWSERBASE_PROJECT_ID"):
            print("   - BROWSERBASE_PROJECT_ID not set")
        try:
            _find_agent_browser()
        except FileNotFoundError:
            print("   - agent-browser CLI not found")
    
    print("\n📋 Available Browser Tools:")
    for schema in BROWSER_TOOL_SCHEMAS:
        print(f"  🔹 {schema['name']}: {schema['description'][:60]}...")
    
    print("\n💡 Usage:")
    print("  from tools.browser_tool import browser_navigate, browser_snapshot")
    print("  result = browser_navigate('https://example.com', task_id='my_task')")
    print("  snapshot = browser_snapshot(task_id='my_task')")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
from tools.registry import registry

_BROWSER_SCHEMA_MAP = {s["name"]: s for s in BROWSER_TOOL_SCHEMAS}

registry.register(
    name="browser_navigate",
    toolset="browser",
    schema=_BROWSER_SCHEMA_MAP["browser_navigate"],
    handler=lambda args, **kw: browser_navigate(url=args.get("url", ""), task_id=kw.get("task_id")),
    check_fn=check_browser_requirements,
    requires_env=[],
)
registry.register(
    name="browser_snapshot",
    toolset="browser",
    schema=_BROWSER_SCHEMA_MAP["browser_snapshot"],
    handler=lambda args, **kw: browser_snapshot(
        full=args.get("full", False), task_id=kw.get("task_id"), user_task=kw.get("user_task")),
    check_fn=check_browser_requirements,
    requires_env=[],
)
registry.register(
    name="browser_click",
    toolset="browser",
    schema=_BROWSER_SCHEMA_MAP["browser_click"],
    handler=lambda args, **kw: browser_click(**args, task_id=kw.get("task_id")),
    check_fn=check_browser_requirements,
    requires_env=[],
)
registry.register(
    name="browser_type",
    toolset="browser",
    schema=_BROWSER_SCHEMA_MAP["browser_type"],
    handler=lambda args, **kw: browser_type(**args, task_id=kw.get("task_id")),
    check_fn=check_browser_requirements,
    requires_env=[],
)
registry.register(
    name="browser_scroll",
    toolset="browser",
    schema=_BROWSER_SCHEMA_MAP["browser_scroll"],
    handler=lambda args, **kw: browser_scroll(**args, task_id=kw.get("task_id")),
    check_fn=check_browser_requirements,
    requires_env=[],
)
registry.register(
    name="browser_back",
    toolset="browser",
    schema=_BROWSER_SCHEMA_MAP["browser_back"],
    handler=lambda args, **kw: browser_back(task_id=kw.get("task_id")),
    check_fn=check_browser_requirements,
    requires_env=[],
)
registry.register(
    name="browser_press",
    toolset="browser",
    schema=_BROWSER_SCHEMA_MAP["browser_press"],
    handler=lambda args, **kw: browser_press(key=args.get("key", ""), task_id=kw.get("task_id")),
    check_fn=check_browser_requirements,
    requires_env=[],
)
registry.register(
    name="browser_close",
    toolset="browser",
    schema=_BROWSER_SCHEMA_MAP["browser_close"],
    handler=lambda args, **kw: browser_close(task_id=kw.get("task_id")),
    check_fn=check_browser_requirements,
    requires_env=[],
)
registry.register(
    name="browser_get_images",
    toolset="browser",
    schema=_BROWSER_SCHEMA_MAP["browser_get_images"],
    handler=lambda args, **kw: browser_get_images(task_id=kw.get("task_id")),
    check_fn=check_browser_requirements,
    requires_env=[],
)
registry.register(
    name="browser_vision",
    toolset="browser",
    schema=_BROWSER_SCHEMA_MAP["browser_vision"],
    handler=lambda args, **kw: browser_vision(question=args.get("question", ""), task_id=kw.get("task_id")),
    check_fn=check_browser_requirements,
    requires_env=[],
)
