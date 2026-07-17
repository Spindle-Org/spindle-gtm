# Runbook — campaign launch

Prepares and (only after sign-off) applies an outbound batch. Real writes require the
rollout checklist (docs/runbooks/outbound-rollout.md) to be complete.

## 1. Build the account set (read-only)
Operating Prompt A: sync ≤15 accounts, score, return top candidates with reasons, flag
uncertain revenue/size, estimate enrichment credits. Approve accounts.

## 2. Buying group (read-only)
Operating Prompt B: ≤2 contacts per account (1 champion, 1 sponsor; approver saved).
Enrich emails only for selected contacts, only after ICP pass. Approve.

## 3. Research → verify → draft
Operating Prompts C and D. Every personalized sentence maps to a verified `evidence_claim_id`.
Drafts are DRAFTED; run deterministic validation + the independent auditor (Prompt E).

## 4. Compliance + deliverability
Confirm each recipient passes `contact_gate` (ALLOW) and the deliverability gate. Start
US + reviewed-UK-corporate only; keep CA and unreviewed EU blocked.

## 5. Approve the batch (dashboard, hash-bound)
DRAFTED → REVIEWED → APPROVED. Only an approver can APPROVE; any change to recipients,
sender, copy, schedule, sequence, or policy invalidates the approval.

## 6. Plan + verify the outbound manifest (no writes)
```sh
uv run spindle-gtm outbound plan   --batch <id>
uv run spindle-gtm outbound verify --batch <id>   # revalidates approval/gates/caps/IDs/kill switch
```

## 7. Apply (only with sign-off + typed confirmation)
```sh
uv run spindle-gtm outbound apply --batch <id> --confirm "SEND <count> <batch-id>"
```
Apply re-runs full validation immediately before writing, skips already-applied items
(no duplicate enrollment), and records structured results. If the kill switch is engaged
or the real client is not enabled, apply refuses — by design.

## 8. Cancel if needed
```sh
uv run spindle-gtm outbound cancel --batch <id>
```

First campaign shape: see the Prompt Pack, Part IV.
