# Capability Declaration — what brain does itself

> **Load when:** brain isn't sure whether to do task itself or ask user. Or when user asks «can you do X?».
>
> **Lazy-load trigger:** capability question, «можешь ли», «делай сам», unfamiliar tool/domain.

---

## Default reflex

Если задача fits a capability → выполняет САМ через tool. Don't ask user to do what brain can.

---

## Capability map

| Domain | Tool | Behaviour |
|---|---|---|
| Browser — **PRIMARY** (direct CDP — attach to running Chrome on port 9222) | **chrome-devtools MCP** (deferred — load via `ToolSearch select:mcp__chrome-devtools__*`) | САМ |
| Browser — **FALLBACK** (headless / scripted / CI scenarios) | Playwright MCP (deferred — load via `ToolSearch select:mcp__playwright__browser_*`) | САМ |
| DB read-only (stage / release) | `scripts/db-query.sh --db <name>` | САМ |
| YouTrack search/get/comments/links | youtrack MCP (`alwaysLoad` — no ToolSearch needed) | САМ (read-only) |
| Allure search/get/scenario | allure MCP (`alwaysLoad` — no ToolSearch needed, `include_scenario=true`) | САМ |
| Bugs index search (find dup) | python on `bugs.json` (3.6 MB — never `Read` whole) | САМ |
| Read KB (insights/rules/glossary/etc) | `Read knowledge_base/*.md` | САМ — but **conditional** (only if relevant to current task area, not all) |
| Journal (mission/log/save/standup/bug/blocker) | `scripts/journal.sh` | САМ |
| Brain-stats / cleanup-zombies | `scripts/brain-stats.py` etc. | САМ |
| Slack read (channel history, threads, users, profile) | **slack MCP** (deferred — load via `ToolSearch select:mcp__slack__*`) | САМ read · **draft + approval** для post/reply |
| YouTrack write (`create_bug`, `create_qa_subtask`, `add_comment`, `update_ticket_status`) | youtrack MCP | **two-step approval** (preview → `approved=true`) |
| Allure write (`create_test_case`) | allure MCP | **`approved=true` gate** |
| Slack write (`post_message`, `reply_to_thread`, `add_reaction`) | slack MCP | **DEFER — brain drafts, Yaroslav posts manually** (Slack write scope intentionally not granted) |
| 2FA Telegram code | — | pause + ask QA to type manually (Insight 7) |
| Screenshots (evidence) | macOS `screencapture` (preferred) OR Playwright `browser_take_screenshot` | САМ — address bar visible per `qa_workflow.md` Phase 3 |
| Release schedule cache | `scripts/refresh-release-schedule.py` | САМ (auto via scheduled task at 12:30 Vietnam Mon-Fri) |

---

## Pre-flight tool loading (deferred MCPs)

Some MCPs are deferred — schemas not loaded at session start. Their names appear in the deferred list (system-reminder), but calling them without `ToolSearch` first → `InputValidationError`.

**Rule:** if tool needed for task and it's not in active tools → `ToolSearch` FIRST, then call.

**Anti-pattern:** «MCP-тула для X не вижу в deferred списке» / «нет доступа к Slack» — это галлюцинация ограничения. Сначала `ToolSearch`, потом честный ответ если действительно не нашлось.

### Always-loaded (no ToolSearch needed)

`youtrack:*` + `allure:*` — `alwaysLoad: true` (v2.1.138+ via `.mcp.json`). Доступны сразу.

### Browser — PRIMARY: chrome-devtools-mcp (direct CDP — no wrapper)

