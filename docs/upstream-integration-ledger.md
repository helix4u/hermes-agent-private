# Upstream Integration Ledger

Tracking upstream PR decisions for `NousResearch/hermes-agent` as they are reviewed and adapted into this fork.

## Continuation Guide

Use this file as the source of truth after context compression. The expected workflow is:

1. Stay on `main` unless the user explicitly asks for a different branch.
2. Review upstream merge PRs in true chronological order from `main..upstream/main`, using first-parent merge history.
3. When the user says `ok next`:
  - identify the next real unreviewed upstream merge PR
  - evaluate whether it is already covered, needs local integration, or is optional
  - write that evaluation to this ledger immediately, even if no code change is made
  - then explain the evaluation to the user
4. When the user asks to add or integrate a PR:
  - implement only in the previously proposed local shape
  - prefer fork-native adaptation over wholesale upstream transplant
  - update the existing ledger entry from evaluated/pending to integrated
  - include any verification command used
5. Always include a short manual test path in every ledger entry, including skips.

## Standing Policy

- Never copy upstream `tests/` content or CI test changes.
- Prefer Windows-safe and UTF-8-safe behavior whenever integration choices differ.
- Proposal before fix: evaluate first, log first, then implement only after the user confirms.
- Treat broad features as optional unless they close a real local correctness gap.
- Keep changes scoped. Do not silently broaden a PR beyond its local need.
- If a PR is already functionally covered, log it as a skip with rationale instead of changing code.
- If a PR is test-only, log it as a skip under the no-upstream-tests rule.

## Entry Template

Each PR entry should record:

- `Title`
- `Status`
- `Decision`
- `Why`
- `Proposal` for pending items, or `Local implementation` for integrated items
- `Verification` if code changed
- `Quick test path`
- `Test policy note`

## Sequencing Notes

- The ledger may contain older entries added out of order during earlier passes.
- Do not assume the last entry is the next PR to review.
- Determine the next PR by comparing this ledger against `git log main..upstream/main --merges --first-parent`.
- Once identified, add the next PR evaluation here before doing anything else.

## Rules

- Stay on `main`.
- Never transplant upstream CI tests or `tests/` content.
- Prefer Windows-safe and UTF-8-safe behavior whenever integration choices differ.
- Adapt upstream fixes to local architecture instead of cherry-picking wholesale when the fork has already diverged.

## Reviewed PRs

### Sequencing Note

- The first review in this pass started with PR `#1394` because it was found on a recent shared-ancestry scan.
- The true chronological missing merge sequence on `main..upstream/main` starts much earlier, with PR `#217`.
- From this point forward, the ledger follows the oldest-missing first-parent merge order.

### PR #1394

- Title: `fix: honor stt.enabled false across gateway transcription`
- Status: Integrated with a fork-native implementation.
- Decision: Keep the behavior, not the patch.
- Why:
  - Our fork already exposes `stt.enabled` in `config.yaml`, but gateway transcription still ignored it.
  - Users with STT disabled would still trigger transcription attempts and misleading API-key errors.
  - Our fork does not contain upstream's `tools/voice_mode.py`, so the upstream patch does not apply cleanly as-is.
- Local implementation:
  - Bridge `stt.enabled` into `GatewayConfig`.
  - Skip gateway transcription when STT is disabled and tell the model that audio was received but not transcribed.
  - Make `tools.transcription_tools.transcribe_audio()` return a clean disabled-state result before checking API credentials.
- Test policy note:
  - No upstream tests were copied.

### PR #217

- Title: `fix(gateway): persist transcript changes in /retry, /undo and fix /reset`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `[gateway/run.py](c:/Users/btgil/.hermes/hermes-agent/gateway/run.py)` already uses `self.session_store._generate_session_key(source)` for reset handling.
  - `[gateway/run.py](c:/Users/btgil/.hermes/hermes-agent/gateway/run.py)` already uses `self.session_store.rewrite_transcript(...)` for both `/retry` and `/undo`.
  - `[gateway/session.py](c:/Users/btgil/.hermes/hermes-agent/gateway/session.py)` already implements `rewrite_transcript(...)`.
- Test policy note:
  - No upstream tests were copied.

### PR #248

- Title: `feat(gateway): include Discord channel topic in session context`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `SessionSource.chat_topic` already exists and is serialized.
  - Discord adapters already capture channel topics for both messages and slash-command interactions.
  - The session-context prompt already surfaces channel topic text when present.
- Test policy note:
  - No upstream tests were copied.

### PR #277

- Title: `fix: handle None message content across codebase`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `agent/auxiliary_client.py` already uses `msg.get("content") or ""`.
  - `cli.py` already uses `msg.get("content") or ""` before slicing and length checks.
  - `honcho_integration/session.py` already uses `msg.get("content") or ""` when rendering transcripts.
  - The relevant `run_agent.py` tool-call formatting path already guards with `if msg.get("content") and msg["content"].strip():`, so `None` does not reach `.strip()`.
- Test policy note:
  - No upstream tests were copied.

### PR #223

- Title: `fix: correct off-by-one in retry exhaustion checks`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - The relevant retry exhaustion checks in `run_agent.py` already use `>= max_retries`.
  - The failure mode described upstream, falling through after the loop and then indexing into an invalid response, appears to already be guarded against by the current retry logic.
- Test policy note:
  - No upstream tests were copied.

### PR #225

- Title: `fix: preserve empty content in ReadResult.to_dict()`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `tools/file_operations.py` already preserves empty-string `content` values in `ReadResult.to_dict()`.
  - The current implementation filters out only `None` and empty lists, which matches the upstream fix intent.
- Test policy note:
  - No upstream tests were copied.

### PR #229

- Title: `fix(agent): copy conversation_history to avoid mutating caller's list`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `run_agent.py` already initializes `messages` with `list(conversation_history)` instead of reusing the caller-owned list.
  - The in-code comment already documents the intent to avoid mutating caller state.
- Test policy note:
  - No upstream tests were copied.

### PR #231

- Title: `fix: use task-specific glob pattern in disk usage calculation`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `tools/terminal_tool.py` already calculates disk usage with a task-specific scratch glob pattern instead of scanning every `hermes-*` directory for each task.
  - The current code comments already note that the calculation is per-task to avoid double-counting.
- Test policy note:
  - No upstream tests were copied.

### PR #233

- Title: `fix(security): add re.DOTALL to prevent multiline bypass of dangerous command detection`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `tools/approval.py` already applies `re.DOTALL` in dangerous-command detection.
  - The multiline regex bypass described upstream appears to already be closed locally.
- Test policy note:
  - No upstream tests were copied.

### PR #243

- Title: `fix(honcho): auto-enable when API key is present`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `honcho_integration/client.py` already auto-enables Honcho when an API key is present and `enabled` is not explicitly set.
  - The current code still respects an explicit `enabled: false` override.
- Test policy note:
  - No upstream tests were copied.

### PR #284

- Title: `fix(cli): throttle UI invalidate to prevent terminal blinking on SSH`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `cli.py` already has a throttled `_invalidate()` helper with a repaint interval.
  - The clarify, sudo, and dangerous-command approval flows already use the throttled invalidation path instead of directly calling `self._app.invalidate()` in their polling loops.
- Test policy note:
  - No upstream tests were copied.

### PR #286

- Title: `Fix ClawHub Skills Hub adapter for API endpoint changes`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `tools/skills_hub.py` already uses the newer ClawHub search endpoint shape and parses `items` results.
  - The current ClawHub adapter already resolves the latest version, fetches version metadata, and falls back to `rawUrl`/download URLs for file content.
  - This matches the upstream fix intent closely enough that no local code change is warranted right now.
- Follow-up note:
  - Because this depends on an external API contract, live verification through the Skills Hub UI/CLI is still worth doing during testing.
- Test policy note:
  - No upstream tests were copied.

### PR #295

- Title: `fix: resolve OPENROUTER_API_KEY before OPENAI_API_KEY in all code paths`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `hermes_cli/runtime_provider.py` already prefers `OPENROUTER_API_KEY` over `OPENAI_API_KEY` for the OpenRouter runtime path.
  - `cli.py` already has a more nuanced resolution strategy that selects keys based on the effective base URL, which covers the upstream bug and avoids sending an OpenAI key to OpenRouter when both are set.
- Test policy note:
  - No upstream tests were copied.

### PR #301

- Title: `feat(mcp): Native MCP client with HTTP transport, reconnection, and security`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `tools/mcp_tool.py` already exists and includes stdio + HTTP transport, reconnection, credential sanitization, environment filtering, timeout handling, and thread-safe lifecycle management.
  - CLI and gateway already expose `/reload-mcp`, refresh tool availability, and shut down MCP servers during cleanup.
  - `model_tools.py`, `hermes_cli/banner.py`, `README.md`, `docs/mcp.md`, and `cli-config.yaml.example` already include MCP integration and documentation.
  - The current fork appears to include the follow-on fixes that were folded into the upstream merge, not just the initial MCP landing.
- Follow-up note:
  - This PR is best treated as a bundled feature train rather than a single isolated patch, so future MCP-related upstream reviews should focus on later bugfix PRs individually.
- Test policy note:
  - No upstream tests were copied.

### PR #219

- Title: `fix: guard POSIX-only process functions for Windows compatibility`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `tools/environments/local.py` and `tools/process_registry.py` now route process lifecycle behavior through shared shell/process helpers, which already avoid raw POSIX-only assumptions on Windows.
  - `tools/code_execution_tool.py` already guards `preexec_fn=os.setsid` and process-group termination behind a Windows check.
  - `gateway/platforms/whatsapp.py` already avoids `os.setsid`, `os.getpgid`, and `os.killpg` on Windows and falls back to `terminate()` / `kill()`.
- Follow-up note:
  - This is an important policy-aligned fix for the fork, but it appears to have already been absorbed through later Windows-safety work.
- Test policy note:
  - No upstream tests were copied.

### PR #137

- Title: `feat: Add Superpowers software development skills`
- Status: No action needed.
- Decision: Skip, already present in this fork.
- Why:
  - The `skills/software-development/` directory already contains the five added skills:
    - `test-driven-development`
    - `systematic-debugging`
    - `subagent-driven-development`
    - `writing-plans`
    - `requesting-code-review`
  - This PR is content-oriented skills packaging rather than a runtime/code-path change, and the content is already available locally.
- Follow-up note:
  - If we ever want to prune or rewrite these skills for fork-specific workflow, that should be treated as a local curation decision, not an upstream integration task.
- Test policy note:
  - No upstream tests were copied.

### PR #184

- Title: `feat: Home Assistant integration (REST tools + WebSocket gateway)`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `tools/homeassistant_tool.py` already provides Home Assistant REST tools, including the security-oriented domain blocklist and `entity_id` validation called out in the upstream feature train.
  - `gateway/platforms/homeassistant.py` already exists and implements the Home Assistant WebSocket event adapter.
  - `toolsets.py`, `model_tools.py`, and related CLI/tool configuration already expose the Home Assistant integration.
  - `run_agent.py` already preserves tool-call `extra_content`, including Gemini `thought_signature`, which was called out as a necessary companion fix in the upstream merge.
- Follow-up note:
  - This merge bundled the feature with several follow-on bugfixes and security improvements, but the current fork appears to already contain those core behaviors.
- Test policy note:
  - No upstream tests were copied.

### PR #350

- Title: `fix(gateway): match _quick_key to _generate_session_key for WhatsApp DMs`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `gateway/session.py` already centralizes session-key construction in `build_session_key(source)`, including the special WhatsApp DM case with `chat_id`.
  - `gateway/run.py` already uses `build_session_key(source)` for the fast interrupt `_quick_key` path.
  - `gateway/run.py` also already uses `build_session_key(source)` for the `/usage` path, so the two relevant code paths are aligned with normal session storage.
- Test policy note:
  - No upstream tests were copied.

### PR #354

- Title: `fix: use os.sep in skill_view path boundary check for Windows compatibility`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `tools/skills_tool.py` already uses `os.sep` in the `skill_view()` path boundary check instead of hardcoding `/`.
  - This preserves the intended directory-escape protection on Windows paths.
- Follow-up note:
  - This is a good example of an upstream Windows fix that aligns directly with the fork’s local platform policy.
- Test policy note:
  - No upstream tests were copied.

### PR #370

- Title: `fix(session): use database session count for has_any_sessions`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `gateway/session.py` already uses the SQLite database as the source of truth in `has_any_sessions()`.
  - The current implementation already documents the single-platform reset bug and falls back to `_entries` only when the DB is unavailable.
- Test policy note:
  - No upstream tests were copied.

### PR #317

- Title: `fix(setup): improve shell config detection for PATH setup`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `setup-hermes.sh` already checks `$SHELL` first to choose the appropriate shell startup file.
  - The current script already falls back to file-existence checks for non-standard shells.
  - It also already `touch`es the selected config file before appending the PATH export.
- Test policy note:
  - No upstream tests were copied.

### PR #192

- Title: `fix(security): catch multi-word prompt injection bypass in skills_guard`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `tools/skills_guard.py` already uses the multi-word-aware prompt-injection regex for `ignore ... instructions`.
  - The current scanner also includes related multi-word-aware patterns for other instruction-bypass phrasing.
- Test policy note:
  - No upstream tests were copied.

### PR #395

- Title: `fix(gateway): use filtered history length for transcript message extraction`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `gateway/run.py` already returns `history_offset` from `_run_agent()` based on the filtered agent history actually passed to the model.
  - Transcript extraction already uses that filtered offset instead of `len(history)`, avoiding message loss from stripped `session_meta` entries.
  - The current code also already uses the safer empty-list fallback when no new messages are found, preventing whole-history duplication.
- Test policy note:
  - No upstream tests were copied.

### PR #403

- Title: `Fix context overrun crash with local LLM backends`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `run_agent.py` already detects local-backend context overruns using phrases like `context size` and `context window`.
  - The context-length check already runs before the generic 4xx client-error abort path.
  - The current non-retryable 4xx phrase list already omits `error code: 400`, which avoids misclassifying local context-overrun responses as immediate hard failures.
- Test policy note:
  - No upstream tests were copied.

### PR #269

- Title: `Fix nous refresh token rotation failure on key mint failure`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `hermes_cli/auth.py` already persists Nous auth state immediately after a successful refresh, before agent-key minting.
  - The mint-retry path already uses the latest in-memory refresh token rather than the original stale one.
  - Auth-store writes are already atomic/durable (`tmp` file, `fsync`, `os.replace`) and OAuth trace logging is already present.
- Test policy note:
  - No upstream tests were copied.

### PR #386

- Title: `fix symlink boundary check prefix confusion in skills_guard`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `tools/skills_guard.py` already uses `Path.is_relative_to()` for the symlink boundary check in `_check_structure()`.
  - This closes the shared-prefix confusion bug that `startswith()` allowed.
- Test policy note:
  - No upstream tests were copied.

### PR #388

- Title: `fix --force bypassing dangerous verdict in should_allow_install`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `tools/skills_guard.py` already blocks `dangerous` verdicts unconditionally before evaluating the `force` override path.
  - The current docstring and implementation are aligned: `--force` only overrides caution-level blocks, not dangerous ones.
- Test policy note:
  - No upstream tests were copied.

### PR #390

- Title: `fix hidden directory filter broken on Windows`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `tools/skills_tool.py` already uses `Path.parts` membership checks instead of hardcoded `/.git/` / `/.hub/` string matches.
  - `agent/skill_commands.py` already uses the same `Path.parts` approach, so quarantined or hidden skills are not exposed on Windows.
- Test policy note:
  - No upstream tests were copied.

### PR #201

- Title: `fix skills hub dedup to prefer higher trust levels`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `tools/skills_hub.py` already uses ranked trust comparison in both `GitHubSource.search()` and `unified_search()`.
  - Builtin results already outrank trusted results, which outrank community results.
- Test policy note:
  - No upstream tests were copied.

### PR #203

- Title: `add unit tests for trajectory_compressor`
- Status: No action needed.
- Decision: Skip, test-only upstream PR.
- Why:
  - This PR only adds upstream test coverage and does not change runtime behavior.
  - The fork’s standing policy is to never take upstream CI tests or transplanted `tests/` content.
- Test policy note:
  - No upstream tests were copied.

### PR #204

- Title: `fix Telegram italic regex newline bug`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `gateway/platforms/telegram.py` already uses the newline-safe italic regex `\*([^*\n]+)\*`.
  - The current code comment already documents the exact bullet-list corruption bug this fixes.
- Test policy note:
  - No upstream tests were copied.

### PR #209

- Title: `add ascii-art skill for creative text banners and art`
- Status: No action needed.
- Decision: Skip, already present in this fork.
- Why:
  - `skills/creative/ascii-art/SKILL.md` already exists locally.
  - The local skill content appears to be a later/more developed version than the initial upstream addition, so taking the upstream file would be a downgrade rather than an integration.
- Follow-up note:
  - As with other skills-only PRs, this is a content curation area rather than a runtime integration task.
- Test policy note:
  - No upstream tests were copied.

### PR #214

- Title: `fix: align _apply_delete comment with actual behavior`
- Status: No action needed.
- Decision: Skip, comment-only upstream PR.
- Why:
  - The PR only updates the explanatory comment in `tools/patch_parser.py`.
  - There is no runtime behavior change to integrate.
- Test policy note:
  - No upstream tests were copied.

### PR #200

- Title: `fix extract_images and truncate_message bugs in platform base`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `gateway/platforms/base.py` already removes only the extracted image tags in `extract_images()` rather than stripping all markdown image syntax indiscriminately.
  - `gateway/platforms/base.py` already walks only `chunk_body` when tracking code-fence state in `truncate_message()`, which preserves correct reopened code-block handling across chunks.
- Test policy note:
  - No upstream tests were copied.

### PR #261

- Title: `improve error handling and type hints in session_search_tool`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `tools/session_search_tool.py` already includes the widened `typing` imports, defensive timestamp formatting, and guarded parent-session resolution logic from the upstream fix.
  - The current implementation already handles `concurrent.futures.TimeoutError` for parallel summarization and returns a structured timeout error instead of hanging or surfacing a raw exception.
- Test policy note:
  - No upstream tests were copied.

### PR #262

- Title: `improve error handling and validation in transcription_tools`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `tools/transcription_tools.py` already has the upstream validation and hardening behavior: supported-format checks, max-size checks, specific OpenAI exception handling, and clearer logging.
  - The current file also includes the fork-native `stt.enabled` handling from PR `#1394`, so it is strictly ahead of the upstream change rather than missing it.
- Test policy note:
  - No upstream tests were copied.

### PR #267

- Title: `feat(skills): add DuckDuckGo search skill as Firecrawl fallback`
- Status: No action needed.
- Decision: Skip, already present in this fork.
- Why:
  - `skills/research/duckduckgo-search/SKILL.md` already exists locally with the DuckDuckGo fallback instructions and `ddgs` usage examples.
  - `skills/research/duckduckgo-search/scripts/duckduckgo.sh` also already exists locally, so the skill content and helper script have already landed in this fork.
- Follow-up note:
  - As with other skills-only PRs, this is content already curated into the local skills tree rather than a runtime integration gap.
- Test policy note:
  - No upstream tests were copied.

### PR #274

- Title: `fix(setup): handle TerminalMenu init failures with safe fallback`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `hermes_cli/setup.py` already catches general `TerminalMenu` initialization/runtime failures in `prompt_choice()` and falls back to the text-based numbered selector.
  - The current implementation also preserves the explicit `ImportError` / `NotImplementedError` fallback path, so the setup wizard remains usable on Windows and unusual terminal environments.
- Test policy note:
  - No upstream tests were copied.

### PR #275

- Title: `fix(batch_runner): preserve traceback when batch worker fails`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `batch_runner.py` already wraps the `pool.imap_unordered(...)` loop with an exception handler that logs the worker failure with `exc_info=True` before re-raising.
  - `tools/registry.py` already uses `logger.exception(...)` for tool dispatch failures, so traceback-rich debugging is already preserved in the related runtime path upstream also touched.
- Test policy note:
  - No upstream tests were copied.

### PR #280

- Title: `fix: add missing dangerous command patterns (tee, process substitution, full-path rm)`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `tools/approval.py` already includes the process-substitution pattern for `bash/sh/zsh/ksh <(curl|wget ...)`.
  - `tools/approval.py` already flags `tee` writes to sensitive paths and the expanded `find ... -exec /full/path/rm` variant, so the upstream safety coverage is already present.
- Test policy note:
  - No upstream tests were copied.

### PR #212

- Title: `feat(skills): add Solana blockchain skill`
- Status: Evaluation complete.
- Decision: Optional follow-up, not required for parity or correctness.
- Why:
  - This fork does not currently include `skills/blockchain/solana/`, so the upstream content is genuinely missing locally.
  - The PR is a bundled optional skill plus helper script, not a runtime bug fix or platform behavior change.
  - The helper script is self-contained and low-risk, but the upstream skill text is Unix-leaning (`python3`, shell export examples), so a fork-native adaptation would be preferable if we choose to take it.
- Proposed fork-native approach:
  - Add the skill as optional bundled content rather than a wholesale upstream transplant.
  - Adjust examples for Windows-safe usage where appropriate (`python`/`py` guidance, UTF-8-safe output expectations, path wording that matches local skill resolution).
  - Keep the script self-contained and avoid any upstream tests.
- Test policy note:
  - No upstream tests were copied.

### PR #393

- Title: `fix(whatsapp): initialize data variable and close log handle on error paths`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `gateway/platforms/whatsapp.py` already initializes `data = {}` before the bridge health-check loop, so a JSON parse failure after HTTP readiness cannot trip a `NameError`.
  - The current adapter already has `_close_bridge_log()` and calls it on failed startup/error paths as well as during disconnect cleanup, so the upstream file-handle leak fix is already present.
- Test policy note:
  - No upstream tests were copied.

### PR #419

- Title: `fix: pass stable task_id in CLI and gateway to preserve sandbox state across turns`
- Status: Integrated locally.
- Decision: Take, implemented fork-natively.
- Why:
  - The fork was still calling `run_conversation(...)` from both `cli.py` and `gateway/run.py` without a stable `task_id`, which risks container/sandbox backends creating fresh environments each turn instead of reusing session state.
  - `tools/file_tools.py` was also creating environments without forwarding `task_id`, which could break consistency between file tools and terminal-backed sandboxes.
- Local implementation:
  - `cli.py` now passes `task_id=self.session_id` into `run_conversation(...)`.
  - `gateway/run.py` now passes `task_id=session_id` into `run_conversation(...)`.
  - `tools/file_tools.py` now forwards `task_id` into `_create_environment(...)` so file operations reuse the same task-scoped environment.
- Verification:
  - `python -m py_compile cli.py gateway/run.py tools/file_tools.py`
- Test policy note:
  - No upstream tests were copied.

### PR #438

- Title: `fix: add missing empty-content guard after think-block stripping in retry path`
- Status: Integrated locally.
- Decision: Take, implemented fork-natively.
- Why:
  - The fork already had the post-`<think>` empty-content guard in the first max-iterations summary branch, but the retry-summary branch still appended `{"role": "assistant", "content": ""}` when a retry response became empty after think-block stripping.
  - That meant the fallback summary text could be skipped even though there was no user-visible response left.
- Local implementation:
  - `run_agent.py` now mirrors the existing first-branch behavior in the retry-summary branch: after stripping `<think>` blocks, it only appends the assistant message if content remains.
  - If stripping leaves the response empty, it now falls back to `self._build_summary_fallback(messages)` and then the existing summary fallback string.
- Verification:
  - `python -m py_compile run_agent.py`
- Test policy note:
  - No upstream tests were copied.

### PR #288

- Title: `feat(whatsapp): stream tool progress as a single live-updating message`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `gateway/platforms/base.py` already defines `edit_message(...)`, and `gateway/platforms/whatsapp.py` already implements it against the bridge.
  - `gateway/run.py` already accumulates progress lines into a rolling progress message and edits it in place for WhatsApp instead of sending a fresh message for every tool step.
  - `scripts/whatsapp-bridge/bridge.js` already returns and handles `messageId`, which is the bridge-side capability this feature depends on.
- Test policy note:
  - No upstream tests were copied.

### PR #292

- Title: `feat(whatsapp): native media attachments for images, videos and documents`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `gateway/platforms/base.py` already has the native media send hooks (`send_image_file`, `send_video`, `send_document`) and routes extracted media by file type.
  - `gateway/platforms/whatsapp.py` already implements `_send_media_to_bridge(...)` plus native image, video, and document send methods.
  - `scripts/whatsapp-bridge/bridge.js` already exposes `/send-media`, and the gateway already has the supporting document-cache/media plumbing needed for attachment delivery.
- Test policy note:
  - No upstream tests were copied.

### PR #293

- Title: `fix: eliminate shell noise from terminal output and fix test failures`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `tools/environments/local.py` already uses the upstream-style fence-marker approach (`_OUTPUT_FENCE` + `_extract_fenced_output(...)`) to isolate real command output from shell init/exit noise.
  - The same file already keeps the fallback noise-pattern cleaner for cases where fences are missing, so the practical upstream behavior is already in place.
  - The remaining upstream changes are test-related, which we are intentionally not taking.
- Test policy note:
  - No upstream tests were copied.

### PR #307

- Title: `fix: correct typo 'Grup' -> 'Group' in test section headers`
- Status: No action needed.
- Decision: Skip, test-only upstream PR.
- Why:
  - The PR only changes comment text inside `tests/test_run_agent.py`.
  - It has no runtime impact, and the fork’s standing policy is to never take upstream tests or transplanted `tests/` content.
- Test policy note:
  - No upstream tests were copied.

### PR #296

- Title: `fix(cron): close lock_fd on failed flock to prevent fd leak`
- Status: No action needed.
- Decision: Skip, already functionally present in this fork.
- Why:
  - `cron/scheduler.py` already initializes `lock_fd = None` before locking.
  - The current `tick()` implementation already closes `lock_fd` in the failed-lock `except` path before returning, which is the exact upstream leak fix.
- Test policy note:
  - No upstream tests were copied.

### PR #451

- Title: `feat: Add Daytona environment backend`
- Status: Integrated locally.
- Decision: Take, implemented fork-natively.
- Why:
  - This fork does not currently include `tools/environments/daytona.py`, and `tools/terminal_tool.py` still only supports `local`, `docker`, `singularity`, `modal`, and `ssh`.
  - So the upstream feature was genuinely missing locally.
