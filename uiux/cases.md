# Page Specification: Continuity Cases Command Center (`cases.md`)
**Routes**: `/w/[workspaceId]/cases` and `/w/[workspaceId]/cases/[caseId]`  
**Role**: The Operational Handover Pipeline, Separation-of-Duties Verification Deck, and Case Command Center.

---

## 1. Strategic Pitch & Narrative Arc

* **The Core Job**: Elevate handovers from casual Slack DMs or loose checklists into **legally non-repudiable, audited enterprise operations**. Guarantee separation of duties, prove that readiness criteria were met, and provide an unbreakable chain of custody for accountability.
* **Narrative Arc**:
  1. **Top Rail**: 5-stage mechanical lifecycle tracker (`Draft ➔ Planning ➔ Ready ➔ Executing ➔ Verified`).
  2. **The Command Header**: Case title, case type badge (`Departure`, `Coverage`, `Transfer`), priority indicator, and effective date countdown.
  3. **The Core Split**:
     - *Left (Scope & Plan)*: In-scope responsibilities, outgoing owner, incoming recipient, and atomic ownership transfer schedule.
     - *Right (Readiness & SOD Gates)*: Mandatory criteria checklist, task dependencies, and the **Separation of Duties (SOD) Approval Seal**.
  4. **The Audit Trail Footprint**: Immutable append-only log of every status transition and approval.

---

## 2. Section-by-Section Blueprint

### Section 1: The 5-Stage Mechanical Pipeline Rail
* **Layout**: Chamfered horizontal rail across the top of the case view.
* **Stages**:
  `[ 01 // INTAKE ] ───► [ 02 // PLANNING ] ───► [ 03 // APPROVED ] ───► [ 04 // EXECUTING ] ───► [ 05 // VERIFIED ]`
* **Styling**:
  - Completed stages: Electric Emerald `#00F5A0` with glowing connectors.
  - Active stage: Baton Copper `#F59E0B` with animated pulsing pip.
  - Pending stages: Muted Smoke `#52525B`.

---

### Section 2: The Case Command Header
* **Layout**: Elevated charcoal plate `#0E1118` with metallic hairline border.
* **Elements**:
  - Title: *"Arjun Rao — Platform Departure & Ownership Transfer"* in `Cabinet Grotesk` (`text-3xl font-black text-white`).
  - Metadata Telemetry Bar:
    - `[ TYPE: DEPARTURE ]` (Crimson pill)
    - `[ PRIORITY: URGENT ]` (Amber pill)
    - `[ EFFECTIVE: 24 NOV // 12 DAYS REMAINING ]`
    - `[ INITIATOR: TOM OKAFOR ]`
  - **Primary Action (Context-Aware)**:
    - If in `Planning`: Acid Chartreuse Pill: `"REQUEST SOD APPROVAL ➔"`.
    - If in `Ready for Transfer`: Monumental Copper Pill: `"EXECUTE OWNERSHIP TRANSFER NOW ➔"`.
    - If `Executed`: Emerald Pill: `"VIEW AUDITED HANDOVER BRIEF ➔"`.

---

### Section 3: The Two-Column Execution Matrix

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                        │
│   LEFT PANEL (60% WIDTH):                      RIGHT PANEL (40% WIDTH):                │
│   OWNERSHIP TRANSFER SCOPE                     READINESS CRITERIA & APPROVAL GATES     │
│                                                                                        │
│   ┌────────────────────────────────────────┐   ┌──────────────────────────────────┐    │
│   │ SCOPED RESPONSIBILITIES (2)            │   │ MANDATORY READINESS CRITERIA     │    │
│   │                                        │   │                                  │    │
│   │ 🔴 Production Deployments              │   │ [✓] 2 Supervised Canary Deploys  │    │
│   │    Current: Arjun Rao (Primary)        │   │     Verified by Maya Chen (14h)  │    │
│   │    Target:  Dev Patel (Primary)        │   │                                  │    │
│   │    Valid From: 24 Nov (Atomic)         │   │ [✓] Rollback Runbook Documented  │    │
│   │    [ VIEW REPLAY // 84 EVENTS ➔ ]      │   │     Knowledge version 2 approved │    │
│   │                                        │   │                                  │    │
│   │ 🟡 Platform On-Call                    │   │ [!] Recipient Acknowledgment     │    │
│   │    Current: Arjun Rao (Primary)        │   │     Waiting on Dev Patel         │    │
│   │    Target:  Leo Martins (Backup)       │   │                                  │    │
│   │                                        │   │ ──────────────────────────────── │    │
│   │ ┌────────────────────────────────────┐ │   │ SEPARATION OF DUTIES (SOD) SEAL: │    │
│   │ │ 📜 GENERATED HANDOVER BRIEF:       │ │   │ [🔒 SOD COMPLIANT: VALIDATED]   │    │
│   │ │ Version 2.0 (Approved by Maya Chen)│ │   │ Approver (Maya Chen) is distinct │    │
│   │ │ [ OPEN HANDOVER CAPSULE & Q&A ➔ ]  │ │   │ from Initiator (Tom Okafor).     │    │
│   │ └────────────────────────────────────┘ │   └──────────────────────────────────┘    │
│   └────────────────────────────────────────┘                                           │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Left Panel: Scoped Responsibilities & Atomic Transfers
* Displays each scoped responsibility with its declared criticality.
* Shows the exact valid-time continuum shift:
  `Arjun Rao [valid_to: 2026-11-24] ──► Dev Patel [valid_from: 2026-11-24]`.
* Highlights that upon execution, PostgreSQL atomic transactions will mutate the catalog without race conditions.
* Links directly to the generated **Handover Brief & Copilot**.

#### Right Panel: Readiness Verification & The Separation of Duties (SOD) Seal
* **The SOD Security Moat**:
  - For critical cases, Relay enforces that the approver **cannot** be the person who created the case.
  - A prominent green illuminated stamp: `[ 🔒 SEPARATION OF DUTIES: ENFORCED // VERIFIED BY KERNEL ]`.
* **Readiness Criteria Checklist**:
  - Supervised demos, access confirmation, task completions.
  - Stamped with the verifier's identity, timestamp, and audit record ID.

---

## 3. Cross-Page Continuity Contract
* **Entry Vectors**:
  - From `/w/[workspaceId]/simulator` via *"Initialize Audited Handover Case"*.
  - From Overview Dashboard via the *"Active Handover"* card.
* **Exit Vectors**:
  - Clicking *"Open Handover Capsule & Q&A"* navigates to `/cases/[caseId]/capsules/[capsuleId]`.
  - Clicking *"View Replay"* on a responsibility navigates to `/responsibilities/[id]/timeline`.
