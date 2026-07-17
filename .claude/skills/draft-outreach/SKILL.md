---
name: draft-outreach
description: Draft personalized outreach from the approved, verified evidence set only. Use after /verify-evidence.
---

Draft outreach copy.

1. Confirm you have an **approved evidence set** from `/verify-evidence`. If not, stop.
2. Delegate to the **outreach-copywriter** subagent, passing ONLY the approved evidence. The
   copywriter has no web/Apollo access and must not invent facts.
3. Each drafted line must cite the evidence item id it relies on. Include the compliance footer
   placeholders (sender identity, physical address, unsubscribe).

Guardrails: no research/fetching here; drafts are written to local files only; nothing is sent.
Next step is `/review-outreach-batch`.
