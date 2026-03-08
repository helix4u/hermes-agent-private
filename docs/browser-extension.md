# Browser Extension Bridge

Hermes Agent includes a localhost browser bridge that lets a Chrome extension
run a dedicated browser chat session through the gateway while still sharing the
current page context when needed.

## How it works

1. `hermes gateway start` starts a local HTTP bridge on `127.0.0.1:8765`.
2. The Chrome extension opens a side panel with its own stable Hermes session.
3. Extension configuration lives in the extension options page (`options.html`),
   not in the side panel chat UI.
4. The extension can either send a normal chat turn or attach the active tab's
   context to that turn.
5. The gateway converts each request into a local `MessageEvent` and runs it
   through the normal Hermes agent flow.
6. The side panel loads its transcript history from the same gateway session
   store Hermes uses everywhere else.

The injected session is separate from the CLI session. A browser session uses a
local channel key like:

`agent:main:local:channel:browser-bridge:chrome-extension:<client-session-id>`

## Security model

- The bridge binds to `127.0.0.1` by default.
- Requests require a bearer token.
- If `HERMES_BROWSER_BRIDGE_TOKEN` is not set, Hermes creates a token at
  `~/.hermes/browser_bridge_token`.
- Browser pages do not get CORS access automatically; the bridge only reflects
  Chrome extension origins.

## Environment variables

- `HERMES_BROWSER_BRIDGE_ENABLED`
  Default: `true`
- `HERMES_BROWSER_BRIDGE_HOST`
  Default: `127.0.0.1`
- `HERMES_BROWSER_BRIDGE_PORT`
  Default: `8765`
- `HERMES_BROWSER_BRIDGE_TOKEN`
  Optional override for the token stored in `~/.hermes/browser_bridge_token`

## Endpoints

### `GET /health`

Returns basic bridge status.

### `POST /inject`

Accepts a page-context payload and sends it as a browser-context turn.

### `POST /session`

Accepts a JSON body with one of these actions:

- `state`: load the current browser session transcript
- `send`: send a normal chat turn, optionally with `pageContext`
- `reset`: start a fresh browser session without affecting the CLI

Example `send` shape:

```json
{
  "action": "send",
  "browserLabel": "Hermes Sidecar",
  "clientSessionId": "b6d3f6d7-...",
  "message": "Summarize this page for me.",
  "pageContext": {
    "url": "https://www.youtube.com/watch?v=example",
    "title": "Example video",
    "pageText": "Visible page text",
    "transcript": {
      "available": true,
      "shared": true,
      "sharedPreviously": false,
      "language": "en",
      "text": "Transcript text"
    }
  }
}
```

## Chrome extension

The unpacked extension lives in [`browser-extension`](../browser-extension).
It uses Chrome's `sidePanel` API so clicking the toolbar icon opens a persistent
Hermes Sidecar with chat history, a normal composer, and optional page sharing
for each turn.
