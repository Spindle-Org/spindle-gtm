## What & why

<!-- What does this change do, and why? -->

## Safety checklist (see docs/adr/0002)

- [ ] No external write happens without an explicit human-approval gate.
- [ ] Apollo stays **read-only** (no accounts/contacts/sequences/campaigns created).
- [ ] No LinkedIn automation or scraping added.
- [ ] Any new outreach path is **dry-run by default** and requires `--apply`.
- [ ] Personalization is backed by **evidence** stored alongside the claim.
- [ ] No PII / secrets / `.csv` exports added; test emails use `example.com`.
- [ ] `ruff`, `mypy`, `pytest`, and the PII guard pass locally.

## Notes

<!-- Migrations, rollout considerations, follow-ups. -->
