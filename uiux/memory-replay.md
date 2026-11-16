# Page Specification: Project Memory Replay (`memory-replay.md`)
**Route**: `/w/[workspaceId]/responsibilities/[responsibilityId]/timeline`  
**Role**: The Historical Time Machine, Context Reconstruction Engine, and Visual Chrono-Ribbon.

---

## 1. Strategic Pitch & Narrative Arc

* **The Core Job**: When an incoming engineer inherits a mission-critical responsibility (e.g. *Production Deployments*), they are terrified of breaking things because they don't know the history: *Why does every deploy require a canary? What broke 6 months ago? Who decided on this architecture?*
  Memory Replay solves this by reconstructing 1 year of GitHub PRs, Linear tickets, Notion docs, and ownership changes into an interactive, cinematic timeline.
* **Narrative Arc**:
  1. **Top Cockpit**: Responsibility title, event counters, category filter chips, and the **Replay Controller** (`[ ▶ PLAYBACK HISTORY ]`).
  2. **The Horizontal Chrono-Ribbon (Center)**: An interactive, scrubbable timeline track (styled like an audio DAW / video editor) with color-coded event nodes.
  3. **Causal Connecting Arcs**: Visual bezier arcs linking PR merges directly to the incidents they fixed (`Fixes Outage #28`).
  4. **The AI Narrative Chapter Constellation**: Grounded summary chapters floating above the timeline, explicitly labeled `INFERRED // CITING 8 EVENTS`.
  5. **The History Oracle (Q&A)**: Grounded conversational prompt that answers historical questions with exact citations or states *"Not in evidence"*.

---

## 2. Section-by-Section Blueprint

### Section 1: The Chrono-Controller Header
* **Layout**: Chamfered elevated plate `#0E1118` with hairline top border.
* **Elements**:
  - Title: *"Project Memory Replay"* in `Cabinet Grotesk` (`text-3xl font-black text-white`).
  - Responsibility: *"Production Deployments"* with criticality badge `[ CRITICAL ]`.
  - Telemetry Counter: `[ 84 TOTAL EVENTS RECONSTRUCTED // 0 GUESSES ]`.
  - **The Playback Transport Controls**:
    - Button: Acid Chartreuse Pill: `[ ▶ REPLAY HISTORY ]` (animates playhead across the 12-month timeline).
    - Scrub Speed Toggle: `[ 1x ]` · `[ 2x ]` · `[ 5x ]`.
  - **Category Filter Chips**:
    - `[ ● ALL (84) ]` (Bone white)
    - `[ ● INCIDENTS (6) ]` (Crimson `#FF2A55`)
    - `[ ● PR MERGES (42) ]` (Emerald `#00F5A0`)
    - `[ ● DECISIONS (8) ]` (Amber `#F59E0B`)
    - `[ ● TECH CHANGES (18) ]` (Violet `#8B5CF6`)
    - `[ ● RUNBOOKS (10) ]` (Cyan `#06B6D4`)

---

### Section 2: The Horizontal Chrono-Ribbon (The DAW Track)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                        │
│   JAN 2026        MAR 2026            JUN 2026            SEP 2026            NOV 2026 │
│   ───┬───────────────┬───────────────────┬───────────────────┬───────────────────┬──── │
│      │               │   ╭───────────────╯                   │                   │     │
│      │               │   │ [CAUSAL LINK: FIXES OUTAGE #28]   │                   │     │
│      ▼               ▼   ▼                                   ▼                   ▼     │
│     [●]             [●] [●]                                 [●]                 [●]    │
│    Stripe        Outage #28:      PR #142: Mandatory       K8s 1.30          Canary v2│
│    Webhook       Canary Bypass    Canary Deployments       Upgrade            Active   │
│   (Decision)     (Incident)       (GitHub PR Merge)        (Tech Change)      (Today)  │
│                                                                                        │
│   ──────────────────────────────────────────────────────────────────────────────────   │
│   AI NARRATIVE CHAPTER CONSTELLATION:                                                  │
│   ┌────────────────────────────────────────────────────────────────────────────────┐   │
│   │ CHAPTER 02 // THE MANDATORY CANARY POLICY (INFERRED // 4 EVENTS CITED)         │   │
│   │ Following Outage #28 where an unverified build degraded checkout, Arjun Rao   │   │
│   │ and Maya Chen merged PR #142 requiring canary validation for all deploys.      │   │
│   │ [ CITED EVENTS: INC_28, PR_142, ADR_04, RUNBOOK_V2 ]                          │   │
│   └────────────────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

#### The Chrono-Track Mechanics:
* **The Track**: A horizontal scrubbable rail with months mapped chronologically.
* **Event Nodes**:
  - Rendered as glowing circular pins along the rail.
  - Hovering an event node illuminates a glassmorphic popover with the full author avatar, commit SHA, PR diff excerpt, or Incident postmortem summary.
* **Causal Connecting Arcs**:
  - Rendered as illuminated bezier curves connecting related events.
  - Example: Arc drawn from `Incident #28` to `PR #142` labeled *"Fixes Outage #28"*.

#### The AI Chapter Cards:
* **Visuals**:
  - Floating glassmorphic cards anchored directly above the relevant cluster of events.
  - Badge: `INFERRED CHAPTER` (Bone white border, `Geist Mono text-[10px]`).
  - Body: 2–3 sentences summarizing what happened, why it matters, and citing the exact event IDs.

---

### Section 3: The History Oracle Console (Grounded Q&A)
* **Layout**: Pinned bottom console with dark inset well `#06070B` and glowing hairline border.
* **Header**: *"Ask About This History (Strictly Grounded in 84 Reconstructed Events)"*.
* **Interactive Pre-Baked Prompt Chips**:
  - `[ "Why was canary deployment made mandatory?" ]`
  - `[ "What broke during the October database failover?" ]`
  - `[ "Who approved the Stripe webhook refactor?" ]`
* **Answer Card Anatomy**:
  - Grounded Answer: Cites exact event pins `[E4: PR #142]`.
  - Negative Knowledge Safety: If the user asks something outside the record (e.g. *"What is the AWS root password?"*), the Oracle displays an illuminated banner:
    **`NOT IN RECONSTRUCTED HISTORY: SPECULATION REFUSED.`**

---

## 3. Cross-Page Continuity Contract
* **Entry Vectors**:
  - From `/w/[workspaceId]/responsibilities/[id]` via *"Memory Replay"* button.
  - From `/cases/[caseId]/capsules/[capsuleId]` via *"Where this work came from"*.
* **Exit Vectors**:
  - Clicking any cited PR/Issue opens the external source in GitHub/Linear in a secure new tab.
  - Clicking *"Return to Handover Brief"* brings the incoming owner back to their active case capsule.