- Local implementation:
  - Added `tools/environments/daytona.py` as a task-scoped Daytona backend with persistent sandbox reuse, interrupt-aware execution, and cleanup behavior that fits the current terminal backend interface.
  - Wired Daytona into `tools/terminal_tool.py` and `tools/file_tools.py`, including image/config selection, container-resource handling, requirement checks, and host-path sanity checks.
  - Added local-style config/setup/doctor/status support in `hermes_cli/config.py`, `hermes_cli/setup.py`, `hermes_cli/doctor.py`, and `hermes_cli/status.py`.
  - Updated `cli-config.yaml.example` and `README.md` so the backend shows up in the local docs/config surface.
- Verification:
  - `python -m py_compile tools/environments/daytona.py tools/terminal_tool.py tools/file_tools.py hermes_cli/config.py hermes_cli/doctor.py hermes_cli/status.py hermes_cli/setup.py`
- Test policy note:
  - No upstream tests were copied.

### PR #469

- Title: `fix(config): route API keys and tokens to .env instead of config.yaml`
- Status: Integrated locally.
- Decision: Take, implemented fork-natively.
- Why:
  - `hermes_cli/config.py` still uses a narrower hardcoded `api_keys` allowlist in `set_config_value()`, so some secrets can still be routed into `config.yaml` instead of `~/.hermes/.env`.
  - The current fork is missing upstream's broader secret routing for keys like `OPENAI_API_KEY`, `NOUS_API_KEY`, `WANDB_API_KEY`, and `TINKER_API_KEY`, and it also lacks the future-proof `_API_KEY` / `_TOKEN` suffix handling.
- Local implementation:
  - Expanded the explicit `api_keys` allowlist in `set_config_value()` to cover the fork's currently supported secret env vars, including `OPENAI_API_KEY`, `NOUS_API_KEY`, `WANDB_API_KEY`, `TINKER_API_KEY`, and `DAYTONA_API_KEY`.
  - Added suffix-based routing for keys ending in `_API_KEY` and `_TOKEN`, while preserving the existing `TERMINAL_SSH*` special-case handling.
- Verification:
  - `python -m py_compile hermes_cli/config.py`
- Test policy note:
  - No upstream tests were copied.

### PR #448

- Title: `fix(cli): use correct dict key for codex auth file path in status output`
- Status: Integrated locally.
- Decision: Take, implemented fork-natively.
- Why:
  - `hermes_cli/status.py` still reads `codex_status.get("auth_file")`, but the auth status payload uses `auth_store`.
  - That means `hermes status` silently omits the Codex auth file path even when it is available.
- Local implementation:
  - Updated `hermes_cli/status.py` to read `codex_status.get("auth_store")` for the displayed Codex auth file path.
  - Left the rest of the status output unchanged.
- Verification:
  - `python -m py_compile hermes_cli/status.py`
- Quick test path:
  - Ensure OpenAI Codex auth is configured.
  - Run `hermes status`.
  - Confirm the `OpenAI Codex` section now shows the auth file path instead of omitting it.
- Test policy note:
  - No upstream tests were copied.

### PR #444

- Title: `fix: add missing re.DOTALL flag to DeepSeek V3 tool call parser`
- Status: Integrated locally.
- Decision: Take, implemented fork-natively.
- Why:
  - `environments/tool_call_parsers/deepseek_v3_parser.py` still compiles the DeepSeek V3 tool-call regex without `re.DOTALL`.
  - That means `.*` will not match newlines, so multiline JSON arguments inside fenced tool-call blocks can fail to parse.
- Local implementation:
  - Added `re.DOTALL` to the DeepSeek V3 parser's `PATTERN = re.compile(...)` call.
  - Left the rest of the parser unchanged.
- Verification:
  - `python -m py_compile environments/tool_call_parsers/deepseek_v3_parser.py`
- Quick test path:
  - Feed the parser a DeepSeek V3 tool-call block whose JSON arguments span multiple lines.
  - Confirm it returns a parsed tool call instead of falling back to raw text / no tool calls.
  - Sanity-check that a single-line argument block still parses the same way.
- Test policy note:
  - No upstream tests were copied.

### PR #441

- Title: `fix(gateway): return response from /retry handler instead of discarding it`
- Status: Integrated locally.
- Decision: Take, implemented fork-natively.
- Why:
  - `gateway/run.py` still has `_handle_retry_command()` call `await self._handle_message(retry_event)` and then discard the return value.
  - That means `/retry` can execute the agent flow and show progress, but the final response can still be dropped instead of being returned through the normal command flow.
- Local implementation:
  - Updated `_handle_retry_command()` to `return await self._handle_message(retry_event)`.
  - Left the rest of the retry behavior unchanged.
- Verification:
  - `python -m py_compile gateway/run.py`
- Quick test path:
  - In any messaging platform, send a message that gets a normal response.
  - Run `/retry`.
  - Confirm the retried response is actually delivered back to the chat instead of silently disappearing after tool progress.
- Test policy note:
  - No upstream tests were copied.

### PR #433

- Title: `fix(whatsapp): replace Linux-only fuser with cross-platform port cleanup`
- Status: Integrated locally.
- Decision: Take, implemented fork-natively.
- Why:
  - `gateway/platforms/whatsapp.py` still uses inline `fuser` calls to clean up bridge processes on the configured port.
  - That works on Linux, but on Windows it silently does nothing, so orphaned bridge processes can keep the port bound and cause reconnect/startup failures.
- Local implementation:
  - Added `_kill_port_process(port)` to `gateway/platforms/whatsapp.py`.
  - On Windows, it uses `netstat -ano -p TCP` plus `taskkill /PID ... /F`; on non-Windows it preserves the existing `fuser` behavior.
  - Replaced the inline startup/shutdown port cleanup blocks with calls to the helper.
- Verification:
  - `python -m py_compile gateway/platforms/whatsapp.py`
- Quick test path:
  - On Windows, start the WhatsApp bridge, then leave an orphaned listener on the configured port.
  - Restart or reconnect the gateway.
  - Confirm Hermes clears the stale port binding and the bridge starts instead of failing with an address-in-use error.
- Test policy note:
  - No upstream tests were copied.

### PR #297

- Title: `Make batch_runner checkpoint incremental and atomic`
- Status: Integrated locally.
- Decision: Take, implemented fork-natively.
- Why:
  - `batch_runner.py` still writes checkpoint files with plain `open(..., 'w')`, which can leave a corrupted checkpoint on crash or interruption.
  - The current run path also still initializes fresh checkpoint state instead of preserving loaded checkpoint state and only saves the checkpoint at the end, which increases progress loss on interrupted runs.
- Local implementation:
  - Updated `_save_checkpoint()` to use an atomic temp-file write with `tempfile`, flush, `os.fsync`, and `os.replace`.
  - Preserved loaded checkpoint state instead of always initializing a fresh empty structure.
  - Added incremental checkpoint saves after each batch result in the parent process, while keeping checkpoint-write failures non-fatal.
- Verification:
  - `python -m py_compile batch_runner.py`
- Quick test path:
  - Start a batch run with multiple batches.
  - After at least one batch completes, interrupt the process.
  - Confirm `checkpoint.json` remains valid JSON and reflects completed work up to the last finished batch.
  - Resume the run and confirm it skips already completed prompts instead of starting over.
- Test policy note:
  - No upstream tests were copied.

### PR #552

- Title: `feat: /insights command — usage analytics, cost estimation & activity patterns`
- Status: Integrated locally.
- Decision: Take, implemented fork-natively.
- Why:
  - The fork was missing the entire insights feature surface:
    - no local `agent/insights.py`
    - no `insights` CLI subcommand in `hermes_cli/main.py`
    - no `/insights` slash command in `hermes_cli/commands.py`
    - no gateway `/insights` handler in `gateway/run.py`
  - The existing SQLite session store in `hermes_state.py` already had the right data model for a fork-native implementation, including sessions, messages, tool calls, tool names, and token counts.
  - Pricing needs to stay conservative in this fork because model/provider pricing drifts over time and the fork supports custom endpoints and self-hosted backends.
- Local implementation:
  - Added `agent/insights.py` with a local insights engine that summarizes session usage from `SessionDB`.
  - Implemented overview metrics, model/platform/tool breakdowns, activity patterns, and notable sessions.
  - Kept unknown/custom/self-hosted models at zero estimated cost unless they match an explicit known-pricing rule.
  - Classified browser sidecar extension sessions as their own `browser-sidecar` platform bucket using the existing persisted session metadata (`source=local`, `user_id=local-browser`) so they appear distinctly in insights output and can be filtered explicitly.
  - Added `hermes insights` in `hermes_cli/main.py`.
  - Added `/insights` to `hermes_cli/commands.py` and wired CLI handling in `cli.py`.
  - Added gateway `/insights` handling in `gateway/run.py`, using executor-backed DB/report work so the event loop stays responsive.
- Verification:
  - `python -m py_compile agent/insights.py cli.py hermes_cli/commands.py hermes_cli/main.py gateway/run.py`
- Quick test path:
  - Run `hermes insights` and confirm it prints a readable usage summary from `~/.hermes/state.db`.
  - Run `hermes insights --days 7` and confirm the date window changes the totals.
  - Use a browser sidecar session, then rerun `hermes insights` and confirm sidecar activity appears under a distinct `browser-sidecar` platform bucket.
  - Run `hermes insights --source browser-sidecar` and confirm it filters to extension-sidecar sessions only.
  - Use `/insights` in the interactive CLI and confirm it renders without breaking the prompt flow.
  - Use `/insights 7` in a gateway chat and confirm a formatted analytics response is returned.
  - Sanity-check that custom or unknown models report zero estimated cost rather than bogus pricing.
- Test policy note:
  - No upstream tests were copied.

### PR #563

- Title: `fix: prevent data loss in skills sync on copy/update failure`
- Status: Integrated locally.
- Decision: Take, implemented fork-natively.
- Why:
  - The local `tools/skills_sync.py` is still on the older manifest format and older sync logic.
  - Right now a failed `copytree()` during new-skill sync can still poison the manifest because the skill name is added even after failure, so later syncs will skip it instead of retrying.
  - The local sync code also does not support safe updates of unchanged bundled skills at all, so we are missing both the upstream bugfix and the newer manifest/hash-based update model it depends on.
  - This is a good fit for the fork because it improves reliability without touching upstream tests, and it can be kept Windows-safe by preserving UTF-8 manifest writes and careful `shutil`/filesystem behavior.
- Local implementation:
  - Upgrade `tools/skills_sync.py` to a hash-aware manifest format, while auto-migrating older name-only manifests.
  - For new skills, only record the manifest entry after a successful copy.
  - For existing bundled skills, update only when the user's copy still matches the previous bundled hash.
  - On update, move the old copy to a backup first and restore it if the replacement copy fails.
  - Keep user-modified skills untouched and keep user deletions respected.
- Verification:
  - `python -m py_compile tools/skills_sync.py`
- Quick test path:
  - Force a new-skill copy failure and confirm the manifest is not updated for that skill, so the next sync retries it.
  - Sync an unchanged bundled skill, then change the bundled source and confirm the local copy updates only if the user copy was unmodified.
  - Force an update failure mid-copy and confirm the user's original skill directory is restored from backup.
  - Confirm a user-modified skill is still skipped rather than overwritten.
- Test policy note:
  - No upstream tests were copied.

### PR #420

- Title: `fix: respect OPENAI_BASE_URL when resolving API key priority`
- Status: Integrated locally after follow-up re-auth UX audit.
- Decision: Integrate local cleanup.
- Why:
  - The main runtime-provider fix is already present locally in `hermes_cli/runtime_provider.py`: custom/OpenAI-compatible endpoints selected through `OPENAI_BASE_URL` already win on base URL resolution.
  - The only remaining upstream nuance was comment wording around key selection, but there is no missing behavioral change to pull in here for this fork review step.
  - The small companion addition from the merge, GLM context lengths for `glm-4.7` and `glm-5` (`202752`), is also already present locally in `agent/model_metadata.py`.
- Quick test path:
  - Set both `OPENROUTER_API_KEY` and `OPENAI_API_KEY`.
  - Set `OPENAI_BASE_URL` to a custom OpenAI-compatible endpoint.
  - Confirm Hermes resolves and uses the custom endpoint instead of defaulting to OpenRouter.
  - Sanity-check that `glm-4.7` and `glm-5` model IDs resolve to the expected context length in `agent/model_metadata.py`.
- Test policy note:
  - No upstream tests were copied.

### PR #473

- Title: `Update model id in OpenRouter from minimax-m2.1 to minimax-m2.5`
- Status: Integrated locally.
- Decision: Take, implemented fork-natively.
- Why:
  - This is mostly a stale model-ID rename, but we still have local user-facing references to `minimax/minimax-m2.1`.
  - The stale references are in active runtime/config surfaces, not just historical docs:
    - `tools/rl_training_tool.py` test-model defaults
    - `tools/rl_training_tool.py` schema/help text
    - `hermes_cli/models.py` OpenRouter model picker list
  - Keeping the older model ID around risks confusing users or causing avoidable failures if the older alias disappears upstream.
- Local implementation:
  - Update local runtime/default model references from `minimax/minimax-m2.1` to `minimax/minimax-m2.5`.
  - Update the corresponding display labels/help text in `tools/rl_training_tool.py` and `hermes_cli/models.py`.
  - Do not touch unrelated cached third-party data blobs.
- Verification:
  - `python -m py_compile tools/rl_training_tool.py hermes_cli/models.py`
- Quick test path:
  - Open the model picker and confirm it offers `minimax/minimax-m2.5` instead of `minimax/minimax-m2.1`.
  - Run the RL inference test flow with default models and confirm the generated model list uses `minimax/minimax-m2.5`.
  - Sanity-check that no active user-facing help text still mentions `minimax-m2.1`.
- Test policy note:
  - No upstream tests were copied.

### PR #571

- Title: `fix: implement Nous credential refresh on 401 error for retry logic`
- Status: Integrated locally.
- Decision: Take, implemented fork-natively.
- Why:
  - The local retry loop in `run_agent.py` already has a Codex-specific 401 refresh path, but it does not yet do the same for Nous.
  - We already have the underlying Nous credential machinery locally in `hermes_cli/auth.py`, including `resolve_nous_runtime_credentials(..., force_mint=...)`, so this is a true missing integration point rather than a missing subsystem.
  - Without this, an expired or invalid Nous agent key can cause a run to fail immediately on 401 even though the fork already knows how to mint a replacement key.
- Local implementation:
  - Add a local `_try_refresh_nous_client_credentials(force=True)` helper to `run_agent.py`, parallel to the existing Codex refresh helper.
  - Re-resolve Nous runtime credentials with `force_mint=True`, rebuild the OpenAI client with the refreshed key/base URL, and clear OpenRouter-only default headers from the rebuilt client kwargs.
  - Add a one-time Nous 401 retry branch in the API retry loop, alongside the existing Codex 401 branch.
- Verification:
  - `python -m py_compile run_agent.py`
- Quick test path:
  - Run Hermes against the Nous provider with a deliberately expired or invalid minted agent key but a still-valid refresh path.
  - Trigger an API call that returns 401.
  - Confirm Hermes remints/reloads the Nous credentials once and retries successfully instead of failing the whole run immediately.
  - Confirm repeated 401s do not cause an infinite refresh loop.
- Test policy note:
  - No upstream tests were copied.

### PR #308

- Title: `fix: rename misspelled directory 'fouth-edition' to 'fourth-edition'`
- Status: Integrated locally.
- Decision: Take, implemented as a direct local rename.
- Why:
  - The misspelled schema directory still exists locally under `skills/productivity/powerpoint/scripts/office/schemas/ecma/fouth-edition`.
  - This is a pure path-correction change, but it is still worth taking so local references and future maintenance use the correct schema naming.
  - There is no runtime logic change here, and there are no upstream tests to consider.
- Local implementation:
  - Rename the directory from `fouth-edition` to `fourth-edition`.
  - Do not make any broader content changes.
- Quick test path:
  - Confirm the directory now exists at `skills/productivity/powerpoint/scripts/office/schemas/ecma/fourth-edition`.
  - Confirm the old `fouth-edition` path no longer exists.
  - Sanity-check that the PowerPoint skill files still resolve/load normally after the rename.
- Test policy note:
  - No upstream tests were copied.

### PR #309

- Title: `fix(timezone): timezone-aware now() for prompt, cron, and execute_code`
- Status: Integrated locally.
- Decision: Take, implemented fork-natively.
- Why:
  - The local fork was still using naive `datetime.now()` in the main places upstream targeted:
    - `run_agent.py` for the conversation-start system prompt timestamp
    - `cron/jobs.py` for schedule math and persisted job timestamps
    - `cron/scheduler.py` for cron run logs and cron session IDs
  - `tools/code_execution_tool.py` also was not passing any configured timezone context into the sandboxed child process.
  - This is a good fit for a scoped local helper rather than a repo-wide datetime sweep.
- Local implementation:
  - Added `hermes_time.py` with a cached timezone-aware `now()` helper.
  - Resolution order is `HERMES_TIMEZONE` -> `config.yaml` `timezone` key -> server-local timezone.
  - Added optional `timezone` to `DEFAULT_CONFIG` in `hermes_cli/config.py` without forcing a broader migration pass.
  - Updated `run_agent.py` to use the shared helper for the conversation-start timestamp in the system prompt.
  - Updated `cron/jobs.py` and `cron/scheduler.py` to use the shared helper for schedule computation, persisted timestamps, human-readable run times, and cron session IDs.
  - Normalized parsed cron timestamps so naive ISO timestamps are attached to the configured/local timezone before comparison.
  - Updated `tools/code_execution_tool.py` to pass `HERMES_TIMEZONE` and `TZ` into the sandbox child environment when a timezone is configured.
- Verification:
  - `python -m py_compile hermes_time.py run_agent.py cron/jobs.py cron/scheduler.py tools/code_execution_tool.py hermes_cli/config.py`
- Quick test path:
  - Set `timezone: America/Denver` in `~/.hermes/config.yaml`.
  - Run `hermes chat -q "what time does Hermes think it is?"` and confirm the prompt-derived time aligns with that timezone.
  - Create a cron job like `run once in 30m` and confirm the stored/displayed run time aligns with the configured timezone.
  - Run a cron job and confirm the output document `Run Time` reflects the configured timezone.
  - Use `execute_code` with a tiny script that prints local time and confirm it reflects the configured timezone instead of raw host-default behavior.
- Test policy note:
  - No upstream tests were copied.

### PR #604

- Title: `fix(tests): isolate max_turns tests from CI env and update default to 90`
- Status: Skipped, test-only upstream PR.
- Decision: Skip.
- Why:
  - The upstream merge only changes `tests/test_cli_init.py`.
  - It does not modify runtime code; it just updates test expectations after upstream changed the default max turns from 60 to 90.
  - Under fork policy, we do not copy upstream tests or CI test content.
- Quick test path:
  - No runtime verification needed.
  - Sanity-check that we intentionally did not import any upstream `tests/` changes.
- Test policy note:
  - No upstream tests were copied.

### PR #573

- Title: `fix(doctor): detect OpenAI custom endpoint env settings`
- Status: Integrated locally.
- Decision: Take, implemented fork-natively.
- Why:
  - `hermes doctor` still used a narrow env scan in the configuration-files section and only treated `OPENROUTER_API_KEY` or `ANTHROPIC_API_KEY` as evidence that provider configuration existed.
  - That produced misleading warnings for valid custom OpenAI-compatible setups using `OPENAI_API_KEY` plus `OPENAI_BASE_URL`.
  - The runtime provider logic was already correct; the stale piece was doctor’s env/config detection.
- Local implementation:
  - Added `_PROVIDER_ENV_HINTS` and `_has_provider_env_config(...)` to `hermes_cli/doctor.py`.
  - Expanded the provider/env hints to include `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and the alternate provider keys already relevant in this fork.
  - Updated the `~/.hermes/.env` configuration-files check to report `API key or custom endpoint configured` when any supported provider auth/base-URL settings are present.
  - Left the OpenRouter connectivity probe unchanged; this patch only fixes environment/config detection.
- Verification:
  - `python -m py_compile hermes_cli/doctor.py`
- Quick test path:
  - Put only `OPENAI_API_KEY` and `OPENAI_BASE_URL` in `~/.hermes/.env`.
  - Run `hermes doctor`.
  - Confirm the configuration-files section reports that an API key or custom endpoint is configured instead of warning that no API key was found.
  - Sanity-check that existing OpenRouter and Anthropic setups still show as configured too.
- Test policy note:
  - No upstream tests were copied.

### PR #575

- Title: `fix(setup): prevent OpenRouter model list fallback for Nous provider`
- Status: Integrated locally.
- Decision: Take, implemented fork-natively.
- Why:
  - The bug is still present in the current setup flow in `hermes_cli/setup.py`.
  - If the user selects `Nous Portal`, login succeeds, but fetching `nous_models` fails or returns an empty list, the model-selection step falls through to the generic static model picker.
  - That fallback picker is the OpenRouter model list from `hermes_cli/models.py`, which is the wrong UX for a Nous provider flow.
- Local implementation:
  - Add an explicit `elif selected_provider == "nous":` branch immediately after the successful `if selected_provider == "nous" and nous_models:` path.
  - In that branch, warn that Nous model discovery failed, prompt for a manual Nous model name, and allow Enter to keep the current model.
  - Only save `LLM_MODEL` if the user actually enters a replacement value.
  - Leave the generic/OpenRouter static model picker only for actual OpenRouter or other non-Nous cases.
- Verification:
  - `python -m py_compile hermes_cli/setup.py`
- Quick test path:
  - Run `hermes setup`.
  - Choose `Nous Portal`.
  - Simulate or force a case where login succeeds but model fetch fails or returns no models.
  - Confirm setup prompts for a manual Nous model name instead of showing the OpenRouter static model list.
  - Hit Enter without typing a model and confirm the current model is preserved.
- Test policy note:
  - No upstream tests were copied.

### PR #614

- Title: `fix: resolve systemd restart loop with --replace flag`
- Status: Integrated locally.
- Decision: Take, implemented fork-natively.
- Why:
  - The local fork is still missing the whole `--replace` flow for `hermes gateway run`.
  - `gateway/run.py` still exposes `start_gateway(config: Optional[GatewayConfig] = None) -> bool` with only the existing duplicate-instance guard.
  - `hermes_cli/main.py` does not expose a `--replace` flag for `gateway run`.
  - `hermes_cli/gateway.py` still generates a systemd unit with plain `ExecStart=... gateway run`, so a stale pid file or slow shutdown can still wedge the service into a restart loop.
- Local implementation:
  - Added `replace: bool = False` to `gateway.run.start_gateway(...)`.
  - When `replace=True` and another gateway PID is detected, the new process sends SIGTERM, waits briefly, escalates if needed, and clears the pid file before continuing.
  - Added `--replace` to `hermes gateway run` in `hermes_cli/main.py`.
  - Threaded the flag through `hermes_cli/gateway.py` so `run_gateway(..., replace=...)` passes it into `start_gateway(...)`.
  - Updated the generated systemd unit to use `gateway run --replace`, plus `ExecStop`, `KillMode`, `KillSignal`, and `TimeoutStopSec` for more reliable service management.
  - Preserved the existing duplicate-instance guard behavior for normal runs that do not use `--replace`.
- Verification:
  - `python -m py_compile gateway/run.py hermes_cli/gateway.py hermes_cli/main.py`
- Quick test path:
  - Install or inspect the generated systemd unit and confirm `ExecStart` includes `gateway run --replace`.
  - Start the gateway, then simulate a stale or still-shutting-down previous instance.
  - Run `hermes gateway run --replace` and confirm the old process is terminated and the new instance starts cleanly.
  - Restart the systemd user service and confirm it does not get stuck in a restart loop because of the duplicate-instance guard.
- Test policy note:
  - No upstream tests were copied.

### PR #620

- Title: `fix: restore missing MIT license file`
- Status: Integrated locally.
- Decision: Take, implemented as a direct local restore.
- Why:
  - The upstream merge itself is a simple repository/legal-file restore: a root `LICENSE` file with the MIT license text.
  - The local fork currently does not have a root `LICENSE` file.
  - This is not a runtime fix, but it is still worth taking because it restores an expected top-level project/legal file without affecting fork behavior.
- Local implementation:
  - Add a root `LICENSE` file with the MIT license text matching the upstream restoration.
  - Do not bundle any unrelated changes that happened near this merge in upstream history.
- Verification:
  - Confirmed root `LICENSE` file exists after restore.
- Quick test path:
  - Confirm a top-level `LICENSE` file exists at the repository root.
  - Open it and confirm it contains the MIT license text.
- Test policy note:
  - No upstream tests were copied.

### PR #629

- Title: `feat: add Polymarket prediction market skill (read-only)`
- Status: Integrated locally.
- Decision: Optional take, implemented fork-natively.
- Why:
  - The local fork does not currently have the Polymarket skill.
  - Upstream adds a self-contained read-only bundled skill under `skills/market-data/polymarket/` with:
    - `SKILL.md`
    - `references/api-endpoints.md`
    - `scripts/polymarket.py`
  - It is a content/skill addition, not a runtime bugfix.
  - The implementation is relatively low-risk because it uses public read-only APIs and no extra authentication, but it still increases bundled skill surface area and maintenance.
- Local implementation:
  - Added the bundled skill under `skills/market-data/polymarket/`:
    - `SKILL.md`
    - `references/api-endpoints.md`
    - `scripts/polymarket.py`
  - Kept it read-only and dependency-light, using only the Python standard library.
  - Polished the helper script usage text for local portability so it uses `python` examples instead of assuming `python3`.
  - Did not bundle any unrelated upstream changes.
- Verification:
  - `python -m py_compile skills/market-data/polymarket/scripts/polymarket.py`
- Quick test path:
  - Confirm the `polymarket` skill is discoverable in local skill listings.
  - Invoke the skill for a simple market query and confirm it guides the agent toward the bundled script/reference flow.
  - Run `skills/market-data/polymarket/scripts/polymarket.py search "bitcoin"` and confirm it can fetch public Polymarket results.
- Test policy note:
  - No upstream tests were copied.

### PR #178

- Title: `fix(install): ignore commented lines when checking for PATH`
- Status: Skipped, already functionally covered.
- Decision: Skip.
- Why:
  - Upstream `#178` is a one-line installer fix in `scripts/install.sh`: ignore commented lines when checking whether `~/.local/bin` is already on PATH.
  - The current local `scripts/install.sh` already has that exact behavior:
    - it filters out commented lines
    - then checks for a real `PATH=.*\.local/bin` entry before deciding whether to append
  - `setup-hermes.sh` still uses a simpler `grep '\.local/bin'` check, but that is outside the literal upstream PR scope and should be treated as a separate local cleanup if we want to address it later.
