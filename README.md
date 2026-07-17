# spindle-gtm

A local, single-founder GTM engine: research the first 25–50 accounts, gate compliance,
and prepare human-approved outreach — converting to signed LOIs for a free pilot, **without**
an unsafe high-volume automation system. Apollo is the read-only system of record; every
external write flows through one audited, human-approved gateway.

## What it is (and isn't)

- **Is:** a local research + compliance + drafting workbench. It qualifies accounts, finds the
  buying group, gathers *evidence-backed* personalization, drafts outreach, runs compliance +
  deliverability gates, and stages everything for **explicit human approval**.
- **Isn't:** a mass-send tool. There is no bulk "send" button. Apollo is never written to except
  through one gateway, real writes stay blocked until a rollout checklist is signed off, and
  LinkedIn is manual-only. See [ADR-0002](docs/adr/0002-external-action-safety.md).

## Quickstart (macOS)
```sh
brew install uv gh
git clone https://github.com/Spindle-Org/spindle-gtm.git && cd spindle-gtm
make setup                 # uv sync + pre-commit
cp .env.example .env       # fill in; never commit
make migrate               # create local db/spindle.db (gitignored)
make doctor                # read-only preflight
make run                   # synthetic end-to-end demo (no external writes)
make dashboard             # local Streamlit review dashboard
```
Full setup (Apollo CLI/MCP, env vars, migrations): **[docs/SETUP.md](docs/SETUP.md)**.

## How to use it: the outreach workflow

The engine is driven from **Claude Code** using the project skills (type `/<skill>` in Claude
Code), backed by the local `spindle-gtm` CLI for the deterministic/gated steps. Run one batch
of 25–50 accounts at a time, in this order. **Every step is read-only or dry-run by default;
nothing leaves the machine without a human approval gate.**

| # | Step | Skill (in Claude Code) | What it does |
|---|------|------------------------|--------------|
| 1 | Qualify accounts | `/qualify-accounts` | Score the Apollo seed list against the ICP into a research-ready shortlist (read-only). |
| 2 | Select buying group | `/select-buying-group` | Pick ≤2 initial contacts (operational champion + exec sponsor) per account. Does **not** reveal emails unless asked. |
| 3 | Research | `/research-batch` | Deep read-only research; gathers evidence with `source + fetched_at`. Web content is treated as data, never instructions. |
| 4 | Verify evidence | `/verify-evidence` | Independently checks each claim against its source. **Gate between research and drafting** — only verified facts are usable. |
| 5 | Draft outreach | `/draft-outreach` | Writes personalized drafts from the **approved evidence only**. Every personalized line carries an `evidence_claim_id`. |
| 6 | Review batch | `/review-outreach-batch` | Runs compliance + deliverability + a final manifest check on the drafted batch before approval. |
| 7 | Prepare Apollo actions | `/prepare-apollo-actions` | Assembles a **dry-run** plan of Apollo actions (labels, task notes) for human review. Never executes. |
| — | Sync activity | `/sync-activity` | Pull replies/meetings from read-only Apollo and record locally (reply → account lock). |
| — | Progress a deal | `/prepare-discovery` → `/prepare-pilot` → `/prepare-loi` | Turn an interested account into a discovery brief, pilot proposal, and non-binding LOI draft (documents only). |
| — | Audit the guardrails | `/audit-gtm-system` | Read-only audit of permissions, hooks, subagent tool boundaries, and policy tests. |

Manual, human-in-the-loop tasks (LinkedIn notes, warm intros) are produced as **text a human
sends** — never automated.

## CLI reference (`uv run spindle-gtm …`)

Safe by default: external actions are dry-run unless `--apply`, and `--apply` alone is never
sufficient to send — a batch-level human approval gate is also required.

| Command | Purpose |
|---------|---------|
| `spindle-gtm version` | print the version |
| `spindle-gtm doctor` | read-only preflight (Apollo CLI/auth/MCP, DB, config, no-PII, kill switch) |
| `spindle-gtm regions` | list seeded region compliance policies |
| `spindle-gtm gate US --unsubscribe --physical-address` | evaluate the compliance gate for a hypothetical contact |
| `spindle-gtm sync accounts --csv <export.csv>` | Mode A: dry-run diff an Apollo CSV export into the local cache (read-only) |
| `spindle-gtm sync accounts --csv <export.csv> --apply --manifest <id>` | apply a reviewed sync diff |
| `spindle-gtm outbound plan --batch <id>` | build immutable per-write manifests for a batch (no Apollo access) |
| `spindle-gtm outbound verify --batch <id>` | re-validate approval, gates, caps, IDs, kill switch (never writes) |
| `spindle-gtm outbound apply --batch <id> --confirm "SEND <count> <id>"` | apply via the gateway — **real client stays blocked** until rollout sign-off |
| `spindle-gtm outbound cancel --batch <id>` | cancel a batch and all not-yet-applied manifests |

