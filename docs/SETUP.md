# Setup guide (macOS)

Verified on macOS 26 with Claude Code 2.1.x and Apollo CLI 1.1.x.

## 1. macOS prerequisites
```sh
# Homebrew (if not present): https://brew.sh
brew install uv        # Python project/dependency manager
brew install gh        # GitHub CLI (for PRs / branch protection)
uv python install 3.12 # the pinned runtime (.python-version)
```

## 2. Project bootstrap
```sh
git clone https://github.com/Spindle-Org/spindle-gtm.git
cd spindle-gtm
make setup             # uv sync + pre-commit install
cp .env.example .env   # fill in values (never commit .env)
make migrate           # create db/spindle.db (gitignored)
make doctor            # read-only preflight
```

## 3. Apollo CLI setup (read-only first)
The official Apollo.io CLI (`apollo-io-cli`) provides shell access to Apollo.
```sh
brew install apolloio/apollo-io-cli/apollo-io-cli
apollo auth login      # interactive browser OAuth — credentials live in Apollo's store, NOT the repo
apollo auth whoami     # confirm identity
```
Read-only commands (search / enrich-preview / usage) are safe. Enrichment consumes
credits; sequence enrollment sends real email — both are gated (see docs/APOLLO_CAPABILITIES.md).

## 4. Apollo MCP setup (project scope)
```sh
claude mcp add --scope project --transport http apollo https://mcp.apollo.io/mcp
# committed .mcp.json holds ONLY the URL — no secrets. Complete OAuth interactively on first use.
```
Install the official CLI skill at project scope (already vendored in this repo at
`.claude/skills/apollo-cli/`; to refresh):
```sh
curl -fsSL https://raw.githubusercontent.com/apolloio/apollo-io-cli/main/.claude/skills/apollo-cli/SKILL.md \
  -o .claude/skills/apollo-cli/SKILL.md
```

## 5. Environment variables (`.env`, gitignored)
| Var | Purpose | Notes |
|-----|---------|-------|
| `SPINDLE_DB_PATH` | local SQLite path | default `db/spindle.db` (gitignored) |
| `OUTBOUND_ENABLED` | outbound **kill switch** | keep `false` in development; `true` only after the rollout sign-off |
| `APOLLO_API_KEY` | optional REST key (Mode B) | admin-only; never commit |
| `APOLLO_SEED_LIST_ID` | saved company list to ingest | scope label for sync |
| `SENDER_NAME` / `SENDER_COMPANY` / `SENDER_POSTAL_ADDRESS` | compliance footer | postal address is legally required for cold email |
| `UNSUBSCRIBE_URL` | opt-out link | required by message rules |
| `SMTP_*` | cold mailbox creds (Phase 4) | leave blank until sending is set up |

Never put secrets in `.mcp.json`, code, or git. The PII guard + pre-commit block accidental commits.

## 6. Database migrations
The local DB is a research/decision/audit cache — **not** the commercial system of record.
```sh
make migrate                                   # alembic upgrade head
uv run alembic revision --autogenerate -m "…"  # after changing src/spindle_gtm/models.py
uv run alembic downgrade -1                     # roll back one revision
```
Migrations are pre-production and periodically squashed into a single initial revision.
Never edit an applied migration in place; add a new revision.

## 7. Daily commands
`make check` (lint+types) · `make test` · `make run` (synthetic demo) · `make verify`
(release gate) · `make dashboard` (Streamlit) · `make doctor`.
