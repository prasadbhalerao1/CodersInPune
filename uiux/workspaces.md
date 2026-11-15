# Page Specification: Workspace Selection & Fast-Path Intake (`workspaces.md`)
**Route**: `/workspaces`  
**Role**: The Workspace Hub, Organization Gateway, and Instant VIP Judge Onboarding Portal.

---

## 1. Strategic Pitch & Narrative Arc

* **The Core Job**: Eliminate all onboarding friction. A judge or executive who arrives here must immediately recognize two distinct paths:
  1. **The Instant VIP Sandbox ("Northwind Labs (demo)")**: 1-click instant provisioning of a fully seeded organization (8 people, 7 critical responsibilities, 1 year of synthetic GitHub/Linear/Notion history, and an engineer actively departing). Zero setup required.
  2. **The Production Workspace Creator**: Clean, high-security creation of a fresh, isolated workspace with custom organization parameters.
* **Narrative Arc**:
  - Top: High-status operational header with ambient status telemetry.
  - Center Left: The featured **Northwind Labs Sandbox Card** (illuminated with acid chartreuse accents and live demo metrics).
  - Center Right: The **New Workspace Creator Plate** (hairline border, tactile input fields).
  - Bottom: Organization list showing active tenant memberships with role badges (`OWNER`, `ADMIN`, `MEMBER`).

---

## 2. Section-by-Section Blueprint

### Section 1: Header & Operational Context
* **Layout**: Fixed top bar identical to global shell, displaying user's verified identity pill (`auth.verified: sub_...`).
* **Title Block**:
  - Expressive Script Accent: *"Select your"* in `Instrument Serif` (Italic, Bone White, `32px`).
  - Monumental Title: **"OPERATIONAL WORKSPACE"** in `Cabinet Grotesk` (Black, All-Caps, `48px`).
  - Micro-HUD Tag: `[ TENANT GATEWAY // RLS BOUNDARY ACTIVE ]` in `Geist Mono` (`text-xs text-zinc-500`).

---

### Section 2: The Two-Door Intake Matrix

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                        │
│   ┌────────────────────────────────────────┐  ┌──────────────────────────────────────┐ │
│   │ ⚡ EXECUTIVE ACCESS // LIVE DEPLOYMENT  │  │ ＋ PROVISION SOVEREIGN TENANT        │ │
│   │                                        │  │                                      │ │
│   │   Northwind Labs                       │  │   Create an isolated, hardened       │ │
│   │   Full Operational Snapshot            │  │   tenant for your firm.              │ │
│   │                                        │  │                                      │ │
│   │   Pre-loaded with 8 engineers,         │  │   Organization Name:                 │ │
│   │   7 critical systems, 1 year of        │  │   [ Acme Corp Platform            ]  │ │
│   │   Git/Linear/Notion context, and       │  │                                      │ │
│   │   an active departure in-flight.       │  │   Primary Domain:                    │ │
│   │                                        │  │   [ acme.com                      ]  │ │
│   │   EXPOSURE: 55/100 // HANDOVER ACTIVE  │  │                                      │ │
│   │                                        │  │                                      │ │
│   │   [ ENTER COMMAND // NORTHWIND ⟶ ]     │  │   [ PROVISION TENANT ⟶ ]             │ │
│   └────────────────────────────────────────┘  └──────────────────────────────────────┘ │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Card 1: The VIP Sandbox Showcase (The Primary Door)
* **Visual Styling (Visual Source: Earbuds Dark Luxury)**:
  - Deep elevated plate (`#0E1118`) with an **Electric Acid Chartreuse glow border** (`shadow-[0_0_32px_rgba(210,255,0,0.12)]`).
  - Header Tag: `[ IMMEDIATE DEMO // ZERO CONFIG REQUIRED ]` with a pulsing emerald status dot.
  - Headline: *"Northwind Labs (demo)"* in `Cabinet Grotesk` (`text-2xl font-black text-white`).
  - Context telemetry badges:
    - `[ 8 SYNTHETIC OPERATORS ]`
    - `[ 7 CATALOG RESPONSIBILITIES ]`
    - `[ 1 ACTIVE DEPARTURE: ARJUN RAO ]`
  - Action: Massive Acid Chartreuse Pill Button: `"ENTER NORTHWIND LABS (DEMO) ➔"`.

#### Card 2: Production Blank Workspace Creator
* **Visual Styling**:
  - Elevated charcoal `#0E1118` with subtle metallic hairline border.
  - Tactile inputs with dark inset wells (`#06070B`), border sharpens to `#D2FF00` on focus.
  - Action: Bone White ghost pill button: `"CREATE PRODUCTION WORKSPACE ➔"`.

---

### Section 3: Active Workspace Directory
* **Layout**: Clean grid of cards for users who belong to multiple workspaces.
* **Card Data Points**:
  - Workspace Name & Created Date.
  - User's Role Badge: `OWNER` (Electric Chartreuse pill), `ADMIN` (Bone White pill), `AUDITOR` (Copper pill).
  - Open Handover Indicator: If an active case is waiting, a glowing amber pill displays: `● 1 HANDOVER WAITING FOR YOU`.

---

## 3. Cross-Page Continuity Contract
* **Entry**:
  - From `/` landing page via `"Launch Sandbox"`.
  - From WorkOS OAuth callback (`/callback`).
* **Exit**:
  - Clicking *"Enter Northwind Labs"* triggers an atomic server action (`api.createSampleWorkspace`), establishes the tenant session in PostgreSQL (`set_config('app.tenant_id', ...)`), and performs a smooth shared-element transition into `/w/[workspaceId]` (Overview Dashboard).
