# Relay Design System: Cyber-Physical Operational Command
**The Single Source of Truth for Visual Tokens, Spatial Physics, Component Grammar, and Motion Choreography**

---

## 1. Ground Truth & Visual DNA Reverse-Engineering

This design system is purely reverse-engineered from and governed by the two provided visual references:
1. **Reference 1 (Dark Luxury Cyber-Organic)**: Deep obsidian void, fluid organic midnight folds, specular-lit floating hardware, electric acid-chartreuse illumination, and sensual high-contrast serif script paired with geometric sans and micro-HUD telemetry.
2. **Reference 2 (Kinetic Streetwear Brutalism)**: Aggressive 45° diagonal tectonic vector slicing the canvas, monumental compressed display typography, spatial text layering (giant outline type behind the 3D focal object), and precision thumbnail rail galleries.

Relay translates these aesthetic engines into an enterprise mission-control interface for organizational continuity.

---

## 2. Color System & Chromatic Tokens

No generic or unapproved colors are permitted. All UI elements draw strictly from this calibrated palette:

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ BASE OBSIDIAN CANVAS           ELEVATED CHARCOAL               TECTONIC CRIMSON SLASH   │
│ #06070B                        #0E1118                         #7E1520                  │
│ HSL: 225, 45%, 4%              HSL: 220, 26%, 7%               HSL: 354, 73%, 29%       │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ ELECTRIC ACID CHARTREUSE       BATON COPPER / EMBER            INTEGRITY HYPER-EMERALD  │
│ #D2FF00                        #F59E0B                         #00F5A0                  │
│ HSL: 71, 100%, 50%             HSL: 38, 92%, 50%               HSL: 159, 100%, 48%      │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ PURE BONE WHITE                MUTED CEMENT STONE              HAIRLINE BORDER SHEEN    │
│ #F5F5F7                        #A1A1AA                         rgba(255,255,255,0.12)   │
│ HSL: 240, 5%, 96%              HSL: 240, 5%, 65%               High-specular edge       │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Layer Tokens
* `color-bg-base`: `#06070B`: Deep obsidian canvas; total light absorption.
* `color-bg-subtle`: `#0A0D13`: Recessed zones, inset tracks, background containers.
* `color-bg-elevated`: `#0E1118`: Primary card plates, floating HUD panels.
* `color-bg-overlay`: `rgba(14, 17, 24, 0.85)`: Backdrop-blurred modal dialogs, drawers, command palette.
* `color-bg-diagonal`: `#7E1520`: The 45° kinetic slash marking urgency, active transfer, and high criticality.

### 2.2 Text & Content Tokens
* `color-text-primary`: `#F5F5F7`: Bone white; maximum contrast for primary headlines and data values.
* `color-text-secondary`: `#A1A1AA`: Cement stone; descriptions, secondary labels, disabled tabs.
* `color-text-muted`: `#52525B`: Inactive metadata, subtle timestamps, placeholder copy.
* `color-text-accent`: `#D2FF00`: Electric acid chartreuse; key callouts, active links, primary CTA text.
* `color-text-crimson`: `#FF4D63`: High-visibility critical risk text against dark plates.

### 2.3 Semantic Glow & State Tokens
* `glow-chartreuse`: `0 0 24px rgba(210, 255, 0, 0.35), 0 0 48px rgba(210, 255, 0, 0.15)`: Active cursor focus, primary CTA illumination, live handovers.
* `glow-copper`: `0 0 20px rgba(245, 158, 11, 0.30)`: Handover in progress, warning overload, pending approvals.
* `glow-emerald`: `0 0 20px rgba(0, 245, 160, 0.30)`: Verified citations, forced RLS integrity, 100% readiness.
* `glow-crimson`: `0 0 24px rgba(255, 42, 85, 0.35)`: Single point of failure alert, unowned critical service.

---

## 3. Typography & Mathematical Type Scale

Relay enforces extreme typographic contrast: sensual, flowing script/serif against heavy, ultra-condensed brutalist sans, framed by razor-sharp monospace micro-HUDs.

### 3.1 Font Stack
1. **The Expressive Serif (The Soul)**: `Instrument Serif`, `PPEiko`, or `Playfair Display` (Italic).
2. **The Monumental Condensed Display (The Core)**: `Cabinet Grotesk` (Black / Extrabold Condensed) or `Bebas Neue`.
3. **The Micro-HUD (Telemetry & Citations)**: `Geist Mono` or `JetBrains Mono`.
4. **The UI Substrate**: `Geist Sans` or `Plus Jakarta Sans`.

