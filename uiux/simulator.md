# Page Specification: The "What If?" Continuity Simulator War Room (`simulator.md`)
**Route**: `/w/[workspaceId]/simulator`  
**Role**: The Strategic Forecasting Deck, Blast-Radius Calculator, and Pre-Emptive Handover Architect.

---

## 1. Strategic Pitch & Narrative Arc

* **The Core Job**: Transform what is normally an abstract fear (*"What happens if Arjun resigns?"*) into an exact, mathematical, visual forecast. Prove that Relay can predict the blast radius of absence, discover cascading dependencies, and recommend successors without burning them out.
* **Narrative Arc**:
  1. **Top Cockpit Controls**: Select the operator (*Arjun Rao*) and drag the absence duration slider (*14 Days*).
  2. **The Blast-Radius Radar (Center)**: Visual topology map showing unowned systems pulsing in alarm crimson.
  3. **The Readiness Delta**: Side-by-side score comparison:
     - *Baseline Without Cover*: **55/100** (Critical Vulnerability).
     - *Simulated With Dev Patel*: **88/100** (Recovered).
  4. **The Candidate Overload Safeguard**: Dev Patel is recommended, but Relay's algorithm detects he will carry 2.4x the team's load and raises an amber warning.
  5. **The Sovereign Action**: 1-click to convert this simulation into a real, audited handover case.

---

## 2. Section-by-Section Blueprint

### Section 1: The Tactical Cockpit Selector Bar
* **Layout**: Full-width elevated plate `#0E1118` with metallic hairline border.
* **Controls**:
  - **Operator Selector**: High-contrast dropdown featuring avatars, display names, and roles (*"Arjun Rao · Platform Lead"*).
  - **Absence Duration Slider**: Tactile horizontal slider with illuminated snap points:
    `[ 3 DAYS ]`  ───  `[ 1 WEEK ]`  ───  `[ 14 DAYS (ACTIVE) ]`  ───  `[ 1 MONTH ]`  ───  `[ INDEFINITE ]`
  - **Live Indicator**: `[ SIMULATION RUNNING: READ-ONLY // ZERO DB WRITES ]` in `Geist Mono` with pulsing amber dot.

---

### Section 2: The Three-Column War Room Matrix

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                        │
│   COLUMN 1 (LEFT):           COLUMN 2 (CENTER):             COLUMN 3 (RIGHT):          │
│   THE ABSENT OPERATOR        THE BLAST-RADIUS TOPOLOGY      SUCCESSOR LOAD BALANCING   │
│                                                                                        │
│   ┌──────────────────────┐   ┌──────────────────────────┐   ┌──────────────────────┐   │
│   │ Arjun Rao            │   │  (Arjun Rao) ──[ABSENT]  │   │ CANDIDATE 01:        │   │
│   │ Platform Lead        │   │        │                 │   │ Dev Patel (SRE)      │   │
│   │                      │   │        ▼                 │   │                      │   │
│   │ OWNED SYSTEMS (4):   │   │  [Production Deployments]│   │ READINESS: 88/100    │   │
│   │ 🔴 Prod Deployments  │   │  🔴 0 Active Backups     │   │ Current Load: 3      │   │
│   │ 🟡 Payments API      │   │        │                 │   │ Inherited:    2      │   │
│   │ 🟢 Kubernetes Infra  │   │        ▼                 │   │ Total:        5      │   │
│   │ 🟢 Observability     │   │  [Downstream: Checkout]  │   │                      │   │
│   │                      │   │  ⚠️ Ripple Impact Risk   │   │ ⚠️ OVERLOAD BREACH:  │   │
│   │ TASKS DUE IN WINDOW: │   │                          │   │ 2.4x Team Average    │   │
│   │ • Canary deploy v2.4 │   │ BASELINE SCORE: 55/100   │   │                      │   │
│   │ • Cert rotation      │   │ (Critical Failure Mode)  │   │ [ SIMULATE DEV ➔ ]   │   │
│   └──────────────────────┘   └──────────────────────────┘   └──────────────────────┘   │
│                                                                                        │
│   ──────────────────────────────────────────────────────────────────────────────────   │
│   COMMAND ACTION:                                                                      │
│   [ ● EXECUTE THE TRANSFER (PRE-FILLED WITH ARJUN & DEV) ⟶ ]                           │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Column 1: The Absent Operator Dossier
* **Visuals**:
  - High-contrast monochromatic portrait with status pill: `SIMULATED UNAVAILABLE`.
  - List of affected responsibilities sorted by criticality (Critical items badge with glowing crimson dot).
  - **Open Work Due in Window**: In-flight GitHub PRs, Linear tickets, and scheduled tasks that fall due during the 14-day absence.

#### Column 2: The Blast-Radius Dependency Graph
* **Visuals**:
  - Dynamic interactive SVG node graph.
  - Arjun's central node is dimmed with a slashed red boundary.
  - Cascading dependency lines illuminate in red, connecting to unowned services (*Production Deployments*) and propagating downstream to dependent systems (*Payments API*, *Checkout Service*).
  - Center Gauge: **Baseline Readiness Score: `55/100`** with breakdown tooltip ($60\%$ coverage, $25\%$ fresh knowledge, $15\%$ redundancy).

#### Column 3: Successor Candidates & Overload Balancing
* **The Algorithmic Moat**:
  - Displays all eligible team members ranked by affinity and historical connection.
  - **The Overload Safeguard**: If a candidate would carry $\ge 2 \times$ team average and $\ge 4$ responsibilities, a glowing amber banner locks onto the card:
    `⚠️ OVERLOAD ALERT: Dev will carry 2.4x typical load. Risk of burnout cascade.`
  - Action on Candidate: Button: `"SIMULATE WITH DEV ➔"`. When clicked, the graph reroutes, and the Readiness Score jumps from `55` to `88/100`.

---

### Section 3: The Command Execution Footprint
* **Banner**: Full-width floating bottom rail.
* **Text**: *"Satisfied with this continuity scenario? Move from simulation into an audited case with zero data re-entry."*
* **Button**: Monumental Acid Chartreuse Pill:
  **`INITIALIZE AUDITED HANDOVER CASE ➔`** (`bg-[#D2FF00] text-black font-extrabold text-sm uppercase px-8 py-3.5 rounded-full hover:shadow-[0_0_32px_rgba(210,255,0,0.6)]`).

---

## 3. Cross-Page Continuity Contract
* **Entry Vectors**:
  - From `/w/[workspaceId]` via *"Simulate Absence Impact"* on Key-Person Exposure card.
  - From `/w/[workspaceId]/people/[personId]` via *"What if ... is away?"*.
* **Exit Vector**:
  - Clicking *"Initialize Audited Handover Case"* transitions to `/w/[workspaceId]/cases/new` with `affected_person_id=Arjun` and `backup_person_id=Dev` pre-populated, carrying over all simulated parameters into a real case.
