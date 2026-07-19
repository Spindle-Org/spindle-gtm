# 07 — Compliance & Deliverability Checklist
**Prepared:** 2026-07-18. **This is a practical checklist, not legal advice.** Items marked 🔴 require qualified legal review before sending, especially for EU contacts.

---

## Part 1 — Legal by region

### 1.1 United States (CAN-SPAM) — 23 US contacts
CAN-SPAM permits B2B cold email (no opt-in) if every message:
- [ ] Uses **truthful From / Reply-To / routing** headers that identify Spindle
- [ ] Has a **non-deceptive subject** that reflects the content
- [ ] Is **identifiable as a commercial message** (context suffices; needn't shout "AD" but must not masquerade as personal/transactional)
- [ ] Includes a **valid physical postal address** for Spindle *(you must provide this — currently a placeholder)*
- [ ] Provides a **clear opt-out** and **honors it within 10 business days**; opt-out must work ≥30 days, cost nothing, and require no more than an email/single web page
- [ ] Never contracts away liability (if an agency/tool sends on your behalf, Spindle is still liable)
- Penalty: up to ~\$53k per email (inflation-adjusted) — 🔴 **verify current figure at ftc.gov**

### 1.2 United Kingdom (PECR + UK GDPR) — 7 UK contacts
- [ ] **Corporate subscribers** (Ltd, LLP): PECR e-mail rules **don't apply** → B2B email allowed **without consent**. Most of the UK list is corporate.
- [ ] 🔴 **Sole traders / most partnerships = individual subscribers** → need consent or PECR **soft opt-in**. **Check each UK contact's entity type** before sending. (Small independent brands can be sole traders.)
- [ ] UK GDPR applies to the named person's data → lawful basis = **legitimate interest**; document a Legitimate Interest Assessment (LIA)
- [ ] Never disguise identity; include a **valid opt-out + contact address** in every message
- [ ] Honor the **absolute right to object** to direct marketing immediately (no balancing)
- [ ] Maintain a **privacy notice** reachable from the email; be ready to state the **data source** on request

### 1.3 EU / EEA (GDPR + national ePrivacy) — 37 contacts (Spain, Portugal, Germany, Denmark, Sweden, Netherlands, France) 🔴🔴
**Highest legal risk. Do NOT treat "legitimate interest + footer" as sufficient.**
- [ ] 🔴 Run and **document a GDPR Art. 6(1)(f) legitimate-interest 3-part test** (purpose → necessity → balancing) *per the EDPB Guidelines 1/2024* — direct marketing is **not automatically** a legitimate interest
- [ ] 🔴 **Check member-state ePrivacy transposition** — several EU states require **consent even for B2B** email (this varies by country: Spain, Germany, etc. have stricter regimes). This is the make-or-break item and needs country-by-country legal input
- [ ] Provide identity, opt-out, contact address, privacy notice in every message; honor objection immediately
- [ ] Record where each contact's data came from (Apollo) and the LIA rationale
- [ ] **Recommendation:** treat EU as a **LinkedIn-first / relationship-first** segment pending legal sign-off, rather than defaulting to cold email — see 09

### 1.4 Out-of-policy contacts (HOLD)
- [ ] Nigeria / UAE / Malaysia contacts: **no region policy row, do not email** (also likely mismatched records) — see 02

> **Bottom line:** US is low-risk with correct footer. UK is workable for corporate subscribers with an LIA. **EU requires per-country legal review before any cold email.** None of this is legal advice.

---

## Part 2 — Required message elements (every send)
- [ ] Valid physical postal address *(BLOCKER: provide Spindle's address)*
- [ ] Working one-click unsubscribe **(RFC 8058: `List-Unsubscribe` + `List-Unsubscribe-Post` headers)** + a visible unsubscribe line
- [ ] Truthful sender identity (real name + Spindle) — the sender ([SENDER]) must be filled
- [ ] Link to a privacy notice
- [ ] Honor opt-outs → maintain a **suppression list**; never re-contact

---

## Part 3 — Deliverability (do before wave 1)
**Authentication (blocker):**
- [ ] **SPF** record on the sending domain
- [ ] **DKIM** signing enabled
- [ ] **DMARC** record (start `p=none`), From-domain aligned with SPF/DKIM
- [ ] Valid **forward + reverse DNS (PTR)** on sending infra; **TLS** enabled
- [ ] Consider a **dedicated sending subdomain** (e.g. `go.` / a separate domain) to protect the primary domain reputation

**Reputation & hygiene:**
- [ ] Enroll domain in **Google Postmaster Tools**; keep **spam rate < 0.3%** (target < 0.1%)
- [ ] **Warm up** the domain/mailbox — ramp volume gradually (start ~10–20/day, increase over 2–4 weeks); do not blast 71 on day 1
- [ ] Verify emails (reduce bounces); **hard-bounce suppression** immediately
- [ ] Complaint handling: any spam complaint → suppress + review

**Format (protect inbox placement):**
- [ ] **Plain text** first touch (no heavy HTML, no images, no tracking pixel)
- [ ] **No attachment** in first touch (offer the Change Map as a link/on-request only, and only after reputation is established)
- [ ] **≤ 1 link** where necessary; ideally zero in the very first touch
- [ ] **Manual / near-manual send** (manual outperforms automated; also respects the repo's no-automation posture)
- [ ] Do **not** optimize for open rate (degraded post-Apple MPP) — measure replies

---

## Part 4 — Process controls (repo governance)
- [ ] Sends go out **manually by the founder** or via the approval-gated CLI — never an automated blast
- [ ] **One contact per account at a time** (account-level sequencing — see 04/09)
- [ ] LinkedIn steps are **manual, human-in-the-loop only** (no automation, per repo policy)
- [ ] Keep PII (emails) out of git; this system folder lives outside the repo
- [ ] Log every send + reply at account level (CRM or the tracker)

---

## Part 5 — Open blockers before ANY send
1. 🔴 Spindle **postal address** (legal requirement, all regions)
2. 🔴 **[SENDER]** identity per segment (Ayush / Marta)
3. 🔴 **EU legal review** (per-country ePrivacy) — or default EU to LinkedIn-first
4. 🔴 UK **entity-type check** (corporate vs sole trader) for each UK contact
5. Domain **auth (SPF/DKIM/DMARC)** + Postmaster + warm-up in place
6. Unsubscribe mechanism + suppression list operational
