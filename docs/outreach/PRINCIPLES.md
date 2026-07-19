# 01 — Outreach Research & Principles
### Evidence base and governing rules for Spindle founder-led outbound
**Prepared:** 2026-07-18. All web access dates below = 2026-07-18 unless stated.

---

## 1. Executive summary

The strongest, best-evidenced findings converge on an approach that is almost the opposite of the current Spindle batch:

1. **Short, specific, and non-salesy wins.** A first cold touch should be ~50–90 words, 3–5 short sentences, with a 1–4 word plain subject line, one company-specific reason for writing, and **no** pitch/feature/price language. *(Gong; Lavender)*
2. **Interest CTAs beat meeting requests at the cold stage — by a lot.** A 304,174-email Gong Labs study: interest-based CTAs ~**12%** reply vs. ~**7%** for meeting-request CTAs, and **68%** vs **41%** positive-reply quality. Meeting/time asks belong later. *(Gong Labs via Growleads)*
3. **"AI" and "platform" language measurably suppress replies.** Buzzword/pitch language lowers reply rates (Gong: ROI-language ~**-15%**). This directly indicts the current batch's universal "AI-native platform" framing.
4. **Relevance ≠ token-merge.** Personalization that works is a real, company-specific reason to write — not `{{first_name}}` or an AI-guessed "I saw you're doing X." Practitioners consistently read templated/AI openers as the *opposite* of research.
5. **Deliverability is now a hard gate.** Google's 2024 sender rules require SPF/DKIM (+DMARC for bulk), one-click unsubscribe, and spam rate <0.3%. Automated blasts underperform manual sends.
6. **The EU/UK legal picture is more nuanced than "add a footer."** UK B2B email to *corporate* subscribers needs no consent under PECR, but sole traders/partnerships do; EU relies on GDPR legitimate interest (which is *not automatic* for marketing) **plus** member-state ePrivacy rules that sometimes require consent even B2B. This materially changes how confidently we can email the ~42 EU/UK contacts.

**Implication for Spindle:** rebuild every first touch around one verified trigger, the recipient's operational language, a one-sentence non-jargon description, and an interest/referral CTA. Hold price, pilot, and meeting asks until a positive reply.

**A candour note on evidence quality.** The cold-email *benchmark* research is genuinely strong (Gong/Lavender large datasets, official Google/FTC/ICO/EDPB sources). The *practitioner* (Reddit/X/LinkedIn) research is weak: those platforms were technically inaccessible to the research pass, so nearly all community "sentiment" came secondhand via vendor blogs and must be treated as hypotheses, not evidence. This memo labels every claim accordingly and never elevates anecdote to benchmark.

---

## 2. Research methodology

- Three parallel read-only research passes on 2026-07-18: (A) cold-email benchmarks + law/deliverability; (B) practitioner community sentiment; (C) fashion-operator vocabulary.
- Every claim is labelled: **[DATA-BACKED]** (primary/large dataset), **[PRACTITIONER-CONSENSUS]** (widely-held expert guidance, no single hard dataset), **[ANECDOTAL]** (single teardown/opinion), **[OFFICIAL]** (regulator/platform requirement).
- Sources that could not be opened at origin (FTC CAN-SPAM guide, ICO B2B page both returned HTTP 403) are flagged; content came from search-surfaced excerpts of the *same official domains* and any specific figure from them is marked "verify at source."
- No statistic in this memo was invented. Where sources conflict, the conflict is stated (§6).

---

## 3. Sources reviewed

**Benchmark / data:** Gong (cold-email stats; exec-reply data; follow-up study, 304,174 emails); Lavender (email length; subject-line data); Salesloft (cadence playbook). **Official:** Google/Gmail sender requirements (2024); FTC CAN-SPAM compliance guide *(403 — excerpts only)*; UK ICO B2B marketing + lawful-basis guidance *(403 — excerpts only)*; EDPB Guidelines 1/2024 on legitimate interest. **Practitioner (weak, mostly secondhand):** Josh Braun essays; Close blog (aggregating named practitioners); Mic journalism (fake reply threads); a University of Florida AI-sincerity study *(cited secondhand — unverified)*; Reddit r/sales, r/coldemail, r/startups **could not be accessed** and are not treated as evidence. **Fashion vocabulary:** PLM glossaries (3clickscloud, Kōbō), role job-descriptions (Velvet Jobs), trade sources (Apparel Resources, The F Word, Style Arcade, Tycoonstory). Full URLs in §11.