- Quick test path:
  - In a shell config file used by `scripts/install.sh`, add a commented line mentioning `~/.local/bin`.
  - Run the installer path that performs PATH setup.
  - Confirm it does not mistake the commented line for a real PATH entry and still appends the export when needed.
- Test policy note:
  - No upstream tests were copied.

### PR #174

- Title: `fix: strip <think> blocks from final response to users`
- Status: Skipped, already functionally covered.
- Decision: Skip.
- Why:
  - The current fork already strips `<think>...</think>` blocks from user-facing responses in the normal final-response path in `run_agent.py`.
  - The fallback path that upstream `#174` also touched is already covered locally as well: fallback content is stripped before being surfaced to the user.
  - We also previously integrated the related retry-summary empty-after-think fix (`#438`), so the current think-block handling is already ahead of this older upstream patch.
- Quick test path:
  - Trigger a response that contains visible text plus a `<think>...</think>` block and confirm the user only sees the visible text.
  - Trigger a fallback/retry path that includes `<think>...</think>` content and confirm the user-facing fallback text also has the think block removed.
- Test policy note:
  - No upstream tests were copied.

### PR #176

- Title: `fix(gateway): prevent TTS voice messages from accumulating across turns`
- Status: Skipped, already functionally covered.
- Decision: Skip.
- Why:
  - Upstream `#176` fixes repeated TTS/media attachment replay by tracking the history length before `run_conversation()` and scanning only the current turn's new messages for `MEDIA:` tags.
  - The current fork already has a stronger fork-native solution in `gateway/run.py`:
    - it pre-collects `_history_media_paths` from the loaded conversation history before the new run
    - then scans result tool messages and only re-attaches `MEDIA:` tags whose paths were not already present in prior history
  - That path-based dedupe avoids the same repeated TTS attachment bug and is safer than relying purely on message-index slicing when history can be compressed or rewritten.
  - The current code also caps multiple audio attachments to the most recent one, which is additional protection against TTS floods.
- Quick test path:
  - In a gateway conversation, trigger a TTS response that produces a media attachment.
  - Send a follow-up text-only message in the same session.
  - Confirm the old voice/audio attachment is not re-attached to the later reply.
  - If possible, trigger multiple TTS outputs in one turn and confirm only the most recent audio attachment is delivered.
- Test policy note:
  - No upstream tests were copied.

### PR #43

- Title: `Enable ChatGPT subscription Codex support end-to-end`
- Status: Skipped, already functionally covered.
- Decision: Skip.
- Why:
  - This upstream merge is the large Codex-provider feature train: runtime provider resolution, Codex auth, Codex model discovery, Responses API handling, CLI/setup/status/doctor integration, and child-agent inheritance.
  - The current fork already contains the substantive pieces of that work:
    - `hermes_cli/auth.py` has Codex auth storage, refresh, recovery, and status
    - `hermes_cli/runtime_provider.py` resolves `openai-codex`
    - `hermes_cli/codex_models.py` is present
    - `run_agent.py` supports `codex_responses`, refresh on 401, and the Responses API tool/reasoning flow
    - `cli.py`, `hermes_cli/main.py`, `hermes_cli/setup.py`, `hermes_cli/status.py`, and `hermes_cli/doctor.py` already surface Codex as a provider
    - `tools/delegate_tool.py` already passes provider/api_mode/runtime auth through to child agents
  - The runtime feature set was already present in substance, but a follow-up audit found a re-auth UX gap:
    - `run_agent.py` already refreshes Codex credentials on `401`
    - auth internals already told users to run `hermes login`
    - but `hermes_cli/auth.py` still implemented `login_command()` as a removed/deprecated stub
    - and `hermes_cli/status.py` / `hermes_cli/setup.py` still pointed users at `hermes model`
  - We fixed that local gap by restoring `hermes login` as the official OAuth re-auth path for Nous and OpenAI Codex, and aligned the surrounding user guidance to point to `hermes login` consistently.
- Local implementation:
  - Updated `hermes_cli/auth.py` so `login_command()` dispatches to `_login_nous(...)` or `_login_openai_codex(...)` instead of exiting as deprecated.
  - Updated `hermes_cli/status.py` to show `run: hermes login` for logged-out Nous and Codex auth state.
  - Updated `hermes_cli/setup.py` fallback guidance to suggest `hermes login` after cancelled or failed OAuth setup.
  - Updated `hermes_cli/main.py` help text so `hermes login` defaults to the active OAuth provider, otherwise Nous.
  - Updated `README.md` troubleshooting text to document `hermes login` as the re-auth path.
- Verification:
  - `python -m py_compile hermes_cli/auth.py hermes_cli/status.py hermes_cli/setup.py hermes_cli/main.py`
- Quick test path:
  - Run `hermes login --provider openai-codex` and confirm the Codex device-code flow starts instead of a deprecated-command message.
  - Run `hermes login --provider nous` and confirm the Nous OAuth flow starts.
  - Trigger a logged-out Codex or Nous state and confirm `hermes status` points to `hermes login`, not `hermes model`.
  - Confirm a Codex-backed session still refreshes credentials automatically on `401`.
  - Confirm delegated child agents still inherit Codex runtime credentials when the parent session is using Codex.
- Test policy note:
  - No upstream tests were copied.

### PR #193

- Title: `add unit tests for 5 security/logic-critical modules (batch 4)`
- Status: Skipped, test-only upstream PR.
- Decision: Skip.
- Why:
  - Upstream `#193` adds only test coverage:
    - `tests/agent/test_auxiliary_client.py`
    - `tests/gateway/test_pairing.py`
    - `tests/honcho_integration/test_session.py`
    - `tests/tools/test_skill_manager_tool.py`
    - `tests/tools/test_skills_tool.py`
  - There are no runtime code changes to port.
  - Under the local integration policy, we never copy upstream `tests/` or CI test content.
- Quick test path:
  - No runtime verification is needed because the upstream merge is test-only.
  - Sanity-check that no upstream `tests/` files were imported locally.
- Test policy note:
  - No upstream tests were copied.

### PR #460

- Title: `feat(tools): add support for self-hosted firecrawl`
- Status: Skipped, already functionally covered.
- Decision: Skip.
- Why:
  - The runtime feature from upstream `#460` is already present locally in `tools/web_tools.py`.
  - The local web tools already:
    - read `FIRECRAWL_API_URL`
    - allow operation when either `FIRECRAWL_API_KEY` or `FIRECRAWL_API_URL` is configured
    - instantiate the Firecrawl client against a self-hosted base URL when provided
  - `check_firecrawl_api_key()` already treats self-hosted Firecrawl as configured, so tool discovery does not require the cloud API key specifically.
  - This means the substantive upstream capability is already absorbed in the fork.
  - One small UX nuance remains outside the core feature scope: setup/status still present Firecrawl primarily as a cloud-key-backed integration, but that does not block self-hosted runtime support.
- Quick test path:
  - Set only `FIRECRAWL_API_URL` in `~/.hermes/.env` and leave `FIRECRAWL_API_KEY` unset.
  - Start Hermes and confirm `web_search` / `web_extract` are still available.
  - Run a simple `web_search` or `web_extract` request and confirm the Firecrawl client targets the configured self-hosted base URL.
- Test policy note:
  - No upstream tests were copied.

### PR #436

- Title: `fix: use _max_tokens_param in max-iterations retry path`
- Status: Integrated locally.
- Decision: Integrate.
- Why:
  - The upstream bug is still present locally in `run_agent.py`.
  - In `_handle_max_iterations(...)`, the first non-Codex summary request already does:
    - `summary_kwargs.update(self._max_tokens_param(self.max_tokens))`
  - But the retry branch still hardcodes:
    - `summary_kwargs["max_tokens"] = self.max_tokens`
  - That means direct OpenAI-compatible paths that expect `max_completion_tokens` can still fail or behave incorrectly during the retry summary step after max-iterations exhaustion.
  - This is a real local runtime gap, not just a test difference.
- Proposal:
  - Update the retry summary branch in `run_agent.py` to use `summary_kwargs.update(self._max_tokens_param(self.max_tokens))` instead of hardcoding `max_tokens`.
  - Keep the rest of the retry-summary behavior unchanged.
  - Continue skipping the upstream tests that accompanied this PR.
- Local implementation:
  - Updated the non-Codex retry summary branch in `run_agent.py` so it now uses `_max_tokens_param(self.max_tokens)` just like the first summary attempt.
- Verification:
  - `python -m py_compile run_agent.py`
- Quick test path:
  - Use a direct OpenAI-compatible provider path that requires `max_completion_tokens`.
  - Force the agent into the max-iterations summary fallback.
  - Confirm both the first summary attempt and the retry summary attempt succeed without a parameter-name error.
  - Sanity-check that OpenRouter and Codex paths still behave the same.
- Test policy note:
  - No upstream tests were copied.

### PR #298

- Title: `Make process_registry checkpoint writes atomic`
- Status: Integrated locally.
- Decision: Integrate.
- Why:
  - This is a real local gap in `tools/process_registry.py`.
  - `_write_checkpoint()` still writes directly to `~/.hermes/processes.json` with `CHECKPOINT_PATH.write_text(...)`, which can leave a truncated or corrupted checkpoint file if Hermes crashes during the write.
  - `recover_from_checkpoint()` also clears the checkpoint with another direct `write_text("[]", ...)` call.
  - The current error handling is also weaker than ideal:
    - `_write_checkpoint()` still swallows exceptions with bare `pass`
    - checkpoint read failures in recovery are silently ignored
  - This is the same durability class of issue we already fixed locally for `batch_runner`, so the local codebase would benefit from making these checkpoint paths consistent.
- Proposal:
  - Add a small atomic JSON write helper in `tools/process_registry.py` using a temp file, flush, `os.fsync`, and `os.replace`.
  - Use that helper for both `_write_checkpoint()` and the “clear checkpoint after recovery” path.
  - Replace the bare `pass` and silent recovery-read failure with `logger.debug(..., exc_info=True)` so failures stay non-fatal but are diagnosable.
  - Keep the rest of the checkpoint/recovery behavior unchanged.
- Local implementation:
  - Added an atomic checkpoint JSON write helper in `tools/process_registry.py` using `tempfile`, flush, `os.fsync`, and `os.replace`.
  - Updated `_write_checkpoint()` to use the helper instead of direct `write_text(...)`.
  - Updated `recover_from_checkpoint()` to use the same helper when clearing the checkpoint after recovery.
  - Replaced the bare `pass` and silent recovery-read failure with `logger.debug(..., exc_info=True)` so checkpoint issues remain non-fatal but diagnosable.
- Verification:
  - `python -m py_compile tools/process_registry.py`
- Quick test path:
  - Start one or more background processes so `~/.hermes/processes.json` is written.
  - Simulate interruption or repeated writes while the checkpoint is being updated.
  - Confirm `processes.json` remains valid JSON after the write path runs.
  - Restart Hermes and confirm `recover_from_checkpoint()` can still recover detached processes and then clear the checkpoint cleanly.
- Test policy note:
  - No upstream tests were copied.

### PR #654

- Title: `feat: git worktree isolation for parallel CLI sessions (--worktree / -w)`
- Status: Integrated locally in a conservative opt-in shape.
- Decision: Integrate scoped local version.
- Why:
  - The fork does not currently have any `--worktree` / `-w` CLI option or git-worktree session isolation flow.
  - Upstream `#654` is a substantial CLI feature, centered mostly in `cli.py` plus a small flag surface in `hermes_cli/main.py`.
  - The feature is useful for users who want multiple Hermes CLI sessions operating in the same repository without colliding, but it also introduces non-trivial Git behavior:
    - creating and naming worktrees
    - choosing worktree locations
    - handling cleanup on exit / crash
    - interacting with existing uncommitted changes
    - Windows path/process edge cases
  - Because this changes local Git workflow rather than fixing a runtime correctness bug, it should be treated as a deliberate fork feature choice instead of an automatic sync.
- Local implementation:
  - Added `--worktree` / `-w` to the top-level CLI and `chat` subcommand in `hermes_cli/main.py`.
  - Added a scoped worktree helper in `cli.py` that:
    - requires running inside a Git repository
    - auto-creates a detached sibling worktree under `.hermes-worktrees/`
    - only activates when `--worktree` is explicitly passed
    - switches the CLI session into that worktree and updates `TERMINAL_CWD`
  - Kept the feature conservative:
    - `--worktree` is fresh-session-only and is rejected with `--resume` / `--continue`
    - `--worktree` is currently limited to the local terminal backend
    - cleanup is manual rather than automatic, and the exit summary prints the removal command
  - Website docs and upstream tests were intentionally not ported.
- Verification:
  - `python -m py_compile cli.py hermes_cli/main.py`
- Quick test path:
  - In a Git repo, start two Hermes CLI sessions with `--worktree`.
  - Confirm each session gets an isolated worktree and can edit files without colliding in the same checkout.
  - Confirm `--worktree` is rejected with `--resume` / `--continue`.
  - Exit a worktree-backed session and confirm the summary shows the created worktree path and the `git worktree remove ...` command.
  - Confirm cleanup/removal works cleanly on Windows as well as non-Windows environments.
- Test policy note:
  - No upstream tests were copied.

### PR #635

- Title: `fix: add Kimi Code API support (api.kimi.com/coding/v1)`
- Status: Integrated locally.
- Decision: Integrate.
- Why:
  - This is a real local provider-integration gap.
  - Upstream `#635` adds first-class Kimi API-key provider support, including the important base-URL distinction between:
    - `sk-kimi-...` keys, which must target `https://api.kimi.com/coding/v1`
    - older Moonshot keys, which continue to use the legacy Moonshot API base URL unless the user explicitly overrides it
  - The current fork does not yet have that Kimi provider registration or key-prefix-based base URL detection in `hermes_cli/auth.py`.
  - The fork does already have some nearby pieces:
    - `README.md` and parser docs reference Kimi-family models
    - `hermes_cli/runtime_provider.py` already has a generic API-key-provider path
  - But without the provider registration and routing logic, Kimi Code is not actually available as a supported first-class provider in the local auth/runtime flow.
- Proposal:
  - Add `kimi-coding` as an API-key provider in `hermes_cli/auth.py`, using the upstream behavior as the model.
  - Add local key-prefix-aware base URL resolution:
    - `sk-kimi-...` keys default to `https://api.kimi.com/coding/v1`
    - legacy Moonshot-style keys default to the existing Moonshot API base URL
    - an explicit `KIMI_BASE_URL` override still wins
  - Thread the provider through local provider selection/status/runtime resolution surfaces without broadening the change beyond Kimi support.
  - Update env/config metadata so the provider is discoverable in setup/status/docs.
  - Continue skipping upstream tests.
- Local implementation:
  - Added `kimi-coding` as a first-class API-key provider in `hermes_cli/auth.py`.
  - Added key-prefix-aware base URL resolution:
    - `sk-kimi-...` keys default to `https://api.kimi.com/coding/v1`
    - legacy Moonshot keys default to `https://api.moonshot.ai/v1`
    - `KIMI_BASE_URL` overrides both
  - Added API-key-provider credential/status helpers in `hermes_cli/auth.py` so the generic runtime provider path can resolve Kimi cleanly.
  - Added Kimi to the interactive provider picker in `hermes_cli/main.py` with a simple manual model flow.
  - Added `kimi-coding` to the `--provider` choices for CLI chat.
  - Added Kimi visibility/metadata in `hermes_cli/status.py`, `hermes_cli/config.py`, `.env.example`, and `README.md`.
- Verification:
  - `python -m py_compile hermes_cli/auth.py hermes_cli/main.py hermes_cli/status.py hermes_cli/config.py hermes_cli/runtime_provider.py`
- Quick test path:
  - Set `KIMI_API_KEY` to a `sk-kimi-...` key with no `KIMI_BASE_URL`.
  - Run Hermes with the Kimi provider and confirm it targets `https://api.kimi.com/coding/v1`.
  - Then set a legacy Moonshot-style key and confirm Hermes uses the legacy Moonshot base URL by default.
  - Set `KIMI_BASE_URL` explicitly and confirm it overrides both defaults.
- Test policy note:
  - No upstream tests were copied.

### PR #657

- Title: `feat: browser screenshot sharing via MEDIA: on all messaging platforms`
- Status: Integrated locally.
- Decision: Integrate.
- Why:
  - This is a real local gap in the browser-to-messaging flow.
  - The current fork already has the downstream delivery pipeline:
    - `gateway/run.py` already scans tool output and final responses for `MEDIA:<path>` tags
    - the messaging platforms already know how to deliver those media attachments
  - But `tools/browser_tool.py` still uses a temp screenshot path inside `browser_vision(...)`, returns only the text analysis, and then deletes the screenshot in `finally`.
  - So browser screenshots are not currently shareable with users through the existing media pipeline, even though the gateway side is ready for them.
- Proposal:
  - Update `browser_vision(...)` in `tools/browser_tool.py` to save screenshots in a persistent Hermes-owned location instead of a temp file.
  - Return `screenshot_path` in the tool result JSON so the model can echo it as `MEDIA:<path>` when it wants to share the screenshot with the user.
  - Add lightweight cleanup for stale browser screenshots so the cache does not grow without bound.
  - Keep the change scoped to `browser_vision` and the existing MEDIA-tag pipeline; do not introduce a new sharing protocol.
- Local implementation:
  - Updated `browser_vision(...)` in `tools/browser_tool.py` to save screenshots under `~/.hermes/browser_screenshots/` instead of using temp-file-only storage.
  - Added stale screenshot pruning so old browser screenshots are cleaned up over time.
  - Updated the tool result JSON to include `screenshot_path` so the model can share it via the existing `MEDIA:<path>` pipeline.
  - If the browser backend writes the screenshot to a different file than requested, the local implementation now copies it into the persistent Hermes screenshot path before returning.
- Verification:
  - `python -m py_compile tools/browser_tool.py`
- Quick test path:
  - Run `browser_vision` on a page with visible content.
  - Confirm the returned JSON includes a persistent `screenshot_path`.
  - In a gateway chat, have Hermes share that screenshot by echoing `MEDIA:<screenshot_path>` and confirm the image is delivered natively on the messaging platform.
  - Confirm old screenshots are pruned over time and not immediately deleted at the end of the tool call.
- Test policy note:
  - No upstream tests were copied.

### PR #659

- Title: `feat: skill prerequisites — hide skills with unmet runtime dependencies`
- Status: Skipped, upstream feature was later reverted.
- Decision: Skip.
- Why:
  - Upstream `#659` added a skill-frontmatter `prerequisites` feature and hid skills with unmet env-var or command requirements from `skills_list`.
  - Upstream later reverted that behavior in `#685` (`Revert "feat: skill prerequisites — hide skills with unmet runtime dependencies"`).
  - The current fork does not have the `#659` prerequisite-hiding behavior, which aligns with upstream’s later decision to back it out.
  - Because the feature was explicitly reverted upstream and is not needed for local correctness, we should not resurrect it here as part of the sync pass.
- Quick test path:
  - No runtime integration test needed because we are intentionally not taking the reverted feature.
  - If revisited later as a fork-local idea, it should be treated as a fresh design decision rather than an upstream sync item.
- Test policy note:
  - No upstream tests were copied.

### PR #648

- Title: `test: add regression coverage for compressor tool-call boundaries`
- Status: Skipped, test-only upstream PR.
- Decision: Skip.
- Why:
  - Upstream `#648` only adds regression coverage for the context compressor boundary behavior.
  - The merge touches only `tests/agent/test_context_compressor.py` and does not change runtime code.
  - Under the fork policy, upstream `tests/` content is never imported, even when the covered behavior is relevant.
- Quick test path:
  - No runtime integration test is needed here because we are intentionally not taking the upstream test-only change.
  - If we want extra local confidence in compressor boundary behavior later, we should add fork-native manual checks or local tests rather than copying upstream coverage.
- Test policy note:
  - No upstream tests were copied.

### PR #685

- Title: `Revert "feat: skill prerequisites — hide skills with unmet runtime dependencies"`
- Status: Skipped, revert of an upstream feature we already skipped.
- Decision: Skip.
- Why:
  - Upstream `#685` explicitly reverts `#659`.
  - We already skipped `#659` locally because the feature was later backed out upstream and did not fix a local correctness issue.
  - Since the fork never adopted the prerequisite-hiding behavior in the first place, there is nothing to revert here.
- Quick test path:
  - No runtime integration test is needed because we intentionally skipped the original feature and therefore have no corresponding behavior to undo.
  - Sanity-check that skills continue to be listed without prerequisite-based hiding logic.
- Test policy note:
  - No upstream tests were copied.

### PR #1440

- Title: `fix: handle dict tool call arguments from local backends`
- Status: Integrated locally.
- Decision: Integrate.
- Why:
  - This is a real local runtime gap in `run_agent.py`.
  - Upstream’s fix is small and targeted: some OpenAI-compatible local backends can return `tool_call.function.arguments` as a dict or list instead of a JSON string.
  - Our current local validation/repair loop still assumes `arguments` is string-shaped and does `if not args or not args.strip():` before JSON validation.
  - That means dict/list arguments can still throw before dispatch even though later parts of the fork already tolerate normalized dict args in other paths.
  - The upstream merge also included tests, but we will not take those under the fork policy.
- Local implementation:
  - Updated the invalid-JSON repair loop in `run_agent.py` to normalize tool-call arguments before any string operations.
  - If `arguments` is a `dict` or `list`, the local implementation now stores it as `json.dumps(arguments, ensure_ascii=False)`.
  - If `arguments` is non-`None` and not already a string, it is coerced with `str(...)`.
  - The existing empty-string handling, JSON validation, and terminal-specific repair logic were left unchanged.
- Verification:
  - `python -m py_compile run_agent.py`
- Quick test path:
  - Use a local OpenAI-compatible backend that returns tool-call arguments as a dict.
  - Trigger a tool call and confirm Hermes reaches dispatch instead of failing in the invalid-JSON validation loop.
  - Sanity-check that normal string JSON arguments still behave the same way.
- Test policy note:
  - No upstream tests were copied.

### PR #1437

- Title: `fix: preserve thread context for cronjob deliver=origin`
- Status: Integrated locally.
- Decision: Integrate.
- Why:
  - This is a real local gateway/cron integration gap.
  - The fork already tracks `thread_id` in `gateway.session.SessionSource`, and platform adapters already populate it where supported.
  - But the cron origin handoff still only records `HERMES_SESSION_PLATFORM`, `HERMES_SESSION_CHAT_ID`, and `HERMES_SESSION_CHAT_NAME`.
  - `gateway/run.py` does not currently export `HERMES_SESSION_THREAD_ID`, and `tools/cronjob_tools.py` does not include thread metadata in the saved origin block.
  - That means cron jobs created from threaded contexts can lose their thread destination when later delivered with `deliver=origin`.
  - Upstream also added tests, but we will not take those under the fork policy.
- Local implementation:
  - Updated `_set_session_env()` in `gateway/run.py` to export `HERMES_SESSION_THREAD_ID` when the current session source has a thread identifier.
  - Updated `_clear_session_env()` to clear `HERMES_SESSION_THREAD_ID` along with the existing session env variables.
  - Updated `tools/cronjob_tools.py` so the saved `origin` block includes `thread_id` from `HERMES_SESSION_THREAD_ID` when available.
  - Kept the change scoped to the cron origin/session-env bridge and left the broader delivery system untouched.
- Verification:
  - `python -m py_compile gateway/run.py tools/cronjob_tools.py`
- Quick test path:
  - Create a cron job from inside a threaded conversation, forum topic, or Slack/Discord thread.
  - Confirm the saved job origin includes the thread identifier.
  - Trigger the job with `deliver=origin` and confirm the output goes back into the original thread instead of the parent channel only.
- Test policy note:
  - No upstream tests were copied.

### PR #1434

- Title: `fix(config): reload .env over stale shell overrides`
- Status: Integrated locally.
- Decision: Integrate.
- Why:
  - This is a real local config/env precedence gap.
  - The intended behavior is that the user-managed `~/.hermes/.env` should win over stale shell-exported values when Hermes starts, while the project `.env` should remain only a dev fallback.
  - Our current fork is inconsistent across entrypoints:
    - `run_agent.py` still loads `~/.hermes/.env` through `load_dotenv_with_fallback(...)` with the default `override=False`
    - `cli.py` still uses direct `load_dotenv(...)` calls without override and without the shared fallback loader
    - `hermes_cli/main.py` and `gateway/run.py` are closer, but the startup behavior is not yet unified
  - That means a stale parent-shell export can still override the user’s saved Hermes config in some entrypaths after restart.
  - Upstream also added tests, but we will not take those under the fork policy.
- Local implementation:
  - Added `load_hermes_dotenv(...)` to `hermes_cli/env_loader.py` as the shared entrypoint helper, built on `agent.env_loader.load_dotenv_with_fallback(...)`.
  - The helper now loads `~/.hermes/.env` with `override=True`.
  - The repo/project `.env` remains a fallback:
    - if user `.env` exists, project `.env` loads with `override=False`
    - if no user `.env` exists, project `.env` loads with `override=True`
  - Switched the main entrypoints to that shared helper:
    - `cli.py`
    - `run_agent.py`
    - `hermes_cli/main.py`
    - `gateway/run.py`
  - Kept the change scoped to startup env loading while preserving the current UTF-8/fallback decode path and existing gateway reload behavior.
- Verification:
  - `python -m py_compile hermes_cli/env_loader.py cli.py run_agent.py gateway/run.py hermes_cli/main.py`
- Quick test path:
  - Export a stale provider key in the shell environment.
  - Put a different value for the same key in `~/.hermes/.env`.
  - Start Hermes through `hermes`, `python cli.py`, and a direct `run_agent.py` path.
  - Confirm the value from `~/.hermes/.env` wins in each case.
  - Sanity-check that when `~/.hermes/.env` is absent, the project `.env` still works as a dev fallback.
- Test policy note:
  - No upstream tests were copied.

### PR #1429

