const bridgeUrlInput = document.getElementById("bridge-url");
const bridgeTokenInput = document.getElementById("bridge-token");
const sharePageByDefault = document.getElementById("share-page-by-default");
const includeTranscript = document.getElementById("include-transcript");
const showQuickPrompts = document.getElementById("show-quick-prompts");
const showChallengeMode = document.getElementById("show-challenge-mode");
const challengeModeLabel = document.getElementById("challenge-mode-label");
const challengeModePrompt = document.getElementById("challenge-mode-prompt");
const quickPromptList = document.getElementById("quick-prompt-list");
const addQuickPromptButton = document.getElementById("add-quick-prompt-button");
const bridgeStatusText = document.getElementById("bridge-status-text");
const statusText = document.getElementById("status-text");

let quickPromptDrafts = [];

function setStatus(message) {
  statusText.textContent = message;
}

function setBridgeStatus(message) {
  bridgeStatusText.textContent = message;
}

function isExtensionContextInvalidated(error) {
  const message = String(error?.message || error || "").toLowerCase();
  return (
    message.includes("extension context invalidated") ||
    message.includes("context invalidated") ||
    message.includes("message port closed before a response was received")
  );
}

function explainExtensionError(error) {
  if (isExtensionContextInvalidated(error)) {
    return "Hermes Sidecar was reloaded or updated. Reload the options page to reconnect.";
  }
  return String(error?.message || error || "Unknown extension error.");
}

function createPromptDraft(prompt = {}) {
  return {
    id: String(prompt.id || "").trim() || crypto.randomUUID(),
    label: String(prompt.label || "").trim(),
    template: String(prompt.template || "").trim(),
    includeTranscript: Boolean(prompt.includeTranscript)
  };
}

function renderQuickPromptList() {
  quickPromptList.textContent = "";

  if (!quickPromptDrafts.length) {
    const emptyState = document.createElement("p");
    emptyState.className = "empty-list";
    emptyState.textContent = "No quick prompts yet. Add one to create a reusable sidecar button.";
    quickPromptList.appendChild(emptyState);
    return;
  }

  quickPromptDrafts.forEach((prompt, index) => {
    const card = document.createElement("section");
    card.className = "prompt-card";

    const head = document.createElement("div");
    head.className = "prompt-card-head";

    const title = document.createElement("p");
    title.className = "prompt-card-title";
    title.textContent = prompt.label || `Prompt ${index + 1}`;
    head.appendChild(title);

    const actions = document.createElement("div");
    actions.className = "prompt-card-actions";

    const moveUpButton = document.createElement("button");
    moveUpButton.className = "ghost-button small-button";
    moveUpButton.type = "button";
    moveUpButton.textContent = "Move up";
    moveUpButton.disabled = index === 0;
    moveUpButton.addEventListener("click", () => {
      const previous = quickPromptDrafts[index - 1];
      quickPromptDrafts[index - 1] = quickPromptDrafts[index];
      quickPromptDrafts[index] = previous;
      renderQuickPromptList();
    });
    actions.appendChild(moveUpButton);

    const moveDownButton = document.createElement("button");
    moveDownButton.className = "ghost-button small-button";
    moveDownButton.type = "button";
    moveDownButton.textContent = "Move down";
    moveDownButton.disabled = index === quickPromptDrafts.length - 1;
    moveDownButton.addEventListener("click", () => {
      const next = quickPromptDrafts[index + 1];
      quickPromptDrafts[index + 1] = quickPromptDrafts[index];
      quickPromptDrafts[index] = next;
      renderQuickPromptList();
    });
    actions.appendChild(moveDownButton);

    const removeButton = document.createElement("button");
    removeButton.className = "ghost-button small-button danger-button";
    removeButton.type = "button";
    removeButton.textContent = "Remove";
    removeButton.addEventListener("click", () => {
      quickPromptDrafts.splice(index, 1);
      renderQuickPromptList();
    });
    actions.appendChild(removeButton);

    head.appendChild(actions);
    card.appendChild(head);

    const labelField = document.createElement("label");
    labelField.className = "field";
    const labelSpan = document.createElement("span");
    labelSpan.className = "field-label";
    labelSpan.textContent = "Button label";
    const labelInput = document.createElement("input");
    labelInput.type = "text";
    labelInput.maxLength = 60;
    labelInput.spellcheck = false;
    labelInput.value = prompt.label;
    labelInput.addEventListener("input", () => {
      quickPromptDrafts[index].label = labelInput.value;
      title.textContent = labelInput.value.trim() || `Prompt ${index + 1}`;
    });
    labelField.appendChild(labelSpan);
    labelField.appendChild(labelInput);
    card.appendChild(labelField);

    const promptField = document.createElement("label");
    promptField.className = "field";
    const promptSpan = document.createElement("span");
    promptSpan.className = "field-label";
    promptSpan.textContent = "Prompt text";
    const promptInput = document.createElement("textarea");
    promptInput.rows = 4;
    promptInput.value = prompt.template;
    promptInput.addEventListener("input", () => {
      quickPromptDrafts[index].template = promptInput.value;
    });
    promptField.appendChild(promptSpan);
    promptField.appendChild(promptInput);
    card.appendChild(promptField);

    const transcriptRow = document.createElement("label");
    transcriptRow.className = "checkbox-row tight-row";
    const transcriptInput = document.createElement("input");
    transcriptInput.type = "checkbox";
    transcriptInput.checked = prompt.includeTranscript;
    transcriptInput.addEventListener("change", () => {
      quickPromptDrafts[index].includeTranscript = transcriptInput.checked;
    });
    const transcriptCopy = document.createElement("span");
    transcriptCopy.textContent = "Force-include the transcript when this prompt is used";
    transcriptRow.appendChild(transcriptInput);
    transcriptRow.appendChild(transcriptCopy);
    card.appendChild(transcriptRow);

    quickPromptList.appendChild(card);
  });
}