---

## 4. Data-backed findings

### 4.1 Length
- Lavender: optimal opening cold email **25–50 words**; cold emails viewed ~9 seconds on average; short/mobile-optimized emails reply better. **[DATA-BACKED]** — https://www.lavender.ai/blog/best-length-cold-email
- Gong: optimal **50–100 words**; reply rates decline sharply past ~100 words; classifies 30–150 as "longer" and finds longer wins for *meetings booked*. **[DATA-BACKED]** — https://www.gong.io/blog/cold-email-stats
- Follow-ups with **4+ sentences → ~15× more meetings** than ≤3-sentence "bubble-up" notes (dataset 304,174). **[DATA-BACKED]** — https://www.gong.io/blog/7-tips-for-writing-the-perfect-follow-up-sales-email-according-to-science
- **Reconciled range for a first cold touch: ~50–90 words / 3–5 sentences.** (Lavender optimizes reply; Gong optimizes meeting; both penalize >150 words and one-line follow-ups.)

### 4.2 Subject lines
- Lavender: **1–3 words (2 optimal)**; 2→4 words **-17.5% replies**; no title case **-30% opens**; questions **-56% opens**; numbers **-46% opens**; punctuation **-36% opens**. **[DATA-BACKED]** — https://www.lavender.ai/blog/cold-email-subject-line-tips
- Gong: subjects best at **1–4 words**. **[DATA-BACKED]** — https://www.gong.io/blog/do-execs-really-reply-to-cold-email-here-s-what-the-data-says
- **Rule: 1–4 words, Title Case, no punctuation, no numbers, no questions.**

### 4.3 CTA type (the single most decision-relevant finding)
- Gong Labs, **304,174 cold emails** (controlled for industry, size, sender reputation; primary-inbox only): interest CTA ~**12%** reply vs meeting-request ~**7%**; meeting asks ~**44% lower** reply at cold stage; positive-reply quality **68%** (interest) vs **41%** (meeting); interest CTAs still convert to meetings ~**15%**. **Reverses** at active-deal stage (specific-time asks then win ~37%). **[DATA-BACKED]** — https://growleads.io/blog/interest-based-ctas-vs-meeting-requests-study/
- **Rule: cold first touch = interest / correction / referral CTA. Specific-time meeting ask only after a positive reply.**

### 4.4 Pitching / buzzwords
- Gong: ROI/pitch language ~**-15%** success on the page opened; broader "pitching cuts replies" direction is data-backed, the larger "-57%" figure is **[PRACTITIONER-CONSENSUS]**, not verified on page. Buzzwords ("AI," "platform," feature-led) lower replies. — https://www.gong.io/blog/cold-email-stats
- **Rule: no "AI-native," "platform," feature lists, or ROI-buzzwords in first touch.**

### 4.5 Executives
- C-level are **~30.2% less likely** to reply to cold email than non-execs; value-led, company-specific content (benchmarks, insight) narrows the gap, generic meeting asks widen it. **[DATA-BACKED]** — https://www.gong.io/blog/do-execs-really-reply-to-cold-email-here-s-what-the-data-says
- **Founder-*as-sender* uplift: no primary dataset found → [ANECDOTAL].** We use Marta-as-sender for warm accounts on *relationship* grounds, not on a data claim.