- Title: `fix(voice): Discord voice channel reliability fixes`
- Status: Skipped after deeper inspection; upstream feature surface is not present locally.
- Decision: Skip for now.
- Why:
  - The initial evaluation overestimated how much of upstream’s Discord voice-channel stack exists in this fork.
  - After checking the local code directly, the fork does not currently expose the upstream feature surface that `#1429` is fixing:
    - no local Discord voice-channel join/listen receiver implementation matching the upstream `VoiceReceiver`
    - no local `_voice_listen_loop` keepalive path
    - no local adapter-owned VC playback path for TTS
  - What the fork *does* have is:
    - Discord audio attachment delivery via `send_voice(...)`
    - the Discord “Listen” button TTS flow that generates audio and sends it back as an attachment in-channel
  - Because the underlying voice-channel feature is not present locally, porting pieces of `#1429` now would mean inventing a partial voice-channel stack rather than integrating an upstream fix.
  - That is broader than this sync pass should be, so the right call is to skip for now.
  - The only locally applicable subset was folded into the scoped CLI voice implementation from `#1299` instead:
    - clearer voice readiness/dependency reporting
    - actual audio-input-device detection for local recording
    - more reliable local Windows playback for generated TTS audio
  - Upstream also added tests, which we will not take.
- Quick test path:
  - No upstream integration test is needed here because the local fork does not currently implement the Discord voice-channel stack that `#1429` targets.
  - Sanity-check that the existing Discord “Listen” button and audio attachment path continue to work unchanged.
- Test policy note:
  - No upstream tests were copied.

### PR #1299

- Title: `fix: salvage PR #327 voice mode onto current main`
- Status: Integrated locally in a scoped fork-native form.
- Decision: Integrate partially as an optional CLI voice feature; defer the broader Discord VC salvage surface.
- Why:
  - Yes, this was missed in the earlier pass, and it is the upstream merge that introduced the Discord voice-mode feature surface that `#1429` later fixes.
  - Upstream `#1299` is not a tiny bugfix. It is the broad voice-mode salvage merge and pulls in:
    - `tools/voice_mode.py`
    - major Discord gateway voice-channel changes in `gateway/platforms/discord.py`
    - gateway voice/TTS/transcription plumbing in `gateway/run.py`
    - supporting changes in `tools/tts_tool.py`, `tools/transcription_tools.py`, and related config/CLI surfaces
  - The merge touched a large runtime surface, not just tests or docs.
  - Our fork does not currently have `tools/voice_mode.py`, nor the upstream-style Discord voice receiver / VC playback stack, which is why `#1429` could not be sensibly integrated on its own.
  - So the right dependency understanding is:
    - `#1299` = missing feature surface
    - `#1429` = later reliability fixes on top of that feature surface
- Local implementation:
  - Added a new fork-native `tools/voice_mode.py` module for optional local CLI voice mode.
  - The local module is intentionally scoped to:
    - push-to-talk audio capture with `sounddevice` + `numpy` when available
    - transcription through the existing `tools.transcription_tools.transcribe_audio(...)` path
    - best-effort local audio playback for generated TTS responses
    - clearer readiness checks, microphone detection, and safer Windows playback behavior
  - Follow-up polish removed extra user setup where possible:
    - OpenAI STT/TTS now falls back to `OPENAI_API_KEY` automatically when `VOICE_TOOLS_OPENAI_KEY` is not set
    - the packaged `cli` extra now includes the local voice dependencies used by the new CLI voice mode
  - Added a new `voice` config section in `hermes_cli/config.py` and the CLI config defaults in `cli.py`:
    - `record_key`
    - `max_recording_seconds`
    - `auto_tts`
  - Added `/voice` to the CLI command surfaces:
    - `hermes_cli/commands.py`
    - local CLI command/completion registry in `cli.py`
  - Wired optional voice mode into `cli.py`:
    - `/voice on|off|tts|status`
    - push-to-talk recording hotkey from config, default `Ctrl+B`
    - transcription queues the recognized text into the normal CLI conversation flow
    - optional automatic TTS playback for final responses when enabled
    - voice-mode prompts request concise conversational replies for spoken interactions
  - Kept the implementation intentionally CLI-only for now.
  - Did not attempt to import the broader upstream Discord voice-channel receiver / playback stack.
- Verification:
  - `python -m py_compile tools/voice_mode.py cli.py hermes_cli/config.py hermes_cli/commands.py tools/transcription_tools.py tools/tts_tool.py`
- Quick test path:
  - Ensure Hermes is installed via the normal setup/update path so the CLI voice deps are present (`setup-hermes.sh` uses `.[all]`, and the `cli` extra now includes them too).
  - Ensure `VOICE_TOOLS_OPENAI_KEY` or `OPENAI_API_KEY` is set and `stt.enabled: true` in `~/.hermes/config.yaml`.
  - Start `hermes`, run `/voice on`, and confirm it reports the configured record key.
  - Press `Ctrl+B` to start recording, speak briefly, then press `Ctrl+B` again to stop.
  - Confirm the transcript is queued as a normal CLI message and Hermes responds.
  - Run `/voice tts` and repeat the flow to confirm final responses attempt local playback.
- Test policy note:
  - No upstream tests were copied.

### PR #1427

- Title: `fix(gateway): cancel active runs during shutdown`
- Status: Integrated locally.
- Decision: Integrate.
- Why:
  - This is a real local gateway shutdown/restart gap.
  - Upstream adds two protections during gateway stop/restart:
    - interrupt any in-flight agents tracked in `GatewayRunner._running_agents`
    - cancel adapter-spawned background message-processing tasks before disconnecting adapters
  - Our current `gateway/run.py` stop path still disconnects adapters directly without first interrupting active agent runs.
  - Our current `gateway/platforms/base.py` still spawns background tasks with bare `asyncio.create_task(...)` and does not track/cancel them on shutdown.
  - That means an old gateway instance can keep processing a message briefly during shutdown/restart, especially around `--replace`, reconnects, or manual stop/start flows.
  - Upstream also adds tests, but we will not take those under the fork policy.
- Proposal:
  - Add background task tracking to `gateway/platforms/base.py` for tasks spawned by `handle_message(...)`.
  - Add `cancel_background_tasks()` to the base adapter and call it from `GatewayRunner.stop()` before adapter disconnect.
  - In `GatewayRunner.stop()`, interrupt any agents still present in `_running_agents` before adapter teardown.
  - Keep the change scoped to shutdown/restart behavior and continue excluding upstream tests.
- Local implementation:
  - Added background task tracking in `gateway/platforms/base.py` for tasks spawned from `handle_message(...)`.
  - Replaced bare `asyncio.create_task(...)` calls with tracked background tasks so the adapter can account for in-flight work.
  - Added `cancel_background_tasks()` to the base adapter, which cancels tracked tasks and clears pending session state during shutdown.
  - Updated `GatewayRunner.stop()` in `gateway/run.py` to:
    - interrupt any still-running agents in `_running_agents`
    - call `adapter.cancel_background_tasks()` before `adapter.disconnect()`
  - Kept the change narrowly focused on shutdown/restart behavior.
- Verification:
  - `python -m py_compile gateway/platforms/base.py gateway/run.py`
- Quick test path:
  - Start the gateway and trigger a long-running message handling flow.
  - While it is still running, stop or restart the gateway, including `hermes gateway run --replace`.
  - Confirm the in-flight run is interrupted and the old gateway instance does not continue processing after shutdown begins.
  - Confirm the new instance starts cleanly without stale task activity from the old process.
- Test policy note:
  - No upstream tests were copied.

### PR #1421

- Title: `fix(tools): preserve MCP toolsets when saving platform tool config`
- Status: Integrated locally.
- Decision: Integrate.
- Why:
  - This is a real local config bug in `hermes_cli/tools_config.py`.
  - Our current `_save_platform_tools(...)` overwrites `config["platform_toolsets"][platform]` with only the checklist’s configurable toolset keys.
  - If a platform already has non-configurable entries there, such as MCP server names/toolsets, those entries get dropped the next time the user saves tool config through `hermes tools`.
  - Upstream’s patch is tightly scoped and preserves existing non-configurable entries while still updating the configurable checklist selection.
  - Upstream also added tests elsewhere, but we will not take those under the fork policy.
- Local implementation:
  - Updated `_save_platform_tools(...)` in `hermes_cli/tools_config.py` to preserve existing `platform_toolsets[platform]` entries that are not part of `CONFIGURABLE_TOOLSETS`.
  - The saved value now merges preserved non-configurable entries with the newly selected configurable toolsets instead of overwriting the whole platform list.
  - Kept the change narrowly scoped to tool-config persistence behavior.
- Verification:
  - `python -m py_compile hermes_cli/tools_config.py`
- Quick test path:
  - Put a platform entry in `~/.hermes/config.yaml` that contains both normal configurable toolsets and an MCP-specific non-configurable entry.
  - Run `hermes tools`, change the configurable selection for that platform, and save.
  - Confirm the MCP/non-configurable entry is still present afterward instead of being dropped.
- Test policy note:
  - No upstream tests were copied.

### PR #1396

- Title: `fix: persist Google OAuth PKCE state for headless setup`
- Status: Integrated locally.
- Decision: Integrate.
- Why:
  - This is a real local bug in the bundled Google Workspace skill setup flow.
  - The upstream merge only touches `skills/productivity/google-workspace/scripts/setup.py` plus tests.
  - Our current local script generates the Google OAuth URL and later exchanges the auth code, but it does not persist the PKCE/session state needed to complete the flow reliably across separate headless/manual steps.
  - In the current local flow, `--auth-url` and `--auth-code` reconstruct separate `Flow(...)` instances without preserving the generated PKCE verifier/state, which can break manual copy-paste setup.
  - Upstream’s patch is tightly scoped:
    - persist pending OAuth state/code_verifier to a small file in `~/.hermes/`
    - reuse that state during `--auth-code`
    - validate returned OAuth state when a full redirect URL is pasted
    - clean up the pending session file on success/revoke
  - Upstream also adds tests, but we will not take those under the fork policy.
- Local implementation:
  - Patched `skills/productivity/google-workspace/scripts/setup.py` to persist pending OAuth PKCE state between `--auth-url` and `--auth-code`.
  - Added a pending OAuth session file under `~/.hermes/` that stores:
    - OAuth state
    - PKCE code verifier
    - redirect URI
  - Updated `--auth-code` handling to:
    - accept either a raw code or a full redirect URL
    - validate the returned OAuth state when present
    - reuse the saved PKCE/code-verifier state for token exchange
  - The pending OAuth session file is now removed after successful auth or revoke.
  - Kept the change narrowly scoped to this bundled skill setup script.
- Verification:
  - `python -m py_compile skills/productivity/google-workspace/scripts/setup.py`
- Quick test path:
  - Run the Google Workspace skill setup script with `--auth-url`.
  - Confirm it writes a pending OAuth session file under `~/.hermes/`.
  - Complete the browser authorization and paste either the raw code or the full redirect URL into `--auth-code`.
  - Confirm token exchange succeeds and the pending OAuth session file is removed.
- Test policy note:
  - No upstream tests were copied.

### PR #1397

- Title: `fix: escape parens and braces in fork bomb regex pattern`
- Status: Integrated in the local dangerous-command pattern shape.
- Decision: Integrated in the local dangerous-command pattern shape.
- Why:
  - This is a tiny but real local gap in `tools/approval.py`.
  - The current fork still has the broken unescaped fork-bomb regex pattern:
    - `r':()\s*{\s*:\s*\|\s*:&\s*}\s*;:'`
  - That pattern does not faithfully match the intended shell fork-bomb syntax and is more brittle than the properly escaped upstream form.
  - Upstream’s fix is narrow and correct:
    - escape the literal parentheses and braces so the dangerous-command detector matches the actual `:(){ :|:& };:` shape reliably
- Local integration notes:
  - Replaced the current fork-bomb regex in `tools/approval.py` with the escaped upstream-safe form.
  - Kept the rest of the dangerous-command pattern table unchanged.
  - Verification:
    - `venv\Scripts\python.exe -m py_compile tools\approval.py`
- Quick test path:
  - Run `detect_dangerous_command(':(){ :|:& };:')` and confirm it now flags the fork-bomb pattern reliably.
  - Sanity-check that the other dangerous-command patterns are unaffected.
- Test policy note:
  - No upstream tests were copied.

### PR #1400

- Title: `fix: harden ClawHub skill search exact matches`
- Status: Integrated in the local ClawHub search-quality shape.
- Decision: Integrated partially in the local ClawHub search-quality shape.
- Why:
  - This is a real local gap in `tools/skills_hub.py`.
  - The current fork’s `ClawHubSource` still uses the older lightweight search path and does not have the upstream exact-match/slug-match/catalog ranking helpers.
  - That means exact skill-name searches can still miss the right ClawHub skill, rank poorly, or return weaker fuzzy matches before the intended result.
  - Upstream’s full patch is broader, but the useful local behavior is:
    - normalize payload/tag shapes
    - score exact and prefix matches more intelligently
    - dedupe results
    - check direct slug candidates for exact multi-word queries
    - use a fuller catalog-backed search before falling back to the lightweight listing API
- Local integration notes:
  - Added the scoped ClawHub helper methods to `tools/skills_hub.py`:
    - tag/payload normalization
    - query term splitting
    - exact/slug-aware search scoring
    - result dedupe/finalization
    - catalog-backed ClawHub search and catalog caching
  - Kept the change limited to the `ClawHubSource` search/inspect path.
  - Verification:
    - `venv\Scripts\python.exe -m py_compile tools\skills_hub.py`
    - `venv\Scripts\python.exe -c "from tools.skills_hub import ClawHubSource, SkillMeta; src=ClawHubSource(); m1=SkillMeta(name='Google Workspace Agent', description='Manage gmail and docs', source='clawhub', identifier='google-workspace-agent', trust_level='community', tags=['google']); m2=SkillMeta(name='Workspace Helper', description='google workspace helper', source='clawhub', identifier='workspace-helper', trust_level='community', tags=['workspace']); print(src._search_score('google workspace', m1) > src._search_score('google workspace', m2)); print(src._finalize_search_results('google workspace', [m2, m1], 5)[0].identifier)"`
- Quick test path:
  - Search ClawHub for an exact multi-word skill name and confirm the intended slug/result comes back first instead of a weaker fuzzy match.
  - Search for a slug-like query and confirm direct slug inspection works when a catalog listing is ambiguous.
  - Sanity-check that generic fuzzy queries still return multiple relevant results.
- Test policy note:
  - No upstream tests were copied.

### PR #1395

- Title: `fix: use description as pattern_key to prevent approval collisions`
- Status: Integrated locally.
- Decision: Integrate.
- Why:
  - This is a real local approval-safety bug in `tools/approval.py`.
  - Our current `detect_dangerous_command(...)` still derives `pattern_key` from the regex text itself.
  - Those regex-derived keys are brittle and can collide or drift in ways that make approvals less precise than the human-facing dangerous-command description.
  - Upstream’s fix switches the canonical approval key to the human-readable `description`, which is more stable and avoids collisions between regex fragments.
  - Upstream also includes a backwards-compatibility layer so existing permanent/session approvals using the old regex-derived keys still continue to work after the key change.
  - Upstream also added tests, but we will not take those under the fork policy.
- Local implementation:
  - Updated `tools/approval.py` so `detect_dangerous_command(...)` now uses the dangerous-command description as the canonical approval key.
  - Added a small alias map that links the new description-based key with the old regex-derived key for each dangerous-command pattern.
  - Updated `is_approved(...)` to accept either the canonical key or any legacy alias, so existing allowlist/session approvals continue to work.
  - Kept the change scoped to approval-key generation and approval-key matching behavior.
- Verification:
  - `python -m py_compile tools/approval.py`
- Quick test path:
  - Trigger two dangerous commands that previously could have shared or collided on a regex-derived approval key.
  - Confirm approvals are tracked by the human-readable dangerous-command description instead.
  - Confirm an existing allowlist/session approval using an old regex-derived key still matches after the change.
- Test policy note:
  - No upstream tests were copied.

### PR #1392

- Title: `fix(discord): preserve native document and video attachment support`
- Status: Integrated locally.
- Decision: Integrate.
- Why:
  - This looks like a real local Discord adapter gap.
  - The upstream patch is tightly scoped to `gateway/platforms/discord.py`.
  - Our current local Discord adapter already overrides native sending for voice and image attachments, but it does not override `send_video(...)` or `send_document(...)`.
  - That means video/document `MEDIA:` attachments can still fall back to the generic base-adapter path instead of being preserved as native Discord file attachments.
  - Upstream’s fix adds:
    - a small `file_name` parameter on the local Discord file-attachment helper
    - native `send_video(...)`
    - native `send_document(...)`
  - Upstream also added tests, but we will not take those under the fork policy.
- Local implementation:
  - Patched `gateway/platforms/discord.py` to add a local Discord file-attachment helper that accepts an optional `file_name`.
  - Added Discord-native `send_video(...)` so video `MEDIA:` attachments stay native on Discord instead of falling back to the generic base-adapter path.
  - Added Discord-native `send_document(...)` so non-image file attachments also stay native on Discord.
  - Kept the change narrowly scoped to Discord attachment delivery behavior.
- Verification:
  - `python -m py_compile gateway/platforms/discord.py`
- Quick test path:
  - Send a response through Discord that includes:
    - a video attachment
    - a non-image document attachment
  - Confirm both arrive as native Discord attachments instead of degrading to plain text/file-path fallback.
  - If a custom filename is supplied for a document, confirm Discord uses it.
- Test policy note:
  - No upstream tests were copied.

### PR #1375

- Title: `feat: add direct endpoint overrides for auxiliary and delegation`
- Status: Integrated in the local config/runtime shape.
- Decision: Integrated partially in the local config/runtime shape.
- Why:
  - This is a real local capability gap.
  - Our fork already supports provider/model overrides for auxiliary tasks and delegation, but it does not yet expose the direct `base_url` / `api_key` override path that upstream added.
  - Upstream’s merge is broader, but the core useful behavior is:
    - auxiliary tasks can target a specific OpenAI-compatible endpoint directly via per-task `base_url` / `api_key`
    - delegation can run subagents against a direct endpoint via `delegation.base_url` / `delegation.api_key`
  - This is useful for self-hosted endpoints and specialized backends without forcing the main runtime model/provider to change.
  - Upstream also added tests and website docs, but we will not take the tests and we only need the local runtime/config surface here.
- Local integration notes:
  - Kept the existing local `delegation.base_url` / `delegation.api_key` direct-endpoint support in place; that path was already present in this fork and did not need a new code patch in this turn.
  - Added fork-native `auxiliary.web_extract` config defaults in `hermes_cli/config.py`, alongside the existing `auxiliary.text` and `auxiliary.vision` blocks, each with optional `provider`, `model`, `base_url`, and `api_key` fields.
  - Patched `agent/auxiliary_client.py` so the centralized Stage 1 router now accepts explicit `base_url` / `api_key` overrides, resolves task-specific auxiliary overrides, and supports env/config-driven direct endpoint routing for `text`, `vision`, and `web_extract`.
  - Added task-specific environment override support for:
    - `AUXILIARY_TEXT_PROVIDER` / `MODEL` / `BASE_URL` / `API_KEY`
    - `AUXILIARY_VISION_PROVIDER` / `MODEL` / `BASE_URL` / `API_KEY`
    - `AUXILIARY_WEB_EXTRACT_PROVIDER` / `MODEL` / `BASE_URL` / `API_KEY`
  - Patched `cli.py` and `gateway/run.py` so those auxiliary task overrides are bridged from config into the runtime environment consistently for both CLI and gateway sessions.
  - Patched `tools/web_tools.py` so the auxiliary client lookup for extraction runs under the explicit `web_extract` task key instead of the generic text task.
  - Verification:
    - `venv\Scripts\python.exe -m py_compile agent\auxiliary_client.py tools\web_tools.py cli.py gateway\run.py hermes_cli\config.py tools\delegate_tool.py`
  - Test policy note:
    - No upstream tests were copied.
- Verification:
  - `python -m py_compile hermes_cli/config.py agent/auxiliary_client.py tools/delegate_tool.py`
- Quick test path:
  - Set an auxiliary task config entry with a direct `base_url` and `api_key`, then trigger that task and confirm it uses the direct endpoint instead of the main model/provider path.
  - Set `delegation.base_url` and `delegation.api_key`, trigger a delegated task, and confirm the child agent uses the delegated endpoint while the parent runtime stays unchanged.
  - Sanity-check that when the new fields are unset, the existing provider/model inheritance behavior is unchanged.
- Test policy note:
  - No upstream tests were copied.

### PR #1405

- Title: `docs: stabilize website diagrams`
- Status: Reviewed.
- Decision: Skip, docs-site-only.
- Why:
  - The merge only touches the upstream website/docs surface:
    - Docusaurus docs pages
    - website CSS
    - SVG docs figures
    - website package metadata
    - a docs-site CI workflow
  - There is no runtime, CLI, gateway, config, tool, or dependency behavior change in the Python application itself.
  - Under the fork sync policy, website-only documentation and CI changes are not something we need to port during this upstream integration pass.
- Quick test path:
  - None needed for the fork runtime, since no application code is being imported.
- Test policy note:
  - No upstream tests were copied.

### PR #1407

- Title: `docs: clarify Slack thread reply behavior`
- Status: Reviewed.
- Decision: Skip, docs-site-only.
- Why:
  - The merge only updates upstream website messaging docs:
    - `website/docs/user-guide/messaging/discord.md`
    - `website/docs/user-guide/messaging/slack.md`
  - It clarifies Discord mention/thread behavior and Slack thread reply behavior, but does not change the Python gateway adapters or CLI/setup/runtime code.
  - Under the current fork sync policy, website-only documentation changes are not imported during this runtime-focused upstream integration pass.
- Quick test path:
  - None needed for the fork runtime, since no application code is being imported.
- Test policy note:
  - No upstream tests were copied.

### PR #1408

- Title: `fix: make Claude image handling work end-to-end`
- Status: Integrated in the local Anthropic runtime shape.
- Decision: Integrated partially in the local Anthropic runtime shape.
- Why:
  - This merge is not wholly missing, but it is not wholly covered either.
  - The Anthropic content-conversion slice is already present locally:
    - `agent/anthropic_adapter.py` already has `_image_source_from_openai_url(...)`
    - it already converts OpenAI-style multimodal content arrays through `_convert_content_to_anthropic(...)`
    - and `convert_messages_to_anthropic(...)` already uses that path for both user and assistant content
  - The remaining real local gap is the end-to-end Anthropic fallback in `run_agent.py`:
    - the current fork does not yet preprocess image-bearing conversation turns into text before building Anthropic API kwargs
    - so image content in history can still reach the Anthropic path in shapes that are not safe or reliable across all message roles
    - upstream solves that by converting image-bearing content into text descriptions via auxiliary vision before the Anthropic API call, with per-run caching to avoid repeated re-analysis
  - There is also a small auxiliary-model follow-up upstream:
    - upstream changes `_CODEX_AUX_MODEL` from `gpt-5.3-codex` to `gpt-5.2-codex`
    - the current fork is already on `gpt-5.4`, so that exact upstream downgrade is not appropriate to transplant blindly here
  - The useful local slice is therefore the Anthropic runtime hardening only, not the exact auxiliary model pin.
- Local integration notes:
  - Left the existing multimodal Anthropic adapter implementation in `agent/anthropic_adapter.py` unchanged, since that upstream slice was already present locally.
  - Patched `run_agent.py` to add a narrow Anthropic image fallback layer:
    - `_content_has_image_parts(...)` to detect image-bearing content arrays
    - `_materialize_data_url_for_vision(...)` to decode data URLs into temporary files for the existing vision tool
    - `_run_async_for_anthropic_fallback(...)` so the async vision tool can be called safely from the synchronous Anthropic preparation path
    - `_describe_image_for_anthropic_fallback(...)` with per-run caching in `self._anthropic_image_fallback_cache`
    - `_preprocess_anthropic_content(...)` and `_prepare_anthropic_messages_for_api(...)` to convert image-bearing message content into text before Anthropic API calls when needed
  - Updated `_build_api_kwargs(...)` so the Anthropic path uses the preprocessed message list instead of passing raw multimodal history through unchanged.
  - Intentionally did not transplant the upstream `_CODEX_AUX_MODEL` downgrade, because the current fork is already on a different local Codex auxiliary model track.
- Verification:
  - `venv\Scripts\python.exe -m py_compile run_agent.py`
- Quick test path:
  - Send an image in a conversation that later continues through the Anthropic provider path.
  - Confirm Hermes can keep the image context alive without Anthropic message-shape failures.
  - Sanity-check that repeated turns referencing the same image do not repeatedly trigger fresh vision analysis inside the same run.
- Test policy note:
  - No upstream tests were copied.

### PR #1417

- Title: `fix(gateway): isolate DM sessions by chat_id`
- Status: Integrated in the local gateway-session shape.
- Decision: Integrated in the local gateway-session shape.
- Why:
  - This is a real local gap in `gateway/session.py`.
  - The current fork still builds DM session keys like this:
    - WhatsApp DMs: one session per `chat_id`
    - all other DMs: one shared `agent:main:{platform}:dm` session
  - That means private conversations on platforms like Telegram, Discord, and Slack can still collapse into a shared DM session instead of being isolated per chat.
  - Upstream’s fix is narrow and sensible:
    - include `chat_id` for DMs whenever it exists
    - include `thread_id` too when present
    - keep simple fallbacks when identifiers are missing
  - No upstream tests should be imported.
- Local integration notes:
  - Patched `build_session_key(...)` in `gateway/session.py` so:
    - DMs use `chat_id` when present
    - threaded DMs further differentiate by `thread_id`
    - group/channel sessions use `chat_id` first and `thread_id` second
    - deterministic fallbacks remain when identifiers are missing
  - This removes the old non-WhatsApp behavior where multiple private conversations on the same platform could collapse into one shared DM session.
- Verification:
  - `venv\Scripts\python.exe -m py_compile gateway\session.py`
- Quick test path:
  - Open two separate DMs with Hermes on the same platform and confirm they no longer share one session transcript.
  - In a threaded DM-capable platform, confirm two threads under the same DM chat get separate sessions.
  - Sanity-check that channel/group sessions still key by parent chat and optional thread.
- Test policy note:
  - No upstream tests were copied.

### PR #1419