### 3.2 Mathematical Scale Matrix

| Role | Font Family | Size | Line Height | Letter Spacing | Weight | Case / Style | Example Use |
|---|---|---|---|---|---|---|---|
| **Display Hero Script** | Expressive Serif | `5rem` (80px) | `0.9` | `-0.02em` | `400` | Italic Titlecase | *"Pass the"* / *"Unbroken"* |
| **Display Hero Brutal** | Monumental Sans | `6.5rem` (104px)| `0.85` | `0.02em` | `900` | All-Caps | **"ACCOUNTABILITY"** |
| **Giant Spatial Outline**| Monumental Sans | `10rem` (160px)| `0.8` | `0.05em` | `900` | All-Caps Outline| **"CONTINUITY"** (behind 3D) |
| **Section Title Script**| Expressive Serif | `2.5rem` (40px) | `1.0` | `-0.02em` | `400` | Italic Titlecase | *"Reconstruct"* / *"Simulate"* |
| **Section Title Brutal**| Monumental Sans | `3.25rem` (52px)| `0.9` | `0.01em` | `800` | All-Caps | **"ABSENCE BLAST RADIUS"** |
| **Card / Modal H3** | Monumental Sans | `1.5rem` (24px) | `1.1` | `0.02em` | `700` | All-Caps | **"PRODUCTION DEPLOYMENTS"** |
| **Subhead Prose** | UI Sans | `1.125rem` (18px)|`1.5` | `-0.01em` | `400` | Sentence case | Long-form descriptions |
| **Body UI** | UI Sans | `0.875rem` (14px)|`1.4` | `0em` | `400` | Sentence case | Table data, form fields |
| **HUD Micro-Spec** | Monospace | `0.6875rem` (11px)|`1.2`| `0.15em` | `600` | ALL-CAPS | `40H TOTAL // RLS LOCKED` |
| **Citation Tag** | Monospace | `0.75rem` (12px) |`1.0` | `0.08em` | `700` | ALL-CAPS | `[E3]` / `PR #142` |

---

## 4. Product Assets & Intentional Design Engineering

Every visual element must be semantically earned and directly represent what Relay actually does: sovereign enterprise continuity, absence blast-radius stress-testing, context reconstruction from real tools, and auditable handovers. **Zero arbitrary 3D geometry, zero decorative tubes/vials, and zero fake laptop/device bezels.**

### 4.1 Intentional Asset Inventory & Semantic Roles
1. **The Sovereign Handover Instrument & Live Radar (Primary Hero Focal Point)**:
   - **Frameless Native Viewport Composition**: Eliminates artificial laptop bezels or 3D device angles that shrink content and waste screen space. The command interface is rendered at 1:1 tactile scale directly into the native browser viewport.
   - **The Departure Signal**: Displays Lead Infrastructure Engineer *Arjun Rao* (with high-contrast monochromatic portrait and active ownership status), departing in 14 days.
   - **The Critical Vulnerability Radar**: 3 unbacked mission-critical services flashing crimson (`Prod Deployments & Secrets Mesh: 0 Backups`).
   - **The Reconstructed Memory Conduit**: Real evidence ribbons pulling cited receipts from GitHub (`PR #388`), Linear (`SEC-104`), and Notion.
   - **The Dual-Key Handover Capsule Seal**: The physicalized cryptographic transfer seal that securely bridges the continuity fault line.
   - **Tactile Stress-Test Controls**: Live absence selector (`3D`, `7D`, `14D`, `30D`), animated SVG readiness dial, and the successor simulator (`DEV PATEL: +33 PTS`).
2. **The 45° Kinetic Crimson Slash (The Continuity Fault Line)**:
   - A bold architectural vector (`#7E1520`) running diagonally across the canvas at `45deg`.
   - Semantically represents the **Continuity Fault Line**: the exact hazardous boundary where revenue, institutional leverage, and engineering context are lost when a key owner departs.
   - Layers behind the Handover Instrument and beneath the massive outline spatial typography (`CONTINUITY` / `ACCOUNTABILITY`).
3. **The Architectural Verification Swatch Gallery (Craftsmanship Proof)**:
   - Three square aspect-ratio (`1:1`) tactile preview frames along the rail, inspired directly by the sneaker reference detail photo tiles:
     - **Swatch 1: Kernel Isolation**: Macro view of real PostgreSQL migration applying `FORCE ROW LEVEL SECURITY`.
     - **Swatch 2: Temporal Precision**: Visual diagram of PostgreSQL `EXCLUDE` constraint preventing overlapping primary owners.
     - **Swatch 3: Citation Grounding**: Macro view of an AI claim being dropped because its reference was missing from the evidence pool.
