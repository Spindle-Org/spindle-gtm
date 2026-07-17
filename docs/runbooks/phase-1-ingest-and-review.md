# Runbook — Phase 1: ingest & review (read-only)

> Prerequisite: Apollo connected **read-only**. This runbook performs no sends.
> Sending is Phase 4 and gated separately (docs/adr/0002).

## Steps
1. Set up:
   ```sh
   uv sync
   cp .env.example .env          # fill APOLLO_SEED_LIST_ID; never commit .env
   uv run alembic upgrade head
   ```
2. Dry-run the ingest to see what would be pulled:
   ```sh
   uv run spindle ingest         # dry-run by default
   ```
3. When Phase 1 ingest is implemented, run it for real with review:
   ```sh
   uv run spindle ingest --apply
   ```
4. Review the batch in the dashboard (aggregate/status only, PII-free):
   ```sh
   uv run streamlit run src/spindle_gtm/dashboard.py
   ```
5. Check compliance for a region before drafting:
   ```sh
   uv run spindle gate CA --unsubscribe --physical-address
   ```

## Guardrails
- Ingest is read-only against Apollo; nothing is written back.
- Contacts in consent-heavy regions (CA/AU/APAC) HOLD until a lawful basis is recorded;
  prefer the LinkedIn-manual channel there.