- Title: `fix(security): block gateway and tool env vars in subprocesses`
- Status: Integrated in the local subprocess-env hardening shape.
- Decision: Integrated in the local subprocess-env hardening shape.
- Why:
  - This is a real local security gap.
  - The current fork still passes subprocess environments in both places with plain merges:
    - `tools/environments/local.py` uses `env=os.environ | self.env`
    - `tools/process_registry.py` uses `os.environ | (env_vars or {})` for both PTY and non-PTY local spawns
  - That means Hermes-managed secrets and runtime config can still leak into subprocesses started by local terminal execution and background process management.
  - The local tree does not yet have:
    - a shared `_sanitize_subprocess_env(...)` helper
    - a blocklist that includes tool/messaging secrets from `OPTIONAL_ENV_VARS`
    - the `_HERMES_FORCE_...` override path for intentionally opting blocked vars back in
  - Upstream’s fix is a focused hardening patch and maps cleanly to the current fork.
- Local integration notes:
  - Added a shared `_sanitize_subprocess_env(...)` helper in `tools/environments/local.py`.
  - Added a derived Hermes-managed env blocklist in `tools/environments/local.py` based on:
    - provider env vars from `hermes_cli.auth.PROVIDER_REGISTRY`
    - tool/messaging/password entries from `hermes_cli.config.OPTIONAL_ENV_VARS`
    - a small explicit set of remaining gateway/runtime auth and config vars not covered there
  - Preserved `_HERMES_FORCE_<VAR>` as the explicit opt-back-in path for callers that intentionally need a blocked variable in a subprocess.
  - Patched `LocalEnvironment.execute(...)` to use the shared sanitizer instead of passing `os.environ | self.env` directly.
  - Patched `tools/process_registry.py` so both PTY and non-PTY local background spawns use the same sanitizer before launch.
- Verification:
  - `venv\Scripts\python.exe -m py_compile tools\environments\local.py tools\process_registry.py`
- Quick test path:
  - Start a local terminal command that prints env vars and confirm Hermes-managed provider, gateway, and tool secrets are absent.
  - Repeat with a background process and PTY process.
  - Set `_HERMES_FORCE_OPENAI_API_KEY` (or another blocked var) in the explicit subprocess env and confirm only that intentionally forced var is restored.
- Test policy note:
  - No upstream tests were copied.

### PR #1422

- Title: `fix(gateway): prevent Telegram photo burst interrupts`
- Status: Integrated in the local Telegram/gateway interrupt shape.
- Decision: Integrated partially in the local Telegram/gateway interrupt shape.
- Why:
  - This is a real local gap even though part of the Telegram media-group work is already present.
  - The current fork already has Telegram media-group buffering in `gateway/platforms/telegram.py`, but that is not enough by itself:
    - `gateway/platforms/base.py` still treats any follow-up message in an active session as an interrupt trigger
    - photo-only follow-ups are still routed into `_pending_messages` with interrupt semantics
  - So rapid Telegram photo bursts can still self-interrupt an in-flight run instead of being absorbed and processed as one logical image turn.
  - The useful local slice is the interrupt-handling hardening:
    - queue photo-only follow-ups without interrupting active runs
    - let adapter-level batching/merge logic absorb photo bursts cleanly
  - The Athabasca note added upstream in `gateway/run.py` looks product-specific and does not appear necessary for the narrow bugfix.
  - No upstream tests should be imported.
- Local integration notes:
  - Patched `gateway/platforms/base.py` so active-session `MessageType.PHOTO` follow-ups are queued without interrupting the current run.
  - Patched `gateway/platforms/telegram.py` to add a narrow non-album photo-burst batching layer:
    - per-burst batch keys
    - short delayed flush
    - merge of media paths/types and caption text
    - cleanup of pending batch tasks during disconnect
  - Updated Telegram photo handling so cached photo events are enqueued into the burst buffer and returned early instead of being processed immediately one-by-one.
  - Patched `gateway/run.py` so the fast priority interrupt path still applies to text and stop messages, but photo-only follow-ups are queued without interrupting an in-flight run.
  - Intentionally did not import the upstream Athabasca-specific image persistence note.
- Verification:
  - `venv\Scripts\python.exe -m py_compile gateway\platforms\base.py gateway\platforms\telegram.py gateway\run.py`
- Quick test path:
  - Send a Telegram photo burst or album while Hermes is already processing the first image message.
  - Confirm the follow-up photo updates are merged/queued instead of interrupting the in-flight run.
  - Sanity-check that a text follow-up or explicit stop message still interrupts immediately.
- Test policy note:
  - No upstream tests were copied.

### PR #1425

- Title: `fix(cli): accept session ID prefixes for session actions`
- Status: Integrated in the local session-CLI shape.
- Decision: Integrated in the local session-CLI shape.
- Why:
  - This is a small real local UX gap in the session CLI/state layer.
  - The current fork does not yet have `resolve_session_id(...)` in `hermes_state.py`.
  - The session CLI in `hermes_cli/main.py` still passes the user-provided session identifier straight through for at least:
    - export
    - delete
  - That means users still need the full session ID even when a unique prefix would be enough.
  - Upstream’s fix is narrow and clean:
    - add exact-or-unique-prefix resolution in `SessionDB`
    - use it in session actions before delete/export/rename
  - No upstream tests should be imported.
- Local integration notes:
  - Added `resolve_session_id(session_id_or_prefix)` to `hermes_state.py`.
  - Updated the session CLI actions in `hermes_cli/main.py` so export and delete now resolve a unique session-ID prefix before acting.
  - Kept ambiguous-prefix handling conservative by returning “not found” unless there is exactly one match.
  - Kept the patch narrowly scoped to the actual local export/delete path that was missing the helper.
- Verification:
  - `venv\Scripts\python.exe -m py_compile hermes_state.py hermes_cli\main.py`
- Quick test path:
  - Run a session action with a unique leading prefix of a real session ID and confirm it resolves to the full session.
  - Try a nonexistent prefix and confirm it still reports not found.
  - If two sessions share the same prefix, confirm the action does not silently pick one.
- Test policy note:
  - No upstream tests were copied.

### PR #1382

- Title: `fix: verify crontab availability for cronjob tools`
- Status: Integrated in the local runtime shape.
- Decision: Integrated in the local runtime shape.
- Why:
  - This is a small real local gap in `tools/cronjob_tools.py`.
  - The current fork still advertises cronjob tool availability based on session mode alone, even if the host does not actually have the `crontab` executable.
  - Upstream’s runtime fix is narrow and useful:
    - require `crontab` to be present on PATH before exposing cronjob tools
  - That avoids exposing scheduling tools in environments where they cannot work.
- Local integration notes:
  - Patched `tools/cronjob_tools.py` so `check_cronjob_requirements()` now also requires `shutil.which("crontab")`.
  - Kept the existing interactive/gateway gating intact, including the local `HERMES_EXEC_ASK` path.
  - Verification:
    - `venv\Scripts\python.exe -m py_compile tools\cronjob_tools.py`
- Quick test path:
  - In an environment without `crontab` on PATH, confirm the cronjob tools are no longer exposed.
  - In an environment with `crontab` present, confirm the current CLI/gateway cronjob behavior is unchanged.
- Test policy note:
  - No upstream tests were copied.

### PR #1383

- Title: `fix: add project root to PYTHONPATH in execute_code sandbox`
- Status: Integrated in the local sandbox-runtime shape.
- Decision: Integrated in the local sandbox-runtime shape.
- Why:
  - This is a small real local gap in `tools/code_execution_tool.py`.
  - The current fork already passes through a sanitized `PYTHONPATH`, but it does not proactively prepend the Hermes project root for sandboxed `execute_code` child scripts.
  - That means repo-local modules that are importable in the main process can still fail to import inside the sandbox when the child script runs from a temp directory.
  - Upstream’s runtime fix is narrow and useful:
    - prepend the Hermes repo root to the child `PYTHONPATH` before launching the sandboxed script
  - This should play nicely with the current local environment filtering because it keeps any existing `PYTHONPATH` entries after the injected project root.
- Local integration notes:
  - Patched `tools/code_execution_tool.py` so the `execute_code(...)` child environment now prepends the Hermes repo root to `PYTHONPATH` before launching the temp-directory child script.
  - Kept the rest of the sandbox environment shaping unchanged, including the sanitized inherited environment and existing `PYTHONPATH` entries after the injected project root.
  - Verification:
    - `venv\Scripts\python.exe -m py_compile tools\code_execution_tool.py`
- Quick test path:
  - Run `execute_code` with a snippet that imports a repo-local module from the Hermes tree and confirm it now succeeds inside the sandbox.
  - Sanity-check that an existing external `PYTHONPATH` still remains available after the injected project root.
- Test policy note:
  - No upstream tests were copied.

### PR #1385

- Title: `fix(discord): retry without reply reference for system messages`
- Status: Integrated in the local Discord adapter shape.
- Decision: Integrated in the local Discord adapter shape.
- Why:
  - This is a small real local gap in `gateway/platforms/discord.py`.
  - The current fork already has broader generic retry handling for chunked Discord sends, but it does not include the specific upstream fallback for reply targets that are Discord system messages.
  - Without that special case, a reply send can still fail outright when Discord rejects the reply reference with:
    - `error code: 50035`
    - `Cannot reply to a system message`
  - Upstream’s runtime fix is narrow and useful:
    - if the first send attempt fails for that exact system-message reply case, retry the send once without the reply reference
  - This fits cleanly into the current local retry loop without disturbing the broader retry/backoff behavior already present.
- Local integration notes:
  - Patched `gateway/platforms/discord.py` so the chunked send loop now detects the Discord system-message reply failure case and retries that send once without `reference`.
  - Kept the broader local retry/backoff behavior intact for all other Discord send failures.
  - Verification:
    - `venv\Scripts\python.exe -m py_compile gateway\platforms\discord.py`
- Quick test path:
  - Trigger a Discord send that replies to a system message and confirm Hermes retries without the reply reference instead of failing the send.
  - Sanity-check that normal reply sends still preserve the reply reference when Discord accepts it.
- Test policy note:
  - No upstream tests were copied.

### PR #1386

- Title: `fix(cli): non-blocking startup update check and banner deduplication`
- Status: Integrated in the local shared-banner/update-check shape.
- Decision: Integrated partially in the local shared-banner/update-check shape.
- Why:
  - The banner deduplication part is a real local gap:
    - `cli.py` imports `build_welcome_banner` and `get_available_skills` from `hermes_cli.banner`
    - but then redefines local versions later in the file, so the shared module is effectively shadowed
  - The startup update-check part is not already present locally either:
    - the current CLI has no startup update-status path at all
    - upstream’s non-blocking prefetch approach is a good fit because it avoids delaying interactive startup
  - The broader upstream diff also carries tests, which we did not import.
- Local integration notes:
  - Removed the duplicate local banner/skills helper implementations from `cli.py` so the CLI now actually uses the shared `hermes_cli.banner` module instead of shadowing it.
  - Added a narrow fork-local update-check helper path in `hermes_cli.banner`:
    - synchronous `check_for_updates()`
    - background `prefetch_update_check()`
    - non-blocking `get_update_result()`
  - Implemented a cached git-based update check that prefers `~/.hermes/hermes-agent` when present and otherwise falls back to the current project checkout, with tracked-branch resolution and sensible remote fallbacks.
  - Patched `hermes_cli.main.cmd_chat(...)` to start the background update check before heavier CLI initialization.
  - Patched `hermes_cli.banner.build_welcome_banner(...)` to surface the prefetched update result when it is ready without blocking startup.
  - Patched `hermes_cli.main.cmd_version(...)` to show synchronous update status.
  - Verification:
    - `venv\Scripts\python.exe -m py_compile hermes_cli\banner.py hermes_cli\main.py cli.py`
- Quick test path:
  - Launch `hermes` interactively and confirm startup does not block on update checking.
  - Confirm the banner still renders through the shared `hermes_cli.banner` implementation after removing the duplicate `cli.py` copy.
  - Run `hermes version` and confirm it reports update status when the git checkout can be checked.
- Test policy note:
  - No upstream tests were copied.

### PR #1387

- Title: `fix: improve Slack setup guidance`
- Status: Integrated in the local setup-UX shape.
- Decision: Integrated in the local setup-UX shape.
- Why:
  - This is a real local user-facing gap in `hermes_cli/setup.py`.
  - The current fork still shows the older minimal Slack setup instructions and the older allowlist wording:
    - it does not distinguish required vs optional private-channel scopes/events
    - it does not remind the user to reinstall the Slack app after scope/event changes
    - it still frames an empty allowlist as “open access,” even though the current gateway defaults deny unpaired users unless explicitly opened up
  - Upstream’s change is guidance-only, but it improves correctness and matches the fork’s current security model better.
- Local integration notes:
  - Updated the Slack setup instructions in `hermes_cli/setup.py` to distinguish required versus optional private-channel scopes and event subscriptions.
  - Added the reinstall reminder and updated the Slack docs URL.
  - Updated the empty-allowlist prompt and warning text so it matches the current default-deny pairing model instead of implying workspace-wide open access.
  - Kept the change scoped to setup guidance only.
  - Verification:
    - `venv\Scripts\python.exe -m py_compile hermes_cli\setup.py`
- Quick test path:
  - Run `hermes setup`, enter the Slack setup branch, and confirm the instructions reflect required vs optional scopes/events and the reinstall reminder.
  - Leave the allowlist empty and confirm the warning now explains default deny plus the explicit env vars needed for open access.
- Test policy note:
  - No upstream tests were copied.

### PR #1388

- Title: `fix: harden .worktreeinclude path containment`
- Status: Reviewed.
- Decision: Skip, not applicable to the current local worktree shape.
- Why:
  - The upstream fix hardens `.worktreeinclude` handling in `cli.py` by preventing path traversal and symlink escapes when copying extra files into a session worktree.
  - The current fork does not implement that `.worktreeinclude` feature surface at all.
  - Local worktree support currently goes through `_create_isolated_worktree(...)` in `cli.py`, which only does:
    - `git worktree add --detach ...`
    - `chdir` into the new worktree
    - `TERMINAL_CWD` rebinding
  - There is no local `.worktreeinclude` parsing, no extra copy step, and no symlink creation path here, so the specific containment bug upstream fixed is not present in this fork right now.
- Quick test path:
  - Start a `--worktree` CLI session and confirm it still creates a detached git worktree normally.
  - Sanity-check that there is no local `.worktreeinclude` processing path in the current implementation.
- Test policy note:
  - No upstream tests were copied.

### PR #1389

- Title: `fix(telegram): check updater/app state before disconnect`
- Status: Integrated in the local Telegram disconnect shape.
- Decision: Integrated in the local Telegram disconnect shape.
- Why:
  - This is a small real local gap in `gateway/platforms/telegram.py`.
  - The current fork still unconditionally calls:
    - `await self._app.updater.stop()`
    - `await self._app.stop()`
  - That can raise noisy disconnect-path errors when the updater or app was never started, or has already stopped due to an earlier conflict/shutdown path.
  - Upstream’s fix is narrow and useful:
    - only stop the updater if it exists and is running
    - only stop the app if it is running
  - The shutdown call can remain unconditional afterward.
- Local integration notes:
  - Patched `gateway/platforms/telegram.py` so disconnect now checks updater/app running state before calling `stop()`.
  - Kept the existing shutdown flow and exception handling intact.
  - Verification:
    - `venv\Scripts\python.exe -m py_compile gateway\platforms\telegram.py`
- Quick test path:
  - Trigger a Telegram connect/disconnect path where startup fails or the updater never fully enters running state, then confirm disconnect no longer emits avoidable stop-related warnings.
  - Sanity-check that a normal running Telegram adapter still disconnects cleanly.
- Test policy note:
  - No upstream tests were copied.

### PR #1391

- Title: `fix: prevent closed OpenAI client reuse across retries`
- Status: Integrated in the local OpenAI client-lifecycle shape.
- Decision: Integrated partially in the local OpenAI client-lifecycle shape.
- Why:
  - This is a real local runtime gap in `run_agent.py`.
  - The current fork still uses a single shared OpenAI client in the non-Anthropic path and closes that shared client during interrupt/retry flows before rebuilding it in place.
  - The local code still has patterns like:
    - `self.client = OpenAI(**client_kwargs)`
    - `self.client.close()`
    - worker threads calling `self.client.chat.completions.create(...)`
    - Codex/Responses helpers calling `self.client.responses.stream(...)`
  - That means retries or background worker paths can still race against a previously closed shared transport and reuse a dead client object.
  - Upstream’s full patch is broad, but the core useful behavior is:
    - protect the shared client behind a lock
    - detect and rebuild a closed shared client before reuse
    - give worker/request threads their own non-shared OpenAI client instances so interrupt-abort only closes the in-flight request client, not the shared seed client
- Local integration notes:
  - Added the shared-client lock and helper methods in `run_agent.py`:
    - `_openai_client_lock()`
    - `_is_openai_client_closed(...)`
    - `_create_openai_client(...)`
    - `_replace_primary_openai_client(...)`
    - `_ensure_primary_openai_client(...)`
    - request-scoped create/close helpers
  - Updated OpenAI client initialization plus the Codex and Nous credential-refresh paths to rebuild the shared client through the new helper layer.
  - Updated the threaded API-call path so OpenAI worker threads now use request-local clients instead of the shared `self.client`, and interrupt-abort closes only the in-flight request client.
  - Updated Codex/Responses helper calls and the memory-flush / iteration-limit summary paths to go through `_ensure_primary_openai_client(...)` rather than blindly using `self.client`.
  - Kept the Anthropic-native paths locally adapted; the remaining direct `self.client.close()` calls are in that Anthropic-specific path by design.
  - Verification:
    - `venv\Scripts\python.exe -m py_compile run_agent.py`
- Quick test path:
  - Trigger an interrupt during an in-flight OpenAI request and confirm a subsequent retry/request does not fail due to a previously closed shared client.
  - Exercise a Codex/Responses streaming path plus a later summary/flush call and confirm the client is recreated safely if the shared transport was closed.
- Test policy note:
  - No upstream tests were copied.

### PR #1393

- Title: `fix: normalize Codex dict tool arguments as JSON`
- Status: Integrated in the local Codex parsing shape.
- Decision: Integrated in the local Codex parsing shape.
- Why:
  - This is a small real local gap in `run_agent.py`.
  - The current fork already uses `json.dumps(arguments, ensure_ascii=False)` in some earlier tool-call normalization paths, but the Responses/Codex parsing branches for:
    - `function_call`
    - `custom_tool_call`
    still fall back to `str(arguments)` when the tool arguments arrive as a Python dict-like object.
  - That produces Python repr-style strings instead of valid JSON, which can break downstream tool-call handling and replay logic.
  - Upstream’s fix is narrow and correct:
    - use `json.dumps(arguments, ensure_ascii=False)` instead of `str(arguments)` in those remaining Codex tool-call branches
- Local integration notes:
  - Patched the remaining `function_call` and `custom_tool_call` argument-normalization branches in `run_agent.py` to use `json.dumps(arguments, ensure_ascii=False)`.
  - Kept the rest of the Codex/Responses parsing logic unchanged.
  - Verification:
    - `venv\Scripts\python.exe -m py_compile run_agent.py`
- Quick test path:
  - Feed the Responses/Codex parser a tool call whose `arguments` or `input` arrives as a dict object and confirm the normalized string is valid JSON rather than a Python repr.
  - Sanity-check that existing string arguments continue to pass through unchanged.
- Test policy note:
  - No upstream tests were copied.

### PR #1394

- Title: `fix: honor stt.enabled false across gateway transcription`
- Status: Reviewed.
- Decision: Skip, already functionally covered.
- Why:
  - The substantive runtime behavior from this merge is already present in the current fork:
    - `hermes_cli/config.py` already exposes `stt.enabled` in `DEFAULT_CONFIG`
    - `gateway/config.py` already carries `stt_enabled` on `GatewayConfig` and bridges `stt.enabled` from config.yaml
    - `gateway/run.py` already short-circuits gateway voice transcription with a disabled note when STT is turned off
    - `tools/transcription_tools.py` already exposes `is_stt_enabled(...)` and returns a disabled-STT error from `transcribe_audio(...)`
    - `tools/voice_mode.py` already reflects disabled STT in requirements and environment state
  - Upstream also bumps config schema version and adds tests, but we do not import upstream tests, and the core disabled-STT behavior is already in place locally.
- Quick test path:
  - Set `stt.enabled: false` in `~/.hermes/config.yaml` and confirm gateway voice input returns the disabled-transcription note instead of attempting STT.
  - Sanity-check that `transcribe_audio(...)` and voice-mode requirements both report disabled STT consistently.
- Test policy note:
  - No upstream tests were copied.

### PR #1373

- Title: `fix: restore config-saved custom endpoint resolution`
- Status: Integrated locally.
- Decision: Integrate in a narrow local runtime-provider patch.
- Why:
  - There is no first-parent merge for `#1374` in `main..upstream/main`; the next real merged PR is `#1373`.
  - This is a real local runtime-provider gap.
  - Our current `hermes_cli/runtime_provider.py` already honors a config-saved `model.base_url` in `auto` mode, but it still does not honor that saved custom endpoint when the caller explicitly requests `requested="custom"` and `OPENAI_BASE_URL` is not set in the live environment.
  - Upstream’s code-side fix is tightly scoped:
    - `hermes_cli/runtime_provider.py` restores config-saved custom endpoint resolution for explicit custom-provider requests
    - `agent/auxiliary_client.py` then relies on that helper path
  - Our fork already added separate direct auxiliary overrides in `#1375`, but the shared runtime-provider helper still has this missing explicit-custom branch.
  - Upstream also added tests, but we will not take those under the fork policy.
- Local implementation:
  - Patched `hermes_cli/runtime_provider.py` so `_resolve_openrouter_runtime(...)` also honors `model.base_url` from config when `requested_provider == "custom"` and the saved config provider is `custom`, as long as no explicit base URL and no live `OPENAI_BASE_URL` env override are present.
  - Kept the rest of runtime-provider resolution unchanged.
- Verification:
  - `python -m py_compile hermes_cli/runtime_provider.py`
- Quick test path:
  - Save a custom endpoint in `~/.hermes/config.yaml` under `model.provider: custom` and `model.base_url: ...`, with no `OPENAI_BASE_URL` exported in the shell.
  - Trigger a path that resolves the runtime with an explicit custom-provider request.
  - Confirm Hermes uses the saved custom endpoint from config instead of falling back to OpenRouter.
  - Sanity-check that `auto` mode and live `OPENAI_BASE_URL` env overrides still behave the same way.
- Test policy note:
  - No upstream tests were copied.

### PR #1376

- Title: `docs: clarify saved custom endpoint routing`
- Status: Evaluated locally.
- Decision: Skip.
- Why:
  - There is no first-parent merge for `#1372` on upstream `main`; the next unreviewed merge adjacent to `#1373` is `#1376`.
  - `#1376` is docs-only upstream. It touches only website documentation:
    - `website/docs/developer-guide/provider-runtime.md`
    - `website/docs/reference/faq.md`
    - `website/docs/user-guide/configuration.md`
  - It does not change runtime code in the fork.
  - Under the fork’s upstream integration policy, this is a straightforward skip.
- Quick test path:
  - No runtime verification needed here because the upstream merge is documentation-only.
  - Sanity-check that we intentionally did not import upstream website/docs content.
- Test policy note:
  - No upstream tests were copied.

### PR #1368

- Title: `fix: resolve cron auto-delivery target after dotenv reload`
- Status: Evaluated locally.
- Decision: Skip as already functionally covered / not directly applicable to the fork’s cron delivery path.
- Why:
  - The upstream fix is targeted at a specific cron auto-delivery bridge in `cron/scheduler.py`:
    - it stops resolving `delivery_target` before `.env` reload
    - then resolves and exports `HERMES_CRON_AUTO_DELIVER_*` env vars after `load_dotenv(...)`
  - Our fork’s scheduler does not currently use that `HERMES_CRON_AUTO_DELIVER_*` env-bridge at all.
  - Instead, the local fork resolves cron delivery lazily in `_deliver_result(...)` at send time:
    - `deliver=origin` reads the stored origin block directly from the job
    - bare platform delivery falls back to `{PLATFORM}_HOME_CHANNEL` at the moment of delivery
  - In the main completion/error/status delivery paths, those calls happen after `load_dotenv_with_fallback(..., override=True)` has already reloaded `~/.hermes/.env`, so the relevant target resolution already sees fresh env state.
  - The scheduler still sends a pre-run “starting” status message before the reload, but that is outside the exact upstream auto-delivery bridge that `#1368` fixes.
  - Upstream also added tests, but we will not take those under the fork policy.
- Quick test path:
  - Configure a cron job with a bare platform delivery target that falls back to `{PLATFORM}_HOME_CHANNEL`.
  - Change the home channel value in `~/.hermes/.env` without restarting Hermes.
  - Trigger the cron job and confirm the main delivered result uses the reloaded home channel value.
  - Sanity-check that `deliver=origin` continues to route via the stored origin block.
- Test policy note:
  - No upstream tests were copied.

### PR #1369

- Title: `fix: exclude Coding Plan-only models from Moonshot model selection`
- Status: Evaluated locally.
- Decision: Skip as not currently applicable to the fork’s Kimi setup flow.
- Why:
  - The upstream runtime/code change is tightly scoped to `hermes_cli/main.py`.
  - Upstream fixes a specific bug in the Kimi / Moonshot provider model picker:
    - the legacy Moonshot branch was using a broader provider model bucket
    - that caused Coding Plan-only models to appear in the selectable list
    - upstream fixes it by routing that branch to a curated `moonshot` model list instead
  - Our local fork does not currently have that auto-populated Moonshot model-picker branch.
  - In the local `kimi-coding` setup flow, `_model_flow_kimi(...)` still uses direct manual model entry:
    - prompt for API key
    - optional base URL override
    - free-form `Model name [...]`
  - Since the local fork is not currently auto-offering the wrong Moonshot model list, the exact upstream bug does not exist in the same shape here.
  - Upstream also added tests, but we will not take those under the fork policy.
- Quick test path:
  - Run the local `kimi-coding` setup flow.
  - Confirm it still asks for a free-form model name instead of presenting the incorrect Moonshot/Coding Plan model picker list.
  - If we later add a curated Kimi/Moonshot picker, revisit this upstream change at that time.
- Test policy note:
  - No upstream tests were copied.

