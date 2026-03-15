# Upstream Merge Reconciliation Report

This report compares:

- Upstream first-parent merge history: `main..upstream/main`
- Local tracking ledger: `docs/upstream-integration-ledger.md`

This is a strict chronology/source-of-truth reconciliation, not a trust-based summary.

## Snapshot

- Total upstream merges in range: `330`
- PR-numbered merges: `302`
- Non-PR merges: `28`
- Ledger PR entries: `172`
- PR merges missing from ledger: `138`
- Ledger PR IDs not in upstream first-parent merge list: `6`
- Duplicate PR entries in ledger: `2`

## Process Drift Confirmed

The ledger is incomplete and internally inconsistent relative to upstream merge history.

### Missing from ledger

- `138` upstream PR merges are not logged at all.

### Duplicated in ledger

- `#1375` appears twice.
- `#1394` appears twice and has conflicting treatment history.

### Logged PR IDs not in first-parent upstream merge list

- `43, 174, 176, 178, 217, 1359`

## Missing PR Merges by Risk Bucket

- `security/auth`: `8`
- `gateway/runtime`: `23`
- `runtime/core`: `92`
- `skills/content`: `9`
- `docs`: `5`
- `tests`: `1`

### `security/auth` missing PRs

- `434, 529, 600, 603, 698, 724, 757, 1128`

### `gateway/runtime` missing PRs

- `369, 538, 599, 611, 716, 720, 733, 736, 746, 754, 758, 761, 763, 766, 773, 779, 784, 810, 873, 1103, 1106, 1117, 1122`

### `runtime/core` missing PRs

- `446, 453, 457, 458, 533, 564, 565, 568, 594, 602, 607, 608, 616, 621, 627, 655, 679, 680, 686, 687, 700, 701, 702, 704, 705, 709, 711, 732, 734, 735, 740, 745, 748, 752, 755, 767, 769, 770, 792, 795, 796, 815, 840, 871, 881, 889, 891, 910, 912, 921, 947, 962, 963, 981, 1062, 1097, 1121, 1123, 1125, 1130, 1135, 1147, 1149, 1152, 1153, 1173, 1181, 1213, 1216, 1227, 1233, 1237, 1239, 1251, 1253, 1255, 1256, 1271, 1272, 1274, 1275, 1278, 1279, 1280, 1282, 1283, 1284, 1286, 1290, 1377, 1398, 1399`

### `skills/content` missing PRs

- `330, 551, 570, 598, 617, 743, 785, 854, 883`

### `docs` missing PRs

- `439, 713, 825, 1059, 1259`

### `tests` missing PRs

- `802`

## High-Priority Unlogged Merges (Security + Gateway Runtime)

These are likely the highest-value audit targets first.

### Security/auth (8)

- `#434` `1151f84351` `Merge PR #434: feat: add WebResearchEnv RL environment for multi-step web research`
- `#529` `805ce8177b` `Merge PR #529: fix: restrict .env file permissions to owner-only`
- `#600` `67fc6bc4e9` `Merge PR #600: fix(security): use in-memory set for permanent allowlist save`
- `#603` `695c017411` `Merge PR #603: fix: return deny on approval callback timeout instead of None`
- `#698` `2c21c4b897` `Merge PR #698: fix(security): pipe sudo password via stdin instead of shell cmdline`
- `#724` `586fe5d62d` `Merge PR #724: feat: --yolo flag to bypass all approval prompts`
- `#757` `6e303def12` `Merge PR #757: security: enforce 0600/0700 file permissions on sensitive files`
- `#1128` `15911d70c0` `Merge pull request #1128 from ASRagab/fix/adaptive-thinking-budget-tokens`

### Gateway/runtime (23)

- `#369` `3214c05e82` `Merge PR #369: fix(gateway): add missing UTF-8 encoding to file I/O`
- `#538` `88f8bcde38` `Merge PR #538: fix cron HERMES_HOME path mismatch, missing HomeAssistant toolset mapping, Daytona timeout drift`
- `#599` `cbca0225f6` `Merge PR #599: fix: strip MarkdownV2 italic markers in Telegram plaintext fallback`
- `#611` `8f0b07ed29` `Merge PR #611: fix(session): atomic write for sessions.json to prevent data loss on crash`
- `#716` `be2e259596` `Merge PR #716: fix: log exceptions instead of silently swallowing in cron scheduler`
- `#720` `c5e8166c8b` `Merge pull request #720 from NousResearch/feat/session-naming`
- `#733` `f88343a6da` `Merge PR #733: feat: interactive session browser with search filtering (#718)`
- `#736` `475dd58a8e` `Merge PR #736: feat(honcho): async writes, memory modes, session title integration, setup CLI`
- `#746` `3be6e8a5f2` `Merge PR #746: feat(cli,gateway): add user-defined quick commands that bypass agent loop`
- `#754` `a2d0d07109` `Merge PR #754: fix: stabilize system prompt across gateway turns for cache hits`
- `#758` `ea0a263434` `Merge PR #758: feat(discord): add DISCORD_ALLOW_BOTS config for bot message filtering`
- `#761` `4b619c9672` `Merge PR #761: Improve Discord gateway error handling and logging`
- `#763` `93230af7bd` `Merge PR #763: improve Telegram gateway error handling and logging`
- `#766` `fe9da5280f` `Merge pull request #766 from spanishflu-est1918/codex/telegram-topic-session-pr`
- `#773` `925f378baa` `Merge PR #773: feat(cli,gateway): add /personality none and custom personality support`
- `#779` `322ffbed61` `Merge PR #779: feat: Telegram native file attachment support (send_document + send_video)`
- `#784` `a5a5d82a21` `Merge pull request #784 from NousResearch/feat/slack-app-mention-and-documents`
- `#810` `bdce33e239` `Merge PR #810: fix(cli): handle unquoted multi-word session names in -c/--continue and -r/--resume`
- `#873` `6e851a1f6a` `Merge PR #873: fix: eliminate 3x SQLite message duplication in gateway sessions`
- `#1103` `4cb553c765` `fix: Slack thread handling - progress messages, responses, and session isolation (#1103)`
- `#1106` `df07baedfe` `feat: Slack adapter improvements - formatting, reactions, user resolution, commands (#1106)`
- `#1117` `3bc933586a` `fix: Slack MAX_MESSAGE_LENGTH + typing indicator via assistant.threads.setStatus (#1117)`
- `#1122` `28ffa8e693` `fix: slack file upload fallback loses thread context (#1122)`

