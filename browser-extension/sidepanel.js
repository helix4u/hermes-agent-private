const AUTO_REFRESH_MS = 1000;

const pageTitle = document.getElementById("page-title");
const pageUrl = document.getElementById("page-url");
const contentKind = document.getElementById("content-kind");
const selectionLength = document.getElementById("selection-length");
const pageTextLength = document.getElementById("page-text-length");
const transcriptStatus = document.getElementById("transcript-status");
const chatMessages = document.getElementById("chat-messages");
const chatInput = document.getElementById("chat-input");
const sharePageCheckbox = document.getElementById("share-page");
const includeTranscript = document.getElementById("include-transcript");
const includeTranscriptLabel = document.getElementById("include-transcript-label");
const statusText = document.getElementById("status-text");
const domainPermissionStatus = document.getElementById("domain-permission-status");
const domainPermissionButton = document.getElementById("domain-permission-button");
const activityText = document.getElementById("activity-text");
const sendButton = document.getElementById("send-button");
const resetChatButton = document.getElementById("reset-chat-button");
const activityPanel = document.getElementById("activity-panel");
const sessionHistorySelect = document.getElementById("session-history-select");
const refreshSessionsButton = document.getElementById("refresh-sessions-button");
const challengeModeButton = document.getElementById("challenge-mode-button");
const bundlePanel = document.getElementById("bundle-panel");
const bundleList = document.getElementById("bundle-list");
const bundleModeNote = document.getElementById("bundle-mode-note");
const presetButtons = Array.from(document.querySelectorAll(".preset-button"));
const STATUS_INLINE_MAX_CHARS = 220;
const STATUS_INLINE_MAX_LINES = 3;
const STATUS_ACTIVITY_MAX_CHARS = 700;
const STATUS_ACTIVITY_MAX_LINES = 10;
const PROGRESS_DETAIL_MAX_CHARS = 140;
const PROGRESS_EVENT_MAX_CHARS = 110;

let activeTabId = null;
let pollTimer = null;
let previewTimer = null;
let refreshDebounceTimer = null;
let previewInFlight = false;
let currentMessages = [];
let currentProgress = null;
let pendingUserMessage = null;
let lastPreview = null;
let sharePageByDefault = true;
let isBusy = false;
let pendingQueuedAt = 0;
let expectedSessionKey = "";
let selectedSessionKey = "";
let isApplyingSessionSelection = false;
let pageContextUnavailable = false;
let latestDomainPermission = null;
let challengeModeEnabled = false;
let bundleSelectionState = null;
let activeAudioMessageKey = "";
let activeReplyAudio = null;
let activeReplyAudioUrl = "";

function compactStatusText(
  message,
  {
    maxChars = STATUS_INLINE_MAX_CHARS,
    maxLines = STATUS_INLINE_MAX_LINES,
    perLineMax = 120
  } = {}
) {
  const normalized = String(message || "")
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .replace(/\t/g, " ")
    .trim();
  if (!normalized) {
    return "";
  }

  const lines = normalized
    .split("\n")
    .map((line) => line.replace(/\s+/g, " ").trim())
    .filter(Boolean)
    .slice(0, maxLines)
    .map((line) => {
      if (line.length > perLineMax) {
        return `${line.slice(0, perLineMax - 1).trimEnd()}...`;
      }
      return line;
    });

  let compacted = lines.join("\n");
  if (compacted.length > maxChars) {
    compacted = `${compacted.slice(0, maxChars - 1).trimEnd()}...`;
  }
  return compacted;
}

function summarizeToolLine(line) {
  const text = String(line || "").trim();
  if (!text) {
    return "";
  }

  const callMatch = text.match(/\bCALL\s+([A-Za-z0-9_.-]+)/i);
  if (callMatch) {
    return `CALL ${callMatch[1]}`;
  }

  const runMatch = text.match(/\bRUN\s+([A-Za-z0-9_.-]+)/i);
  if (runMatch) {
    return `RUN ${runMatch[1]}`;
  }

  return "";
}

