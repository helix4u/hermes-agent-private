---
title: Browser Automation
description: Control websites with Hermes's Playwright-backed browser tools, with optional Browserbase fallback.
sidebar_label: Browser
sidebar_position: 5
---

# Browser Automation

Hermes Agent includes a full browser automation toolset powered by a local Playwright backend by default, with the legacy [Browserbase](https://browserbase.com) path still available as an opt-in fallback. The goal is simple: free local browser control first, paid cloud sessions only if you explicitly want them.

## Overview

The browser tools expose the same `browser_*` interface regardless of backend. On the default Playwright backend, Hermes launches a persistent local Chromium profile, applies lightweight anti-automation shims, and builds text snapshots with stable element refs like `@e1`, `@e2` for clicking and typing.

Key capabilities:

- **Local execution by default** — no Browserbase account required
- **Persistent profile support** — reuse cookies, sessions, and seeded credentials
- **Light anti-detection shims** — user-agent, webdriver, hardware, timezone, screen, and media fingerprint shaping
- **Session isolation** — each task gets its own browser session
- **Automatic cleanup** — inactive sessions are closed after a timeout
- **Optional Browserbase fallback** — still available when you explicitly enable it
- **Vision analysis** — screenshot + AI analysis for visual understanding

## Setup

### Default Setup: Local Playwright

```bash
# ~/.hermes/config.yaml
browser:
  backend: playwright
  navigate_timeout: 12
  headless: false
```

Optional environment variables for the local backend:

```bash
# ~/.hermes/.env
BROWSER_PROFILE_DIR=C:\Users\you\.hermes\browser-profile
BROWSER_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36
```

`BROWSER_PROFILE_DIR` is the important one if you want Hermes to reuse a seeded browser profile with existing cookies or login state.

### Optional Browserbase Fallback

```bash
# ~/.hermes/config.yaml
browser:
  backend: browserbase

# ~/.hermes/.env
BROWSERBASE_API_KEY=your-api-key-here
BROWSERBASE_PROJECT_ID=your-project-id-here

# Optional Browserbase extras
BROWSERBASE_PROXIES=true
BROWSERBASE_ADVANCED_STEALTH=false
BROWSERBASE_KEEP_ALIVE=true
BROWSERBASE_SESSION_TIMEOUT=600000
```

### Local Backend Configuration

```bash
# ~/.hermes/.env
BROWSER_INACTIVITY_TIMEOUT=120
BROWSER_NAVIGATE_TIMEOUT=12
BROWSER_HEADLESS=false
```

:::info
The `browser` toolset must be included in your config's `toolsets` list or enabled via `hermes config set toolsets '["hermes-cli", "browser"]'`.
:::

## Available Tools

### `browser_navigate`

Navigate to a URL. Must be called before any other browser tool. Initializes the active browser session for the selected backend.

```
Navigate to https://github.com/NousResearch
```

:::tip
For simple information retrieval, prefer `web_search` or `web_extract` — they are faster and cheaper. Use browser tools when you need to **interact** with a page (click buttons, fill forms, handle dynamic content).
:::

### `browser_snapshot`

Get a text-based snapshot of the current page's accessibility tree. Returns interactive elements with ref IDs like `@e1`, `@e2` for use with `browser_click` and `browser_type`.

- **`full=false`** (default): Compact view showing only interactive elements
- **`full=true`**: Complete page content

Snapshots over 8000 characters are automatically summarized by an LLM.

### `browser_click`

Click an element identified by its ref ID from the snapshot.

```
Click @e5 to press the "Sign In" button
```

### `browser_type`

Type text into an input field. Clears the field first, then types the new text.

```
Type "hermes agent" into the search field @e3
```

### `browser_scroll`

Scroll the page up or down to reveal more content.

```
Scroll down to see more results
```

### `browser_press`

Press a keyboard key. Useful for submitting forms or navigation.

```
Press Enter to submit the form
```

Supported keys: `Enter`, `Tab`, `Escape`, `ArrowDown`, `ArrowUp`, and more.

### `browser_back`

Navigate back to the previous page in browser history.

### `browser_get_images`

List all images on the current page with their URLs and alt text. Useful for finding images to analyze.

### `browser_vision`

Take a screenshot and analyze it with a vision model. Use this when text snapshots don't capture important visual information — especially useful for CAPTCHAs, complex layouts, or visual verification challenges.

```
What does the chart on this page show?
```

### `browser_close`

Close the browser session and release resources. On the Playwright backend this closes the local page. On the Browserbase backend it also releases the remote session quota.

## Practical Examples

### Filling Out a Web Form

```
User: Sign up for an account on example.com with my email john@example.com

Agent workflow:
1. browser_navigate("https://example.com/signup")
2. browser_snapshot()  → sees form fields with refs
3. browser_type(ref="@e3", text="john@example.com")
4. browser_type(ref="@e5", text="SecurePass123")
5. browser_click(ref="@e8")  → clicks "Create Account"
6. browser_snapshot()  → confirms success
7. browser_close()
```

### Researching Dynamic Content

```
User: What are the top trending repos on GitHub right now?

Agent workflow:
1. browser_navigate("https://github.com/trending")
2. browser_snapshot(full=true)  → reads trending repo list
3. Returns formatted results
4. browser_close()
```

## Backend Behavior

The current default is `playwright`. Browserbase is optional.

| Feature | Default | Notes |
|---------|---------|-------|
| Backend | `playwright` | Free local browser automation with a persistent profile |
| Profile reuse | On when `BROWSER_PROFILE_DIR` is set | Good for seeded creds/cookies |
| User-agent override | On | Configurable with `BROWSER_USER_AGENT` |
| Browserbase fallback | Off by default | Enable with `browser.backend: browserbase` |
| Browser vision | Separate from backend | Still requires a configured vision provider |

:::note
Local Playwright browsing is free. `browser_vision` is a separate capability and still depends on your configured multimodal provider.
:::

## Session Management

- Each task gets an isolated browser session
- Sessions are automatically cleaned up after inactivity
- A background thread checks every 30 seconds for stale sessions
- Emergency cleanup runs on process exit to prevent orphaned sessions
- Browserbase sessions are only released via API when the Browserbase backend is active

## Limitations

- **Text-based interaction** — snapshots are DOM/text driven, not pixel-coordinate computer use
- **Anti-detection is best-effort** — user-agent spoofing and webdriver masking help, but some sites still block automation
- **Anti-detection is best-effort** — Hermes now shapes user-agent, hardware, timezone, screen, and media signals, but determined anti-bot systems can still detect automation
- **Snapshot size** — large pages may be truncated or LLM-summarized at 8000 characters
- **Browser vision is not free by itself** — screenshot analysis still depends on the configured multimodal backend
- **Browserbase costs only apply if you switch to the Browserbase backend**
- **No file downloads** — cannot download files from the browser
