function collapseWhitespace(text) {
  return (text || "")
    .replace(/\u00a0/g, " ")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function clamp(text, maxLength) {
  if (!text) {
    return "";
  }
  if (text.length <= maxLength) {
    return text;
  }
  return text.slice(0, maxLength).trim();
}

function getMetaValue(selectors) {
  for (const selector of selectors) {
    const element = document.querySelector(selector);
    const value = element?.content || element?.getAttribute?.("content") || "";
    if (value && value.trim()) {
      return value.trim();
    }
  }
  return "";
}

function getSelectedText() {
  return clamp(collapseWhitespace(window.getSelection?.().toString() || ""), 8000);
}

function getCurrentUrl() {
  try {
    return new URL(window.location.href);
  } catch (_error) {
    return null;
  }
}

function isXOrTwitterHost() {
  const url = getCurrentUrl();
  const host = (url?.hostname || "").toLowerCase();
  return host === "x.com" || host.endsWith(".x.com") || host === "twitter.com" || host.endsWith(".twitter.com");
}

function isProbablyReadableText(text) {
  const value = collapseWhitespace(text || "");
  if (!value || value.length < 120) {
    return false;
  }

  const words = value.split(/\s+/).filter(Boolean);
  if (words.length < 20) {
    return false;
  }

  const longWords = words.filter((word) => word.length >= 7);
  const sentenceMarks = (value.match(/[.!?:]/g) || []).length;
  return longWords.length >= 8 || sentenceMarks >= 3;
}

function collectTextFromSelectors(selectors, perNodeMax = 1800, totalMax = 12000) {
  const parts = [];
  const seen = new Set();

  for (const selector of selectors) {
    const nodes = document.querySelectorAll(selector);
    for (const node of nodes) {
      const text = clamp(collapseWhitespace(node?.innerText || node?.textContent || ""), perNodeMax);
      if (!text || seen.has(text)) {
        continue;
      }
      seen.add(text);
      parts.push(text);
      const joined = parts.join("\n\n");
      if (joined.length >= totalMax) {
        return clamp(joined, totalMax);
      }
    }
  }

  return clamp(parts.join("\n\n"), totalMax);
}

function getXTimelineText() {
  if (!isXOrTwitterHost()) {
    return "";
  }

  const parts = [];
  const seen = new Set();

  function addTweetText(text) {
    const normalized = clamp(collapseWhitespace(text || ""), 900);
    if (!normalized || normalized.length < 30 || seen.has(normalized)) {
      return false;
    }
    seen.add(normalized);
    parts.push(normalized);
    return true;
  }

  // 1) Same as web_utils.py / DiscordSam: article[data-testid="tweet"] + div[data-testid="tweetText"]
  const tweetArticles = document.querySelectorAll("article[data-testid='tweet']");
  for (const article of tweetArticles) {
    const tweetText =
      article.querySelector("div[data-testid='tweetText']")?.innerText ||
      article.querySelector("[data-testid='tweetText']")?.innerText ||
      article.querySelector("[lang]")?.innerText ||
      article.innerText ||
      "";
    if (addTweetText(tweetText) && parts.length >= 12) {
      return clamp(parts.join("\n\n"), 12000);
    }
  }

  // 2) Fallback: plain article or [data-testid="tweet"] (div or other)
  const fallbackContainers = document.querySelectorAll("article, [data-testid='tweet']");
  for (const container of fallbackContainers) {
    const tweetText =
      container.querySelector("div[data-testid='tweetText']")?.innerText ||
      container.querySelector("[data-testid='tweetText']")?.innerText ||
      container.querySelector("[lang]")?.innerText ||
      container.innerText ||
      "";
    if (addTweetText(tweetText) && parts.length >= 12) {
      return clamp(parts.join("\n\n"), 12000);
    }
  }

  return clamp(parts.join("\n\n"), 12000);
}

function getVisiblePageText() {
  // On X, prefer timeline-specific extraction so we send tweet content, not nav/sidebar chrome.
  if (isXOrTwitterHost()) {
    const timelineText = getXTimelineText();
    if (timelineText.length >= 300 || isProbablyReadableText(timelineText)) {
      return timelineText;
    }
  }

  const rootCandidates = [
    document.querySelector("article"),
    document.querySelector("[data-testid='primaryColumn']"),
    document.querySelector("main"),
    document.querySelector("[role='main']"),
    document.body
  ].filter(Boolean);

  let bestText = "";
  for (const root of rootCandidates) {
    const text = clamp(collapseWhitespace(root?.innerText || ""), 12000);
    if (text.length > bestText.length) {
      bestText = text;
    }
    if (isProbablyReadableText(bestText)) {
      return bestText;
    }
  }

  const timelineText = getXTimelineText();
  if (timelineText.length > bestText.length) {
    bestText = timelineText;
  }
  if (isProbablyReadableText(bestText)) {
    return bestText;
  }

  const fallback = collectTextFromSelectors(
    [
      "article[data-testid='tweet'] div[data-testid='tweetText']",
      "article [data-testid='tweetText']",
      "[data-testid='tweet'] [data-testid='tweetText']",
      "article [lang]",
      "[data-testid='tweet'] [lang]",
      "article[data-testid='tweet']",
      "article",
      "[data-testid='tweet']",
      "main article",
      "main section",
      "main div[dir='auto']",
      "[role='main'] article",
      "[role='main'] div[dir='auto']"
    ],
    1000,
    12000
  );
  if (fallback.length > bestText.length) {
    bestText = fallback;
  }

  if (!bestText) {
    bestText = clamp(collapseWhitespace(document.body?.innerText || ""), 12000);
  }

  return bestText;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function getHydrationState() {
  const main =
    document.querySelector("[data-testid='primaryColumn']") ||
    document.querySelector("main") ||
    document.querySelector("[role='main']") ||
    document.body;

  const mainText = collapseWhitespace(main?.innerText || "");
  const articleCount = document.querySelectorAll("article").length;
  const tweetTextCount = document.querySelectorAll(
    "article[data-testid='tweet'] div[data-testid='tweetText'], article [data-testid='tweetText'], article [lang], [data-testid='tweet'] [data-testid='tweetText'], [data-testid='tweet'] [lang], article[data-testid='tweet'], [data-testid='tweet']"
  ).length;

  return {
    mainTextLength: mainText.length,
    articleCount,
    tweetTextCount
  };
}

function isHydratedEnoughForCapture() {
  const state = getHydrationState();
  if (isXOrTwitterHost()) {
    return (
      state.tweetTextCount >= 2 ||
      (state.articleCount >= 2 && state.mainTextLength >= 500)
    );
  }
  return state.mainTextLength >= 400 || state.articleCount >= 1;
}

async function waitForHydratedCapture(timeoutMs = 4500) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (isHydratedEnoughForCapture()) {
      return true;
    }
    await sleep(250);
  }
  return false;
}

