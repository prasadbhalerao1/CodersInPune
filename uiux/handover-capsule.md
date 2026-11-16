# Page Specification: The Classified Handover Dossier & Grounded Copilot (`handover-capsule.md`)
**Route**: `/w/[workspaceId]/cases/[caseId]/capsules/[capsuleId]`  
**Role**: The Official Handover Artifact, Proof-Backed Intelligence Brief, and Grounded Copilot Console.

---

## 1. Strategic Pitch & Narrative Arc

* **The Core Job**: Deliver an airtight, role-specific handover document for the incoming engineer that eliminates speculation. Provide an interactive AI Copilot that answers questions strictly from authorized evidence, refuses to hallucinate, and records legally non-repudiable recipient acknowledgment.
* **Narrative Arc**:
  1. **Top Security Header**: Classified intelligence dossier formatting, version watermark (`VERSION 2.0 // APPROVED`), and audience privacy badge.
  2. **The Handover Briefing (Left / Center)**: Structured sections (*What you now own*, *In-flight work*, *Decisions made*, *Knowledge gaps*, *Risks & conflicts*). Every single statement is tagged with its origin (`Fact`, `Rule`, `AI inference`) and clickable evidence citations (`[E1]`, `[E4]`).
  3. **Holographic Citation Hover Popovers**: Hovering over any citation tag instantly reveals the underlying raw Git PR, commit SHA, Linear ticket, or Notion excerpt.
  4. **The Grounded Handover Copilot (Right Rail)**: Live conversational terminal where the successor asks questions and receives answers cited to exact lines, with a prominent stamp of *"Speculation Refused"* if unanswerable.
  5. **The Cryptographic Acknowledgment Seal**: The incoming owner clicks to seal the handover, generating a permanent audit receipt.

---

## 2. Section-by-Section Blueprint

### Section 1: The Dossier Security Header
* **Visuals (Visual Source: Dark Luxury & Cyber-Physical Bevels)**:
  - Background: Obsidian plate with top metallic hairline sheen.
  - Watermark: `SOVEREIGN CONTINUITY ARTIFACT // VERSION 2.0 (APPROVED)`.
  - Recipient Identity: *Dev Patel (SRE)* with role and permissions clearance.
  - Auditor Seal: `APPROVED BY MAYA CHEN (ADMIN) // SOD VERIFIED`.
  - **Version Switcher & Diff Trigger**:
    - Dropdown: `[ Version 2.0 (Active) ]` · `[ Version 1.0 (Initial Draft) ]`.
    - Button: `[ ⚡ COMPARE VERSIONS (SIDE-BY-SIDE DIFF) ]`.

---