function summarizeStatusMessage(message, fallback = "Working...") {
  const normalized = String(message || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const lines = normalized.split("\n").map((line) => line.trim()).filter(Boolean);
  if (!lines.length) {
    return fallback;
  }

  const toolSummaries = [];
  for (const line of lines) {
    const summary = summarizeToolLine(line);
    if (summary && !toolSummaries.includes(summary)) {
      toolSummaries.push(summary);
    }
  }
  if (toolSummaries.length) {
    return `Working: ${toolSummaries.slice(0, 3).join(", ")}`;
  }

  const firstLine = lines[0];
  if (/[{[]/.test(firstLine) && firstLine.length > 80) {
    return fallback;
  }
  return firstLine;
}

function setStatus(message, { openActivity = false } = {}) {
  const summarized = summarizeStatusMessage(message, "Waiting for input.");
  const inlineMessage = compactStatusText(summarized, {
    maxChars: STATUS_INLINE_MAX_CHARS,
    maxLines: 2,
    perLineMax: 110
  }) || "Waiting for input.";
  const activityMessage = compactStatusText(message, {
    maxChars: STATUS_ACTIVITY_MAX_CHARS,
    maxLines: STATUS_ACTIVITY_MAX_LINES,
    perLineMax: 180
  }) || "Waiting for input.";

  statusText.textContent = inlineMessage;
  if (activityText) {
    activityText.textContent = activityMessage;
  }
  if (openActivity && activityPanel) {
    activityPanel.open = true;
  }
}

function getMessageText(message) {
  return String(message?.display_content || message?.content || "").trim();
}

async function copyTextToClipboard(text) {
  const value = String(text || "");
  if (!value) {
    return;
  }
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }

  const fallback = document.createElement("textarea");
  fallback.value = value;
  fallback.setAttribute("readonly", "readonly");
  fallback.style.position = "fixed";
  fallback.style.opacity = "0";
  document.body.appendChild(fallback);
  fallback.select();
  document.execCommand("copy");
  document.body.removeChild(fallback);
}

function rerenderCurrentMessages() {
  renderMessages(currentMessages, currentProgress, pendingUserMessage);
}

function clearReplyAudioState() {
  if (activeReplyAudio) {
    try {
      activeReplyAudio.pause();
    } catch (_error) {
      // Ignore pause failures during cleanup.
    }
    activeReplyAudio.src = "";
  }
  if (activeReplyAudioUrl) {
    URL.revokeObjectURL(activeReplyAudioUrl);
  }
  activeReplyAudio = null;
  activeReplyAudioUrl = "";
  activeAudioMessageKey = "";
}

function stopReplySpeech({ rerender = true } = {}) {
  clearReplyAudioState();
  if (rerender) {
    rerenderCurrentMessages();
  }
}

function decodeBase64Audio(base64Text) {
  const binary = atob(String(base64Text || ""));
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

async function speakReply(message) {
  const text = getMessageText(message);
  if (!text) {
    return;
  }

  const nextKey = messageKey(message);
  if (activeAudioMessageKey === nextKey) {
    stopReplySpeech();
    return;
  }

  clearReplyAudioState();
  activeAudioMessageKey = nextKey;
  rerenderCurrentMessages();
  setStatus("Generating reply audio with Hermes TTS...");

  try {
    const response = await sendRuntimeMessage({
      type: "hermes:speak-chat-message",
      text
    });
    const result = response.result || {};
    const audioBase64 = String(result.audio_base64 || "");
    if (!audioBase64) {
      throw new Error("Hermes TTS did not return any audio.");
    }

    const mimeType = String(result.mime_type || "audio/mpeg");
    const audioBytes = decodeBase64Audio(audioBase64);
    const blob = new Blob([audioBytes], { type: mimeType });
    const audioUrl = URL.createObjectURL(blob);
    const audio = new Audio(audioUrl);

    activeReplyAudio = audio;
    activeReplyAudioUrl = audioUrl;
    audio.onended = () => {
      if (activeReplyAudio !== audio) {
        return;
      }
      clearReplyAudioState();
      rerenderCurrentMessages();
    };
    audio.onerror = () => {
      if (activeReplyAudio !== audio) {
        return;
      }
      clearReplyAudioState();
      rerenderCurrentMessages();
      setStatus("Could not play Hermes TTS audio.");
    };

    await audio.play();
    const provider = String(result.provider || "").trim();
    setStatus(
      provider
        ? `Playing reply with Hermes TTS (${provider}).`
        : "Playing reply with Hermes TTS."
    );
  } catch (error) {
    clearReplyAudioState();
    rerenderCurrentMessages();
    setStatus(error?.message || "Could not generate Hermes TTS audio.", { openActivity: true });
  }
}

function formatCharCount(value) {
  const count = Number(value || 0);
  if (!count) {
    return "0 chars";
  }
  return `${count.toLocaleString()} chars`;
}

function createDefaultBundleSelectionState(preview) {
  const chunks = preview?.bundle?.chunks || {};
  return {
    includeTitle: Boolean(chunks.title?.includedByDefault),
    includeUrl: Boolean(chunks.url?.includedByDefault),
    includeMetadata: Boolean(chunks.metadata?.includedByDefault),
    includeSelection: Boolean(chunks.selection?.includedByDefault),
    includePageText: Boolean(chunks.pageText?.includedByDefault)
  };
}

function syncBundleSelectionState(preview, { preserveExisting = false } = {}) {
  const defaults = createDefaultBundleSelectionState(preview);
  if (!preserveExisting || !bundleSelectionState) {
    bundleSelectionState = defaults;
    return;
  }
  bundleSelectionState = {
    includeTitle: preview?.bundle?.chunks?.title?.available
      ? bundleSelectionState.includeTitle !== false
      : defaults.includeTitle,
    includeUrl: preview?.bundle?.chunks?.url?.available
      ? bundleSelectionState.includeUrl !== false
      : defaults.includeUrl,
    includeMetadata: preview?.bundle?.chunks?.metadata?.available
      ? bundleSelectionState.includeMetadata !== false
      : defaults.includeMetadata,
    includeSelection: preview?.bundle?.chunks?.selection?.available
      ? bundleSelectionState.includeSelection !== false
      : defaults.includeSelection,
    includePageText: preview?.bundle?.chunks?.pageText?.available
      ? bundleSelectionState.includePageText !== false
      : defaults.includePageText
  };
}

function buildOutgoingMessage(message) {
  const userMessage = String(message || "").trim();
  if (!challengeModeEnabled) {
    return userMessage;
  }
  const challengeInstruction =
    "Before answering, briefly challenge my framing. " +
    "Call out likely assumptions, missing context, and plausible alternative interpretations, then continue with the best answer.";
  if (!userMessage) {
    return challengeInstruction;
  }
  return `${userMessage}\n\n${challengeInstruction}`;
}

function getContextOptionsForSend() {
  const state = bundleSelectionState || createDefaultBundleSelectionState(lastPreview);
  return {
    includeTitle: state.includeTitle !== false,
    includeUrl: state.includeUrl !== false,
    includeMetadata: state.includeMetadata !== false,
    includeSelection: state.includeSelection !== false,
    includePageText: state.includePageText !== false
  };
}

function listEnabledBundleChunks() {
  const chunks = lastPreview?.bundle?.chunks || {};
  const enabled = [];
  const state = getContextOptionsForSend();
  if (chunks.title?.available && state.includeTitle) {
    enabled.push(chunks.title.label || "Title");
  }
  if (chunks.url?.available && state.includeUrl) {
    enabled.push(chunks.url.label || "URL");
  }
  if (chunks.metadata?.available && state.includeMetadata) {
    enabled.push(chunks.metadata.label || "Metadata");
  }
  if (chunks.selection?.available && state.includeSelection) {
    enabled.push(chunks.selection.label || "Selected text");
  }
  if (chunks.pageText?.available && state.includePageText) {
    enabled.push(chunks.pageText.label || "Page text");
  }
  if (chunks.transcript?.available && includeTranscript.checked && !includeTranscript.disabled) {
    enabled.push(chunks.transcript.label || "YouTube transcript");
  }
  return enabled;
}

function applyPresetTemplate(template) {
  const value = String(template || "").trim();
  if (!value) {
    return;
  }
  const current = chatInput.value.trim();
  chatInput.value = current ? `${current}\n\n${value}` : value;
  chatInput.focus();
  chatInput.setSelectionRange(chatInput.value.length, chatInput.value.length);
}

function setChallengeModeEnabled(enabled) {
  challengeModeEnabled = Boolean(enabled);
  if (challengeModeButton) {
    challengeModeButton.setAttribute("aria-pressed", challengeModeEnabled ? "true" : "false");
  }
  if (bundleModeNote) {
    bundleModeNote.hidden = !challengeModeEnabled;
  }
}

function renderContextBundle() {
  if (!bundlePanel || !bundleList) {
    return;
  }
  const preview = lastPreview;
  const chunks = preview?.bundle?.chunks || {};
  const shouldShow = Boolean(
    sharePageCheckbox.checked &&
    !pageContextUnavailable &&
    preview &&
    Object.values(chunks).some((chunk) => chunk?.available)
  );

  const wasHidden = bundlePanel.hidden;
  bundlePanel.hidden = !shouldShow;
  bundleList.textContent = "";
  if (bundleModeNote) {
    bundleModeNote.hidden = !challengeModeEnabled;
  }
  if (!shouldShow) {
    return;
  }
  if (wasHidden) {
    bundlePanel.open = true;
  }

  const rows = [
    { chunkKey: "title", stateKey: "includeTitle" },
    { chunkKey: "url", stateKey: "includeUrl" },
    { chunkKey: "metadata", stateKey: "includeMetadata" },
    { chunkKey: "selection", stateKey: "includeSelection" },
    { chunkKey: "pageText", stateKey: "includePageText" },
    { chunkKey: "transcript", stateKey: null }
  ];

  for (const row of rows) {
    const chunk = chunks[row.chunkKey];
    if (!chunk?.available) {
      continue;
    }

    const wrapper = document.createElement("label");
    wrapper.className = "bundle-row";

    const toggle = document.createElement("input");
    toggle.className = "bundle-toggle";
    toggle.type = "checkbox";

    let checked = false;
    let disabled = false;
    if (row.chunkKey === "transcript") {
      checked = includeTranscript.checked && !includeTranscript.disabled;
      disabled = includeTranscript.disabled;
      toggle.addEventListener("change", () => {
        includeTranscript.checked = toggle.checked;
        renderContextBundle();
      });
    } else {
      checked = bundleSelectionState?.[row.stateKey] !== false;
      toggle.addEventListener("change", () => {
        bundleSelectionState = {
          ...(bundleSelectionState || createDefaultBundleSelectionState(preview)),
          [row.stateKey]: toggle.checked
        };
        renderContextBundle();
      });
    }
    toggle.checked = checked;
    toggle.disabled = disabled;
    wrapper.classList.toggle("is-disabled", !checked || disabled);
    wrapper.appendChild(toggle);

    const body = document.createElement("div");
    body.className = "bundle-body";

    const top = document.createElement("div");
    top.className = "bundle-row-top";

    const label = document.createElement("span");
    label.className = "bundle-label";
    label.textContent = chunk.label || row.chunkKey;
    top.appendChild(label);

    const metric = document.createElement("span");
    metric.className = "bundle-metric";
    metric.textContent = formatCharCount(chunk.length || 0);
    top.appendChild(metric);
    body.appendChild(top);

    if (chunk.preview) {
      const previewText = document.createElement("p");
      previewText.className = "bundle-preview";
      previewText.textContent = chunk.preview;
      body.appendChild(previewText);
    }

    if (chunk.reason) {
      const reason = document.createElement("p");
      reason.className = "bundle-reason";
      reason.textContent = chunk.reason;
      body.appendChild(reason);
    }

    wrapper.appendChild(body);
    bundleList.appendChild(wrapper);
  }
}

function renderChatNotice(message) {
  chatMessages.textContent = "";
  const empty = document.createElement("div");
  empty.className = "empty-state";
  empty.textContent = message;
  chatMessages.appendChild(empty);
}

function setBusyState(busy) {
  isBusy = busy;
  sendButton.disabled = busy;
  resetChatButton.disabled = busy;
  if (sessionHistorySelect) {
    sessionHistorySelect.disabled = busy;
  }
  if (refreshSessionsButton) {
    refreshSessionsButton.disabled = busy;
  }
  sendButton.textContent = busy ? "Working..." : "Send";
  sendButton.title = busy
    ? "Hermes is working on the current turn"
    : "Send your current message to Hermes";
}

function stopPolling() {
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
}

function schedulePolling() {
  stopPolling();
  pollTimer = setTimeout(() => {
    loadChatSession({ quiet: true }).catch((error) => {
      setStatus(error.message || String(error), { openActivity: true });
      stopPolling();
      setBusyState(false);
    });
  }, 900);
}

function startPreviewLoop() {
  if (previewTimer) {
    clearInterval(previewTimer);
  }
  previewTimer = setInterval(() => {
    refreshPreview({ quiet: true }).catch((error) => {
      setStatus(error.message || String(error), { openActivity: true });
    });
  }, AUTO_REFRESH_MS);
}

async function sendRuntimeMessage(payload) {
  const response = await chrome.runtime.sendMessage(payload);
  if (!response?.ok) {
    throw new Error(response?.error || "Unknown extension error.");
  }
  return response;
}

function explainBackgroundMismatch(error) {
  const message = String(error?.message || error || "");
  const lower = message.toLowerCase();
  if (message.includes("Unknown message type")) {
    return (
      "This side panel is talking to an older Hermes extension worker. " +
      "Reload the unpacked extension in chrome://extensions, then close and reopen the side panel."
    );
  }
  if (
    lower.includes("cannot access contents of url") ||
    lower.includes("browser-internal tab") ||
    lower.includes("internal browser page")
  ) {
    return (
      "This tab is a browser internal page and cannot be shared with Hermes. " +
      "Switch to a normal website tab, or uncheck \"Use the current page in this turn\"."
    );
  }
  if (
    lower.includes("receiving end does not exist") ||
    lower.includes("could not establish connection")
  ) {
    return (
      "This tab is using an old or unavailable Hermes page bridge. " +
      "Reload this tab and try again."
    );
  }
  return message;
}

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) {
    throw new Error("No active tab found.");
  }
  activeTabId = tab.id;
  return tab;
}

function formatTimestamp(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function formatSessionLabel(session) {
  const title = session?.browser_label || "Sidecar session";
  const updatedAt = session?.updated_at ? formatTimestamp(session.updated_at) : "";
  const rawCount = Number(session?.message_count);
  const messageCount = Number.isFinite(rawCount) ? rawCount : null;
  const running = session?.running ? " [Working]" : "";
  const countPart = messageCount === null ? "" : ` (${messageCount})`;
  const updatedPart = updatedAt ? ` \u00b7 ${updatedAt}` : "";
  return `${title}${countPart}${updatedPart}${running}`;
}

function renderSessionHistory(sessions, activeSessionKey = "") {
  if (!sessionHistorySelect) {
    return;
  }
  const normalizedSessions = Array.isArray(sessions) ? sessions : [];
  const knownKeys = new Set();
  for (const session of normalizedSessions) {
    if (session?.session_key) {
      knownKeys.add(session.session_key);
    }
  }

  let nextSelected = "";
  if (selectedSessionKey && knownKeys.has(selectedSessionKey)) {
    nextSelected = selectedSessionKey;
  } else if (activeSessionKey && knownKeys.has(activeSessionKey)) {
    nextSelected = activeSessionKey;
  } else if (expectedSessionKey && knownKeys.has(expectedSessionKey)) {
    nextSelected = expectedSessionKey;
  } else if (normalizedSessions.length > 0) {
    nextSelected = normalizedSessions[0].session_key || "";
  }

  isApplyingSessionSelection = true;
  sessionHistorySelect.textContent = "";
  if (!normalizedSessions.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No sidecar sessions yet";
    sessionHistorySelect.appendChild(option);
    sessionHistorySelect.disabled = true;
    isApplyingSessionSelection = false;
    selectedSessionKey = "";
    return;
  }

  for (const session of normalizedSessions) {
    const option = document.createElement("option");
    option.value = session.session_key || "";
    option.textContent = formatSessionLabel(session);
    sessionHistorySelect.appendChild(option);
  }

  sessionHistorySelect.disabled = isBusy;
  sessionHistorySelect.value = nextSelected;
  selectedSessionKey = nextSelected;
  if (nextSelected) {
    expectedSessionKey = nextSelected;
  }
  isApplyingSessionSelection = false;
}

function renderSessionHistoryUnavailable(message = "") {
  if (!sessionHistorySelect) {
    return;
  }

  isApplyingSessionSelection = true;
  sessionHistorySelect.textContent = "";
  const option = document.createElement("option");
  option.value = "";
  option.textContent = "Session history unavailable";
  sessionHistorySelect.appendChild(option);
  sessionHistorySelect.value = "";
  sessionHistorySelect.disabled = true;
  isApplyingSessionSelection = false;
  selectedSessionKey = "";
  expectedSessionKey = "";

  if (message) {
    setStatus(message, { openActivity: true });
  }
}

function renderDomainPermissionStatus(result) {
  latestDomainPermission = result || null;
  if (!domainPermissionStatus || !domainPermissionButton) {
    return;
  }

  const detail = String(result?.detail || "Domain access unavailable");
  if (!result?.supported) {
    domainPermissionStatus.textContent = `Domain access: ${detail}`;
    domainPermissionButton.textContent = "Allow domain";
    domainPermissionButton.disabled = true;
    return;
  }

  domainPermissionStatus.textContent = `Domain access: ${detail}`;
  if (!result.granted) {
    domainPermissionButton.textContent = "Allow domain";
    domainPermissionButton.disabled = false;
    return;
  }

  if (result.removable) {
    domainPermissionButton.textContent = "Remove domain";
    domainPermissionButton.disabled = false;
    return;
  }

  domainPermissionButton.textContent = "Built-in";
  domainPermissionButton.disabled = true;
}

async function refreshDomainPermissionStatus({ quiet = false, tabId = null } = {}) {
  const resolvedTabId = tabId || activeTabId || (await getActiveTab()).id;
  const response = await sendRuntimeMessage({
    type: "hermes:get-domain-permission-status",
    tabId: resolvedTabId
  });
  const result = response.result || {};
  renderDomainPermissionStatus(result);
  if (!quiet && result.detail) {
    setStatus(result.detail);
  }
}

async function loadSessionHistory({ quiet = false, preferredSessionKey = "" } = {}) {
  const response = await sendRuntimeMessage({
    type: "hermes:list-chat-sessions",
    sessionKey: preferredSessionKey || selectedSessionKey || expectedSessionKey || "",
    limit: 40
  });
  const result = response.result || {};
  const sessions = result.sessions || [];
  renderSessionHistory(sessions, result.active_session_key || preferredSessionKey || "");
  if (!quiet) {
    setStatus("Session history refreshed.");
  }
}

function createPendingAssistantMessage(progress) {
  const detail = compactStatusText(
    summarizeStatusMessage(progress?.detail || "Hermes is thinking...", "Hermes is thinking..."),
    {
    maxChars: PROGRESS_DETAIL_MAX_CHARS,
    maxLines: 2,
    perLineMax: 100
    }
  );
  const events = Array.isArray(progress?.recent_events)
    ? progress.recent_events
        .slice(-6)
        .map((event) => summarizeStatusMessage(event, "Working..."))
        .filter(Boolean)
        .map((event) => compactStatusText(event, {
          maxChars: PROGRESS_EVENT_MAX_CHARS,
          maxLines: 1,
          perLineMax: 100
        }))
        .filter(Boolean)
        .filter((event, index, list) => list.indexOf(event) === index)
        .slice(-3)
    : [];
  const elapsed = progress?.elapsed_seconds ? ` (${progress.elapsed_seconds}s)` : "";
  const body = events.length ? `${detail}\n\n${events.join("\n")}` : `${detail}${elapsed}`;
  return {
    role: "assistant",
    kind: "pending",
    display_content: body,
    timestamp: ""
  };
}

function buildOptimisticUserMessage(message, sharePage) {
  if (sharePage) {
    return {
      role: "user",
      kind: "page_context",
      display_content: message || "Shared the current page context.",
      page_title: lastPreview?.title || "Current page",
      page_url: lastPreview?.url || "",
      timestamp: new Date().toISOString()
    };
  }

  return {
    role: "user",
    kind: "chat",
    display_content: message,
    timestamp: new Date().toISOString()
  };
}

function messageKey(message) {
  return JSON.stringify({
    role: message?.role || "",
    kind: message?.kind || "",
    content: message?.display_content || message?.content || "",
    pageTitle: message?.page_title || "",
    pageUrl: message?.page_url || ""
  });
}

function clearPendingIfAcknowledged() {
  if (!pendingUserMessage) {
    return;
  }
  const lastUser = [...currentMessages].reverse().find((item) => item.role === "user");
  if (lastUser && messageKey(lastUser) === messageKey(pendingUserMessage)) {
    pendingUserMessage = null;
    pendingQueuedAt = 0;
  }
}

function renderMessages(messages, progress = null, optimisticMessage = null) {
  chatMessages.textContent = "";

  const displayMessages = [...(Array.isArray(messages) ? messages : [])];
  if (optimisticMessage) {
    displayMessages.push(optimisticMessage);
  }
  if (progress?.running) {
    displayMessages.push(createPendingAssistantMessage(progress));
  }

  if (!displayMessages.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "This sidecar session does not have any Hermes messages yet.";
    chatMessages.appendChild(empty);
    return;
  }

  for (const message of displayMessages) {
    const wrapper = document.createElement("article");
    const roleName = message.role === "user" ? "user" : "assistant";
    wrapper.className = `message ${roleName}`;

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    if (message.kind === "pending") {
      bubble.classList.add("pending-bubble");
    }

    const meta = document.createElement("div");
    meta.className = "message-meta";

    const role = document.createElement("span");
    role.className = "message-role";
    role.textContent = message.role === "user" ? "You" : "Hermes";
    meta.appendChild(role);

    if (message.kind === "page_context") {
      const kind = document.createElement("span");
      kind.className = "message-kind";
      kind.textContent = "Page share";
      meta.appendChild(kind);
    } else if (message.kind === "pending") {
      const kind = document.createElement("span");
      kind.className = "message-kind";
      kind.textContent = "Working";
      meta.appendChild(kind);
    }

    const time = formatTimestamp(message.timestamp);
    if (time) {
      const timeLabel = document.createElement("span");
      timeLabel.textContent = time;
      meta.appendChild(timeLabel);
    }

    bubble.appendChild(meta);

    if (message.page_title) {
      const title = document.createElement("p");
      title.className = "message-title";
      title.textContent = message.page_title;
      bubble.appendChild(title);
    }

    const body = document.createElement("p");
    body.className = "message-body";
    body.textContent = getMessageText(message);
    bubble.appendChild(body);

    const canActOnReply = message.role === "assistant" && message.kind !== "pending" && getMessageText(message);
    if (canActOnReply) {
      const actions = document.createElement("div");
      actions.className = "message-actions";

      const copyButton = document.createElement("button");
      copyButton.className = "message-action-button";
      copyButton.type = "button";
      copyButton.textContent = "Copy";
      copyButton.title = "Copy this reply to your clipboard";
      copyButton.addEventListener("click", async () => {
        try {
          await copyTextToClipboard(getMessageText(message));
          setStatus("Reply copied to clipboard.");
        } catch (error) {
          setStatus(error?.message || "Could not copy this reply.");
        }
      });
      actions.appendChild(copyButton);

      const speakButton = document.createElement("button");
      speakButton.className = "message-action-button";
      speakButton.type = "button";
      const isSpeaking = activeAudioMessageKey === messageKey(message);
      if (isSpeaking) {
        speakButton.classList.add("is-active");
      }
      speakButton.textContent = isSpeaking ? "Stop audio" : "Read aloud";
      speakButton.title = isSpeaking
        ? "Stop Hermes TTS playback for this reply"
        : "Read this reply aloud using Hermes' configured TTS voice";
      speakButton.addEventListener("click", () => {
        speakReply(message).catch((error) => {
          setStatus(error?.message || "Could not generate Hermes TTS audio.", { openActivity: true });
        });
      });
      actions.appendChild(speakButton);

      bubble.appendChild(actions);
    }

    wrapper.appendChild(bubble);
    chatMessages.appendChild(wrapper);
  }

  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function applyTranscriptUiState(result) {
  if (result.contentKind === "youtube-watch" && result.transcriptAvailable && result.transcriptAlreadyShared) {
    includeTranscript.checked = false;
    includeTranscript.disabled = true;
    includeTranscriptLabel.textContent = "Transcript already shared";
    return;
  }

  includeTranscript.disabled = false;
  includeTranscriptLabel.textContent = "Include transcript once per video";
}

function renderPreview(result) {
  pageContextUnavailable = false;
  const previousUrl = lastPreview?.url || "";
  lastPreview = result || null;
  syncBundleSelectionState(result, {
    preserveExisting: Boolean(previousUrl && previousUrl === (result?.url || ""))
  });
  pageTitle.textContent = result.title || "Untitled page";
  pageUrl.textContent = result.url || "";
  contentKind.textContent = result.contentKind || "web-page";
  selectionLength.textContent = `${result.selectionLength || 0} chars selected`;
  pageTextLength.textContent = `${result.pageTextLength || 0} chars page text`;

  if (result.contentKind === "restricted-page") {
    pageContextUnavailable = true;
    sharePageCheckbox.checked = false;
    sharePageCheckbox.disabled = true;
    includeTranscript.checked = false;
    includeTranscript.disabled = true;
    includeTranscriptLabel.textContent = "Transcript unavailable on this tab";
    transcriptStatus.textContent = "Unavailable on this tab";
    renderContextBundle();
    return;
  }

  sharePageCheckbox.disabled = false;

  if (result.transcriptAvailable) {
    if (result.transcriptAlreadyShared) {
      transcriptStatus.textContent = "Transcript already sent";
    } else {
      transcriptStatus.textContent = result.transcriptLanguage
        ? `Transcript ready (${result.transcriptLanguage})`
        : "Transcript ready";
    }
  } else {
    transcriptStatus.textContent = "No transcript";
  }

  applyTranscriptUiState(result);
  renderContextBundle();
}

function renderUnavailablePreview(message) {
  pageContextUnavailable = true;
  lastPreview = null;
  bundleSelectionState = null;
  pageTitle.textContent = "Page context unavailable";
  pageUrl.textContent = "";
  contentKind.textContent = "unavailable";
  selectionLength.textContent = "0 chars selected";
  pageTextLength.textContent = "0 chars page text";
  transcriptStatus.textContent = "No transcript";
  sharePageCheckbox.checked = false;
  sharePageCheckbox.disabled = true;
  includeTranscript.checked = false;
  includeTranscript.disabled = true;
  includeTranscriptLabel.textContent = "Transcript unavailable until page context loads";
  renderContextBundle();
  if (message) {
    setStatus(message);
  }
}

async function loadSettings() {
  const response = await sendRuntimeMessage({ type: "hermes:get-settings" });
  const settings = response.settings || {};
  includeTranscript.checked = settings.includeTranscriptByDefault !== false;
  sharePageByDefault = settings.sharePageByDefault !== false;
  sharePageCheckbox.checked = sharePageByDefault;
  renderContextBundle();
}

async function refreshPreview({ quiet = false } = {}) {
  if (previewInFlight) {
    return;
  }
  previewInFlight = true;
  let tab = null;
  try {
    tab = await getActiveTab();
    const response = await sendRuntimeMessage({
      type: "hermes:preview-page-context",
      tabId: tab.id
    });
    const preview = response.result || {};
    renderPreview(preview);
    if (!quiet) {
      if (preview.contentKind === "restricted-page") {
        setStatus(
          preview.unavailableReason ||
          "This tab is a browser internal page and cannot be shared with Hermes."
        );
      } else {
        setStatus("Current page context is ready.");
      }
    }
  } catch (error) {
    if (!quiet) {
      throw error;
    }
  } finally {
    if (tab?.id) {
      refreshDomainPermissionStatus({ quiet: true, tabId: tab.id }).catch(() => {});
    }
    previewInFlight = false;
  }
}

async function loadChatSession({ quiet = false, sessionKey = "" } = {}) {
  const wasBusy = isBusy;
  if (!quiet) {
    setStatus("Loading Hermes sidecar...");
  }

  const targetSessionKey = String(sessionKey || selectedSessionKey || expectedSessionKey || "").trim();
  const response = await sendRuntimeMessage({
    type: "hermes:get-chat-session",
    sessionKey: targetSessionKey
  });
  const incomingMessages = response.result?.messages || [];
  const incomingSessionKey = response.result?.session_key || "";
  const sessionKeyChanged = Boolean(
    incomingSessionKey &&
    expectedSessionKey &&
    expectedSessionKey !== incomingSessionKey
  );

  if (incomingSessionKey) {
    if (sessionKeyChanged) {
      setStatus(
        "Sidecar session changed. Synced to the current session. If your last queued turn does not appear, send it once more.",
        { openActivity: true }
      );
      pendingUserMessage = null;
      pendingQueuedAt = 0;
    }
    expectedSessionKey = incomingSessionKey;
    selectedSessionKey = incomingSessionKey;
    if (sessionHistorySelect && !isApplyingSessionSelection) {
      const hasOption = Array.from(sessionHistorySelect.options).some((option) => option.value === incomingSessionKey);
      if (hasOption) {
        isApplyingSessionSelection = true;
        sessionHistorySelect.value = incomingSessionKey;
        isApplyingSessionSelection = false;
      }
    }
  }

  currentMessages = incomingMessages;
  currentProgress = response.result?.progress || null;
  clearPendingIfAcknowledged();

  if (currentProgress?.running) {
    setBusyState(true);
    renderMessages(currentMessages, currentProgress, pendingUserMessage);
    setStatus(currentProgress.detail || "Hermes is working...", { openActivity: true });
    schedulePolling();
  } else {
    const waitingForQueuedTurn =
      Boolean(pendingUserMessage) &&
      !currentMessages.length &&
      !currentProgress?.error &&
      Date.now() - pendingQueuedAt < 90000;

    if (waitingForQueuedTurn) {
      setBusyState(true);
      renderMessages(
        currentMessages,
        { running: true, detail: "Waiting for Hermes queue state...", recent_events: [] },
        pendingUserMessage
      );
      setStatus("Your turn is still queued. Waiting for queue state to sync...", { openActivity: true });
      schedulePolling();
      return;
    }

    if (currentProgress?.error) {
      setStatus(currentProgress.error, { openActivity: true });
    } else if (!quiet) {
      setStatus("Hermes sidecar is ready.");
    } else if (wasBusy) {
      setStatus("Reply ready.");
    }
    pendingUserMessage = null;
    pendingQueuedAt = 0;
    renderMessages(currentMessages, null, null);
    setBusyState(false);
    stopPolling();
  }

  if (sessionKeyChanged && quiet) {
    loadSessionHistory({ quiet: true, preferredSessionKey: incomingSessionKey }).catch(() => {});
  }
}

async function sendChatMessage(messageOverride = null, options = {}) {
  stopReplySpeech({ rerender: false });
  if (isBusy) {
    await loadChatSession({ quiet: true });
    if (isBusy) {
      setStatus("Hermes is already working on this sidecar session. Waiting for the current turn to finish.", { openActivity: true });
      return;
    }
  }
  if (!activeTabId) {
    await getActiveTab();
  }

  const message = messageOverride === null
    ? chatInput.value.trim()
    : String(messageOverride || "").trim();
  const outgoingMessage = buildOutgoingMessage(message);
  const forceIncludeTranscript = Boolean(options.forceIncludeTranscript);
  const sharePage = forceIncludeTranscript || sharePageCheckbox.checked;
  const includeTranscriptForSend = forceIncludeTranscript || includeTranscript.checked;
  if (sharePage && pageContextUnavailable) {
    throw new Error(
      "Current tab context is unavailable. Switch to a normal webpage tab, or turn off page sharing for this turn."
    );
  }
  if (!message && !sharePage) {
    throw new Error("Type a message or enable page sharing before sending.");
  }

  pendingUserMessage = buildOptimisticUserMessage(message, sharePage);
  pendingQueuedAt = Date.now();
  renderMessages(currentMessages, { running: true, detail: "Sending your turn to Hermes...", recent_events: [] }, pendingUserMessage);
  setBusyState(true);
  setStatus(sharePage ? "Sending your message with current page context..." : "Sending your message...", { openActivity: true });
  const targetSessionKey = String(selectedSessionKey || expectedSessionKey || "").trim();

  let response;
  try {
    response = await sendRuntimeMessage({
      type: "hermes:start-chat-message",
      tabId: activeTabId,
      message: outgoingMessage,
      sharePage,
      includeTranscript: includeTranscriptForSend,
      sessionKey: targetSessionKey,
      contextOptions: sharePage ? getContextOptionsForSend() : null
    });
  } catch (error) {
    if (String(error?.message || "").includes("Unknown message type")) {
      response = await sendRuntimeMessage({
        type: "hermes:send-chat-message",
        tabId: activeTabId,
        message: outgoingMessage,
        sharePage,
        includeTranscript: includeTranscriptForSend,
        sessionKey: targetSessionKey,
        contextOptions: sharePage ? getContextOptionsForSend() : null
      });
    } else {
      throw error;
    }
  }

  currentMessages = response.result?.messages || currentMessages;
  currentProgress = response.result?.progress || { running: true, detail: "Hermes is thinking..." };
  expectedSessionKey = response.result?.session_key || expectedSessionKey;
  selectedSessionKey = expectedSessionKey;

  if (response.result?.accepted === false && response.result?.busy) {
    pendingUserMessage = null;
    pendingQueuedAt = 0;
    renderMessages(currentMessages, currentProgress, null);
    setBusyState(Boolean(currentProgress?.running));
    setStatus(response.result?.detail || "Hermes is already working on this sidecar session.", { openActivity: true });
    schedulePolling();
    return;
  }

  clearPendingIfAcknowledged();
  renderMessages(currentMessages, currentProgress, pendingUserMessage);

  const lines = ["Your turn was queued."];
  const sentPageTextLength = Number(response.result?.sent_page_text_length || 0);
  const sentSelectionLength = Number(response.result?.sent_selection_length || 0);
  if (sharePage) {
    const enabledChunks = listEnabledBundleChunks();
    if (enabledChunks.length) {
      lines.push(`Included chunks: ${enabledChunks.join(", ")}.`);
    }
    lines.push(
      `Sent page context: ${sentPageTextLength} chars page text, ${sentSelectionLength} chars selection.`
    );
    const previewChars = Number(lastPreview?.pageTextLength || 0);
    if (previewChars > 0 && sentPageTextLength + 300 < previewChars) {
      lines.push(
        `Warning: preview showed ${previewChars} page-text chars, but only ${sentPageTextLength} were prepared for this send.`
      );
    }
  }
  if (response.result?.transcript_shared) {
    lines.push("The YouTube transcript was included.");
  } else if (response.result?.transcript_shared_previously) {
    lines.push("Transcript was skipped because this video was already shared earlier.");
  }
  setStatus(lines.join("\n"), { openActivity: true });

  if (messageOverride === null) {
    chatInput.value = "";
  }
  if (sharePage) {
    await refreshPreview({ quiet: true });
  }
  loadSessionHistory({ quiet: true, preferredSessionKey: expectedSessionKey }).catch(() => {});
  schedulePolling();
}

function handleSendError(error) {
  setBusyState(false);
  pendingUserMessage = null;
  renderMessages(currentMessages, null, null);
  setStatus(explainBackgroundMismatch(error), { openActivity: true });
}

async function resetChatSession() {
  stopReplySpeech({ rerender: false });
  if (isBusy) {
    setStatus("Wait for the current Hermes turn to finish before starting a new chat.", { openActivity: true });
    return;
  }

  setBusyState(true);
  setStatus("Starting a fresh sidecar session...", { openActivity: true });
  try {
    const response = await sendRuntimeMessage({
      type: "hermes:reset-chat-session",
      createNew: true,
      sessionKey: ""
    });
    currentMessages = response.result?.messages || [];
    currentProgress = response.result?.progress || null;
    pendingUserMessage = null;
    pendingQueuedAt = 0;
    expectedSessionKey = response.result?.session_key || "";
    selectedSessionKey = expectedSessionKey;
    renderMessages(currentMessages, null, null);
    chatInput.value = "";
    sharePageCheckbox.checked = sharePageByDefault;
    setStatus("Started a fresh Hermes sidecar session.");
    loadSessionHistory({ quiet: true, preferredSessionKey: expectedSessionKey }).catch(() => {});
  } finally {
    setBusyState(false);
    stopPolling();
  }
}

function scheduleRefresh() {
  if (refreshDebounceTimer) {
    clearTimeout(refreshDebounceTimer);
  }
  refreshDebounceTimer = setTimeout(() => {
    refreshPreview({ quiet: true }).catch((error) => {
      setStatus(error.message || String(error), { openActivity: true });
    });
  }, 250);
}

document.getElementById("refresh-button").addEventListener("click", () => {
  refreshPreview()
    .then(() => refreshDomainPermissionStatus({ quiet: true }))
    .catch((error) => setStatus(error.message, { openActivity: true }));
});

if (domainPermissionButton) {
  domainPermissionButton.addEventListener("click", async () => {
    try {
      const permission = latestDomainPermission;
      if (!permission) {
        setStatus("Checking domain access status...");
        await refreshDomainPermissionStatus({ quiet: true });
        return;
      }
      if (!permission.supported) {
        setStatus(permission.detail || "Domain access is unavailable on this tab.");
        return;
      }

      if (permission.granted && !permission.removable) {
        setStatus("This domain is built into extension permissions and cannot be removed.");
        return;
      }

      const originPattern = String(permission.originPattern || "").trim();
      if (!originPattern) {
        throw new Error("Could not determine the current tab origin for domain access.");
      }

      const grant = !permission.granted;
      if (grant) {
        // Must happen directly in this click handler so Chrome accepts user gesture.
        setStatus(`Requesting domain access for ${permission.hostname || originPattern}...`);
        const allowed = await chrome.permissions.request({ origins: [originPattern] });
        if (!allowed) {
          setStatus(`Domain access request was not granted for ${permission.hostname || originPattern}.`);
          await refreshDomainPermissionStatus({ quiet: true });
          return;
        }
      } else {
        setStatus(`Removing domain access for ${permission.hostname || originPattern}...`);
        const removed = await chrome.permissions.remove({ origins: [originPattern] });
        if (!removed) {
          setStatus(`Could not remove domain access for ${permission.hostname || originPattern}.`);
          await refreshDomainPermissionStatus({ quiet: true });
          return;
        }
      }

      await refreshDomainPermissionStatus({ quiet: true });
      await refreshPreview({ quiet: true });
      setStatus(latestDomainPermission?.detail || "Domain permission updated.");
    } catch (error) {
      setStatus(explainBackgroundMismatch(error), { openActivity: true });
    }
  });
}

if (refreshSessionsButton) {
  refreshSessionsButton.addEventListener("click", () => {
    loadSessionHistory({ quiet: false }).catch((error) => {
      renderSessionHistoryUnavailable(explainBackgroundMismatch(error));
    });
  });
}

if (sessionHistorySelect) {
  sessionHistorySelect.addEventListener("change", () => {
    if (isApplyingSessionSelection) {
      return;
    }
    if (isBusy) {
      setStatus("Wait for the current Hermes turn to finish before switching sessions.", { openActivity: true });
      if (expectedSessionKey) {
        isApplyingSessionSelection = true;
        sessionHistorySelect.value = expectedSessionKey;
        isApplyingSessionSelection = false;
      }
      return;
    }
    selectedSessionKey = String(sessionHistorySelect.value || "").trim();
    expectedSessionKey = selectedSessionKey;
    pendingUserMessage = null;
    pendingQueuedAt = 0;
    loadChatSession({ sessionKey: selectedSessionKey }).catch((error) => {
      renderChatNotice("Unable to load this sidecar session right now.");
      setStatus(explainBackgroundMismatch(error), { openActivity: true });
    });
  });
}

document.getElementById("send-button").addEventListener("click", () => {
  sendChatMessage().catch(handleSendError);
});

document.getElementById("reset-chat-button").addEventListener("click", () => {
  resetChatSession().catch((error) => {
    setBusyState(false);
    setStatus(explainBackgroundMismatch(error), { openActivity: true });
  });
});

document.getElementById("open-options-button").addEventListener("click", () => {
  chrome.runtime.openOptionsPage();
});

if (challengeModeButton) {
  challengeModeButton.addEventListener("click", () => {
    setChallengeModeEnabled(!challengeModeEnabled);
    renderContextBundle();
  });
}

function isTranscriptPreset(template) {
  const t = String(template || "").trim();
  return t.startsWith("Summarize this video.") || t.includes("transcript");
}

for (const button of presetButtons) {
  button.addEventListener("click", () => {
    const template = button.dataset.template || "";
    const options = isTranscriptPreset(template) ? { forceIncludeTranscript: true } : {};
    sendChatMessage(template, options).catch(handleSendError);
  });
}

sharePageCheckbox.addEventListener("change", () => {
  renderContextBundle();
});

includeTranscript.addEventListener("change", () => {
  renderContextBundle();
});

chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendChatMessage().catch(handleSendError);
  }
});

