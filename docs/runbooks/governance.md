# Runbook — Claude Code governance layer

This repo ships a project-scoped Claude Code governance layer that enforces the
safety posture in [ADR-0002](../adr/0002-external-action-safety.md). Built and verified
against **Claude Code 2.1.212**.

## What's in it

| Layer | File(s) | Enforces |
|-------|---------|----------|
| Permission denies | `.claude/settings.json` → `permissions.deny` | Block reading `.env`/`.mcp.json`/credential dirs and `data//db//exports//logs/`; block `WebFetch` of LinkedIn domains. |
| Deterministic hook | `.claude/settings.json` → `hooks.PreToolUse` + `.claude/hooks/pretooluse_guard.py` | Classify every Bash/Read/Edit/Write/WebFetch/MCP call and **deny / ask / defer**; log external-write attempts. |
| Policy logic | `src/spindle_gtm/policy.py` | Pure, tested classifier the hook calls. |
| Subagents | `.claude/agents/*.md` | Per-agent `tools:` allowlists (read-only vs no-web vs no-send). |
| Skills | `.claude/skills/*/SKILL.md` | The 12 `/…` workflow commands, each delegating to the right subagent. |

### What the hook decides (`src/spindle_gtm/policy.py`)
- **DENY**: credential/`.env` access · LinkedIn fetch (WebFetch or shell fetcher) · browser
  automation (Playwright/Selenium/Puppeteer/chromedriver/extensions) · `git add/commit` of
  `data//db//exports/`, `.csv`, `.sqlite`, `.db`, secrets · Apollo **send / sequence-enrollment** ·
  outbound `--apply` without an approved manifest.
- **ASK** (forces a human approval prompt): any Apollo **write** (create/update/purchase/…),
  any unclassified Apollo action (fail-safe), outbound `--apply` **with** an approved manifest.
- **DEFER** (normal permission flow): Apollo reads and everything unmatched.

Apollo is matched **semantically** (any `mcp__…apollo…` tool or an `apollo` CLI, classified by
verb) — no exact tool names are hardcoded, so it stays correct after you connect Apollo and the
exact tool list appears. After connecting, review `policy.py`'s verb regexes against the real tool
names and tighten if needed.

### Audit log
Every attempted external write — allowed, ask, or **denied** — is appended to
`logs/external-attempts.log` (JSONL, gitignored). Denied attempts are logged before they are
blocked.

### Outbound apply gate
An outbound `spindle … send --apply` is denied unless BOTH exist:
`outbox/approved/manifest.json` and `outbox/approved/manifest.approved`. Even then it only
reaches an **ask** prompt — a human still confirms. (Sending itself is not wired in this
foundation; see ADR-0002.)

## Verify it's live

1. **Permissions** — run `/permissions`. Confirm the deny rules from `.claude/settings.json`
   appear (credential paths, LinkedIn `WebFetch`) and note which source file they load from.
2. **Hooks** — run `/hooks`. Confirm a `PreToolUse` hook is registered with the matcher
   `Bash|Read|Edit|Write|NotebookEdit|MultiEdit|WebFetch|mcp__` pointing at
   `.claude/hooks/pretooluse_guard.py`.
3. **Subagents** — run `/agents` (or check `.claude/agents/`). Each agent's `tools:` line matches
   its boundary (e.g. `outreach-copywriter` has no web/Apollo tools; `loi-preparer` has no send).
4. **Policy tests** — the deterministic core is unit-tested:
   ```sh
   uv run pytest tests/unit/test_policy.py tests/integration/test_hook_guard.py -q
   ```
5. **Manual hook smoke test** — feed the guard a call and see the decision:
   ```sh
   echo '{"tool_name":"mcp__apollo__apollo_emailer_messages_send_now","tool_input":{},"cwd":"'"$PWD"'"}' \
     | python3 .claude/hooks/pretooluse_guard.py
   # -> {"hookSpecificOutput":{...,"permissionDecision":"deny",...}}
   echo '{"tool_name":"Bash","tool_input":{"command":"ls"},"cwd":"'"$PWD"'"}' \
     | python3 .claude/hooks/pretooluse_guard.py
   # -> (no output = defer to normal permissions)
   ```
6. **Self-audit** — run the `/audit-gtm-system` skill for a full read-only review of the layer.

## Known limitation
Claude Code hooks do **not** receive the invoking subagent's identity (v2.1.212), so per-agent
rules like "contact-selector must not enrich emails unless asked" are enforced by the subagent's
`tools:` allowlist + system prompt, not the hook. The hook enforces the invariants that must hold
for **every** agent. Re-check this if a future version exposes subagent identity to hooks.