async function getVisiblePageTextWithRetry() {
  let best = "";
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const text = getVisiblePageText();
    if (text.length > best.length) {
      best = text;
    }
    if (isProbablyReadableText(best)) {
      return best;
    }
    if (attempt < 3) {
      await sleep(140);
    }
  }
  return best;
}

function getPageDescription() {
  return clamp(
    getMetaValue([
      "meta[name='description']",
      "meta[property='og:description']",
      "meta[name='twitter:description']"
    ]),
    2000
  );
}

function getSiteName() {
  return getMetaValue([
    "meta[property='og:site_name']",
    "meta[name='application-name']"
  ]);
}

function getCanonicalUrl() {
  const canonical = document.querySelector("link[rel='canonical']")?.href || "";
  return canonical.trim();
}

function isYouTubeWatchPage() {
  const url = new URL(window.location.href);
  return /(^|\.)youtube\.com$/i.test(url.hostname) && url.pathname === "/watch" && url.searchParams.has("v");
}

function extractBalancedJson(source, marker) {
  const markerIndex = source.indexOf(marker);
  if (markerIndex === -1) {
    return null;
  }

  const startIndex = source.indexOf("{", markerIndex + marker.length);
  if (startIndex === -1) {
    return null;
  }

  let depth = 0;
  let inString = false;
  let escaped = false;
  for (let index = startIndex; index < source.length; index += 1) {
    const character = source[index];
    if (escaped) {
      escaped = false;
      continue;
    }
    if (character === "\\") {
      escaped = true;
      continue;
    }
    if (character === "\"") {
      inString = !inString;
      continue;
    }
    if (inString) {
      continue;
    }
    if (character === "{") {
      depth += 1;
    } else if (character === "}") {
      depth -= 1;
      if (depth === 0) {
        return source.slice(startIndex, index + 1);
      }
    }
  }
  return null;
}

function findYouTubePlayerResponse() {
  const markers = [
    "var ytInitialPlayerResponse = ",
    "ytInitialPlayerResponse = ",
    "window[\"ytInitialPlayerResponse\"] = ",
    "window['ytInitialPlayerResponse'] = "
  ];

  for (const script of document.scripts) {
    const content = script.textContent || "";
    if (!content) {
      continue;
    }
    for (const marker of markers) {
      const jsonText = extractBalancedJson(content, marker);
      if (!jsonText) {
        continue;
      }
      try {
        return JSON.parse(jsonText);
      } catch (error) {
        console.debug("Hermes extension: failed to parse ytInitialPlayerResponse", error);
      }
    }
  }

  return null;
}