chrome.tabs.onActivated.addListener(() => {
  scheduleRefresh();
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (tabId === activeTabId && (changeInfo.status === "complete" || changeInfo.url)) {
    scheduleRefresh();
  }
});

chrome.windows.onFocusChanged.addListener((windowId) => {
  if (windowId !== chrome.windows.WINDOW_ID_NONE) {
    scheduleRefresh();
  }
});

chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName !== "sync") {
    return;
  }

  if (changes.includeTranscriptByDefault) {
    includeTranscript.checked = Boolean(changes.includeTranscriptByDefault.newValue);
    renderContextBundle();
  }

  if (changes.sharePageByDefault) {
    sharePageByDefault = changes.sharePageByDefault.newValue !== false;
    if (!isBusy) {
      sharePageCheckbox.checked = sharePageByDefault;
      renderContextBundle();
    }
  }
});

(async () => {
  const startupWarnings = [];

  try {
    await loadSettings();
  } catch (error) {
    const message = explainBackgroundMismatch(error);
    startupWarnings.push(message);
    setStatus(message, { openActivity: true });
  }

  try {
    await refreshPreview();
  } catch (error) {
    const message = explainBackgroundMismatch(error);
    startupWarnings.push(message);
    renderUnavailablePreview(message);
  }

  try {
    await refreshDomainPermissionStatus({ quiet: true });
  } catch (error) {
    const message = explainBackgroundMismatch(error);
    startupWarnings.push(message);
    renderDomainPermissionStatus({
      supported: false,
      detail: message
    });
  }

  try {
    await loadSessionHistory({ quiet: true });
  } catch (error) {
    const message = explainBackgroundMismatch(error);
    startupWarnings.push(message);
    renderSessionHistoryUnavailable(message);
  }

  try {
    await loadChatSession({ quiet: true });
  } catch (error) {
    const message = explainBackgroundMismatch(error);
    startupWarnings.push(message);
    renderChatNotice("Unable to load Hermes sidecar history right now.");
    setStatus(message, { openActivity: true });
    setBusyState(false);
    stopPolling();
  }

  if (startupWarnings.length) {
    const uniqueWarnings = [...new Set(startupWarnings)];
    setStatus(uniqueWarnings[uniqueWarnings.length - 1], { openActivity: true });
  } else {
    setStatus("Hermes sidecar is ready.");
  }

  setChallengeModeEnabled(false);
  startPreviewLoop();
})();
