# Runbook — enabling real Apollo writes (outbound gateway)

The gateway (`src/spindle_gtm/apollo_gateway.py`) is the **only** Apollo write path.
`RealApolloClient` refuses to write until every step below is completed **in order** and
signed off. One-off email send is NOT in v1 and needs separate explicit approval after
test-mail validation.

## Pre-enable checklist
1. **Mocks** — full gateway test suite green against mock clients (`uv run pytest tests/unit/test_gateway.py`).
2. **Synthetic fixtures** — plan/verify/apply dry-run against the synthetic fixture batch; verify caps, region blocks, and duplicate-skip behavior.
3. **One real task creation** — a single `create_task` write for an **internal test contact** in our own Apollo workspace. Verify it appears correctly; record the result id here.
4. **One real sequence enrollment** — enroll one internal, Spindle-owned test mailbox contact into a test sequence using exact Apollo inbox + sequence IDs from `apollo email-accounts list` / `apollo sequences search`. Verify state in Apollo.
5. **Removal + pause behavior** — remove the test contact from the sequence and verify pause/stop semantics work as expected.
6. **Explicit human sign-off** — the founder records sign-off below; only then implement `RealApolloClient.apply` and flip `OUTBOUND_ENABLED=true`.

| Step | Date | Result / evidence | Sign-off |
|------|------|-------------------|----------|
| 1 |  |  |  |
| 2 |  |  |  |
| 3 |  |  |  |
| 4 |  |  |  |
| 5 |  |  |  |
| 6 |  |  |  |

## Standing rules
- Dry-run is the default everywhere; `outbound apply` requires `--confirm "SEND <count> <batch-id>"`.
- The kill switch (`OUTBOUND_ENABLED=false`) blocks execution regardless of confirmation.
- Approval is hash-bound; any batch change invalidates it.
- Retries are idempotent — items with an APPLIED result are skipped (no duplicate enrollment).
- An account lock (REPLIED / MEETING_SET / DO_NOT_CONTACT / LEGAL_HOLD) blocks writes and
  queues remove-from-sequence actions for that account's other contacts.
