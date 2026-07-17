# spindle-gtm
Built for another level of out reach.

A local, single-founder GTM engine: research the first 25–50 accounts, gate compliance,
and prepare human-approved outreach — converting to signed LOIs for a free pilot, **without**
an unsafe high-volume automation system. Apollo is the read-only system of record; every
external write flows through one audited, human-approved gateway.

## Quickstart (macOS)
```sh
brew install uv gh
git clone https://github.com/Spindle-Org/spindle-gtm.git && cd spindle-gtm
make setup                 # uv sync + pre-commit
cp .env.example .env        # fill in; never commit
make migrate               # create local db/spindle.db (gitignored)
make doctor                # read-only preflight
make run                   # synthetic end-to-end demo (no external writes)
make dashboard             # local Streamlit review dashboard
```
Full setup (Apollo CLI/MCP, env vars, migrations): **[docs/SETUP.md](docs/SETUP.md)**.

## Make targets
| Target | What |
|--------|------|
| `make setup` | install deps + git hooks |
| `make check` | ruff format check + lint + mypy |
| `make test` | pytest suite |
| `make run` | synthetic end-to-end demo (no external writes) |
| `make verify` | full release gate |
| `make dashboard` | Streamlit review dashboard |
| `make doctor` | read-only preflight |
| `make migrate` | apply DB migrations |

## Safety invariants (non-negotiable — see [ADR-0002](docs/adr/0002-external-action-safety.md))
- **Apollo is read-only** except through the single audited write gateway; **no send without
  hash-bound approval + a typed `SEND <count> <batch-id>` confirmation**, and real writes stay
  blocked until the rollout runbook is signed off.
- **No LinkedIn automation** — manual tasks only.
- **Compliance + suppression + account-lock rechecks** before every apply; region gates fail closed.
- **PII stays local** — `data/`/`db/`/`exports/`/`logs/`/`outbox/`/`.env*`/`.csv` are gitignored;
  a guard + CI fail on real-looking emails or exports. Test emails use `example.com`.

## Docs
- Design: [IMPLEMENTATION_PLAN](docs/IMPLEMENTATION_PLAN.md) · ADRs [0001](docs/adr/0001-architecture.md)/[0002](docs/adr/0002-external-action-safety.md) · [Apollo capabilities](docs/APOLLO_CAPABILITIES.md)
- Governance: [docs/runbooks/governance.md](docs/runbooks/governance.md)
- Operate: [daily](docs/runbooks/daily-operator.md) · [campaign launch](docs/runbooks/campaign-launch.md) · [reply triage](docs/runbooks/reply-triage.md) · [region compliance](docs/runbooks/region-compliance.md)
- Safety ops: [incident & kill switch](docs/runbooks/incident-kill-switch.md) · [suppression & objection](docs/runbooks/suppression-objection.md) · [backup & retention](docs/runbooks/backup-retention.md) · [rollback](docs/runbooks/rollback.md)
- Ship: [outbound rollout](docs/runbooks/outbound-rollout.md) · [first-real-send checklist](docs/runbooks/first-real-send-checklist.md) · [GitHub & release](docs/runbooks/github-and-release.md)
- The full build/operate/verify prompt pack: [docs/Spindle_GTM_Claude_Code_Prompt_Pack.md](docs/Spindle_GTM_Claude_Code_Prompt_Pack.md)
