# CRM tracker schema

50 columns, one row per contact. The authoritative definition lives in
`src/spindle_gtm/tracker.py` (`COLUMNS` + `ENUMS`) — this doc explains it. Generate a
blank with `spindle-gtm tracker template`, check a filled one with
`spindle-gtm tracker validate`.

Filled trackers contain real emails (PII) → they live in gitignored `exports/` and are
**never committed**.

## Columns

**Identity**
| Column | Notes |
|---|---|
| `contact_id` | Stable id, e.g. `SP001`. Required on every row. |
| `first_name`, `last_name`, `full_name` | Names. |
| `job_title`, `company` | Role and employer. |
| `country`, `region` | `region` ∈ `US, UK, EU, CA, IN, KR, JP` — drives the compliance gate. |
| `email`, `linkedin` | Contact points. Enrich deliberately, late. |

**Segmentation**
| Column | Notes |
|---|---|
| `relationship_status` | e.g. `cold`, `cold-strong`, `warm`. Warm = relationship-first, needs owner approval. |
| `persona` | Buyer persona, e.g. `Merchandising/Planning`. |
| `deal_role` | `Operational champion` / `Economic buyer` / `Exec sponsor`. Champion first. |
| `primary_use_case`, `secondary_use_case` | Use-case tags. |

**Scoring (0–10)** — sort/filter to prioritize
| Column | Notes |
|---|---|
| `icp_score`, `role_fit_score`, `trigger_score`, `evidence_score`, `reply_potential_score`, `pilot_potential_score` | Higher = better. |
| `source_tier` | Evidence quality `A`–`E`. A/B only in copy. |

**Evidence** — every personalized claim needs this
| Column | Notes |
|---|---|
| `verified_trigger` | The one verified, company-specific reason to write. |
| `trigger_source`, `trigger_publication_date`, `trigger_access_date` | Provenance. |
| `trigger_confidence` | `high` / `medium` / `low`. |
| `safe_interpretation` | The claim as it may be safely phrased (no over-reach). |

**Copy** — produced by `/draft-outreach` from approved evidence only
| Column | Notes |
|---|---|
| `recommended_sender`, `recommended_channel` | Who sends, on what channel. |
| `subject_a/b/c` | 1–4 word subjects for A/B/C testing. |
| `email_1`, `followup_1..3` | First touch + follow-ups (each adds a new idea, never guilt). |
| `linkedin_connection_note`, `linkedin_message` | Manual LinkedIn steps (human-sent only). |
| `positive_reply_message`, `referral_message` | Reply-handling scripts. |

**Status & tracking** — the filter axes
| Column | Allowed values |
|---|---|
| `legal_review_status` | `not-required`, `pending`, `cleared`, `hold` |
| `personalization_review_status` | `pending`, `pass`, `fail` |
| `send_status` | `hold`, `draft`, `ready`, `approved`, `sent`, `replied`, `bounced` |
| `reply_status` | `none`, `positive`, `negative`, `neutral`, `ooo`, `referral`, `unsubscribe`, `bounce` |
| `hold_reason`, `next_action`, `owner`, `last_contacted`, `notes` | Free text / date. |

## Validation rules enforced by `tracker validate`

- All 50 columns present, in canonical order.
- Constrained fields (above) only hold allowed values.
- Every row has a `contact_id`.
- Any row with `send_status ∈ {ready, approved, sent}` must have `subject_a`, `email_1`,
  and `recommended_sender` filled — you cannot mark a row send-ready without copy and a sender.

## Changing the schema

Edit `COLUMNS`/`ENUMS` in `src/spindle_gtm/tracker.py`, update this doc and
`tests/test_tracker.py` in the same commit. The template and validator both read from
the code, so they can never drift from each other.
