const bridgeUrlInput = document.getElementById("bridge-url");
const bridgeTokenInput = document.getElementById("bridge-token");
const sharePageByDefault = document.getElementById("share-page-by-default");
const includeTranscript = document.getElementById("include-transcript");
const statusText = document.getElementById("status-text");

function setStatus(message) {
  statusText.textContent = message;
}

async function sendRuntimeMessage(payload) {
  const response = await chrome.runtime.sendMessage(payload);
  if (!response?.ok) {
    throw new Error(response?.error || "Unknown extension error.");
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
}

async function checkBridge() {
  setStatus("Checking the local bridge...");
  const response = await sendRuntimeMessage({ type: "hermes:check-bridge-health" });
  const result = response.result || {};
  if (result.ok) {
    setStatus(`Bridge is reachable on port ${result.port}.`);
  } else {
    setStatus("Bridge health check returned an unexpected response.");
  }
}

async function saveSettings() {
  await sendRuntimeMessage({
    type: "hermes:save-settings",
    settings: {
      bridgeUrl: bridgeUrlInput.value.trim(),
      bridgeToken: bridgeTokenInput.value.trim(),
      includeTranscriptByDefault: includeTranscript.checked,
      sharePageByDefault: sharePageByDefault.checked
    }
  });

  setStatus("Settings saved. Checking the local bridge...");
  try {
    const response = await sendRuntimeMessage({ type: "hermes:check-bridge-health" });
    const result = response.result || {};
    if (result.ok) {
      setStatus(`Settings saved. Bridge is reachable on port ${result.port}.`);
    } else {
      setStatus("Settings saved, but bridge health returned an unexpected response.");
    }
  } catch (error) {
    setStatus(`Settings saved, but bridge check failed: ${error.message || String(error)}`);
  }
}

document.getElementById("health-button").addEventListener("click", () => {
  checkBridge().catch((error) => setStatus(error.message || String(error)));
});

document.getElementById("save-settings-button").addEventListener("click", () => {
  saveSettings().catch((error) => setStatus(error.message || String(error)));
});

(async () => {
  try {
    await loadSettings();
  } catch (error) {
    setStatus(error.message || String(error));
  }
})();