4. **Interactive Telemetry Radar Gauges**:
   - Multi-ring vector gyroscopes rendered with animated SVG strokes, mathematical readiness dials, and glowing drop-shadows.

---

## 5. Spatial Grid & Layout Rhythm

### 5.1 Grid Specifications
* **Max Container Width**: `1440px` (Ultra-wide desktop: `1680px` edge-to-edge).
* **Column Grid**: 12-column asymmetric grid with variable gutters:
  - Desktop (`lg`): 12 columns, `32px` gutter, `48px` page margin.
  - Tablet (`md`): 8 columns, `24px` gutter, `32px` page margin.
  - Mobile (`sm`): 4 columns, `16px` gutter, `20px` page margin.
* **Vertical Rhythm (Section Spacing Scale)**:
  - Hero Section: `160px` top, `120px` bottom.
  - Standard Section: `120px` padding top and bottom.
  - Dense Tactical Workspace: `40px` padding top and bottom.

---

## 6. Surface & Component Grammar

Every component is custom-crafted to match the high-status aesthetic:

### 6.1 Card Anatomy (The "Hardware Plate")
```
┌─────────────────────────────────────────────────────────────┐
│ ┌─┐ [HUD TAG: CRITICALITY // HIGH]          [ID: RESP_04]   │ ◄── Metallic Hairline Top Bevel
│ └─┘                                                         │
│     PRODUCTION DEPLOYMENTS                                  │ ◄── Monumental Display Title
│     Primary: Arjun Rao (Sole Owner)                         │
│                                                             │
│     4 PRs IN-FLIGHT          0 VERIFIED BACKUPS             │ ◄── Telemetry Pill Counters
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ─── CITED EVIDENCE: [E1] [E4] // LAST COMMIT 2H AGO ─── │ │ ◄── Inset Monospace Well
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```
* **Background**: Elevated charcoal `#0E1118`.
* **Border**: 1px directional hairline:
  `border-top: 1px solid rgba(255,255,255,0.18); border-bottom: 1px solid rgba(255,255,255,0.03); border-inline: 1px solid rgba(255,255,255,0.06);`
* **Corner Radius**: `16px` (`rounded-2xl`).
* **Hover Interaction**: Lifts `translate-y-[-4px]` with shadow shift to `0 20px 40px -10px rgba(0,0,0,0.8), 0 0 20px rgba(210,255,0,0.08)`.

### 6.2 Button Hierarchy: Haute-Horlogerie & Tactile Luxury Grammar

Rather than loud, chunky, or flat neon blocks, Relay's buttons are engineered with the understated refinement of luxury horology, precision Leica hardware, and bespoke architectural glass.

```
┌────────────────────────────────────────────────────────────────────────┐
│  THE SOVEREIGN SMOKED TITANIUM PILL (PRIMARY)                          │
│                                                                        │
│  ╭──────────────────────────────────────────────────────────────────╮  │
│  │  ●  STRESS-TEST THE SYSTEM                                   ⟶   │  │
│  ╰──────────────────────────────────────────────────────────────────╯  │
│     ▲                                                           ▲      │
│  Luminous Jewel Bead (4px)                        Hairline Slender Arrow│
│  Specular Metallic Top Chamfer (1px rgba(255,255,255,0.22))            │
│  Smoked Obsidian Satin Glass (rgba(14, 17, 24, 0.85) + Blur 24px)      │
└────────────────────────────────────────────────────────────────────────┘
```

