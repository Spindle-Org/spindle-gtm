# Compliance — region policy

> **Not legal advice.** These are conservative operational defaults pending legal
> sign-off (IMPLEMENTATION_PLAN §15) before sending to CA / EU / APAC.

The machine-readable source of truth is [`config/region_policy.toml`](../../config/region_policy.toml),
enforced by `spindle_gtm.compliance.compliance_gate()`.

| Region | Basis | Cold email | Consent required | Notes |
|--------|-------|-----------|------------------|-------|
| US | CAN-SPAM | yes | no | Truthful headers, physical address, honor opt-out. |
| CA | CASL | caution | yes | Prefer LinkedIn-manual or documented EBR. |
| UK | GDPR+PECR | caution | no | Legitimate interest; LIA note; role-based addresses. |
| EU | GDPR+PECR | caution | no | Legitimate interest; LIA note; role-based addresses. |
| AU | Spam Act 2003 | caution | yes | Consent/inferred consent + unsubscribe. |
| IN | DPDP Act | caution | yes | Default LinkedIn-manual; HOLD email w/o lawful basis. |
| KR | PIPA | no | yes | Do not cold-email without recorded consent. |
| JP | APPI | caution | yes | Default LinkedIn-manual; HOLD email w/o lawful basis. |

## Global invariants (every send)
- Suppression honored (wins over everything).
- Unsubscribe mechanism present.
- Sender identity + physical postal address present.
- Per-contact frequency cap respected.