### PR #1367

- Title: `refactor: unify vision backend gating`
- Status: Integrated partially in a narrow local shape.
- Decision: Integrate partially in a narrow local shape, not as a wholesale refactor.
- Why:
  - This upstream merge is broad. It spans:
    - `agent/auxiliary_client.py`
    - `hermes_cli/setup.py`
    - `hermes_cli/tools_config.py`
    - `tools/vision_tools.py`
    - plus upstream tests we will not take
  - The fork already has broader auxiliary vision runtime support in `agent/auxiliary_client.py` than an OpenRouter-only path:
    - OpenRouter
    - Nous Portal
    - Codex
    - explicit direct vision overrides added locally in `#1375`
  - But the fork’s setup/config gating is still stale and does not consistently reflect that runtime reality:
    - `hermes_cli/setup.py` still reports vision availability primarily via `OPENROUTER_API_KEY`
    - `hermes_cli/tools_config.py` still labels/configures the vision toolset without consulting the actual runtime resolver
    - `tools/vision_tools.py` still caches `_aux_async_client` at import time, so `check_vision_requirements()` can remain stale until process restart
  - So the core problem upstream is solving does exist locally, but we do not need the full refactor train to fix it.
- Local implementation:
  - Patched `hermes_cli/setup.py` so setup summary now reports vision availability via the actual auxiliary vision resolver instead of an OpenRouter-only heuristic.
  - Added a narrow optional vision-configuration step in `hermes_cli/setup.py` that can configure either:
    - OpenRouter for Gemini vision
    - a direct auxiliary vision endpoint via `auxiliary.vision` config fields
  - Patched `hermes_cli/tools_config.py` so the vision toolset now checks runtime availability using the actual auxiliary vision resolver instead of only static env-var assumptions, and added a matching vision-backend setup prompt there.
  - Patched `tools/vision_tools.py` so both `check_vision_requirements()` and `vision_analyze_tool(...)` resolve the current vision backend dynamically at call time instead of relying only on module-import-time cached state.
  - Kept the existing local auxiliary vision resolver in `agent/auxiliary_client.py` and did not port upstream’s full vision-provider refactor.
- Verification:
  - `python -m py_compile hermes_cli/setup.py hermes_cli/tools_config.py tools/vision_tools.py`
- Quick test path:
  - Configure vision via Nous, Codex, or an explicit direct vision override without `OPENROUTER_API_KEY`.
  - Run `hermes setup` and confirm the summary now reports vision as available.
  - Run `hermes tools` and confirm the vision toolset no longer appears unavailable just because `OPENROUTER_API_KEY` is absent.
  - Reconfigure vision in the same environment and confirm `vision_analyze` availability reflects the current resolver without requiring a full process restart.
- Test policy note:
  - No upstream tests were copied.

### PR #1360

- Title: `fix: refresh Anthropic OAuth before stale env tokens`
- Status: Integrated locally.
- Decision: Take it as part of a scoped fork-native native Anthropic runtime slice, not as a standalone cherry-pick.
- Why:
  - The upstream bug is real: a stale env-persisted Anthropic OAuth/setup token can shadow Claude Code credential files that are actually refreshable.
  - Instead of trying to cherry-pick only the late fix, the fork now has the minimal native Anthropic feature surface needed for the fix to make sense:
    - new `agent/anthropic_adapter.py`
    - native `anthropic_messages` runtime handling in `run_agent.py`
    - native provider resolution in `hermes_cli/auth.py` / `hermes_cli/runtime_provider.py`
    - Anthropic provider selection in `hermes_cli/main.py`
  - The local adapter intentionally keeps the rest of Hermes stable by translating Anthropic responses back into the OpenAI-like response shape the agent loop already expects.
  - The `#1360` behavior itself is included in the local adapter:
    - `ANTHROPIC_TOKEN` / `CLAUDE_CODE_OAUTH_TOKEN` are still supported
    - but refreshable Claude Code credential-file tokens are preferred over stale static env OAuth tokens when a refresh path exists
    - and the runtime only reports a successful Anthropic auth refresh on `401` when credential re-resolution actually yields a different token
  - Auto-detection was kept conservative: Anthropic is available as an explicit option without silently overriding existing OpenRouter setups just because an Anthropic key is present.
- Quick test path:
  - Set `model.provider: anthropic` and a Claude model such as `anthropic/claude-sonnet-4-20250514`, or run `hermes chat --provider anthropic`.
  - Confirm Hermes initializes against the native Anthropic Messages API instead of rejecting `api.anthropic.com`.
  - If both a stale `ANTHROPIC_TOKEN` and valid Claude Code credentials exist, confirm Hermes prefers the credential-file token path and can recover from `401` once instead of getting stuck on the stale env token.
  - Sanity-check that OpenRouter, Nous, and Codex provider flows remain unchanged.
- Test policy note:
  - No upstream tests were copied.

### Anthropic Native Runtime Dependency Note

- Context:
  - `#1360` is not the feature-introduction point for native Anthropic OAuth/runtime support.
  - The local fork currently lacks the whole native Anthropic surface:
    - no local `agent/anthropic_adapter.py`
    - no native `anthropic_messages` runtime in `run_agent.py`
    - no Claude Code credential auto-discovery/token-refresh path
- Upstream feature train identified:
  - Earliest code-introduction commit found on the upstream history for this surface:
    - `5e12442b` — `feat: native Anthropic provider with Claude Code credential auto-discovery`
  - Notable follow-on commits on that same upstream train:
    - `d7adfe8f` — fix: anthropic deep-dive gaps
    - `7086fde3` — revert inline vision, add model flow, wire vision aux
    - `d51243b6` — read credentials from `~/.claude.json`
    - `cd4e995d` — live model fetching + adaptive thinking
    - `4068f20c` / `aaaba781` / `3dc148ab` / `638136e3`
    - `d24bcad9` / `bb3f5ed3` — separate Anthropic OAuth tokens from API keys
    - `e052c747` — refresh Anthropic OAuth before stale env tokens (the `#1360` bugfix itself)
  - The first-parent merge we found in this area is:
    - `#1121` — `fix: anthropic adapter — max_tokens, fallback crash, proxy base_url`
  - But `#1121` is already on top of an earlier branch history where the native Anthropic feature was introduced, so `#1360` should be treated as part of a broader Anthropic-native feature train, not as a standalone sync patch.
- Recommended handling:
  - Completed locally in scoped fork-native form:
    - introduce the native Anthropic adapter/runtime surface first
    - then fold in the later token precedence/refresh fix from `#1360`
  - Continue treating follow-on upstream Anthropic PRs as part of this feature train, not as isolated patches.

### PR #1363

- Title: `docs: fix messaging gateway diagram alignment`
- Status: Evaluated locally.
- Decision: Skip.
- Why:
  - The upstream merge is docs-only.
  - It touches only `website/docs/user-guide/messaging/index.md`.
  - There is no runtime code, CLI behavior, or local repository logic change to carry over into the fork.
- Quick test path:
  - No runtime verification needed.
  - Sanity-check that we intentionally did not import upstream website/docs content.
- Test policy note:
  - No upstream tests were copied.

### PR #1362

- Title: `docs: complete voice mode docs`
- Status: Evaluated locally.
- Decision: Skip.
- Why:
  - The upstream merge is docs-only.
  - It touches only website documentation and sidebar wiring for voice mode coverage.
  - There is no runtime, CLI, gateway, config, or dependency behavior change to import into the fork from this PR itself.
- Quick test path:
  - No runtime verification needed.
  - Sanity-check that we intentionally did not import upstream website/docs content.
- Test policy note:
  - No upstream tests were copied.

### PR #1361

- Title: `docs: add provider contribution guide`
- Status: Evaluated locally.
- Decision: Skip because the only runtime-relevant pieces are already functionally covered in the fork.
- Why:
  - Although the PR title is docs-focused, the upstream merge also touched:
    - `cron/scheduler.py`
    - `tools/send_message_tool.py`
    - `tools/cronjob_tools.py`
    - `agent/prompt_builder.py`
  - The runtime-relevant cron/messaging behavior is already present locally:
    - `cron/scheduler.py` already resolves bare delivery targets like `telegram` to the configured `{PLATFORM}_HOME_CHANNEL`
    - `tools/send_message_tool.py` already supports bare platform sends via the platform home channel
    - `tools/send_message_tool.py` already guards against recursive sends back into the current active chat
  - The remaining upstream changes are docs, tests, or prompt-builder drift that should not be transplanted blindly into the fork.
  - In particular, the upstream `agent/prompt_builder.py` diff is not a narrow bugfix; it carries broader prompt/persona/context-scanning churn that does not belong in this selective sync pass.
- Quick test path:
  - Configure a home channel such as `TELEGRAM_HOME_CHANNEL`.
  - Use a cron job or `send_message(target='telegram', ...)` path without an explicit chat ID.
  - Confirm Hermes resolves the bare platform name to the configured home channel.
  - Sanity-check that sending to the current active chat is still blocked to prevent loops.
- Test policy note:
  - No upstream tests were copied.

### PR #1365

- Title: `fix: support multiple parallel tool calls in DeepSeek V3 parser (#989)`
- Status: Integrated locally.
- Decision: Take, implemented fork-natively.
- Why:
  - This is a real local parser gap in `environments/tool_call_parsers/deepseek_v3_parser.py`.
  - The earlier local `re.DOTALL` fix only addressed multiline JSON parsing. It did not fix the multiple-tool-call case.
  - The current local parser still uses a greedy regex plus `findall()`, which can collapse or over-capture adjacent DeepSeek V3 tool-call blocks.
  - Upstream's actual fix is small and applies cleanly here:
    - make the regex non-greedy and whitespace-tolerant
    - use `finditer()` to capture each tool call block independently
  - This is scoped to the parser only and does not require any of the upstream tests.
- Proposed local patch:
  - Implemented in `environments/tool_call_parsers/deepseek_v3_parser.py`:
    - regex now uses non-greedy groups and `\s*` around fenced JSON boundaries
    - parsing now uses `finditer()` and named groups
    - parser contract remains unchanged
- Quick test path:
  - Feed the parser a DeepSeek V3 output containing two adjacent tool-call blocks in one response.
  - Confirm it returns two structured tool calls instead of collapsing them into one malformed parse.
  - Sanity-check that a single tool-call block still parses the same way.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile environments\tool_call_parsers\deepseek_v3_parser.py`

### PR #1359

- Title: `Fix Firecrawl web tool config reloading`
- Status: Evaluated locally.
- Decision: Skip because the runtime fix is already functionally present in the fork.
- Why:
  - The upstream change is a real runtime fix in `tools/web_tools.py`, but the current local file already includes the same substantive behavior:
    - on-demand Firecrawl settings loading via `_ensure_firecrawl_settings_loaded()`
    - lazy reload from `~/.hermes/.env` and project `.env`
    - config-file fallback loading from `~/.hermes/config.yaml`
    - client recreation when the effective `(FIRECRAWL_API_KEY, FIRECRAWL_API_URL)` changes
    - `check_firecrawl_api_key()` reloading settings before reporting availability
    - `requires_env` widened to include both `FIRECRAWL_API_KEY` and `FIRECRAWL_API_URL`
  - Because the local fork already has the actual runtime behavior from this upstream patch, there is nothing additional to port.
- Quick test path:
  - Start a process where Firecrawl env vars were not loaded during bootstrap.
  - Set `FIRECRAWL_API_KEY` or `FIRECRAWL_API_URL` in `~/.hermes/.env`.
  - Trigger `web_search` or `web_extract` and confirm the tool becomes available without requiring a separate manual bootstrap path.
  - Sanity-check that changing the Firecrawl URL or key causes the client to rebuild with the new config.
- Test policy note:
  - No upstream tests were copied.

### PR #1343

- Title: `feat: compress cron management into one tool`
- Status: Evaluated locally.
- Decision: Skip deliberately because the fork already has a different, newer local cron tool surface.
- Why:
  - The upstream PR collapses cron management into a single `cronjob` tool shape.
  - The current fork already exposes the newer split cron tool surface in `tools/cronjob_tools.py`:
    - `schedule_cronjob`
    - `list_cronjobs`
    - `remove_cronjob`
  - That split local shape is already wired through the current CLI/runtime surface and is clearer than re-collapsing everything into one overloaded tool.
  - Taking `#1343` now would be a backwards API-shape move for the fork rather than a missing bugfix.
  - The rest of the upstream merge is a mixture of tests, docs, and larger cron/CLI churn that should not be transplanted wholesale during this selective sync pass.
- Quick test path:
  - Confirm the agent still exposes `schedule_cronjob`, `list_cronjobs`, and `remove_cronjob`.
  - Sanity-check that cron creation, listing, and removal still work through the existing split tool surface.
- Test policy note:
  - No upstream tests were copied.

### PR #1341

- Title: `fix(gateway): buffer Telegram media groups to prevent self-interruption`
- Status: Evaluated locally.
- Decision: Skip because the runtime fix is already functionally present in the fork.
- Why:
  - The upstream runtime change is scoped to `gateway/platforms/telegram.py`.
  - The current local Telegram adapter already implements album/media-group buffering:
    - `TelegramAdapter.MEDIA_GROUP_WAIT_SECONDS`
    - `TelegramAdapter._queue_media_group_event(...)`
    - `TelegramAdapter._flush_media_group_event(...)`
  - `_handle_media_message(...)` already detects `media_group_id`, merges media items into a single logical `MessageEvent`, debounces briefly, and only then forwards the merged event to `handle_message(...)`.
  - That is the core behavior upstream `#1341` adds to prevent the gateway from treating later album items as new user messages and interrupting the first one.
  - The local implementation also already cancels pending album flush tasks on disconnect, which is at least as robust as the upstream fix shape.
- Quick test path:
  - Send a Telegram album/media group with multiple photos or mixed media items in one user action.
  - Confirm Hermes receives and processes them as one logical message instead of interrupting itself on the second item.
  - Sanity-check that disconnecting the Telegram adapter clears any pending media-group flush tasks cleanly.
- Test policy note:
  - No upstream tests were copied.

### PR #1340

- Title: `fix(cli): fall back to main when current branch has no remote counterpart`
- Status: Integrated locally.
- Decision: Take, implemented fork-natively.
- Why:
  - This is a small real local gap in `hermes_cli/main.py` `cmd_update()`.
  - The current local update flow still assumes the current local branch exists on the update remote:
    - it resolves the current branch with `git rev-parse --abbrev-ref HEAD`
    - then directly checks `HEAD..{remote}/{branch}`
    - then directly pulls `{remote} {branch}`
  - If Hermes is running from a local-only branch without a matching remote branch, that logic can fail instead of updating from the repo's canonical `main` branch.
  - Upstream's fix is narrow and sensible, and it does not require any upstream tests.
- Proposed local patch:
  - Implemented in `hermes_cli/main.py` `cmd_update()`:
    - detect whether `refs/remotes/{remote}/{branch}` exists before using it
    - if it does not exist, print a short note and fall back to `main`
    - use the resolved update branch consistently for both the commit-count check and `git pull`
  - The rest of the update flow is unchanged.
- Quick test path:
  - Create or check out a local branch that has no matching branch on the update remote.
  - Run `hermes update`.
  - Confirm Hermes falls back to updating from `main` instead of failing on `{remote}/{branch}` lookup.
  - Sanity-check that updates still use the current branch normally when the remote counterpart does exist.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile hermes_cli\main.py`

### PR #1339

- Title: `Merging Telegram gateway conflict hardening: same-host token lock, clean shutdown on getUpdates conflict, persisted runtime health, and clearer gateway status diagnostics.`
- Status: Partially integrated locally.
- Decision: Partial take, implemented fork-natively for the runtime-health/status slice.
- Why:
  - This upstream merge bundles several gateway hardening changes together.
  - The Telegram conflict-hardening core is already functionally present in the fork:
    - `gateway/platforms/telegram.py` already uses a same-host token lock via `acquire_scoped_lock(...)` / `release_scoped_lock(...)`
    - it already detects getUpdates polling conflicts and stops polling cleanly
    - it already records fatal adapter state through `_set_fatal_error(...)`
  - The gateway shutdown side is also already improved locally:
    - `gateway/platforms/base.py` already tracks and cancels background tasks
    - `gateway/run.py` already interrupts active agents and calls `adapter.cancel_background_tasks()` during shutdown
  - The still-missing piece is the richer persisted runtime-health/status surface:
    - local `gateway/status.py` is still PID-file-only
    - local `hermes_cli/gateway.py` status output still reports only basic running/not-running state
    - the upstream runtime-health file and clearer gateway status diagnostics are not yet present locally
- Proposed local patch:
  - Implemented the runtime-health/status slice:
    - extended `gateway/status.py` with a persisted runtime health record alongside the PID file
    - updated `gateway/run.py` to write startup/running/stopping/stopped platform health state
    - surfaced that state in `hermes_cli/gateway.py` status output for manual, Windows, systemd, and launchd status checks
  - Did not import the upstream tests.
  - Did not broaden this turn into Telegram behavioral changes beyond the status surface.
- Quick test path:
  - Start the gateway with Telegram configured normally and confirm `hermes gateway status` shows healthy running state.
  - Trigger a connect failure or other startup problem and confirm the persisted runtime status shows the platform failure details instead of only “not running.”
  - Sanity-check that normal PID-based running detection still works when no fatal state is present.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile gateway\status.py gateway\run.py hermes_cli\gateway.py`

### PR #1338

- Title: `fix(vision): surface actual error reason instead of generic message`
- Status: Integrated locally.
- Decision: Take, implemented fork-natively.
- Why:
  - This is a tiny real local gap in `tools/vision_tools.py`.
  - The current local code already logs the real exception as `error_msg = f"Error analyzing image: {str(e)}"`.
  - But the returned JSON still collapses all failures to the generic analysis text:
    - `"There was a problem with the request and the image could not be analyzed."`
  - That means callers and users still lose the actionable failure reason even though the exception text is already available.
- Proposed local patch:
  - Implemented in `tools/vision_tools.py`:
    - the failure JSON now returns the actual `error_msg`
    - the rest of the tool behavior is unchanged
- Quick test path:
  - Trigger a vision failure, such as an invalid local path or unsupported backend/config situation.
  - Confirm the returned JSON includes the real analysis error reason instead of the generic fallback sentence.
  - Sanity-check that successful vision responses are unchanged.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile tools\vision_tools.py`

### PR #1337

- Title: `fix(cli): repair dangerous command approval UI`
- Status: Partially integrated locally.
- Decision: Partial take, implemented fork-natively for long-command visibility.
- Why:
  - The upstream merge bundles a few CLI approval-panel cleanups together.
  - The relevant local gap is real:
    - `cli.py` still truncates long dangerous commands to 70 characters in the approval panel
    - there is no local `view` affordance to expand the full command before choosing once/session/always/deny
  - The larger upstream refactor around `allow_permanent` is not a direct local fit right now:
    - the current local `_approval_callback(...)` still has the simpler `(command, description)` signature
    - there is no local `allow_permanent` branch to port cleanly as-is
  - So the right fork-native move is to take only the long-command visibility improvement, not the whole upstream refactor.
- Proposed local patch:
  - Implemented in `cli.py`:
    - added `_approval_choices(...)` so long commands offer `view`
    - added `_handle_approval_selection()` so selecting `view` expands the full command without closing the prompt
    - updated the approval panel renderer to preserve expanded-state display
  - Left the rest of the approval flow unchanged.
- Quick test path:
  - Trigger a dangerous command with a long command string that exceeds the current approval-panel truncation.
  - Confirm the approval UI offers a `Show full command` option.
  - Select that option and confirm the panel expands to the full command while keeping the approval prompt active.
  - Sanity-check that normal short-command approvals still work the same way.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile cli.py`

### PR #1335

- Title: `Salvaged PR #1037 onto current main with contributor commits preserved.`
- Status: Evaluated locally.
- Decision: Skip.
- Why:
  - The upstream merge is test-only in the actual merged diff.
  - It touches only `tests/test_cli_provider_resolution.py`.
  - Under the fork policy, upstream tests are not imported during this sync pass.
  - There is no runtime code change in the merge itself that needs to be carried over.
- Quick test path:
  - No runtime verification needed.
  - Sanity-check that we intentionally did not import upstream test-only content.
- Test policy note:
  - No upstream tests were copied.

### PR #1334

- Title: `fix: auto-enable systemd linger during gateway install on headless servers`
- Status: Integrated locally.
- Decision: Take, implemented fork-natively.
- Why:
  - This is a real local UX gap in `hermes_cli/gateway.py`.
  - The current local `systemd_install()` still only prints manual linger guidance:
    - `sudo loginctl enable-linger $USER`
  - On headless Linux servers, forgetting that step means the user service can stop on logout even though install otherwise appears successful.
  - This is a targeted Linux-only install improvement and fits the fork cleanly.
- Proposed local patch:
  - Implemented in `hermes_cli/gateway.py`:
    - added a helper to attempt `loginctl enable-linger $USER` during `systemd_install()`
    - kept failure non-fatal and preserved clear printed guidance when automatic enable fails
    - preserved existing behavior on non-Linux platforms
  - The rest of systemd service installation is unchanged.
- Quick test path:
  - Run `hermes gateway install` on Linux with linger disabled.
  - Confirm Hermes attempts to enable linger automatically.
  - If automatic enable succeeds, confirm the install output reports that.
  - If automatic enable fails due to privilege/policy, confirm install still succeeds and prints the manual `loginctl enable-linger` guidance.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile hermes_cli\gateway.py`

### PR #1333

- Title: `fix: improve browser cleanup, local browser PATH setup, and screenshot recovery`
- Status: Partially integrated locally.
- Decision: Partial take, implemented fork-natively for the browser reliability slice.
- Why:
  - The current local `tools/browser_tool.py` already has several nearby improvements:
    - persistent screenshot caching under `~/.hermes/browser_screenshots`
    - screenshot pruning
    - inactivity cleanup thread
    - broader Playwright-local runtime support
  - But the upstream merge still contains a few reliability fixes that are not clearly present locally:
    - recovering a screenshot file path when `agent-browser screenshot` returns non-JSON human-readable output
    - stronger PATH bootstrapping for local browser commands using Hermes-managed Node/bin locations
    - a simpler `browser_close()` path that always routes through shared cleanup logic instead of partially duplicating close/release behavior
    - more robust emergency cleanup state clearing
  - Those are narrow browser-tool resilience fixes and fit the fork well without importing the upstream tests.
- Proposed local patch:
  - Implemented in `tools/browser_tool.py`:
    - added screenshot-path recovery from non-JSON `agent-browser` output for the `screenshot` command
    - strengthened local PATH bootstrapping for browser subprocesses using Hermes-managed Node/bin plus sane system fallbacks
    - routed `browser_close()` through `cleanup_browser(...)`
    - tightened emergency cleanup state clearing
  - Left the rest of the browser tool behavior unchanged.
- Quick test path:
  - Trigger a browser screenshot flow where `agent-browser` emits a human-readable success line instead of JSON and confirm Hermes still recovers the screenshot path.
  - Run a local browser command in an environment where Node binaries are not fully in PATH and confirm the Hermes-managed Node/bin fallback is used.
  - Open and close a browser session, then confirm `browser_close()` clears session state cleanly.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile tools\browser_tool.py`

### PR #1330

- Title: `Merging the policy-precedence fix salvaged from #1007 onto current main, plus the CLI --yes/-y alias consistency follow-up.`
- Status: Integrated locally.
- Decision: Take, implemented fork-natively.
- Why:
  - The policy-precedence bug is still present locally in `tools/skills_guard.py`:
    - `should_allow_install(...)` still hard-blocks every `dangerous` verdict before consulting `INSTALL_POLICY`
    - that means the trust-level policy table never gets to control precedence for cases where the table intentionally allows a verdict
  - The small CLI alias follow-up is also still missing:
    - `hermes skills install` does not yet accept `--yes` / `-y` as aliases for the existing force/install-without-confirmation path
    - `/skills install` likewise only checks `--force`
  - This is a small, self-contained fix that fits the fork cleanly.
- Proposed local patch:
  - Implemented in `tools/skills_guard.py`:
    - removed the hardcoded early dangerous-verdict block
    - now let `INSTALL_POLICY` determine the decision precedence
    - kept `force` as an override for blocked policy decisions
  - Implemented in `hermes_cli/main.py`:
    - added `--yes` / `-y` as aliases for `hermes skills install --force`
  - Implemented in `hermes_cli/skills_hub.py`:
    - `/skills install` now recognizes `--yes` / `-y` in addition to `--force`
  - No upstream tests were imported.
- Quick test path:
  - Confirm `should_allow_install(...)` now follows `INSTALL_POLICY` precedence instead of pre-blocking every `dangerous` verdict.
  - Run `hermes skills install ... --yes` and confirm it behaves the same as `--force`.
  - Run `/skills install ... --yes` or `/skills install ... -y` and confirm it skips the confirmation/disclaimer prompt the same way as `--force`.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile tools\skills_guard.py hermes_cli\main.py hermes_cli\skills_hub.py`

### PR #1329

- Title: `fix: tighten memory and session recall guidance`
- Status: Integrated locally.
- Decision: Take, implemented fork-natively in a narrow prompt/schema guidance patch.
- Why:
  - This is not just wording churn. The current fork still teaches the model to use persistent memory like a diary:
    - `agent/prompt_builder.py` says to save what it learns and does "like a diary!"
    - `tools/memory_tool.py` still explicitly encourages logging completed work and complex task outcomes to memory
  - That is the wrong boundary for this architecture because memory is injected into future turns, while completed task history already lives in transcripts and is recallable via `session_search`.
  - Upstream tightens that boundary in a useful way:
    - memory should hold durable facts, stable conventions, tool quirks, and user preferences
    - task progress, session outcomes, and completed-work logs should be recalled via `session_search`, not promoted into persistent memory
  - The current local `tools/session_search_tool.py` is already mostly aligned, including raw-transcript default and proactive recall guidance, so the main remaining gap was in memory guidance and prompt wording.
- Local implementation:
  - Updated `agent/prompt_builder.py`:
    - replaced the diary-style memory instruction with durable-facts guidance
    - explicitly told the model not to store task progress, session outcomes, or completed-work logs in memory
    - pointed it to `session_search` for cross-session recall
  - Updated `tools/memory_tool.py` schema description:
    - removed encouragement to save completed tasks as memory entries
    - added explicit guidance not to save temporary task state or session outcomes in memory
    - preserved the existing guidance to save reusable workflows as skills
  - Left `tools/session_search_tool.py` unchanged.
- Quick test path:
  - Start a session, complete a one-off task, and inspect whether the model is now less likely to store the task outcome in persistent memory.
  - Ask later "what did we do about X?" and confirm the model prefers `session_search` for recall instead of relying on persistent memory.
  - Sanity-check that durable facts like user preferences, environment details, and stable project conventions are still natural memory entries.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile agent\prompt_builder.py tools\memory_tool.py`