async function sendRuntimeMessage(payload) {
  let response;
  try {
    response = await chrome.runtime.sendMessage(payload);
  } catch (error) {
    throw new Error(explainExtensionError(error));
  }
  if (!response?.ok) {
    throw new Error(explainExtensionError(response?.error || "Unknown extension error."));
  }
  return response;
}

async function loadSettings() {
  const response = await sendRuntimeMessage({ type: "hermes:get-settings" });
  const settings = response.settings || {};
  bridgeUrlInput.value = settings.bridgeUrl || "";
  bridgeTokenInput.value = settings.bridgeToken || "";
  sharePageByDefault.checked = settings.sharePageByDefault !== false;
  includeTranscript.checked = settings.includeTranscriptByDefault !== false;
  showQuickPrompts.checked = settings.showQuickPrompts === true;
  showChallengeMode.checked = settings.showChallengeMode === true;
  challengeModeLabel.value = settings.challengeModeLabel || "";
  challengeModePrompt.value = settings.challengeModePrompt || "";
  quickPromptDrafts = Array.isArray(settings.quickPrompts)
    ? settings.quickPrompts.map((prompt) => createPromptDraft(prompt))
    : [];
  renderQuickPromptList();
}

async function checkBridge() {
  const response = await sendRuntimeMessage({ type: "hermes:check-bridge-health" });
  const result = response.result || {};
  if (result.ok) {
    return `Bridge is reachable on port ${result.port}.`;
  }
  return "Bridge health check returned an unexpected response.";
}

