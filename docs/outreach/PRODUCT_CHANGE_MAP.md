# The Fashion Product Change Map
### A one-page reference for what happens downstream when a product changes

> **Purpose of this asset.** This is an *educational leave-behind*, not a pitch. It is the thing Spindle offers in a follow-up ("worth sharing the one-page change map?"). It should be useful to a product operator even if they never talk to Spindle. Exactly **one** subtle Spindle line appears, at the very bottom.

---

## The idea in one line

In fashion, most delay and margin loss doesn't come from the *decision* to change something — it comes from the change not reaching everyone who needs to act on it, in time, on the right version.

A single change fans out. This map shows the fan-out for the eight most common triggers.

---

## The eight triggers → what moves downstream

For each trigger, the operator can read across: **what data changes → who's affected → what re-opens → what deadline moves → what supplier action is needed → what system record must update → what commercial decision is now at risk → who owns the next action.**

### 1. Fit change (fit comments after a fit session)
- **Data that changes:** measurements / points of measure, graded spec, the tech-pack revision number
- **Teams affected:** technical design, product development, the supplier's pattern room, QA
- **Approval that re-opens:** the fit approval; sometimes the PP (pre-production) sample sign-off
- **Deadline that moves:** the size-set or PP-sample date, and therefore the fit-approval milestone on the critical path
- **Supplier action:** re-cut and re-send the corrected sample; confirm graded measurements
- **System record:** PLM tech-pack version; the "approved sample" flag
- **Commercial risk:** if the wrong version reaches bulk, a full production run is off-spec
- **Owner of next action:** technical designer → then production

### 2. Cost change (a revised cost sheet or a new supplier quote)
- **Data that changes:** cost sheet line items, landed cost, the BOM if a component drove it
- **Teams affected:** buying/sourcing, merchandising/planning, finance
- **Approval that re-opens:** the margin/price approval; the buy quantity if margin breaks
- **Deadline that moves:** the order-placement (PO) date if re-negotiation is needed
- **Supplier action:** confirm the revised quote; re-quote alternatives
- **System record:** ERP cost + PO; PLM cost sheet
- **Commercial risk:** the style ships below target margin, or gets cut from the range
- **Owner of next action:** buyer/sourcing → then merchandising

### 3. Colour / colourway change
- **Data that changes:** the colourway on the tech pack, the lab dip / strike-off approval, the BOM colour codes
- **Teams affected:** design, product development, the mill/dye house, merchandising
- **Approval that re-opens:** lab-dip / strike-off approval
- **Deadline that moves:** fabric commitment date (dyeing lead time)
- **Supplier action:** re-dip, re-approve, confirm minimums for the new colour
- **System record:** PLM colourway + material; line sheet imagery
- **Commercial risk:** the assortment loses a colour story, or a drop launches incomplete
- **Owner of next action:** design/PD → then merchandising for assortment

### 4. Material / component change (substitution, or a sustainability swap)
- **Data that changes:** BOM, material spec, certification/traceability record, cost
- **Teams affected:** sourcing, product development, sustainability/compliance, QA
- **Approval that re-opens:** material approval; any published product-level sustainability claim
- **Deadline that moves:** material lead time → PP sample → the whole downstream chain
- **Supplier action:** confirm availability, MOQ, certification evidence
- **System record:** BOM in PLM; DPP / traceability data; ERP cost
- **Commercial risk:** a published claim goes out of sync with the actual product; margin shifts
- **Owner of next action:** sourcing → then sustainability to reconcile the claim

### 5. Quantity change (a buy re-forecast)
- **Data that changes:** order quantity, size ratio, allocation by channel/door
- **Teams affected:** planning, buying, production, the supplier
- **Approval that re-opens:** the buy sign-off; sometimes price (breaks at volume tiers)
- **Deadline that moves:** production booking against supplier capacity
- **Supplier action:** confirm capacity for the revised quantity; re-price if a tier changes
- **System record:** ERP PO; allocation plan
- **Commercial risk:** over-buy → markdown; under-buy → lost sales / cannibalization
- **Owner of next action:** planner → then production