### PR #1319

- Title: `Merging the remaining useful regression coverage from #1308 on top of the already-merged cron fix in #949.`
- Status: Evaluated locally.
- Decision: Skip.
- Why:
  - The merged diff is test-only upstream content.
  - It touches only `tests/test_timezone.py`.
  - The runtime cron/timezone behavior it references was already fixed upstream in earlier code merges; this PR only adds regression coverage on top.
  - Under the fork policy, we do not import upstream `tests/` content during this sync pass.
- Quick test path:
  - No runtime integration test is needed here because we are intentionally not taking the upstream test-only merge.
  - If we want extra confidence in local cron timezone handling later, we should add fork-native verification rather than copying upstream tests.
- Test policy note:
  - No upstream tests were copied.

### PR #1317

- Title: `docs(skills): add integrated hubs reference section`
- Status: Evaluated locally.
- Decision: Skip.
- Why:
  - The merged diff is docs-only upstream content.
  - It touches only `website/docs/user-guide/features/skills.md`.
  - There is no runtime, CLI, gateway, config, or tool behavior change in the PR itself.
  - Under the fork policy, we do not import upstream website/docs content during this sync pass.
- Quick test path:
  - No runtime verification needed.
  - Sanity-check that we intentionally did not import upstream website/docs content.
- Test policy note:
  - No upstream tests were copied.

### PR #1316

- Title: `docs(voice): add comprehensive voice mode guide`
- Status: Evaluated locally.
- Decision: Skip.
- Why:
  - The merged diff is docs-only upstream content.
  - It touches only website docs, sidebar wiring, and learning-path pages for voice mode.
  - There is no runtime, CLI, gateway, config, or dependency behavior change in the PR itself.
  - Under the fork policy, we do not import upstream website/docs content during this sync pass.
- Quick test path:
  - No runtime verification needed.
  - Sanity-check that we intentionally did not import upstream website/docs content.
- Test policy note:
  - No upstream tests were copied.

### PR #1315

- Title: `docs(soul): add comprehensive SOUL.md guide`
- Status: Evaluated locally.
- Decision: Skip.
- Why:
  - The merged diff is docs-only upstream content.
  - It touches only website docs, guide pages, and sidebar wiring for SOUL.md and personality/context-file documentation.
  - There is no runtime, CLI, gateway, config, or dependency behavior change in the PR itself.
  - Under the fork policy, we do not import upstream website/docs content during this sync pass.
- Quick test path:
  - No runtime verification needed.
  - Sanity-check that we intentionally did not import upstream website/docs content.
- Test policy note:
  - No upstream tests were copied.

### PR #1314

- Title: `fix: defer discord adapter annotations`
- Status: Evaluated locally.
- Decision: Skip, already functionally present in this fork.
- Why:
  - This is a small but real local import-safety fix in `gateway/platforms/discord.py`.
  - The adapter already handles missing `discord.py` imports by setting `discord = None` and `DISCORD_AVAILABLE = False`.
  - The current local file already includes `from __future__ import annotations` at the top of `gateway/platforms/discord.py`.
  - That means the actual upstream import-safety fix is already present locally, so there is nothing to patch.
- Quick test path:
  - In an environment without `discord.py`, import `gateway.platforms.discord` and confirm the module loads without annotation-related errors.
  - Sanity-check that when `discord.py` is installed, Discord gateway startup behavior is unchanged.
- Test policy note:
  - No upstream tests were copied.

### PR #1311

- Title: `feat: seed a default global SOUL.md`
- Status: Integrated locally.
- Decision: Integrate partially in the fork’s existing cwd-first/global-fallback SOUL model.
- Why:
  - The fork already has the core SOUL runtime behavior:
    - `agent/prompt_builder.py` already loads project-local `SOUL.md`
    - it already falls back to `~/.hermes/SOUL.md`
    - README already documents that cwd-first plus global fallback behavior
  - Upstream `#1311` bundles two distinct changes:
    - seed a default global `~/.hermes/SOUL.md` on first run
    - change prompt discovery so only the global SOUL is loaded, not project-local SOUL files
  - The first part is a reasonable UX improvement.
  - The second part is a product change we should not take blindly in this fork, because local project-level persona files are already supported and documented here.
  - So the useful local adaptation was:
    - add default global SOUL seeding
    - keep the current cwd-first plus global-fallback discovery logic unchanged
- Local implementation:
  - Added `hermes_cli/default_soul.py` with a default global SOUL template.
  - Updated `hermes_cli/config.py` so `ensure_hermes_home()` seeds `~/.hermes/SOUL.md` only if it does not already exist.
  - Updated `load_config()` to call `ensure_hermes_home()` so the default file is created during normal config bootstrap.
  - Left `agent/prompt_builder.py` unchanged so project-local `SOUL.md` still overrides the global fallback.
- Quick test path:
  - Start Hermes with no existing `~/.hermes/SOUL.md` and confirm a default file is seeded.
  - Confirm an existing user-authored `~/.hermes/SOUL.md` is left untouched.
  - Confirm a project-local `SOUL.md` still overrides the global fallback in the prompt builder.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile hermes_cli\default_soul.py hermes_cli\config.py`

### PR #1310

- Title: `fix: harden gateway restart recovery`
- Status: Integrated locally.
- Decision: Partial take, implemented fork-natively.
- Why:
  - We already integrated one important slice from this area earlier:
    - persisted runtime health in `gateway/status.py`
    - richer `hermes gateway status` output in `hermes_cli/gateway.py`
  - But the remaining upstream hardening in this PR is still missing locally:
    - `gateway/status.py` still writes a bare PID file instead of a PID record with metadata
    - `get_gateway_pid()` still trusts any live process holding that PID, without checking process identity or start time
    - `hermes_cli/gateway.py` does not yet auto-refresh an outdated installed systemd unit definition before start/restart
  - That meant stale PID reuse or a changed unit file could still cause confusing restart/status behavior even though the newer runtime-health surface exists.
- Local implementation:
  - Updated `gateway/status.py`:
    - pid files now store a JSON record with pid, argv, kind, and process start-time metadata
    - reading remains backward-compatible with older plain-text pid files
    - `get_gateway_pid()` now validates the live PID using start-time checks when available and command-line identity checks when inspectable
  - Updated `hermes_cli/gateway.py`:
    - added normalized systemd unit currentness checks
    - added `refresh_systemd_unit_if_needed()`
    - `systemd_start()` and `systemd_restart()` now auto-refresh the installed user unit if the generated definition has changed
    - `systemd_status()` now warns when the installed unit is outdated
  - Left the already-integrated runtime-health/status slice unchanged.
- Quick test path:
  - Start the gateway, inspect the PID file, and confirm it contains structured metadata while still tolerating older plain-text PID files if present.
  - Simulate a stale PID file or PID reuse scenario and confirm `get_gateway_pid()` rejects the wrong process and cleans up the stale record.
  - Change the generated systemd unit definition, then run `hermes gateway restart` and confirm the installed unit is refreshed before restart.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile gateway\status.py hermes_cli\gateway.py`

### PR #1306

- Title: `fix: backfill model on gateway sessions after agent runs`
- Status: Integrated locally.
- Decision: Take, implemented fork-natively in a narrow session-persistence patch.
- Why:
  - This is a small real local gap in the gateway/session persistence path.
  - Upstream’s runtime change is narrowly scoped:
    - after an agent run completes in `gateway/run.py`, it backfills the resolved model onto the stored session entry
    - nearby persistence helpers are adjusted so the model field can be updated cleanly even when the session was created before the final runtime model was known
  - That matters because gateway sessions can otherwise retain empty or stale model metadata even though the run result knows which model actually executed.
  - This merge also bundles upstream tests, which we should not import.
- Local implementation:
  - Updated `gateway/run.py` so the post-run `session_store.update_session(...)` call now passes through the resolved `model` from the agent result when available.
  - Updated `gateway/session.py` so `update_session(...)` accepts an optional `model` parameter and persists it during the normal post-run metadata update path.
  - Added a tiny `update_session_model(...)` helper in `hermes_state.py` to persist the model field on the SQLite session row.
  - Left the rest of the gateway/session flow unchanged.
- Quick test path:
  - Run a gateway conversation that creates or updates a session.
  - Confirm the stored session metadata includes the actual model used after the agent finishes.
  - Sanity-check that older sessions without a model can still be updated without breaking reads.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile gateway\run.py gateway\session.py hermes_state.py`

### PR #1305

- Title: `fix: salvage PR #327 voice mode onto current main` (merge wrapper for upstream voice salvage train)
- Status: Evaluated locally.
- Decision: Skip as already handled through the earlier `#1299` voice review and scoped local integration.
- Why:
  - The first-parent merge number here is `#1305`, but the merge commit itself is carrying the broad upstream voice salvage that we already treated as `#1299`.
  - That feature train was already reviewed and intentionally adapted in this fork as a scoped local CLI voice feature instead of a wholesale Discord voice-channel transplant.
  - The earlier ledger entry for `#1299` already captures:
    - the optional local CLI voice mode implementation
    - the dependency/install cleanup
    - the locally applicable follow-up fixes from `#1429`
    - the explicit decision not to import the broader Discord VC receiver/playback stack
  - So `#1305` is not a separate new action item for the fork; it is the same upstream voice salvage train surfacing under a different merge wrapper.
- Quick test path:
  - Reuse the existing `#1299` validation path for local CLI voice mode.
  - No additional runtime integration is needed beyond what was already done there.
- Test policy note:
  - No upstream tests were copied.

### PR #1298

- Title: `fix: clearer terminal backend requirement errors`
- Status: Integrated locally.
- Decision: Take, implemented fork-natively in a narrow terminal-requirements patch.
- Why:
  - This is a small but real local UX/runtime gap in `tools/terminal_tool.py`.
  - The current `check_terminal_requirements()` logic still returns bare `False` in several backend-specific failure cases without logging a useful reason:
    - SSH selected without both host and user configured
    - Modal selected without a token or `~/.modal.toml`
    - unknown `TERMINAL_ENV` values
  - The broad requirement check already exists locally, so the useful upstream change is simply clearer backend-specific error reporting plus slightly better debug logging for unexpected exceptions.
  - This merge also bundles tests, which we should not import.
- Local implementation:
  - Updated `tools/terminal_tool.py` so `check_terminal_requirements()` now logs clear backend-specific errors for:
    - SSH selected without both `TERMINAL_SSH_HOST` and `TERMINAL_SSH_USER`
    - Modal selected without `MODAL_TOKEN_ID` or `~/.modal.toml`
    - unknown `TERMINAL_ENV` values
  - Kept the underlying requirement behavior unchanged.
  - Expanded the generic exception log to include `exc_info=True` for easier debugging.
- Quick test path:
  - Set `TERMINAL_ENV=ssh` without `TERMINAL_SSH_HOST` / `TERMINAL_SSH_USER` and confirm the log/error clearly explains what is missing.
  - Set `TERMINAL_ENV=modal` without Modal credentials and confirm the log/error explains the missing token/config.
  - Set an invalid `TERMINAL_ENV` and confirm the error tells the user which backend values are valid.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile tools\terminal_tool.py`

### PR #1297

- Title: `docs: salvage #980 terminal backend and Windows troubleshooting`
- Status: Evaluated locally.
- Decision: Skip.
- Why:
  - The merged diff is docs-only upstream content.
  - It touches only website documentation for terminal backend setup and Windows troubleshooting.
  - There is no runtime, CLI, gateway, config, or dependency behavior change in the PR itself.
  - Under the fork policy, we do not import upstream website/docs content during this sync pass.
- Quick test path:
  - No runtime verification needed.
  - Sanity-check that we intentionally did not import upstream website/docs content.
- Test policy note:
  - No upstream tests were copied.

### PR #1301

- Title: `feat: add Parallel CLI research skill`
- Status: Integrated locally.
- Decision: Optional take, implemented as a bundled skill add.
- Why:
  - This merge adds a bundled skill only: `skills/research/parallel-cli/SKILL.md`.
  - The skill is not currently present in the fork.
  - There is no runtime code change in the PR itself, so this is a content/product choice rather than a correctness fix.
  - If we take it, it fits the fork’s existing bundled-skill model cleanly and does not require upstream tests.
- Local implementation:
  - Added `skills/research/parallel-cli/SKILL.md` to the local bundled skills tree.
  - Kept the change limited to the skill content only.
  - Did not import upstream tests or broader docs.
- Quick test path:
  - Confirm `parallel-cli` appears in local skill listings under the research category.
  - Invoke the skill through the local skills flow and confirm it is discoverable and loadable.
- Test policy note:
  - No upstream tests were copied.

### PR #1302

- Title: `feat(mcp): salvage selective tool loading with utility policies`
- Status: Integrated locally.
- Decision: Take, implemented as a narrow local MCP-config/runtime patch.
- Why:
  - This is a real local gap in `tools/mcp_tool.py`.
  - The local MCP integration already supports:
    - stdio and HTTP MCP transports
    - dynamic tool registration
    - MCP utility tools for resources/prompts
  - But it does not yet have the upstream selective-loading and policy controls:
    - per-server `enabled: false` gating
    - `tools.include` / `tools.exclude` filtering for discovered MCP tools
    - capability-aware utility registration so resource/prompt utility tools are only exposed when both:
      - the config enables them
      - the connected MCP session actually supports the corresponding capability
  - The upstream merge also bundles tests and website docs, which we should not import.
- Local implementation:
  - Update `tools/mcp_tool.py` to support `mcp_servers.<name>.enabled` so disabled servers are skipped without deleting config.
  - Add support for `mcp_servers.<name>.tools.include` and `mcp_servers.<name>.tools.exclude` when registering discovered MCP tools.
  - Make MCP utility tool registration capability-aware and config-aware for:
    - resources
    - prompts
  - Track registered MCP tool names explicitly so status/reporting reflects what was actually exposed, not just the raw discovered tool count.
- Quick test path:
  - Configure one MCP server with `enabled: false` and confirm discovery skips it entirely.
  - Configure another server with `tools.include` or `tools.exclude` and confirm only the intended MCP tools are registered.
  - Disable `resources` or `prompts` under the MCP tool config and confirm the matching utility tools are not exposed.
  - Connect to a server that lacks prompt/resource capabilities and confirm unsupported utility tools are not registered.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile tools\mcp_tool.py`

### PR #1320

- Title: `Salvaged PR #968 onto current main with contributor commits cherry-picked and preserved.`
- Status: Integrated locally.
- Decision: Take partially, implemented as a narrow CLI slash-command patch.
- Why:
  - The runtime-relevant part of this merge is a small `cli.py` improvement for slash-command prefix matching.
  - The local CLI currently supports prefix matching in autocomplete, but not at execution time.
  - That means inputs like a unique slash-command prefix can still fail as unknown commands even when completion already knows the intended target.
  - The upstream runtime change is tightly scoped:
    - if a typed slash command uniquely matches one built-in command or installed skill command, expand it and execute it
    - if it matches multiple commands, show an ambiguity message instead of a plain unknown-command failure
  - The merge also bundles upstream tests, which we should not import.
- Local implementation:
  - Update `cli.py` so unknown slash commands fall back to unique-prefix resolution using both built-in commands and installed skill commands.
  - If one unique match exists, redispatch to the full command name while preserving arguments.
  - If multiple matches exist, report an ambiguity message listing the matching commands.
  - Leave the rest of slash-command dispatch unchanged.
- Quick test path:
  - Type a uniquely identifying prefix of a built-in slash command and confirm it executes the intended command.
  - Type a uniquely identifying prefix of an installed skill slash command and confirm it resolves correctly.
  - Type an ambiguous prefix and confirm the CLI prints the matching candidates instead of a generic unknown-command message.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile cli.py`

### PR #1322

- Title: `fix: make config set examples use placeholder syntax`
- Status: Integrated locally.
- Decision: Take, implemented as a tiny CLI/help text consistency patch.
- Why:
  - This is a small real UX mismatch in `hermes_cli/config.py` and `hermes_cli/setup.py`.
  - The local help text still shows `hermes config set KEY VALUE` in several places.
  - Upstream switches that to placeholder syntax, which is clearer and more consistent with the rest of the CLI help surface.
  - The merge also bundles tests, which we should not import.
- Local implementation:
  - Update config and setup help text to use `hermes config set <key> <value>`.
  - Leave runtime behavior unchanged.
- Quick test path:
  - Run `hermes config`, `hermes config set` with missing args, and `hermes setup`, and confirm all displayed help/examples now use `<key> <value>` placeholder syntax consistently.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile hermes_cli\config.py hermes_cli\setup.py`

### PR #1323

- Title: `fix: smart vision setup that respects the user's chosen provider`
- Status: Evaluated locally.
- Decision: Skip, already functionally covered in the fork.
- Why:
  - This is a real upstream setup-flow improvement, but the local fork already has the substantive behavior in `hermes_cli/setup.py`.
  - The current local setup flow already:
    - reports vision availability through the real runtime resolver in the setup summary
    - avoids treating vision as OpenRouter-only
    - prompts separately for OpenRouter only for web + Mixture of Agents when needed
    - offers a dedicated optional vision setup step only when `_has_runtime_vision_backend()` is false
    - allows direct auxiliary vision configuration through an OpenAI-compatible endpoint instead of hard-coding one provider path
  - That means the core bug `#1323` fixes upstream is already solved locally, and the fork’s current version is actually broader than the upstream patch.
  - The merge also bundles tests, which we should not import.
- Quick test path:
  - Run `hermes setup` with a provider that already supports vision and confirm the separate vision prompt is skipped.
  - Run `hermes setup` with a provider that does not support vision natively and confirm the optional vision step appears.
  - Confirm the setup summary reflects the real runtime vision availability instead of only checking for OpenRouter.
- Test policy note:
  - No upstream tests were copied.

### PR #1327

- Title: `Merging the non-redundant fixes salvaged from #993 onto current main, plus adjacent trajectory compressor hardening found during review.`
- Status: Integrated locally.
- Decision: Take partially, implemented as a narrow three-part runtime patch.
- Why:
  - The merge bundles three small runtime fixes plus tests.
  - The local gaps are still real:
    - `environments/agent_loop.py` resizes the tool thread pool without shutting down the previous executor
    - `gateway/delivery.py` still uses a two-tuple local dedupe key that can miss the current seen-platform key shape
    - `trajectory_compressor.py` still assumes summary-model output is always a string and normalizes the summary prefix inline in two duplicate places
  - These are useful local hardening fixes, but the upstream tests should not be imported.
- Local implementation:
  - Update `environments/agent_loop.py` so `resize_tool_pool()` shuts down the previous executor after swapping in the new one.
  - Update `gateway/delivery.py` so the local logging dedupe key matches the same tuple shape used elsewhere in delivery target deduplication.
  - Update `trajectory_compressor.py` to normalize summary-model output more defensively:
    - coerce non-string content safely
    - ensure the `[CONTEXT SUMMARY]:` prefix is applied exactly once through a shared helper
- Quick test path:
  - Resize the agent loop tool pool repeatedly and confirm no old executors are left hanging.
  - Use gateway delivery with `always_log_local` enabled and confirm local delivery is deduped correctly alongside other targets.
  - Force or simulate a summary-model response with non-string or oddly prefixed content and confirm the compressor always emits a clean `[CONTEXT SUMMARY]: ...` line.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile environments\agent_loop.py gateway\delivery.py trajectory_compressor.py`

### PR #1328

- Title: `Salvaged PR #1012 onto current main with the contributor commit preserved plus a small follow-up for builtin-provider shadowing and stale test cleanup.`
- Status: Integrated locally.
- Decision: Take, implemented as a narrow runtime-provider patch for named saved custom providers.
- Why:
  - This is a real local gap in `hermes_cli/runtime_provider.py`.
  - The fork already supports saved custom providers in the broader config/UI flow, but the runtime resolver still only handles:
    - built-in providers
    - plain `custom`
    - config-saved `model.base_url` fallback for the generic custom case
  - It does not yet resolve a specifically named saved custom provider from `custom_providers`, such as:
    - `custom:local`
    - or a raw saved custom provider name when it does not collide with a built-in provider
  - The upstream follow-up for builtin-provider shadowing also matters here: raw names should not override real built-in provider names or aliases.
  - The merge also bundles tests, which we should not import.
- Local implementation:
  - Add named custom-provider lookup in `hermes_cli/runtime_provider.py` using saved entries from `custom_providers`.
  - Support both `custom:<name>` and non-conflicting raw custom-provider names.
  - Keep built-in provider names and aliases taking precedence over saved custom-provider names.
  - Route successful named custom-provider resolution through the existing chat-completions runtime shape.
- Quick test path:
  - Save a named custom provider under `custom_providers` and request it explicitly via `custom:<name>`.
  - Confirm runtime resolution uses that provider’s saved `base_url` and `api_key`.
  - Try a raw name that matches a built-in provider alias and confirm Hermes still resolves the built-in provider instead of the custom one.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile hermes_cli\runtime_provider.py`

### PR #949

- Title: `fix(cron): handle naive legacy timestamps in due-job checks`
- Status: Integrated locally.
- Decision: Take, implemented as a narrow cron timestamp-compatibility patch.
- Why:
  - The local `cron/jobs.py` already has partial naive-datetime handling, but it is not the same behavior as upstream.
  - Current local logic attaches the Hermes configured timezone directly to naive stored timestamps.
  - Upstream’s fix is more correct for backward compatibility:
    - interpret legacy naive timestamps as system-local wall time, which is how they were originally created
    - then convert them into Hermes’ configured timezone before due-job comparison
  - That matters when users change timezone settings after older naive cron timestamps were already stored.
  - The merge also bundles tests, which we should not import.
- Local implementation:
  - Replace the current naive timestamp coercion in `cron/jobs.py` with an `_ensure_aware(...)` helper matching the upstream compatibility behavior.
  - Use it in due-job checks and next-run calculations.
  - Keep the rest of cron storage/runtime behavior unchanged.
- Quick test path:
  - Create or simulate legacy cron jobs with naive `next_run_at` / `run_at` timestamps.
  - Change the Hermes configured timezone or run under a different local timezone context.
  - Confirm due-job checks still interpret those legacy timestamps correctly instead of shifting them as if they were already in the target timezone.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile cron\jobs.py`

### PR #950

- Title: `docs: conditional skill activation — duckduckgo-search fallback + documentation`
- Status: Evaluated locally.
- Decision: Skip for now.
- Why:
  - The merge itself is docs plus skill metadata only:
    - CONTRIBUTING documentation
    - website docs
    - one `fallback_for_toolsets: [web]` metadata addition to the DuckDuckGo skill
  - The local fork already has the DuckDuckGo skill content itself.
  - The underlying conditional-skill-activation runtime is not present locally yet, so importing just the metadata key would be a no-op today.
  - Under the fork policy, upstream website/docs content should not be imported during this sync pass.
  - If the conditional skill activation runtime lands later, we can revisit the DuckDuckGo metadata then.
- Quick test path:
  - No runtime verification needed for this merge as skipped.
  - Sanity-check that the existing DuckDuckGo fallback skill remains available through the current local skills flow.
- Test policy note:
  - No upstream tests were copied.

### PR #954

- Title: `fix(config): atomic write for .env to prevent API key loss on crash`
- Status: Integrated locally.
- Decision: Take, implemented as a narrow `.env` persistence hardening patch.
- Why:
  - This is a real local gap in `hermes_cli/config.py`.
  - The current `save_env_value()` still rewrites `~/.hermes/.env` in place.
  - That means an interrupted write can still truncate or corrupt the secrets file and lose API keys.
  - Upstream’s fix is small and clean:
    - write to a temp file in the same directory
    - flush and fsync
    - atomically replace the target file
    - clean up the temp file on failure
- Local implementation:
  - Update `save_env_value()` in `hermes_cli/config.py` to use same-directory temp-file atomic writes for `~/.hermes/.env`.
  - Keep the existing UTF-8 normalization and permission-hardening behavior.
- Quick test path:
  - Update one or more env values through `hermes config set` or setup flows.
  - Confirm `~/.hermes/.env` is rewritten successfully and still contains the full file contents.
  - Sanity-check that repeated updates do not leave orphaned temp files behind.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile hermes_cli\config.py`

### PR #955

- Title: `fix(vision): log error when vision client is unavailable + doctor MiniMax fix`
- Status: Integrated locally.
- Decision: Take partially, implemented as a tiny vision logging patch only.
- Why:
  - The actual runtime change in this merge is a one-line logging improvement in `tools/vision_tools.py`.
  - The local tool still returns the “vision analysis unavailable” error JSON when no auxiliary vision client is configured, but it does not log that condition.
  - The logging addition is useful for debugging and safe to take.
  - The “doctor MiniMax fix” part is not present in the runtime diff here, so there is nothing else to port from this merge in the current repo state.
- Local implementation:
  - Add an explicit `logger.error(...)` line before returning the “vision analysis unavailable” result when the auxiliary vision client is missing.
  - Leave the rest of the tool behavior unchanged.
- Quick test path:
  - Run a vision request with no configured vision backend.
  - Confirm the returned JSON is unchanged for the user-facing failure case.
  - Confirm the logs now record the missing-vision-client condition explicitly.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile tools\vision_tools.py`

### PR #960

- Title: `fix: add exc_info=True to image generation error logging`
- Status: Integrated locally.
- Decision: Take, implemented as a tiny logging hardening patch.
- Why:
  - The actual runtime change in this merge is small and still missing locally in `tools/image_generation_tool.py`.
  - The image generation tool currently logs failures, but it does not include traceback context for:
    - image upscaling failures
    - main image generation failures
  - Adding `exc_info=True` improves debugging without changing tool behavior or user-facing responses.
- Local implementation:
  - Add `exc_info=True` to the error logs in `tools/image_generation_tool.py` for:
    - `_upscale_image(...)`
    - `image_generate_tool(...)`
  - Leave the rest of the tool behavior unchanged.