function collectQuickPromptPayload() {
  const prompts = [];
  let skippedCount = 0;

  for (const draft of quickPromptDrafts) {
    const label = String(draft.label || "").trim();
    const template = String(draft.template || "").trim();
    if (!label && !template) {
      skippedCount += 1;
      continue;
    }
    if (!label || !template) {
      skippedCount += 1;
      continue;
    }
    prompts.push({
      id: String(draft.id || "").trim() || crypto.randomUUID(),
      label,
      template,
      includeTranscript: Boolean(draft.includeTranscript)
    });
  }

  return { prompts, skippedCount };
}

function buildSettingsPayload() {
  const { prompts, skippedCount } = collectQuickPromptPayload();
  return {
    skippedCount,
    settings: {
      bridgeUrl: bridgeUrlInput.value.trim(),
      bridgeToken: bridgeTokenInput.value.trim(),
      includeTranscriptByDefault: includeTranscript.checked,
      sharePageByDefault: sharePageByDefault.checked,
      showQuickPrompts: showQuickPrompts.checked,
      showChallengeMode: showChallengeMode.checked,
      quickPrompts: prompts,
      challengeModeLabel: challengeModeLabel.value.trim(),
      challengeModePrompt: challengeModePrompt.value.trim()
    }
  };
}

async function saveSettings({
  checkBridgeAfterSave = true,
  savedPrefix = "Settings saved."
} = {}) {
  const { settings, skippedCount } = buildSettingsPayload();
  await sendRuntimeMessage({
    type: "hermes:save-settings",
    settings
  });

  await loadSettings();

  const skippedMessage = skippedCount
    ? ` Skipped ${skippedCount} incomplete quick prompt${skippedCount === 1 ? "" : "s"}.`
    : "";

  if (!checkBridgeAfterSave) {
    setStatus(`${savedPrefix}${skippedMessage}`);
    return;
  }

  setStatus(`${savedPrefix}${skippedMessage} Checking the local bridge...`);
  setBridgeStatus("Checking bridge...");
  try {
    const bridgeMessage = await checkBridge();
    setBridgeStatus(bridgeMessage);
    setStatus(`${savedPrefix}${skippedMessage} ${bridgeMessage}`);
  } catch (error) {
    setBridgeStatus(`Bridge check failed: ${error.message || String(error)}`);
    setStatus(`${savedPrefix}${skippedMessage} Bridge check failed: ${error.message || String(error)}`);
  }
}

document.getElementById("health-button").addEventListener("click", () => {
  setBridgeStatus("Checking bridge...");
  checkBridge()
    .then((message) => setBridgeStatus(message))
    .catch((error) => setBridgeStatus(error.message || String(error)));
});

addQuickPromptButton.addEventListener("click", () => {
  quickPromptDrafts.push(createPromptDraft({ label: "", template: "", includeTranscript: false }));
  renderQuickPromptList();
});

showQuickPrompts.addEventListener("change", () => {
  saveSettings({
    checkBridgeAfterSave: false,
    savedPrefix: "Sidecar tool visibility saved."
  }).catch((error) => setStatus(error.message || String(error)));
});

showChallengeMode.addEventListener("change", () => {
  saveSettings({
    checkBridgeAfterSave: false,
    savedPrefix: "Sidecar tool visibility saved."
  }).catch((error) => setStatus(error.message || String(error)));
});

document.getElementById("save-settings-button").addEventListener("click", () => {
  saveSettings().catch((error) => setStatus(error.message || String(error)));
});

window.addEventListener("error", (event) => {
  if (!isExtensionContextInvalidated(event?.error || event?.message)) {
    return;
  }
  const message = explainExtensionError(event.error || event.message);
  setStatus(message);
  setBridgeStatus(message);
  event.preventDefault();
});

window.addEventListener("unhandledrejection", (event) => {
  if (!isExtensionContextInvalidated(event?.reason)) {
    return;
  }
  const message = explainExtensionError(event.reason);
  setStatus(message);
  setBridgeStatus(message);
  event.preventDefault();
});

(async () => {
  try {
    await loadSettings();
  } catch (error) {
    setStatus(error.message || String(error));
  }
})();