### 4.6 Follow-ups
- Reply rates **decay per touch**: follow-up #2 ~31% → #8 ~14%. **[DATA-BACKED]**
- Phrasing (same 304,174 dataset): "Hope all is well" **+24%** meetings; "Thoughts?" **-20%**; "Never heard back" **-14%**; "Following up" **-5%**. **[DATA-BACKED]** — https://www.gong.io/blog/7-tips-for-writing-the-perfect-follow-up-sales-email-according-to-science
- **Rule: each follow-up adds a *new* idea (Gong's 4+ sentence finding), never guilt ("bumping this," "am I annoying you"). Reasonable spacing 3–7 business days.** (Exact day-spacing is [PRACTITIONER-CONSENSUS].)

### 4.7 Deliverability — Google 2024 sender requirements **[OFFICIAL]**
Source: https://support.google.com/a/answer/81126
- All senders (from Feb 1 2024): **SPF or DKIM**, valid **forward+reverse DNS (PTR)**, **TLS**.
- Bulk (>5,000/day to Gmail): **SPF and DKIM and DMARC** (p=none ok), **From-domain alignment**.
- **Spam rate < 0.3%** in Postmaster Tools (stay well under).
- **RFC 8058 one-click unsubscribe** for marketing mail + visible unsubscribe link.
- Manual sends outperform automated. Keep first touch plain-text-like, **no attachments**, minimal/zero links (best practice, not an explicit Google ban).

---

## 5. Practitioner observations (Reddit / X / LinkedIn) — **weak evidence, hypotheses only**

> Foreground caveat: Reddit and LinkedIn were inaccessible to the research pass. Almost everything here is either a named practitioner quote re-hosted on a vendor blog, or vendor marketing paraphrasing communities. Treat as directional. All reply-rate percentages from these sources are **unverified marketing**.

**Recurring complaints (directionally consistent):**
- Templated/copy-pasted personalization reads as the opposite of research (named: Brooklin Nash, via Close).
- Raw AI first lines ("I saw you're doing X…") backfire; lightly-AI-assisted rated far more "sincere" than heavily-AI (Univ. of Florida study, **cited secondhand — verify**).
- First-touch meeting/Calendly asks are "a big ask" and get ignored (named: James Laurain, via Close).
- Feature dumps / pitch-qualify-book in one email fail.
- Guilt-trip breakup lines breed resentment (though breakup emails "still convert" per vendors — contested).
- Fake "Re:"/"Fwd:" threads read as bait-and-switch and hurt deliverability (Mic journalism).
- A "creepiness line": personal/social details feel invasive; public *professional* facts (a hire, a launch, a talk) are fine.

**Recurring positives:**
- Lead with a genuinely useful asset instead of asking for time (named: Amy Volas, Josh Braun).
- "Permission to say no," low-ego, human tone; "is this something you'd be open to exploring?" over demanding a meeting.
- Write like a person, not a company.

These *reinforce* the benchmark findings; they do not independently prove anything.

---

## 6. Where evidence conflicts

| Question | Conflict | Resolution used |
|---|---|---|
| Email length | Lavender 25–50w (reply-optimized) vs Gong 50–150w (meeting-optimized) | First touch **50–90w**; both penalize >150w & one-liners |
| Follow-up length | Gong "4+ sentences → 15× meetings" vs practitioner "keep follow-ups short" | Follow-ups stay short **but carry a new substantive idea**, never a one-line bump |
| "Personalization triples replies" / "pitching -57%" | Direction data-backed; exact multipliers not visible on-page | Use direction, not the specific multiplier |
| Founder-as-sender uplift | Claimed everywhere; **no dataset** | Treated as anecdotal; sender choice driven by relationship |
| Multi-threading magnitude | Direction supported; % from vendor blogs | Multi-thread yes; no magnitude claim |

---

## 7. Rules that should govern Spindle outreach

1. **One verified trigger per email.** Tier A/B sources only in copy (see 02/verification). No inferred internal problems.
2. **50–90 words, 3–5 short sentences, plain text.**
3. **Subject: 1–4 words, Title Case, no punctuation/numbers/questions** (offer 3 options for testing).
4. **Recipient's operational language, not Spindle's pitch deck.** Use the §D vocabulary; never "blast radius," "AI-native," "single source of truth," "platform" (except with an IT/PLM stakeholder where technically necessary).
5. **Frame the problem as a hypothesis/question, never a diagnosis** ("I'm curious whether the approved version stays visible when a style crosses both teams" — not "your spreadsheets are breaking").
6. **≤ one sentence describing Spindle, tailored to the recipient's process.**
7. **CTA = interest / correction / referral.** No price, pilot, contract, LOI, or meeting time in a cold first touch.
8. **Operational champion before executive sponsor; one contact per account at a time.**
9. **Warm accounts (Marta's history) get a relationship-first note from Marta, flagged for her approval — never a generic template with an inserted "our CEO worked here."**
10. **Follow-ups add value, never guilt. Manual send, tracked at account level.**

---

## 8. Rules that should NOT be treated as universal

- **"25–50 words is always optimal."** That's Lavender's reply-optimized figure; meeting-oriented and executive cycles tolerate/benefit from a bit more. Range, don't dogmatize.
- **"Never send more than N words / N touches."** Cadence length depends on segment; don't hard-cap mechanically.
- **"Founder-signed always converts better."** Unproven — don't build the plan on it.
- **"A one-click unsubscribe footer makes EU sends lawful."** False (see §9). Compliance is a separate analysis.
- **Any specific reply-rate % from a vendor blog.** Not evidence; do not set targets from them.
- **Open rate as a success metric.** Degraded post-Apple MPP; use reply/positive-reply.

---

## 9. Legal & deliverability considerations (summary; full checklist in 07)

**US — CAN-SPAM [OFFICIAL, some figures 403-flagged]:** no opt-in required; but need truthful headers, non-deceptive subject, ad identification, **valid physical postal address**, working opt-out honored within **10 business days**, and liability can't be contracted away. Penalty up to ~$53k/email (inflation-adjusted — **verify at ftc.gov**).

**UK — PECR + UK GDPR [OFFICIAL]:** PECR e-mail rules **do not apply to corporate subscribers** → B2B email to a *company* address needs no consent. **BUT sole traders and most partnerships = individual subscribers** and need consent or PECR soft opt-in. UK GDPR still applies to the named person's data; lawful basis usually legitimate interest; **absolute right to object** to direct marketing (must stop, no balancing). Must never disguise identity; must give a valid opt-out + contact address in every message.

**EU — GDPR + ePrivacy [OFFICIAL]:** GDPR legitimate interest requires a documented **3-part test** (purpose / necessity / balancing) and per EDPB Guidelines 1/2024, **direct marketing is *not automatically* a legitimate interest**. **Plus** member-state ePrivacy transpositions vary — some require **consent even for B2B**. → The 37 EU contacts are the **highest legal-risk** segment; the original batch's "legitimate interest + footer" assumption is necessary but **not sufficient**. Flag for qualified legal review before EU sends.

**Deliverability:** SPF/DKIM/DMARC + reverse DNS + TLS; RFC 8058 one-click unsubscribe; spam <0.3% (Postmaster Tools); warm the domain; plain text; no attachments and ≤1 link in first touch; manual sending; bounce/complaint/suppression handling. (Full checklist: 07.)

> Not legal advice. Items above marked for qualified legal review before sending, especially EU.

---

## 10. Exact implications for the existing drafts

Measured on the current 71 drafts (see 02 for the full audit):

| Current-batch property | Measured | New rule | Verdict |
|---|---|---|---|
| "AI-native" in body | **71/71** | banned first-touch | **fail all** |
| "blast radius" | **71/71** | banned | **fail all** |
| Identical Spindle sentence | ~**56/71** near-verbatim | ≤1 tailored sentence, varied | **fail** |
| "12–16 week paid pilot" pitched | **71/71** | no price/pilot in first touch | **fail all** |
| Meeting/"15 minutes" CTA | **~70/71** | interest/referral CTA | **fail** |
| Subject length | avg **59 chars**, all >35, max 75 | 1–4 words, <35 chars | **fail all** |
| Body length | avg **100w**, 35 >100w | 50–90w | **half fail** |
| Problem stated as fact ("cascades invisibly") | frequent | hypothesis/question | **fail** |
| Parent-company stats as brand stats (e.g. Oxford → Lilly; group supplier counts) | present | forbidden | **fail — see 02/verification** |

**Conclusion:** the existing batch cannot be lightly edited to compliance with the evidence. It is a single templated architecture repeated 71× and must be rebuilt from the trigger up. That rebuild is 02–09.

---

## 11. Full source list (accessed 2026-07-18)
Gong: /blog/cold-email-stats · /blog/do-execs-really-reply-to-cold-email-here-s-what-the-data-says · /blog/7-tips-for-writing-the-perfect-follow-up-sales-email-according-to-science ·
Gong Labs 304K CTA study via https://growleads.io/blog/interest-based-ctas-vs-meeting-requests-study/ ·
Lavender: /blog/best-length-cold-email · /blog/cold-email-subject-line-tips ·
Salesloft Big Book of Sales Cadences (PDF) ·
Google sender requirements https://support.google.com/a/answer/81126 ·
FTC CAN-SPAM guide https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business *(403; excerpts)* ·
ICO B2B + lawful basis https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/ *(403; excerpts)* ·
EDPB Guidelines 1/2024 legitimate interest (PDF) ·
Josh Braun joshbraun.com; Close blog; Mic (fake reply emails); Univ. of Florida AI-sincerity study *(secondhand)* ·
Fashion vocab: 3clickscloud PLM glossary; Kōbō ERP-vs-PLM & PLM-vs-ERP; Velvet Jobs role JDs (technical designer, sourcing director, production manager, buyer, sustainability); Apparel Resources T&A; The F Word critical path *(403; excerpts)*; Style Arcade; Tycoonstory; Fashion Index.