### 6. Supplier change (new vendor, or re-sourcing)
- **Data that changes:** supplier of record, cost, lead time, capabilities, the whole cost/quality baseline
- **Teams affected:** sourcing, product development, QA, compliance
- **Approval that re-opens:** the sample approval chain restarts with the new vendor
- **Deadline that moves:** everything downstream of first sample
- **Supplier action:** onboard, quote, sample, confirm compliance
- **System record:** PLM supplier link; ERP vendor + cost; compliance/audit records
- **Commercial risk:** critical-path slip; quality regression; certification gap
- **Owner of next action:** sourcing → then PD/QA

### 7. Delivery-date change (a supplier moves the delivery window)
- **Data that changes:** delivery window, the T&A / critical-path dates
- **Teams affected:** merchandising, planning, retail/e-commerce, buying
- **Approval that re-opens:** launch-readiness sign-off; the drop plan
- **Deadline that moves:** the launch/drop date; allocation timing
- **Supplier action:** confirm the realistic revised date; expedite options
- **System record:** ERP delivery; drop/launch calendar
- **Commercial risk:** late launch → missed selling window → lost sales; empty allocation
- **Owner of next action:** planning/merchandising → then retail

### 8. Approval-status change (a sign-off is given, withheld, or reversed)
- **Data that changes:** the approval flag itself, and *which version* is now the approved one
- **Teams affected:** everyone downstream of the gate — PD, production, QA, buying
- **Approval that re-opens:** the specific gate (fit / lab-dip / PP / final)
- **Deadline that moves:** the next milestone that was waiting on this gate
- **Supplier action:** proceed on the approved version — or stop and hold
- **System record:** PLM approval state + version pointer
- **Commercial risk:** production proceeds on an unapproved or superseded version
- **Owner of next action:** whoever owns the gate → then production

---

## How to read your own exposure (a 60-second self-check)

Pick your last real change. Ask:
1. How many people found out **more than 48 hours** after the change?
2. Was anyone working from the **wrong version** at any point?
3. Which downstream **deadline moved**, and who updated the calendar?
4. Did the change ever get reflected in **both** PLM/ERP **and** the working files (email, Excel, shared folders)?
5. Which **commercial decision** (margin, launch, allocation) was quietly at risk before someone noticed?

If two or more of these are uncomfortable, the cost isn't the change — it's the propagation of the change.

---

<sub>Spindle is exploring how to keep these change-to-action chains connected to the product record, so the answers to those five questions are visible by default. If the map is useful, we'd value 15 minutes of your view on where it's most and least accurate for how **[Company]** actually works.</sub>

---

## Design brief — turning this into a one-page PDF

- **Format:** single landscape A4/Letter page (or a 2-page portrait if the matrix needs room). Print-safe margins.
- **Core visual:** a left column of the **8 trigger icons** (fit, cost, colour, material, quantity, supplier, delivery, approval) feeding a horizontal 8-column matrix. Columns = the eight downstream questions (data → teams → approval → deadline → supplier action → system → commercial risk → owner). Keep cells to 3–6 words.
- **Hierarchy:** triggers are the loudest element; the "commercial risk" column is the second emphasis (this is what an exec scans for). De-emphasize the system column.
- **Palette:** restrained, editorial, fashion-credible — warm paper/ivory ground, near-black text, a single muted accent for the risk column (a desaturated clay or ink-blue). No neon, no gradient hero. It should look like a trade one-pager, not a SaaS ad.
- **Type:** one characterful serif for the trigger names + section heads; a clean grotesque/sans for the matrix body; tabular figures if any numbers appear. Generous leading in the matrix.
- **Branding:** tiny Spindle wordmark bottom-left; the single CTA line bottom-right. No logo wall, no feature list, no screenshots.
- **Tone check:** a merchandiser or PD manager should be able to pin it to a wall and use it in a T&A meeting without Spindle in the room. That's the bar.
- **Do NOT include:** pricing, "AI", "platform", the word "blast radius", product screenshots, or any claim about a specific brand.
