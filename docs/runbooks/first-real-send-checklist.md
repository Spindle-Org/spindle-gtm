# Checklist — first real send

Do NOT send until every box is checked. This gates the transition from synthetic to real.

## Automated gates (must all pass)
- [ ] `make verify` (release gate) PASS: format/lint/types, tests, no tracked PII, no tracked
      secrets, real-write tools blocked, synthetic e2e demo.
- [ ] `make doctor` all OK (Apollo CLI/auth/MCP, DB, config, kill switch engaged).

## Manual verifier prompts (Prompt Pack, Part III) — all PASS/GO
- [ ] Verifier 1 architecture & source-of-truth
- [ ] Verifier 2 Apollo integration & credit safety
- [ ] Verifier 3 security, secrets & PII
- [ ] Verifier 4 state machine, locking & idempotency
- [ ] Verifier 5 qualification & contact selection
- [ ] Verifier 6 research integrity (any unsupported personalized claim = BLOCKER)
- [ ] Verifier 7 outreach copy red-team
- [ ] Verifier 8 compliance & deliverability
- [ ] Verifier 9 LinkedIn policy (any automation = BLOCKER)
- [ ] Verifier 10 end-to-end dry run
- [ ] Verifier 11 real-send readiness → **GO**

## Rollout runbook (docs/runbooks/outbound-rollout.md) — steps 1–6 signed off
- [ ] mocks → fixtures → one real internal test task → one real internal test enrollment →
      removal/pause verified → founder sign-off recorded.
- [ ] `RealApolloClient.apply` implemented; sender inbox + sequence IDs verified from Apollo.

## Deliverability & scope
- [ ] SPF, DKIM, DMARC verified for the sending domain; mailbox health OK; daily cap ≤ configured.
- [ ] Batch ≤ 15 accounts, ≤ 2 contacts per account; region = US + reviewed UK corporate only.
- [ ] Exact messages approved (hash-bound); suppression + account-lock recheck clean.

## Send
- [ ] Set `OUTBOUND_ENABLED=true` for this batch only.
- [ ] `outbound apply --batch <id> --confirm "SEND <count> <batch-id>"`.
- [ ] Re-engage the kill switch after the batch.