**Calibrated 2026-05-14:** switched from Claude_in_Chrome (Anthropic extension) to `ChromeDevTools/chrome-devtools-mcp` (Google's official MCP). Reason: removes the extension as a middleman — brain talks raw CDP via WebSocket to a Chrome started with `--remote-debugging-port=9222`. Same session/cookies/2FA preserved, same VPN context.

**Setup (one-time):** start the CDP Chrome via launcher (idempotent, persistent profile):

```bash
./scripts/launch-chrome-cdp.sh         # start (or no-op if already up)
./scripts/launch-chrome-cdp.sh --status # check :9222 alive
./scripts/launch-chrome-cdp.sh --kill   # stop the CDP Chrome
```

Profile lives at `~/.chrome-cdp-profile` — log into CRM once, it persists across launches.

**Pre-flight (one-time per chat) — load tool schemas:**

```
ToolSearch(query="select:mcp__chrome-devtools__navigate_page,mcp__chrome-devtools__list_pages,mcp__chrome-devtools__new_page,mcp__chrome-devtools__select_page,mcp__chrome-devtools__close_page,mcp__chrome-devtools__click,mcp__chrome-devtools__fill,mcp__chrome-devtools__fill_form,mcp__chrome-devtools__hover,mcp__chrome-devtools__press_key,mcp__chrome-devtools__type_text,mcp__chrome-devtools__upload_file,mcp__chrome-devtools__wait_for,mcp__chrome-devtools__evaluate_script,mcp__chrome-devtools__take_screenshot,mcp__chrome-devtools__take_snapshot,mcp__chrome-devtools__list_console_messages,mcp__chrome-devtools__get_console_message,mcp__chrome-devtools__list_network_requests,mcp__chrome-devtools__get_network_request,mcp__chrome-devtools__handle_dialog,mcp__chrome-devtools__resize_page")
```

**Typical flow:**
1. `list_pages` — get tabs/pageIds
2. `select_page(pageId)` OR `new_page(url)` — focus or open
3. `navigate_page(url)` — go to CRM (login persists from profile)
4. `take_snapshot` — get DOM accessibility tree with element references
5. `click(ref)` / `fill(ref, value)` / `press_key("Enter")` — interact
6. `evaluate_script(...)` — page-context JS (ag-grid scroll-loop etc.)
7. `take_screenshot(fullPage|element)` — evidence
8. `list_network_requests` / `list_console_messages` — debugging

**Key advantages over Playwright + Claude_in_Chrome:**
- **No wrapper** — direct CDP over WebSocket, no Playwright runtime, no Chrome extension
- **Persistent login** — `~/.chrome-cdp-profile` keeps session between launches
- **Same VPN** — user's Chrome process inherits user's network namespace
- **Performance tooling built in** — `performance_start_trace`, `lighthouse_audit` for free
- **No Anthropic-extension dependency** — works on any machine with Chrome + Node

**Trade-offs vs Claude_in_Chrome:**
- No `find("natural language")` — must use `take_snapshot` refs (CDP-standard, more deterministic)
- No `gif_creator` — but `screencast_start/stop` covers session recording

### Browser — FALLBACK: Playwright (separate Chromium)

Use only when:
- Chrome extension not available (different machine, fresh setup)
- Headless / scripted / CI scenarios
- User explicitly requests Playwright

```
ToolSearch(query="select:mcp__playwright__browser_navigate,mcp__playwright__browser_click,mcp__playwright__browser_snapshot,mcp__playwright__browser_evaluate,mcp__playwright__browser_fill_form,mcp__playwright__browser_take_screenshot,mcp__playwright__browser_press_key,mcp__playwright__browser_network_requests,mcp__playwright__browser_console_messages,mcp__playwright__browser_wait_for")
```

### Slack — before any «прочитай канал», «напиши в Slack», «найди обсуждение», «standup в Slack»

```
ToolSearch(query="select:mcp__slack__slack_list_channels,mcp__slack__slack_get_channel_history,mcp__slack__slack_get_thread_replies,mcp__slack__slack_post_message,mcp__slack__slack_reply_to_thread,mcp__slack__slack_get_users,mcp__slack__slack_get_user_profile,mcp__slack__slack_add_reaction")
```

### Session management / preview / others — load on demand

`mcp__ccd_session_mgmt__*`, `mcp__Claude_Preview__*` — load when needed for session forensics or HTML preview.

---

## Decision tree — «can I do this myself?»

```
Is it in the capability map above?
  → Yes, capability exists → check Tier in trust_tiers.md:
      - Tier 1: do it, no surface
      - Tier 2: do it, mention briefly
      - Tier 3: preview → ask → execute
  → No capability listed:
      - Search ToolSearch first ("maybe it's deferred?")
      - If still no → honest "I can't do X directly — can you do it or want me to find a workaround?"
```

Better 100× «нет capability, давай вместе» than 1 fabricated «sorry I don't have access» (when ToolSearch would've found it).