1. **The Sovereign Primary (Smoked Titanium & Specular Glass Capsule)**:
   - **Geometry**: Slender, balanced capsule (`h-11`, `px-7`, `rounded-full`).
   - **Surface**: Translucent smoked obsidian glass (`rgba(14, 17, 24, 0.82)`) with deep hardware backdrop blur (`backdrop-blur-xl`).
   - **Bevel & Edge Treatment**: Precision dual-layer specular edge:
     - Top border: `1px solid rgba(255, 255, 255, 0.22)` (simulating light hitting polished chamfered titanium).
     - Bottom border: `1px solid rgba(255, 255, 255, 0.04)`.
     - Inner shadow: `inset 0 1px 0 rgba(255, 255, 255, 0.15)`.
     - Drop shadow: `0 12px 32px -4px rgba(0, 0, 0, 0.70), 0 0 16px rgba(210, 255, 0, 0.08)`.
   - **Jewel Pip**: An illuminated `4px` micro-jewel indicator bead (`bg-[#D2FF00] shadow-[0_0_8px_#D2FF00]`) anchored on the left.
   - **Typography**: `text-[11px] font-medium tracking-[0.18em] uppercase text-[#F5F5F7]`.
   - **Action Phrasing (Zero Tech-Bro Jargon)**:
     - Primary Hero: `"●  STRESS-TEST THE SYSTEM  ⟶"` or `"●  TEST YOUR EXPOSURE  ⟶"`.
     - Navigation: `"●  TAKE COMMAND  ⟶"` or `"●  ENTER RELAY  ⟶"`.
     - Handover Execution: `"●  EXECUTE THE TRANSFER  ⟶"`.
   - **Trailing Element**: An ultra-slender hairline arrow (`⟶`) that slides `+3px` with physics-based spring easing on hover.
   - **Hover State**: The specular top edge glows with an ambient luminous chartreuse tint (`border-color: rgba(210, 255, 0, 0.40)`), while the body subtly lifts with `transform: translateY(-1.5px)`.

2. **The Satin Champagne Pearl (High-Status Hero Inversion)**:
   - **Use Case**: Flagship hero conversion point where maximum contrast is required with bespoke quiet luxury.
   - **Surface**: Warm satin bone/champagne pearl (`#EDE8DF` to `#E3DDD1` subtle vertical gradient).
   - **Typography**: Deep rich obsidian (`#08090C`), `text-[11px] font-semibold tracking-[0.16em] uppercase`.
   - **Border & Shadow**: Fine `1px solid rgba(255, 255, 255, 0.60)` hairline with an inner bevel shadow `inset 0 1px 0 rgba(255, 255, 255, 0.90)`.

3. **The Minimalist Ghost Playhead (Secondary Editorial Action)**:
   - **Geometry**: Slender capsule with circular icon anchor.
   - **Surface**: Ultra-thin frosted glass (`rgba(255, 255, 255, 0.03)`).
   - **Border**: Uniform hairline `1px solid rgba(255, 255, 255, 0.12)`.
   - **Icon**: Fine circular hairline border with centered play glyph `(▷)`.
   - **Typography**: `text-[11px] font-normal tracking-[0.14em] uppercase text-[#A1A1AA] hover:text-[#F5F5F7]`.
   - **Action Phrasing**: `"(▷)  SEE IT IN MOTION"` (never "Watch film" or "Take tour").

### 6.3 Form Inputs (Tactile Cockpit Controls)
* **Default**: `#0A0D13` background, hairline border `rgba(255,255,255,0.10)`, text `#F5F5F7`, `rounded-xl`.
* **Focus State**: Border sharpens to `#D2FF00`, box-shadow `0 0 16px rgba(210,255,0,0.20)`, label illuminates.
* **Error State**: Border flashes to `#FF2A55`, box-shadow `0 0 16px rgba(255,42,85,0.25)`.

---

## 7. Motion Physics & Transition Choreography

All motion in Relay obeys physical principles: mechanical snappiness, heavy mass, zero wobble.

### 7.1 Unified Easing Curves
* **The Command Snap (Default)**: `cubic-bezier(0.16, 1, 0.3, 1)` (Ultra-fast out, smooth settle).
* **The Mechanical Reveal**: `cubic-bezier(0.25, 1, 0.5, 1)`.
* **Durations**:
  - Micro-interactions (hover, click, toggle): `150ms`.
  - Component morphs & drawers: `300ms`.
  - Full-page layout shifts / 3D rotation: `500ms`.

### 7.2 Shared-Element Transitions
* **Card to Detail Expansion**: When clicking a responsibility card from the catalog into Memory Replay, the card's bounding box smoothly expands into the viewport header without hard unmounting or white flashes.
* **The 45° Diagonal Sweep**: Page route transitions trigger a brief 45° diagonal light-beam wipe across the screen, echoing the crimson tectonic slash.

---

## 8. UX Polish & Edge States

* **Loading Skeletons**: Deep obsidian plates pulsing with a faint acid-chartreuse luminous gradient sweep (`linear-gradient(90deg, transparent, rgba(210,255,0,0.06), transparent)`).
* **Empty States**: Not an empty box: an illuminated tactical sensor reading: `[ SCAN COMPLETE: 0 ANOMALIES DETECTED ]`.
* **Error Fallbacks**: Industrial red HUD warning card detailing the exact database constraint or verification code, with a 1-click `"RESUME RETRY DRILL"` button.