### Section 2: The Two-Column Dossier & Copilot Console

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                        │
│   LEFT / CENTER (65% WIDTH):                   RIGHT RAIL (35% WIDTH):                 │
│   THE CLASSIFIED HANDOVER BRIEF                THE GROUNDED COPILOT CONSOLE            │
│                                                                                        │
│   ┌────────────────────────────────────────┐   ┌──────────────────────────────────┐    │
│   │ SECTION 01 // WHAT YOU NOW OWN         │   │ ⚡ HANDOVER COPILOT (GROUNDED)   │    │
│   │                                        │   │ [ ● CITATIONS VALIDATED: 100% ]  │    │
│   │ [FACT] You are primary owner of        │   │                                  │    │
│   │ Production Deployments starting 24 Nov.│   │ Dev Patel:                       │    │
│   │ Cited: [E1: Catalog Assignment #42]    │   │ "How do I deploy payments-api?"  │    │
│   │                                        │   │                                  │    │
│   │ SECTION 02 // IN-FLIGHT WORK           │   │ Copilot (citing E3 & E4):        │    │
│   │                                        │   │ "Every payments-api deployment   │    │
│   │ [WORK] 3 PRs are open on deploy-repo:  │   │  requires an approved canary run │    │
│   │ • PR #142: Canary validator (E3)       │   │  per PR #142 [E4]. Rollback is   │    │
│   │ • PR #145: Migration script (E4)       │   │  automated via script /bin/rb."  │    │
│   │                                        │   │                                  │    │
│   │ SECTION 03 // RISKS & CONFLICTS        │   │ Dev Patel:                       │    │
│   │                                        │   │ "What is the AWS root password?" │    │
│   │ [CONFLICT] Two deploy runbooks         │   │                                  │    │
│   │ disagree on canary requirement:        │   │ Copilot:                         │    │
│   │ • Doc A (Notion: E5) says optional.    │   │ ┌──────────────────────────────┐ │    │
│   │ • Doc B (Repo: E6) says mandatory.     │   │ │ ⚠️ NOT IN AUTHORIZED EVIDENCE │ │    │
│   │ ACTION: Mandatory canary confirmed.    │   │ │ SPECULATION STRICTLY REFUSED │ │    │
│   │                                        │   │ └──────────────────────────────┘ │    │
│   │ ────────────────────────────────────── │   │                                  │    │
│   │ [ 🔒 ACKNOWLEDGE HANDOVER RECEIPT ➔ ]  │   │ [ Ask about this handover...   ] │    │
│   └────────────────────────────────────────┘   └──────────────────────────────────┘    │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Left Panel: The Structured Handover Dossier
* Structured into Relay's 9 committed sections:
  1. *What you now own*
  2. *In-flight work*
  3. *Decisions already made*
  4. *Knowledge gaps & open questions*
  5. *Risks & conflicts*
  6. *Dependencies*
  7. *From the handover interview*
  8. *Recommended first steps*
  9. *Other findings*
* **Origin Tag Badges**:
  - `[FACT]` (Bone White pill)
  - `[WORK]` (Emerald pill)
  - `[CONFLICT]` (Crimson warning pill)
  - `[RULE]` (Amber pill)
  - `[AI INFERENCE]` (Cyan pill)
* **Citation Hover Cards**:
  - Every citation `[E3]`, `[E4]` is rendered as a glowing monospace badge.
  - Hovering triggers a glassmorphic popover showing author, commit SHA, PR diff excerpt, and a direct link to GitHub/Linear.

#### Right Rail: The Grounded Handover Copilot
* **The Trust Moat (The Harvey Standard)**:
  - Copilot answers **strictly** from the case's evidence pool.
  - When an answer is found, it formats the response with verified citation chips `[E3]`, `[E4]`.
  - When the user asks a question whose answer does not exist in the evidence (e.g. *"What is the AWS root password?"*), Copilot displays an illuminated crimson/amber security badge:
    **`NOT IN AUTHORIZED EVIDENCE: SPECULATION REFUSED.`**
  - This single behavior proves to judges that Relay is enterprise-grade and immune to hallucinations.

---

### Section 3: The Cryptographic Acknowledgment Seal
* **Location**: Sticky bottom action bar for the recipient (Dev Patel).
* **The Interaction**:
  - Checkbox: *"I, Dev Patel, confirm receipt of this handover brief (v2.0) and accept primary accountability for Production Deployments starting 24 Nov 2026."*
  - Action Button: Monumental Acid Chartreuse Pill: **`SEAL & ACKNOWLEDGE HANDOVER ➔`**.
  - Animated Result: Stamped with an animated SVG digital seal: `[ ACKNOWLEDGED // DEV PATEL // 2026-11-12T20:30Z // AUDIT ID: 019a... ]`.
  - Unlocks the **Next Steps Roadmap**: Shows Dev's immediate tasks, calendar links, and direct shortcuts to Memory Replay.

---

## 3. Cross-Page Continuity Contract
* **Entry Vectors**:
  - From `/w/[workspaceId]` via *"Open Handover Dossier"* on the top banner.
  - From `/cases/[caseId]` via *"Open Handover Capsule & Q&A"*.
* **Exit Vectors**:
  - Clicking *"Open Memory Replay"* under *Where this work came from* navigates to `/responsibilities/[id]/timeline`.
  - Clicking *"Acknowledge"* commits the acknowledgment in PostgreSQL, triggers audit logs, and redirects to `/w/[workspaceId]/my-work`.
