# Page Specification: Mission Control Overview Dashboard (`workspace-overview.md`)
**Route**: `/w/[workspaceId]`  
**Role**: The Operational Nerve Center, Situational Awareness Command Deck, and Daily Driver.

---

## 1. Strategic Pitch & Narrative Arc

* **The Core Job**: The moment an engineering leader or continuity manager opens this screen, they must immediately know:
  1. **Is our organization secure against sudden departure right now?** (The Continuity Gyroscope score).
  2. **Is a critical handover actively in flight?** (The Baton in Flight banner).
  3. **Where are our ticking time-bombs?** (Key-person bottlenecks and unowned critical services).
* **Narrative Arc**:
  - Top Rail: Urgent Handover Alert Banner (illuminated in Baton Copper).
  - Center Left: The **Multi-Axis Continuity Gyroscope** (concentric telemetry dial).
  - Center Right: The **Active Handover Command Card** (Arjun Rao ➔ Dev Patel).
  - Bottom Left: **Key-Person Exposure Radar** (single points of failure ranked by criticality).
  - Bottom Right: **Guided Continuity Drills & Walkthroughs** (interactive tours that unlock dynamically with data).

---

## 2. Section-by-Section Blueprint

### Section 1: The "Transfer In Flight" Operational Handover Banner
* **Condition**: Renders prominently whenever a case is assigned to or waiting on the current user.
* **Layout**: Full-width chamfered plate across the top of the content area.
* **Visual Styling (Visual Source: Sneaker Crimson & Copper Accent)**:
  - Background: Deep charcoal with an illuminated **Amber Alert border** (`border-[#F59E0B]/40 shadow-[0_0_24px_rgba(245,158,11,0.15)]`).
  - Left Icon: Pulsing illuminated cryptographic seal glyph.
  - Headline: *"A HANDOVER CASE IS WAITING FOR YOUR ACKNOWLEDGEMENT"* in `Cabinet Grotesk` (`font-bold text-white tracking-wide`).
  - Subhead: *"Arjun Rao has transferred 2 critical responsibilities (Production Deployments, Platform On-Call) to Dev Patel."*
  - Action: Solid Acid Chartreuse Pill Button: `"OPEN HANDOVER DOSSIER ➔"` (`bg-[#D2FF00] text-black font-bold text-xs uppercase px-5 py-2.5 rounded-full`).

---

### Section 2: The Two-Column Command Matrix

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                        │
│   ┌────────────────────────────────────────┐  ┌──────────────────────────────────────┐ │
│   │ THE CONTINUITY GYROSCOPE               │  │ ACTIVE HANDOVER: ARJUN RAO (DEPARTURE)│ │
│   │                                        │  │                                      │ │
│   │        ╭───────────────╮               │  │   Phase: READY FOR TRANSFER          │ │
│   │     ╭──╯   78 / 100    ╰──╮            │  │   Transferred to: Dev Patel          │ │
│   │    │  CONTINUITY INDEX     │           │  │   Effective: 24 Nov (12d remaining)  │ │
│   │     ╰──╮               ╭──╯            │  │                                      │ │
│   │        ╰───────────────╯               │  │   [●] Plan Scope: 2 Responsibilities │ │
│   │                                        │  │   [●] Grounded Copilot Brief Ready   │ │
│   │   [●] Primary Coverage: 92% (Emerald)  │  │   [●] Approved by Maya Chen (Admin)  │ │
│   │   [●] Fresh Knowledge:  64% (Copper)   │  │                                      │ │
│   │   [●] Backup Redundancy:48% (Crimson)  │  │   [ REVIEW BRIEF & COPILOT ➔ ]       │ │
│   └────────────────────────────────────────┘  └──────────────────────────────────────┘ │
│                                                                                        │
│   ┌────────────────────────────────────────┐  ┌──────────────────────────────────────┐ │
│   │ ⚠️ KEY-PERSON EXPOSURE (BUS FACTOR)    │  │ GUIDED CONTINUITY DRILLS             │ │
│   │                                        │  │                                      │ │
│   │   Arjun Rao (Platform Lead)            │  │   [▷] Memory Replay Drill            │ │
│   │   Sole holder: Production Deployments  │  │       Watch how Deployments evolved  │ │
│   │   [ SIMULATE ABSENCE IMPACT ➔ ]        │  │                                      │ │
│   │                                        │  │   [▷] What-If Simulation Drill       │ │
│   │   Maya Chen (Infrastructure)           │  │       Forecast leave blast radius    │ │
│   │   Sole holder: Cloud Infrastructure    │  │                                      │ │
│   │   [ SIMULATE ABSENCE IMPACT ➔ ]        │  │   [▷] Grounded Copilot Drill         │ │
│   └────────────────────────────────────────┘  └──────────────────────────────────────┘ │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Panel 1: The Continuity Gyroscope (Concentric Telemetry Dial)
* **Visual Styling**:
  - An interactive vector dial with 3 concentric rings:
    - **Outer Ring (Emerald `#00F5A0`)**: Primary Owner Coverage (`92%`).
    - **Middle Ring (Copper `#F59E0B`)**: Fresh, Non-Stale Knowledge (`64%`).
    - **Inner Ring (Crimson `#FF2A55`)**: Secondary Backup Redundancy (`48%`).
  - Center: Monumental numeral `78/100` in `Cabinet Grotesk` (`text-5xl font-black text-white`).
  - Below: Telemetry legend with click-to-filter triggers that open filtered catalog views.

#### Panel 2: The Active Handover Command Card
* **Visual Styling**:
  - Elevated plate with 5-stage mechanical progress tracker: `[ Intake ➔ Planning ➔ Approved ➔ Executing ➔ Verified ]`.
  - Stamped with the current case status badge: `READY_FOR_TRANSFER` (Solid Acid Chartreuse pill).
  - Recipient profile chip: *Dev Patel* with avatar and role.
  - Action: Chartreuse pill button to jump directly into the Handover Capsule.

#### Panel 3: Key-Person Exposure Radar (The Bus Factor Matrix)
* **The Strategic Job**: Highlight sole owners of critical work before they resign.
* **Card Elements**:
  - Lists operators who solely own $\ge 1$ critical responsibility.
  - Displays their name, avatar, and the exposed critical responsibilities.
  - **Instant Action**: A dedicated pill button on each person: `"SIMULATE ABSENCE IMPACT ➔"` which links directly into the Simulator with that person pre-selected.

#### Panel 4: Guided Continuity Drills & Walkthroughs
* **The Strategic Job**: Onboarding for judges and new operators.
* **Tours Supported**:
  1. *Project Memory Replay Drill*: 3-minute guided tour of production deployment history.
  2. *What-If Absence Simulation Drill*: 2-minute simulation of Arjun leaving.
  3. *Handover Copilot Q&A Drill*: 3-minute test of grounded AI answering.

---

## 3. Cross-Page Continuity Contract
* **Entry**:
  - From `/workspaces` upon selecting an organization.
* **Exit Vectors**:
  - Clicking *"Review Brief"* jumps to `/cases/[caseId]/capsules/[capsuleId]`.
  - Clicking *"Simulate Absence Impact"* jumps to `/simulator?person=[personId]`.
  - Clicking a Responsibility jumps to `/responsibilities/[id]/timeline`.
