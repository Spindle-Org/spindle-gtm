# Runbook — region compliance

Operational risk control, **not legal advice**. Get counsel sign-off on the policy matrix
before sending to CA / EU / APAC. Source of truth: `config/outreach_policy.yaml` +
`src/spindle_gtm/gates.py`.

## Decision matrix (initial)
| Region | Behavior |
|--------|----------|
| **US** | ALLOW tightly-targeted B2B only when email is verified and CAN-SPAM/opt-out fields are complete |
| **UK** | ALLOW corporate B2B only; sole traders / individual subscribers / uncertain → REVIEW |
| **Canada** | BLOCK cold outreach unless express or documented implied consent (CASL) is recorded |
| **EU/EEA** | REVIEW: country-specific review + documented legal basis before send; always honor objection |
| **Unconfigured country** | `LEGAL_REVIEW_REQUIRED` — never guess |

Missing policy data → **BLOCK** (fail closed). Suppression and opt-out block before any
country logic.

## Operating rules
- First campaign: **US + explicitly-configured UK corporate accounts only.** Keep Canada and
  unreviewed EU markets blocked until documented.
- Every send needs sender identification + physical postal address + a working opt-out.
- Open/click tracking is **off by default**; enable only via an allow-listed experiment.
- Region/consent basis is recorded per contact; the compliance decision log keeps reason codes.

## Adding a country
1. Add a row to `config/outreach_policy.yaml` (quote `cold_email_allowed`: "yes"/"no"/"caution").
2. If it needs bespoke logic, extend `_country_decision` in `gates.py` + add a unit test.
3. Record the counsel review that justified it.

## Verify
```sh
uv run pytest tests/unit/test_gates.py -q   # US, UK corporate, UK sole trader, CA, FR, unknown EU, unknown country
```
