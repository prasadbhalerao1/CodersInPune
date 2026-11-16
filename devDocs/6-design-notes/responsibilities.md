# Page Specification: Responsibility Catalog & Stewardship Matrix (`responsibilities.md`)
**Routes**: `/w/[workspaceId]/responsibilities` and `/w/[workspaceId]/responsibilities/[responsibilityId]`  
**Role**: The Master Ownership Registry, Accountability Ledger, and Stewardship Matrix.

---

## 1. Strategic Pitch & Narrative Arc

* **The Core Job**: Serve as the indisputable single source of truth for **who is on the hook for what**. Replace stale spreadsheets, buried Backstage team fields, and vague Slack channels with an active, audited ownership ledger featuring valid-time temporal history, backup coverage, and linked asset stewardship.
* **Narrative Arc**:
  1. **Top Telemetry Cockpit**: Total responsibilities, coverage ratio, criticality breakdown (`Critical`, `High`, `Standard`, `Low`), and filter chips.
  2. **The Tactical Responsibility Matrix (Grid)**: Replaces flat HTML tables with tactile, hardware-inspired operator cards. Each card displays current primary holder, backup holder, criticality glow badge, and recent activity sparkline.
  3. **The Responsibility Detail Dossier (`/[id]`)**: Deep-dive view showing temporal ownership continuum, linked infrastructure assets, verified knowledge items, and the direct gateway into **Project Memory Replay**.

---

## 2. Section-by-Section Blueprint

### Section 1: The Catalog Command Header
* **Layout**: Full-width elevated charcoal plate `#0E1118` with metallic top hairline border.
* **Elements**:
  - Title: *"Responsibility Catalog"* in `Cabinet Grotesk` (`text-3xl font-black text-white`).
  - Subhead: *"Active accountability mappings with temporal valid-time enforcement."*
  - **Quick Telemetry Counters**:
    - `[ 7 TOTAL SYSTEMS ]`
    - `[ 2 CRITICAL (RED) ]`
    - `[ 3 HIGH (AMBER) ]`
    - `[ 1 UNOWNED VULNERABILITY (PULSING) ]`
  - **Actions**:
    - Search Bar: Dark inset well `#06070B` with keyboard shortcut `[ ⌘K ]`.
    - Primary Action: Acid Chartreuse Pill Button: `[ ＋ REGISTER NEW RESPONSIBILITY ]`.

---

### Section 2: The Tactical Matrix (Grid View)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                        │
│   ┌────────────────────────────────────────┐  ┌──────────────────────────────────────┐ │
│   │ 🔴 CRITICAL // DEPLOYMENT PIPELINES    │  │ 🟡 HIGH // PAYMENTS API MIGRATIONS   │ │
│   │                                        │  │                                      │ │
│   │   Production Deployments               │  │   Payments Engine v2                 │ │
│   │   Primary: Arjun Rao (Sole Holder!)    │  │   Primary: Maya Chen                 │ │
│   │   Backup:  NONE (VULNERABLE)           │  │   Backup:  Dev Patel                 │ │
│   │                                        │  │                                      │ │
│   │   ACTIVITY: 4 PRs active · 2h ago      │  │   ACTIVITY: 1 Linear Issue active    │ │
│   │   [~~~~/\_/\~~] Sparkline              │  │   [~~/\_/\~~~~] Sparkline            │ │
│   │                                        │  │                                      │ │
│   │   [ ⚡ LAUNCH MEMORY REPLAY (84) ➔ ]    │  │   [ ⚡ LAUNCH MEMORY REPLAY (32) ➔ ]  │ │
│   └────────────────────────────────────────┘  └──────────────────────────────────────┘ │
│                                                                                        │
│   ┌────────────────────────────────────────┐  ┌──────────────────────────────────────┐ │
│   │ 🟢 STANDARD // KUBERNETES INFRA        │  │ 🟢 STANDARD // OBSERVABILITY & LOGS  │ │
│   │                                        │  │                                      │ │
│   │   Core Cluster SRE                     │  │   Datadog & OpenTelemetry           │ │
│   │   Primary: Leo Martins                 │  │   Primary: Priya Nair                │ │
│   │   Backup:  Sara Kim                    │  │   Backup:  Tom Okafor                │ │
│   │                                        │  │                                      │ │
│   │   ACTIVITY: 0 open issues · Stable     │  │   ACTIVITY: 2 Runbooks verified      │ │
│   │                                        │  │                                      │ │
│   │   [ ⚡ LAUNCH MEMORY REPLAY (18) ➔ ]    │  │   [ ⚡ LAUNCH MEMORY REPLAY (12) ➔ ]  │ │
│   └────────────────────────────────────────┘  └──────────────────────────────────────┘ │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Card Architecture (The Tactile Hardware Plate):
* **Header Tag**: Criticality badge with pulsing status dot (`Critical` = Crimson `#FF2A55`, `High` = Amber `#F59E0B`, `Standard` = Emerald `#00F5A0`).
* **Title**: Monumental display name in `Cabinet Grotesk` (`text-xl font-bold text-white`).
* **Holders Block**:
  - Primary Owner avatar & name.
  - Backup Owner avatar & name (If missing, highlighted in pulsing crimson: `[ ⚠️ NO BACKUP RECORDED ]`).
* **Live Activity Sparkline**: Mini SVG wave showing recent Git commit and ticket activity over the past 30 days.
* **Direct Gateway Action**: Acid Chartreuse text pill: `"LAUNCH MEMORY REPLAY ➔"` linking directly to its reconstructed history.

---

### Section 3: The Responsibility Detail Dossier (`/[id]`)
* **Layout**: Two-column layout breaking down the full anatomy of the responsibility:
  1. **Temporal Ownership Continuum**: Shows current and past primary owners with half-open date ranges `[valid_from, valid_to)` backed by PostgreSQL GiST exclusion integrity.
  2. **Stewarded Assets**: Repositories, cloud clusters, and databases tied to this responsibility.
  3. **Governed Knowledge Items**: Associated runbooks and architectural decision records (ADRs) with review cutoff dates, steward signatures, and cryptographic text revision hashes.
  4. **The Memory Replay Banner**: Direct prominent callout to launch the historical playback engine.

---

## 3. Cross-Page Continuity Contract
* **Entry Vectors**:
  - From Global Command Dock via *"Catalog"*.
  - From Overview Dashboard via clicking any unowned or critical responsibility.
* **Exit Vectors**:
  - Clicking *"Launch Memory Replay"* navigates to `/responsibilities/[id]/timeline`.
  - Clicking *"Simulate Absence of [Owner]"* navigates to `/simulator?person=[personId]`.
  - Clicking an asset opens the Asset Detail Inspector.