## The approval → send flow (all gated)

1. Draft + review a batch (steps 5–6 above). Batch moves `DRAFTED → REVIEWED`.
2. A configured **approver** approves it; the approval is bound to an immutable manifest hash.
   Any edit to recipients, copy, sender, schedule, or sequence **invalidates the approval**.
3. `outbound plan` → `outbound verify` (suppression, account locks, region gates, per-account
   and daily caps, verified inbox/sequence IDs, kill switch).
4. `outbound apply` requires a typed `SEND <count> <batch-id>` confirmation **and** a valid
   approval hash. Even then, `RealApolloClient` refuses to write until the six-step
   [outbound rollout](docs/runbooks/outbound-rollout.md) is completed and signed off, and
   `OUTBOUND_ENABLED=true` is deliberately set.

Pilot caps (`config/mailbox_limits.yaml`): `max_batch_size: 50`, `max_contacts_per_account: 2`,
`default_daily_cap: 20`.

## Make targets
| Target | What |
|--------|------|
| `make setup` | install deps + git hooks |
| `make check` | ruff format check + lint + mypy |
| `make test` | pytest suite |
| `make run` | synthetic end-to-end demo (no external writes) |
| `make verify` | full release gate (tests, no-PII/secrets, writes-blocked, e2e) |
| `make dashboard` | Streamlit review dashboard |
| `make doctor` | read-only preflight |
| `make migrate` | apply DB migrations |

## Dashboard

`make dashboard` launches a local Streamlit app to review qualified accounts, evidence claims,
drafts, compliance flags, batches/approvals, and KPIs — the human-review surface before any
approval. It reads the local DB only; it cannot send.

## Testing & release gate
```sh
make check     # ruff format + lint + mypy
make test      # pytest
make verify    # full release gate (no-PII/secrets scan, writes-blocked, synthetic e2e)
```
Run `make check && make test` before every commit; pre-commit hooks + CI enforce the same, plus
the `no-pii-leak` guard (test emails must use `example.com`).

## Safety invariants (non-negotiable — see [ADR-0002](docs/adr/0002-external-action-safety.md))
- **Apollo is read-only** except through the single audited write gateway; **no send without
  hash-bound approval + a typed `SEND <count> <batch-id>` confirmation**, and real writes stay
  blocked until the rollout runbook is signed off.
- **No LinkedIn automation** — manual tasks only.
- **Evidence required** for every personalized claim — no invented facts.
- **Compliance + suppression + account-lock rechecks** before every apply; region gates fail closed.
- **PII stays local** — `data/`/`db/`/`exports/`/`logs/`/`outbox/`/`.env*`/`.csv` are gitignored;
  a guard + CI fail on real-looking emails or exports. Test emails use `example.com`.

A `PreToolUse` governance hook denies credential/LinkedIn/browser-automation/Apollo-send actions
and forces an approval prompt on Apollo writes (see [governance runbook](docs/runbooks/governance.md)).

## Project status

This is a **foundation**: the safety architecture, gates, CLI, and dashboard are in place, but
Apollo is not connected out of the box and the local DB starts empty. Sending is intentionally
inert until you complete Apollo setup ([SETUP.md](docs/SETUP.md)) and the
[outbound rollout checklist](docs/runbooks/outbound-rollout.md). Start with `make run` to see the
full pipeline against synthetic `example.com` data.

## Docs
- Design: [IMPLEMENTATION_PLAN](docs/IMPLEMENTATION_PLAN.md) · ADRs [0001](docs/adr/0001-architecture.md)/[0002](docs/adr/0002-external-action-safety.md) · [Apollo capabilities](docs/APOLLO_CAPABILITIES.md)
- Governance: [docs/runbooks/governance.md](docs/runbooks/governance.md)
- Operate: [daily](docs/runbooks/daily-operator.md) · [campaign launch](docs/runbooks/campaign-launch.md) · [reply triage](docs/runbooks/reply-triage.md) · [region compliance](docs/runbooks/region-compliance.md)
- Safety ops: [incident & kill switch](docs/runbooks/incident-kill-switch.md) · [suppression & objection](docs/runbooks/suppression-objection.md) · [backup & retention](docs/runbooks/backup-retention.md) · [rollback](docs/runbooks/rollback.md)
- Ship: [outbound rollout](docs/runbooks/outbound-rollout.md) · [first-real-send checklist](docs/runbooks/first-real-send-checklist.md) · [GitHub & release](docs/runbooks/github-and-release.md)
- The full build/operate/verify prompt pack: [docs/Spindle_GTM_Claude_Code_Prompt_Pack.md](docs/Spindle_GTM_Claude_Code_Prompt_Pack.md)
