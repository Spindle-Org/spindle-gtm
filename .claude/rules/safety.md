# Safety rules (binding)

Mirror of the non-negotiables in `CLAUDE.md` / `docs/adr/0002`. If a task would violate
any of these, stop and ask.

- Apollo is the **system of record** and **read-only** here — never write back.
- **No LinkedIn automation** — manual, human-in-the-loop only.
- **Evidence required** for any personalization — no invented facts.
- **Human approval for every external write** — dry-run by default; `--apply` + batch approval.
- **No PII in git** — test emails use `example.com`; never commit `data/`, `db/`, `exports/`,
  `.env*`, or `.csv`.