## Full Unlogged PR ID List (138)

```text
330,369,434,439,446,453,457,458,529,533,538,551,564,565,568,570,594,598,599,600,602,603,607,608,611,616,617,621,627,655,679,680,686,687,698,700,701,702,704,705,709,711,713,716,720,724,732,733,734,735,736,740,743,745,746,748,752,754,755,757,758,761,763,766,767,769,770,773,779,784,785,792,795,796,802,810,815,825,840,854,871,873,881,883,889,891,910,912,921,947,962,963,981,1059,1062,1097,1103,1106,1117,1121,1122,1123,1125,1128,1130,1135,1147,1149,1152,1153,1173,1181,1213,1216,1227,1233,1237,1239,1251,1253,1255,1256,1259,1271,1272,1274,1275,1278,1279,1280,1282,1283,1284,1286,1290,1377,1398,1399
```

## Non-PR First-Parent Merges Also Missing from Ledger (28)

- `719f2eef32` `Merge branch 'pr-217'`
- `c4ea996612` `fix: repair flush sentinel test ? mock auxiliary client and add guard`
- `99bd69baa8` `Merge feat/modular-setup-wizard: modular setup wizard with section subcommands and tool-first UX`
- `5d7d76025a` `fix: setup wizard default max iterations 60 ? 90`
- `efb64aee5a` `fix: default MoA, Home Assistant, RL Training to off for new installs`
- `bb489a3903` `fix: add first_install flag to tools setup for reliable API key prompting`
- `52f92eb689` `fix: first-install tool setup shows all providers + skip options`
- `af67ea8800` `fix: setup wizard overwrites platform_toolsets saved by tools_command`
- `c21d77ca08` `Merge: OBLITERATUS skill v2.0 + unified gateway compression`
- `0dafdcab86` `Merge: skill reorganization + sub-category support`
- `7b63a787b3` `Merge: named custom providers in hermes model`
- `ff3f3169b2` `Merge: auto-save custom endpoints + removal option`
- `a7ad6f6d28` `Merge: custom providers instant activation + model persistence`
- `a34102049b` `Merge: vision auto-detection fallback to local endpoints`
- `8bc0d4f77d` `Merge: WebResearchEnv Atropos standards compliance`
- `a5c6348d41` `Merge: WebResearchEnv compute_reward fix (verified with live test)`
- `ab7dc22984` `Merge: WebResearchEnv evaluate() with full agent loop + tools`
- `d5811c887a` `Merge: fix double judge call + eval buffer pollution in WebResearchEnv`
- `3e352f8a0d` `fix: add upstream guard for non-dict function_args + tests for build_tool_preview`
- `5fc751e543` `Merge: fix(gateway) add metadata param to _keep_typing and base send_typing`
- `2210068f5b` `Merge: fix(signal) align send() signature with base class`
- `ad1fbd88b2` `Merge feature/background-command: add /background slash command`
- `fe29594716` `fix: replace blocking time.sleep with await asyncio.sleep in WhatsApp connect`
- `f524aed23e` `fix: clean up empty file after failed wl-paste clipboard extraction`
- `c837ef949d` `fix: replace debug print() with logger.error() in file_tools`
- `bcefc2a475` `fix(skills): improve 1password skill ? env var prompting, auth docs, broken examples`
- `973aa9b549` `fix(update): drop autostash by stash selector`
- `6c611c852e` `fix(update): clarify manual autostash cleanup`

## Logged But Not Fully Done (By Ledger’s Own Wording)

- `#1003` stage 1 only
- `#1303` stage 1 only
- `#1287` skip for now
- `#1429` skip for now
- `#950` skip for now

## How to Use This Report

If you want strict control and no repeated drift:

1. Treat this file as the backlog source, not freeform “ok next”.
2. Triage in this order:
   - Security/auth
   - Gateway/runtime
   - Runtime/core
3. For each PR: mark `skip/covered/integrate` with a hash and verification note.
4. Only after this reconciliation is exhausted, resume normal incremental upstream sync.