- Quick test path:
  - Trigger an image generation failure and confirm the returned JSON is unchanged.
  - Confirm logs now include traceback context for the failure.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile tools\image_generation_tool.py`

### PR #1003

- Title: `feat: centralized provider router, call_llm API, unified /model command`
- Status: Integrated locally in Stage 1 only.
- Decision: Take partially, implemented as a staged local integration rather than a wholesale transplant.
- Why:
  - This is a real foundational gap, not just cleanup.
  - The local `agent/auxiliary_client.py` still uses the older ad-hoc auxiliary client pattern:
    - no centralized `resolve_provider_client(...)`
    - no centralized `call_llm(...)` / `async_call_llm(...)`
    - multiple auxiliary consumers still manage provider/client behavior separately
  - The upstream merge also bundles a broad CLI `/model` command unification and a large wave of consumer migrations.
  - Taking the entire merge wholesale would be too risky in this fork because we have already made several fork-local provider/runtime changes after this point.
  - The useful path is to take the provider-router foundation first, then migrate consumers onto it in a controlled way.
- Local implementation:
  - Stage 1 completed in `agent/auxiliary_client.py`:
    - added centralized provider-router helpers
    - added `resolve_provider_client(...)`
    - added `call_llm(...)` and `async_call_llm(...)`
    - added shared task-kind/model resolution helpers for text vs vision auxiliary calls
    - preserved current provider behavior and fork-local runtime choices by routing through the existing local client-resolution paths
  - Stage 2 intentionally deferred:
    - auxiliary consumer migration remains a separate follow-up
  - Stage 3 intentionally deferred:
    - `/model` command unification still needs a separate fork-local evaluation
- Quick test path:
  - Run auxiliary text tasks and confirm the new router surface can still resolve the correct provider/model across OpenRouter, Nous, Codex, and custom endpoint cases.
  - Run a small direct smoke path against `call_llm(...)` / `async_call_llm(...)` in the next consumer-migration step to confirm request dispatch stays aligned with current provider behavior.
  - Sanity-check fallback behavior when no auxiliary provider is configured.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile agent\auxiliary_client.py`

### PR #1018

- Title: `feat: versioning infrastructure + release script + v0.2.0 changelog`
- Status: Integrated locally.
- Decision: Take partially, implemented as a narrow local version-metadata cleanup only.
- Why:
  - Most of this merge is release-process content we should not import into the fork as part of selective upstream sync:
    - `scripts/release.py`
    - `RELEASE_v0.2.0.md`
    - related release-version bump churn
  - But there is still a small real local runtime/UX issue in the current tree:
    - `hermes_cli.__version_`_ is still set to `"v1.0.0"` with a leading `v`
    - `hermes_cli.main.cmd_version()` prints `f"Hermes Agent v{__version__}"`, which can produce a doubled `v`
    - `pyproject.toml` still reports `0.1.0`, so package metadata and CLI version metadata are out of sync
  - The useful local part of the upstream merge is the version-plumbing cleanup:
    - normalize `__version__` to a plain numeric string
    - add release-date metadata if we want the richer banner/version display
    - align the package version field with the CLI metadata
  - The release script and changelog should stay out of scope for this fork sync pass.
- Proposed local implementation:
  - Update `hermes_cli/__init__.py` so `__version__` is a plain version string and add `__release_date__`.
  - Update `hermes_cli/main.py` and `hermes_cli/banner.py` so version display is consistent and does not double-prefix `v`.
  - Update `pyproject.toml` to keep package metadata aligned with the CLI version metadata.
  - Do not import `scripts/release.py` or `RELEASE_v0.2.0.md`.
- Local implementation:
  - Set `hermes_cli.__version__` to `0.2.0` and added `__release_date__ = "2026.3.12"` in `hermes_cli/__init__.py`.
  - Updated `hermes_cli/main.py` so `hermes version` prints a single normalized version string with the release date.
  - Updated `hermes_cli/banner.py` so the interactive banner title uses the same normalized version metadata.
  - Updated `pyproject.toml` from `0.1.0` to `0.2.0` to keep package metadata aligned.
  - Intentionally did not import `scripts/release.py` or `RELEASE_v0.2.0.md`.
- Quick test path:
  - Run `hermes version` and confirm it prints a single normalized version string, optionally with the release date.
  - Start the interactive CLI and confirm the banner title uses the same normalized version metadata.
  - Sanity-check that package metadata in `pyproject.toml` matches the displayed version.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile hermes_cli\__init__.py hermes_cli\banner.py hermes_cli\main.py`

### PR #1040

- Title: `feat: include session ID in system prompt via --pass-session-id flag`
- Status: Integrated locally.
- Decision: Take, implemented locally as a narrow CLI/runtime flag patch.
- Why:
  - This merge is small, self-contained, and still missing locally.
  - The current local CLI already creates and persists a session ID, but it does not offer a way to pass that ID into the agent's system prompt.
  - The upstream behavior is opt-in via a flag, so it does not change default behavior or leak session identifiers unless the user explicitly asks for it.
  - The diff only touches `cli.py`, `hermes_cli/main.py`, and `run_agent.py`, with no test or release-process spillover.
- Proposed local implementation:
  - Add `--pass-session-id` to the top-level CLI and `chat` subcommand in `hermes_cli/main.py`.
  - Thread that flag through `cmd_chat(...)` into `cli.py` and then into `AIAgent`.
  - In `run_agent.py`, append a `Session ID: ...` line next to the existing conversation-start timestamp only when the flag is enabled and a session ID exists.
  - Leave default behavior unchanged when the flag is not provided.
- Local implementation:
  - Added `--pass-session-id` to the top-level CLI and `chat` subcommand in `hermes_cli/main.py`.
  - Threaded the flag through `cmd_chat(...)` into `cli.py` and then into `AIAgent`.
  - Updated `run_agent.py` so the system prompt adds `Session ID: ...` below the conversation-start timestamp only when the flag is enabled and a session ID exists.
  - Left default behavior unchanged when the flag is not provided.
- Quick test path:
  - Run `hermes --pass-session-id` or `hermes chat --pass-session-id` and confirm the agent is initialized with the flag enabled.
  - Confirm the system prompt includes the current session ID only when the flag is set.
  - Sanity-check that normal CLI startup is unchanged without the flag.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile cli.py hermes_cli\main.py run_agent.py`

### PR #862

- Title: `Merging — clean fix for local skills mislabeling. Follow-up cleanup coming.`
- Status: Integrated locally.
- Decision: Take, implemented locally as a narrow skills-source provenance fix.
- Why:
  - This is a real local gap in the current fork.
  - `hermes skills list` currently only distinguishes:
    - hub-installed skills
    - everything else as `builtin`
  - That means user-created local skills under the skills directory are mislabeled as builtins.
  - The upstream fix is small and clean:
    - add `local` as a distinct source classification
    - derive builtin names from the bundled manifest rather than treating all non-hub skills as builtin
    - expose `--source local` in the CLI and help text
  - The merge includes tests, which we should not import.
- Proposed local implementation:
  - Update `hermes_cli/skills_hub.py` so `do_list(...)` distinguishes `hub`, `builtin`, and `local` skills.
  - Use the bundled manifest to identify actual builtin skill names.
  - Update `hermes_cli/main.py` so `hermes skills list --source` accepts `local`.
  - Update help text in `hermes_cli/skills_hub.py` to document `--source hub|builtin|local`.
- Local implementation:
  - Updated `hermes_cli/skills_hub.py` so `do_list(...)` now distinguishes `hub`, `builtin`, and `local` skills instead of treating every non-hub skill as builtin.
  - Used the bundled manifest to identify actual builtin skill names.
  - Updated `hermes_cli/main.py` so `hermes skills list --source` accepts `local`.
  - Updated the `/skills` help text to document `--source hub|builtin|local`.
- Quick test path:
  - Create a local skill that is not hub-installed and not bundled.
  - Run `hermes skills list` and confirm it shows `local` instead of `builtin`.
  - Run `hermes skills list --source local` and confirm only local skills are shown.
  - Sanity-check that bundled skills still show as `builtin` and hub-installed skills still show as `hub`.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile hermes_cli\main.py hermes_cli\skills_hub.py`

### PR #1053

- Title: `chore(skills): clean up PR #862 + feat(docs): add search to Docusaurus`
- Status: Evaluated.
- Decision: Skip, already functionally covered for the runtime-relevant part.
- Why:
  - Most of this merge is website-only:
    - local search plugin wiring in `website/docusaurus.config.ts`
    - `website/package.json`
    - `website/package-lock.json`
  - The remaining Python diff is a tiny cleanup to the `#862` skills-source fix:
    - `builtin_names = set(_read_manifest())`
  - In the current fork, `tools.skills_sync._read_manifest()` already returns a dict, and the local implementation in `hermes_cli/skills_hub.py` uses `set(bundled_manifest.keys())`, which is already correct for that return shape.
  - So there is no additional runtime behavior to port from this merge.
- Quick test path:
  - Run `hermes skills list` and confirm builtin/local/hub labeling still works after the `#862` integration.
  - Sanity-check that no website/docs dependencies were imported.
- Test policy note:
  - No upstream tests were copied.

### PR #1058

- Title: `fix: strip call_id/response_item_id from tool_calls for Mistral compatibility`
- Status: Integrated locally.
- Decision: Take, implemented locally as a narrow strict-provider sanitization patch.
- Why:
  - This is a real local gap in `run_agent.py`.
  - The current fork already strips some internal-only fields like `reasoning` and `finish_reason` before sending Chat Completions payloads.
  - But assistant `tool_calls` can still retain Codex Responses API-specific fields such as:
    - `call_id`
    - `response_item_id`
  - Strict providers like Mistral reject unknown Chat Completions fields with 422 errors.
  - The upstream fix is tightly scoped and low-risk:
    - sanitize only the outgoing API copy
    - preserve the internal message history with the extra fields intact
    - apply the sanitization only for strict providers
- Proposed local implementation:
  - Add a helper in `run_agent.py` that strips `call_id` and `response_item_id` from outgoing `tool_calls` without mutating the internal message history.
  - Use it in `_prepare_api_messages(...)` for strict providers like Mistral.
  - Use it in the memory flush API-message builder as well, since that path also constructs outgoing assistant/tool-call messages separately.
  - Leave Codex/internal session behavior unchanged.
- Local implementation:
  - Added a helper in `run_agent.py` that strips `call_id` and `response_item_id` from outgoing `tool_calls` without mutating the internal message history.
  - Applied it in `_prepare_api_messages(...)` for strict providers like Mistral.
  - Applied it in the memory flush API-message builder as well, since that path constructs outgoing assistant/tool-call messages separately.
  - Left Codex/internal session behavior unchanged.
- Quick test path:
  - Run a session against a strict Chat Completions provider such as Mistral after a tool-calling turn.
  - Confirm follow-up requests no longer fail with unknown-field 422 errors on `tool_calls`.
  - Sanity-check that Codex Responses mode still retains internal `call_id` / `response_item_id` metadata in the stored session messages.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile run_agent.py`

### PR #1098

- Title: `fix: eliminate execute_code progress spam on gateway platforms`
- Status: Integrated locally.
- Decision: Take partially, as a narrow local display/progress dedup patch.
- Why:
  - The current fork already has a more advanced gateway progress system than the upstream diff, so we should not transplant the whole progress-queue implementation.
  - But two real local gaps from this merge still apply:
    - `agent/display.py` still lets multiline text leak into tool previews instead of collapsing it to one line
    - `gateway/run.py` still records repeated identical progress/detail events separately, so `execute_code`-style loops can spam the rolling gateway status output
  - The useful local path is to keep the current richer progress system and add only:
    - one-line preview normalization
    - repeated progress/detail dedup for gateway updates
- Proposed local implementation:
  - Add a small whitespace-collapsing helper in `agent/display.py` and use it for preview text that can contain multiline input.
  - In `gateway/run.py`, deduplicate consecutive identical tool-progress details before they are added to the rolling progress state and detail backlog.
  - Keep the current browser bridge / gateway progress architecture intact.
- Local implementation:
  - Added a small whitespace-collapsing helper in `agent/display.py` and used it for preview text that can contain multiline input.
  - Updated `gateway/run.py` to deduplicate consecutive identical live progress details before they are added to the rolling progress state.
  - Updated `gateway/run.py` to collapse consecutive identical detail-backlog entries with a repeat counter instead of enqueueing each duplicate separately.
  - Kept the current browser bridge / gateway progress architecture intact.
- Quick test path:
  - Trigger repeated `execute_code` calls with effectively identical code snippets on a gateway platform.
  - Confirm the live progress message stops growing with duplicate repeated entries.
  - Sanity-check that multiline tool previews are rendered as single-line summaries instead of embedding raw newlines.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile agent\display.py gateway\run.py`

### PR #953

- Title: `Fix several documentation typos across training references`
- Status: Integrated locally as a content-only refresh.
- Decision: Take selectively as a bundled skill-reference content refresh.
- Why:
  - This merge touches only bundled training-skill reference files under `skills/mlops/training/.../references/`.
  - There is no runtime, CLI, gateway, config, or dependency behavior change in the diff.
  - The changes are typo and wording cleanups inside large reference documents.
  - These fixes are content-only rather than runtime-critical, but they are safe to import when we intentionally want a bundled skill-doc refresh.
- Local implementation:
  - Imported the typo and wording fixes for the bundled skill reference files that exist in this fork:
    - `skills/mlops/axolotl/references/api.md`
    - `skills/mlops/unsloth/references/llms-full.md`
    - `skills/mlops/unsloth/references/llms-txt.md`
    - `skills/mlops/unsloth/references/llms.md`
  - Did not import the upstream `pytorch-fsdp` reference changes because that bundled skill path does not exist in the current fork tree.
- Quick test path:
  - Open the refreshed bundled reference files and confirm the wording fixes are present.
  - No runtime verification needed because this is content-only.
- Test policy note:
  - No upstream tests were copied.

### PR #1288

- Title: `fix: reliably notify gateway users when updates finish`
- Status: Integrated locally via the underlying gateway update feature train.
- Decision: Take, but only as a coherent local gateway `/update` feature slice plus the reliable-notification fix.
- Why:
  - The upstream `#1288` fix sits on top of an earlier gateway `/update` feature train that was not present locally.
  - To make the notification fix meaningful in the fork, we first needed the smallest coherent local implementation of:
    - gateway `/update` command routing
    - detached update subprocess launch
    - marker files under `~/.hermes/`
    - completion watcher / notification delivery
    - executable resolution that works in local install modes
  - The local implementation was adapted to play nicely with this fork's current gateway lifecycle and Windows-safe constraints:
    - kept the current gateway startup/status architecture
    - used a detached Python wrapper to capture update output and write exit markers cross-platform
    - resolved Hermes via `hermes` first, then `sys.executable -m hermes_cli.main`
- Local implementation:
  - Added gateway `/update` command routing and help text in `gateway/run.py`.
  - Added detached gateway update execution with output capture and exit-code markers:
    - `.update_pending.json`
    - `.update_pending.claimed.json`
    - `.update_output.txt`
    - `.update_exit_code`
  - Added `_schedule_update_notification_watch(...)`, `_watch_for_update_completion(...)`, and `_send_update_notification(...)` in `gateway/run.py`.
  - Hooked startup to send an already-finished notification immediately or schedule a watcher if the update is still running.
  - Added Discord slash command wiring for `/update` in `gateway/platforms/discord.py`.
- Quick test path:
  - Run `/help` on a gateway platform and confirm `/update` is available.
  - Trigger `/update` from a gateway chat and confirm Hermes replies that the update started.
  - Confirm the user receives a follow-up success or failure notification when the update process finishes.
  - Sanity-check that the fallback executable resolution works when Hermes is launched from a venv or module invocation.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile gateway\run.py gateway\platforms\discord.py`

### PR #1287

- Title: `fix(gateway): avoid slash-command crash with GatewayConfig`
- Status: Reviewed.
- Decision: Skip for now.
- Why:
  - The upstream merge fixes a typed-config crash in a gateway quick-command path that assumes `self.config.get(...)` even when `self.config` is a `GatewayConfig` object.
  - In the current fork, that quick-command feature surface is not present locally:
    - `gateway/config.py` does not define `quick_commands` on `GatewayConfig`
    - `load_gateway_config()` does not bridge `quick_commands` from `config.yaml`
    - `gateway/run.py` does not contain the user-defined quick-command dispatch block that the upstream fix patches
  - So this is not a narrow local bug on top of an existing feature. It belongs with any future import of the gateway quick-commands feature train, not as a standalone sync patch.
- Quick test path:
  - Run gateway slash commands such as `/help`, `/new`, `/retry`, and `/update` and confirm they route through the existing explicit command handlers.
  - Sanity-check that there is no current user-configurable gateway `quick_commands` surface to exercise.
- Test policy note:
  - No upstream tests were copied.

### PR #1294

- Title: `fix(update): salvage autostash update flow from PR #978`
- Status: Integrated locally.
- Decision: Take, implemented locally in a narrow local shape.
- Why:
  - This is a real local gap in the current fork.
  - `hermes_cli/main.py` still performs `git pull` directly in `cmd_update(...)` even when the worktree has local modifications or untracked files.
  - `scripts/install.sh` likewise updates an existing checkout in place with `git checkout` + `git pull` and no autostash protection.
  - That means local edits can block updates or produce a rough/confusing failure path instead of a safer update flow.
  - The useful upstream slice is small and maps cleanly to the fork:
    - detect local changes
    - stash them before pulling
    - restore them afterward
    - keep them preserved in `git stash` if restore fails or the user declines restore interactively
  - Upstream tests should not be imported.
- Proposed local implementation:
  - Add a small autostash helper pair in `hermes_cli/main.py` for `cmd_update(...)`.
  - Use the existing `git_cmd` / remote-branch fallback logic already present locally and wrap only the pull phase.
  - Add the same autostash protection to the existing-update path in `scripts/install.sh`.
  - Keep the implementation Windows-safe and avoid broad update-flow refactors.
- Local implementation:
  - Added `_stash_local_changes_if_needed(...)` and `_restore_stashed_changes(...)` in `hermes_cli/main.py`.
  - Wrapped the git pull phase in `cmd_update(...)` so local tracked and untracked changes are stashed before update and restored afterward.
  - Preserved the current remote-branch fallback logic and dependency refresh flow.
  - Added matching autostash/restore protection to the existing-checkout update path in `scripts/install.sh`.
  - Kept restore failures non-destructive by leaving the user's changes preserved in `git stash` with a manual recovery hint.
- Quick test path:
  - Make a tracked local modification plus an untracked file, then run `hermes update`.
  - Confirm Hermes stashes changes, updates, and then restores them or leaves them safely in `git stash` if restoration fails.
  - Sanity-check that a clean worktree still updates exactly as before.
  - Sanity-check that the installer update path behaves the same way on an existing checkout.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile hermes_cli\main.py`
  - `python -c "from pathlib import Path; import subprocess; p=Path('scripts/install.sh'); q=Path('scripts/install.syntaxcheck.sh'); q.write_text(p.read_text(encoding='utf-8', errors='replace').replace('\r\n','\n'), encoding='utf-8', newline='\n'); r=subprocess.run(['bash','-n',q.as_posix()]); q.unlink(); raise SystemExit(r.returncode)"`

### PR #1303

- Title: `feat(skills): integrate skills.sh as a hub source`
- Status: Partially integrated locally (Stage 1).
- Decision: Optional take, implemented locally as Stage 1 of a staged feature effort.
- Why:
  - This is a real missing feature surface locally, not an already-covered fix.
  - The current fork does not have:
    - `SkillsShSource`
    - `WellKnownSkillSource`
    - stored bundle metadata in the hub lock file
    - `hermes skills check`
    - `hermes skills update`
  - The upstream merge is large and bundled:
    - new source adapters and identifier formats
    - new update-checking lifecycle for installed hub skills
    - richer inspect/install metadata
    - CLI and slash-command surface expansion
    - docs and tests, which we should not import wholesale
  - That makes this better treated as a product feature train than a one-shot narrow bugfix sync.
- Recommended local path:
  - Stage 1: add `skills.sh` and well-known discovery/fetch adapters in `tools/skills_hub.py`.
  - Stage 2: persist source metadata needed for future update checks.
  - Stage 3: add `hermes skills check` / `hermes skills update` plus the matching `/skills` subcommands.
  - Stage 4: optionally bring over the richer inspect metadata panels once the source plumbing exists.
- Local implementation:
  - Added `SkillsShSource` in `tools/skills_hub.py`, backed by the public `https://skills.sh/api/search` search endpoint and the existing `GitHubSource` fetch/inspect path.
  - Added `WellKnownSkillSource` in `tools/skills_hub.py` for sites exposing `/.well-known/skills/index.json`.
  - Registered both adapters in `create_source_router(...)`.
  - Updated `hermes_cli/main.py` so `hermes skills search --source` accepts `skills-sh` and `well-known`.
  - Updated `/skills search` usage te1xt in `hermes_cli/skills_hub.py` to document the new source filters.
  - Intentionally did not implement Stage 2/3 yet:
    - no hub lock metadata persistence for upstream bundle provenance
    - no `hermes skills check`
    - no `hermes skills update`
    - no richer inspect metadata panel
- Quick test path:
  - Search a `skills.sh` query and a well-known endpoint URL once adapter support exists.
  - Install a hub skill from one of those sources and confirm provenance metadata is stored.
  - Run `hermes skills check` and `hermes skills update` to verify update detection/reinstall behavior.
- Test policy note:
  - No upstream tests were copied.
- Verification:
  - `venv\Scripts\python.exe -m py_compile tools\skills_hub.py hermes_cli\skills_hub.py hermes_cli\main.py`
  - `venv\Scripts\python.exe -c "from tools.skills_hub import GitHubAuth, SkillsShSource, WellKnownSkillSource; s=SkillsShSource(GitHubAuth()); r=s.search('react', limit=2); print('skills-sh', len(r), r[0].identifier if r else ''); w=WellKnownSkillSource(); q=w.search('https://mintlify.com/docs', limit=2); print('well-known', len(q), q[0].identifier if q else '')"`

### PR #1355

- Title: `Salvaged PR #1052 onto current main with the contributor commit preserved plus a small follow-up for current-main conflict resolution and safe command quoting.`
- Status: Reviewed.
- Decision: Skip, already functionally covered.
- Why:
  - The upstream merge tightens the gateway `/update` command by:
    - resolving the Hermes executable as argv parts rather than a single string
    - shell-quoting multi-part commands safely
    - improving the missing-executable error text
  - The current fork already has the substantive behavior in `gateway/run.py`:
    - `_resolve_hermes_bin()` returns argv parts
    - `/update` falls back to `sys.executable -m hermes_cli.main`
    - the gateway update launcher uses a detached Python wrapper with `subprocess.run(cmd, ...)` instead of shell-building `hermes update`
  - That means the shell-quoting hazard upstream fixed does not apply to the local implementation, because the current fork never shell-joins the Hermes command for execution.
  - The local gateway `/update` flow is already broader and safer than the upstream patch shape.
- Quick test path:
  - Trigger `/update` from a gateway chat in an environment where the `hermes` shim is not on PATH.
  - Confirm Hermes still launches the update through the `sys.executable -m hermes_cli.main` fallback.
  - Sanity-check that paths with spaces do not break the detached update flow.
- Test policy note:
  - No upstream tests were copied.

### PR #1375

- Title: `feat: add direct endpoint overrides for auxiliary and delegation`
- Status: Integrated in the local config/runtime shape.
- Decision: Integrated partially in the local config/runtime shape.
- Why:
  - This is a real missing slice on top of the Stage 1 auxiliary routing foundation already integrated from `#1003`.
  - The current fork has centralized auxiliary provider routing, but it still does not support per-task direct endpoint overrides such as:
    - `AUXILIARY_VISION_BASE_URL`
    - `AUXILIARY_VISION_API_KEY`
    - `AUXILIARY_WEB_EXTRACT_BASE_URL`
    - `AUXILIARY_WEB_EXTRACT_API_KEY`
  - The current config defaults did not include a dedicated `auxiliary.web_extract` block, and the runtime/config bridge still needed to carry the task-specific direct endpoint settings through to the shared helper layer.
  - The delegation direct-endpoint path is already present locally, so this turn only needed to preserve compatibility with it rather than re-add it.
  - The useful local slice is the runtime/config bridge only; upstream tests and docs should not be imported wholesale.
- Local integration notes:
  - Added `auxiliary.web_extract` config defaults in `hermes_cli/config.py`, alongside the existing `auxiliary.text` and `auxiliary.vision` task blocks.
  - Patched `agent/auxiliary_client.py` so the centralized auxiliary router now accepts explicit `base_url` / `api_key` overrides, resolves task-specific auxiliary overrides, and supports env/config-driven direct endpoint routing for `text`, `vision`, and `web_extract`.
  - Added task-specific environment override support for:
    - `AUXILIARY_TEXT_PROVIDER` / `MODEL` / `BASE_URL` / `API_KEY`
    - `AUXILIARY_VISION_PROVIDER` / `MODEL` / `BASE_URL` / `API_KEY`
    - `AUXILIARY_WEB_EXTRACT_PROVIDER` / `MODEL` / `BASE_URL` / `API_KEY`
  - Patched `cli.py` and `gateway/run.py` so those auxiliary task overrides are bridged from config into the runtime environment consistently for both CLI and gateway sessions.
  - Patched `tools/web_tools.py` so the auxiliary client lookup for extraction runs under the explicit `web_extract` task key instead of the generic text task.
  - Delegation direct-endpoint support was already present locally in `tools/delegate_tool.py`, so no new delegation runtime patch was needed in this turn.
  - Verification:
    - `venv\Scripts\python.exe -m py_compile agent\auxiliary_client.py tools\web_tools.py cli.py gateway\run.py hermes_cli\config.py tools\delegate_tool.py`
  - Test policy note:
    - No upstream tests were copied.
- Quick test path:
  - Configure `auxiliary.vision.base_url` + `api_key` and confirm vision calls route to that endpoint without changing the main provider.
  - Set `AUXILIARY_WEB_EXTRACT_BASE_URL` / `API_KEY` and confirm web extraction uses the override.
  - Configure `delegation.base_url` / `api_key` / `model` and confirm subagents use that endpoint instead of inheriting the parent provider.
- Test policy note:
  - No upstream tests were copied.