function chooseTranscriptTrack(tracks) {
  if (!Array.isArray(tracks) || !tracks.length) {
    return null;
  }

  const languageHints = [
    document.documentElement.lang,
    navigator.language
  ]
    .filter(Boolean)
    .map((value) => value.toLowerCase());

  const scoreTrack = (track) => {
    const lang = String(track.languageCode || "").toLowerCase();
    let score = 0;
    if (languageHints.some((hint) => hint === lang)) {
      score += 4;
    }
    if (languageHints.some((hint) => hint.startsWith(lang) || lang.startsWith(hint))) {
      score += 2;
    }
    if (lang.startsWith("en")) {
      score += 1;
    }
    if (!track.kind) {
      score += 1;
    }
    return score;
  };

  return [...tracks].sort((left, right) => scoreTrack(right) - scoreTrack(left))[0];
}

async function fetchYouTubeTranscript(includeText) {
  const url = new URL(window.location.href);
  const videoId = url.searchParams.get("v") || "";
  const transcriptBase = {
    available: false,
    key: videoId ? `youtube:${videoId}` : "",
    source: "youtube-captions",
    videoId
  };

  const playerResponse = findYouTubePlayerResponse();
  const tracks =
    playerResponse?.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];

  if (!tracks.length) {
    return transcriptBase;
  }

  const track = chooseTranscriptTrack(tracks);
  if (!track?.baseUrl) {
    return transcriptBase;
  }

  const transcript = {
    ...transcriptBase,
    available: true,
    language: track.languageCode || "",
    baseUrl: track.baseUrl || "",
    source: "youtube-captions-json3"
  };

  if (!includeText) {
    return transcript;
  }

  const separator = track.baseUrl.includes("?") ? "&" : "?";
  const transcriptUrl = /[?&]fmt=/.test(track.baseUrl)
    ? track.baseUrl
    : `${track.baseUrl}${separator}fmt=json3`;

  try {
    const response = await fetch(transcriptUrl, { credentials: "omit" });
    if (!response.ok) {
      return transcript;
    }

    const data = await response.json();
    const lines = [];
    for (const event of data.events || []) {
      const line = collapseWhitespace(
        (event.segs || [])
          .map((segment) => segment.utf8 || "")
          .join("")
      );
      if (line) {
        lines.push(line);
      }
    }

    return {
      ...transcript,
      text: clamp(lines.join("\n"), 30000)
    };
  } catch (error) {
    console.debug("Hermes extension: failed to fetch YouTube transcript", error);
    return transcript;
  }
}

async function collectPageContext(includeTranscriptText, waitForHydration = false) {
  if (waitForHydration) {
    const hydrationTimeoutMs = isXOrTwitterHost() ? 9000 : 5000;
    await waitForHydratedCapture(hydrationTimeoutMs);
  }

  const url = getCurrentUrl();
  const title = document.title || "";
  const description = getPageDescription();
  const canonicalUrl = getCanonicalUrl();
  const siteName = getSiteName();
  const selection = getSelectedText();
  let pageText = await getVisiblePageTextWithRetry();
  let contentKind = "web-page";
  if (isYouTubeWatchPage()) {
    contentKind = "youtube-watch";
  } else if (isXOrTwitterHost()) {
    contentKind = "x-feed";
  }

  const metadata = {
    author: getMetaValue([
      "meta[name='author']",
      "meta[property='article:author']",
      "meta[itemprop='author']"
    ]),
    byline: collapseWhitespace(
      document.querySelector("[rel='author'], .byline, [itemprop='author']")?.textContent || ""
    )
  };

  let transcript = {
    available: false,
    shared: false,
    sharedPreviously: false,
    source: "",
    key: ""
  };

  if (isYouTubeWatchPage()) {
    metadata.videoId = url?.searchParams?.get("v") || "";
    metadata.channelName = collapseWhitespace(
      document.querySelector("ytd-channel-name a, #channel-name a, [itemprop='author']")?.textContent || ""
    );
    metadata.publishedTime = collapseWhitespace(
      document.querySelector("#info-strings, #title + yt-formatted-string, #description-inline-expander #info")?.textContent || ""
    );
    transcript = await fetchYouTubeTranscript(includeTranscriptText);
  } else if (isXOrTwitterHost()) {
    metadata.timelineItems = document.querySelectorAll("article").length;
  }

  // X can render sparse/virtualized text nodes while selection still contains rich text.
  // If selection is significantly larger, promote it so the bridge sends useful context.
  if ((pageText || "").length < 500 && (selection || "").length > (pageText || "").length + 300) {
    pageText = selection;
    metadata.pageTextSource = "selection-fallback";
  }

  return {
    url: window.location.href,
    title: clamp(title, 512),
    description,
    canonicalUrl,
    siteName,
    selection,
    pageText,
    contentKind,
    metadata,
    transcript
  };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type !== "hermes:collect-page-context") {
    return false;
  }

  collectPageContext(
    Boolean(message.includeTranscriptText),
    Boolean(message.waitForHydration)
  )
    .then((result) => sendResponse(result))
    .catch((error) => {
      sendResponse({
        error: error instanceof Error ? error.message : String(error)
      });
    });

  return true;
});
