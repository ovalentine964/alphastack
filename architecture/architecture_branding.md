# Alpha Stack — Branding & Identity Architecture

> **Version:** 1.0 · **Date:** 2026-07-13 · **Author:** Architecture Team
> **Source Research:** [`research/research_11_branding_identity.md`](../research/research_11_branding_identity.md) — Brand identity, visual design system, UI/UX guidelines
> **Status:** Architecture Complete

---

> **Author:** Brand & Design Architect
> **Date:** 2026-07-13
> **Status:** Architecture Design — Ready for Implementation Review
> **Dependencies:** `architecture_ui_desktop.md`, `architecture_ui_mobile.md`, `architecture_ui_web.md`, `architecture_channels.md`, `research_11_branding_identity.md`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Design Philosophy](#2-design-philosophy)
3. [Brand Identity System](#3-brand-identity-system)
4. [Color Architecture](#4-color-architecture)
5. [Typography System](#5-typography-system)
6. [Logo Architecture](#6-logo-architecture)
7. [Icon System](#7-icon-system)
8. [Layout & Spacing Framework](#8-layout--spacing-framework)
9. [Component Design Language](#9-component-design-language)
10. [Dark Mode Architecture](#10-dark-mode-architecture)
11. [Data Visualization Standards](#11-data-visualization-standards)
12. [Motion & Animation](#12-motion--animation)
13. [Platform-Specific Adaptations](#13-platform-specific-adaptations)
14. [Brand Voice & Copy Guidelines](#14-brand-voice--copy-guidelines)
15. [Asset Management](#15-asset-management)
16. [Accessibility Standards](#16-accessibility-standards)
17. [Implementation Roadmap](#17-implementation-roadmap)

---

## 1. Executive Summary

Alpha Stack's branding architecture defines a **trader-first, dark-mode-native visual system** optimized for long screen sessions, dense data displays, and split-second decision-making. Every design choice — from color contrast ratios to number legibility — serves the core mission: **making institutional-grade trading intelligence accessible and actionable for retail traders.**

### Design Pillars

| Pillar | Description | Measurable Outcome |
|--------|-------------|-------------------|
| **Clarity** | Every element communicates without ambiguity | Zero user confusion in usability testing |
| **Speed** | Visual hierarchy enables instant comprehension | <500ms to identify key signal/action |
| **Trust** | Professional aesthetic builds confidence | Brand perception matches institutional tools |
| **Accessibility** | Works for all users, all conditions | WCAG 2.1 AA compliance minimum |

---

## 2. Design Philosophy

### 2.1 Core Principles

**1. Dark-First, Not Dark-Only**
Traders stare at screens for hours. Dark backgrounds reduce eye strain, minimize light emission in dark rooms, and make neon accent colors pop. Every component is designed dark-first, then adapted for light mode — not the other way around.

**2. Data Density Over Whitespace**
Trading interfaces must display maximum information in minimum space. Unlike consumer apps that breathe with whitespace, Alpha Stack embraces density — but with disciplined visual hierarchy so density doesn't become clutter.

**3. Semantic Color Is Non-Negotiable**
Green means profit. Red means loss. Blue means action. These associations are universal in finance. We never repurpose these colors for non-semantic purposes (e.g., never use green for a "delete" button).

**4. Typography Serves Numbers**
80% of trading-relevant data is numeric. Our typography system prioritizes number legibility — monospace for prices, tabular figures for aligned columns, distinct glyphs for 0/O and 1/l/I.

**5. Progressive Disclosure**
Show the essential first. Let users drill deeper. A signal card shows direction and confidence at a glance; tap to see full analysis. This prevents cognitive overload while preserving depth.

### 2.2 Anti-Patterns

| Anti-Pattern | Why We Avoid It |
|-------------|----------------|
| Light-mode-first design | Causes eye strain for power users |
| Decorative animations on live data | Distracting during active trading |
| Non-semantic color usage | Creates confusion in high-pressure moments |
| Thin fonts on dark backgrounds | Poor legibility, especially on lower-quality displays |
| Rounded/friendly aesthetic for data | Undermines trust — traders want precision, not playfulness |

---

## 3. Brand Identity System

### 3.1 Name Architecture

**ALPHA STACK** — Two words, always capitalized in the logotype.

| Component | Meaning | Trading Context |
|-----------|---------|-----------------|
| **ALPHA** | Excess returns over benchmark | The holy grail — outperformance every trader seeks |
| **STACK** | Layered, compounding technology | Multiple intelligence layers stacked into one engine |

**Tagline (Primary):** *Stack the Alpha. Beat the Market.*
**Tagline (Secondary):** *Institutional Intelligence. Retail Access.*

### 3.2 Brand Values

| Value | Design Implication |
|-------|-------------------|
| **Intelligence** | Clean data visualizations, logical information architecture, no gimmicks |
| **Accessibility** | Plain language, intuitive UX, works on low-end devices |
| **Reliability** | Consistent components, predictable interactions, no "surprise" UI changes |
| **Transparency** | Visible logic paths, auditable performance metrics, no black-box UI |

### 3.3 Brand Personality Matrix

| Trait | We Are | We Are Not |
|-------|--------|------------|
| **Smart** | Data-driven, analytical, precise | Jargon-heavy, condescending |
| **Confident** | Bold claims backed by evidence | Arrogant, making guarantees |
| **Approachable** | Friendly, inclusive, warm UX copy | Casual to the point of unprofessional |
| **Futuristic** | Modern, AI-native, forward-looking | Gimmicky, buzzword-dependent |

### 3.4 Brand Voice Rules

- **Tone:** Confident but not arrogant. Smart but not condescending.
- **Perspective:** "We built this for traders like us." Peer-to-peer, first-person plural.
- **Language:** Clear, direct, active voice. Short sentences. Trading terms used naturally.
- **Forbidden:** "Guaranteed returns," "risk-free," "get rich," "easy money"

**Example Copy Patterns:**

| Context | Good | Bad |
|---------|------|-----|
| Signal notification | "EURUSD BUY signal — 78% confidence. H4 trend aligned." | "🚀🚀🚀 EURUSD MOON INCOMING!! BUY NOW!!!" |
| Error state | "Connection to broker lost. Reconnecting in 5s..." | "Oops! Something went wrong 😅" |
| Performance summary | "Monthly return: +4.2%. Max drawdown: -1.8%. 23 trades." | "You're crushing it! Keep going! 💪" |

---

## 4. Color Architecture

### 4.1 Primary Palette

| Token | Hex | RGB | Role | Usage |
|-------|-----|-----|------|-------|
| `--color-bg-primary` | `#0A1628` | 10, 22, 40 | Deep Navy | Primary background, dark mode base |
| `--color-accent` | `#2D7FF9` | 45, 127, 249 | Electric Blue | CTAs, active states, links, primary actions |
| `--color-text-primary` | `#FFFFFF` | 255, 255, 255 | White | Primary text on dark backgrounds |

### 4.2 Semantic Palette

| Token | Hex | RGB | Role | Usage |
|-------|-----|-----|------|-------|
| `--color-profit` | `#00E676` | 0, 230, 118 | Neon Green | Profit, positive signals, success, BUY |
| `--color-loss` | `#FF3D57` | 255, 61, 87 | Signal Red | Loss, negative signals, risk warnings, SELL |
| `--color-premium` | `#FFD700` | 255, 215, 0 | Gold | Premium features, highlights, achievements |
| `--color-neutral` | `#8892A4` | 136, 146, 164 | Slate Gray | Secondary text, borders, inactive states |

### 4.3 Gradient Definitions

| Token | Start | End | Angle | Usage |
|-------|-------|-----|-------|-------|
| `--gradient-alpha` | `#2D7FF9` | `#00E676` | 135° | Hero sections, key metrics, brand moments |
| `--gradient-depth` | `#0A1628` | `#1A2A4A` | 180° | Backgrounds, cards, panels |
| `--gradient-alert` | `#FF3D57` | `#FF6B35` | 135° | High-priority warnings |

### 4.4 Color Contrast Requirements

| Pair | Minimum Ratio | Standard |
|------|--------------|----------|
| White text on Deep Navy | 15.4:1 | AAA |
| Electric Blue on Deep Navy | 4.8:1 | AA (large text AAA) |
| Neon Green on Deep Navy | 8.9:1 | AAA |
| Signal Red on Deep Navy | 5.2:1 | AA |
| Slate Gray on Deep Navy | 3.1:1 | AA (large text only) |

### 4.5 Color Usage Rules

1. **Never** use `--color-profit` or `--color-loss` for non-semantic purposes
2. **Never** place colored text on colored backgrounds without contrast verification
3. **Always** provide a non-color indicator (icon, label) alongside color for accessibility
4. **Minimum touch target:** 44×44px for all color-coded interactive elements

---

## 5. Typography System

### 5.1 Font Stack

| Role | Font | Fallback | Usage |
|------|------|----------|-------|
| **Display / Headlines** | Inter (Bold 700, Extra Bold 800) | system-ui, -apple-system, sans-serif | App name, hero text, section headers |
| **Body / UI** | Inter (Regular 400, Medium 500) | system-ui, -apple-system, sans-serif | All UI text, descriptions, labels |
| **Monospace / Data** | JetBrains Mono (Regular 400, Medium 500) | Consolas, 'Courier New', monospace | Prices, numbers, code, terminal output |

**Why Inter:** Free, open-source, exceptional screen readability, excellent number rendering, wide language support, tabular figures built-in.

**Why JetBrains Mono:** Distinct characters (zero/O differentiation), ligature support, excellent at small sizes for dense data displays.

### 5.2 Type Scale

| Token | Desktop | Mobile | Weight | Line Height | Letter Spacing |
|-------|---------|--------|--------|-------------|----------------|
| `--text-h1` | 32px | 24px | 800 (Extra Bold) | 1.2 | -0.02em |
| `--text-h2` | 24px | 20px | 700 (Bold) | 1.3 | -0.01em |
| `--text-h3` | 20px | 17px | 600 (Semi Bold) | 1.3 | 0 |
| `--text-body` | 14px | 15px | 400 (Regular) | 1.5 | 0 |
| `--text-caption` | 12px | 12px | 400 (Regular) | 1.4 | 0.01em |
| `--text-data` | 14px | 14px | 500 (Medium) | 1.3 | 0.02em |
| `--text-data-lg` | 20px | 18px | 600 (Semi Bold) | 1.2 | 0 |
| `--text-data-sm` | 12px | 12px | 500 (Medium) | 1.3 | 0.03em |

### 5.3 Number Typography Rules

- **Always** use `font-variant-numeric: tabular-nums` for aligned number columns
- **Always** use JetBrains Mono for price displays and P&L figures
- **Minimum** font size for live price data: 14px (12px for secondary data)
- **Color-code** numbers: green for positive, red for negative, white for neutral
- **Sign prefix:** Always show `+` for positive values, `-` for negative (never omit the sign)

---

## 6. Logo Architecture

### 6.1 Primary Mark: "Stacked Alpha"

**Concept:** A stylized letter "A" constructed from three horizontal layers (stacks) that converge upward into an arrow/peak shape. The layers are slightly offset for depth and motion.

**Structure:**
- Bottom layer: Widest — represents data/foundation
- Middle layer: Narrower — represents intelligence/processing
- Top layer: Converges to point — represents alpha/edge
- Small accent dot on top layer — the signal

**Color:** Gradient from Electric Blue (bottom) to Neon Green (top)

### 6.2 Icon Size Lattice

| Size | Context | Detail Level |
|------|---------|-------------|
| 512×512 | App icon, splash screen | Full — all three layers, gradient, subtle shadow |
| 256×256 | High-res displays | Full detail maintained |
| 128×128 | Standard app icon | Simplified, reduced shadow |
| 64×64 | Dock/taskbar | Bold layers, minimal shadow, high contrast |
| 48×48 | Small taskbar | Simplified to essential shape |
| 32×32 | Favicon, system tray | Two layers only, arrow peak emphasized |
| 16×16 | Minimal favicon | Single bold peak shape, solid color |

### 6.3 Mobile Icon: "The Stack"

**Differences from desktop:**
- Rounded corners (iOS/Android convention)
- No fine detail — bold, solid shapes only
- Stronger contrast for any-background compatibility
- Designed for squircle mask (iOS) and adaptive icon (Android)

| Size | Context |
|------|---------|
| 1024×1024 | App Store / Play Store listing |
| 180×180 | iOS home screen (@3x) |
| 120×120 | iOS home screen (@2x) |
| 192×192 | Android adaptive icon |
| 48×48 | Android notification/small |

### 6.4 Logo Usage Rules

- **Minimum clear space:** Equal to height of one "layer" on all sides
- **Never** stretch, rotate, or add effects beyond defined variants
- **Never** place on busy backgrounds without a backing shape
- **Approved variants:** Full color, monochrome white, monochrome navy
- **Bot avatars (Telegram/Discord):** Single stack shape, no wordmark

---

## 7. Icon System

### 7.1 Icon Library

**Primary:** Phosphor Icons — consistent weight, open-source, comprehensive set.

**Custom icons for trading-specific concepts:**
- Candlestick patterns (doji, hammer, engulfing)
- Signal types (BUY, SELL, HOLD)
- Risk levels (low, medium, high, critical)
- Market states (trending, ranging, volatile, quiet)

### 7.2 Icon Style Rules

| Aspect | Specification |
|--------|--------------|
| Style | Flat with subtle depth — no heavy 3D, no skeuomorphism |
| Line weight | 1.5–2px for outline icons, consistent across set |
| Corner radius | 4px for small elements, 8px for cards, 12px for modals |
| Size grid | 16×16, 20×20, 24×24, 32×32, 48×48 |
| Color | Inherits from context (text color or semantic color) |
| Padding | 2px minimum within bounding box |

### 7.3 Icon Naming Convention

```
icon-{category}-{name}-{variant}.svg

Examples:
icon-trading-buy-filled.svg
icon-trading-sell-outline.svg
icon-risk-high-filled.svg
icon-nav-dashboard-outline.svg
```

---

## 8. Layout & Spacing Framework

### 8.1 Spacing Scale (4px base)

| Token | Value | Usage |
|-------|-------|-------|
| `--space-1` | 4px | Tight padding, icon gaps |
| `--space-2` | 8px | Default padding, form field gaps |
| `--space-3` | 12px | Card internal padding |
| `--space-4` | 16px | Section gaps, list item spacing |
| `--space-6` | 24px | Section separation |
| `--space-8` | 32px | Major section breaks |
| `--space-12` | 48px | Page-level spacing |
| `--space-16` | 64px | Hero section spacing |

### 8.2 Grid System

| Breakpoint | Columns | Gutter | Margin |
|------------|---------|--------|--------|
| Mobile (< 640px) | 4 | 16px | 16px |
| Tablet (640–1024px) | 8 | 16px | 24px |
| Desktop (1024–1440px) | 12 | 24px | 32px |
| Wide (> 1440px) | 12 | 24px | Auto (max 1440px) |

### 8.3 Component Spacing Rules

- **Cards:** 16px internal padding, 8px between cards in a grid
- **Forms:** 12px between label and input, 16px between fields
- **Tables:** 8px cell padding, 4px row gap
- **Charts:** 24px padding around plot area, 8px between adjacent charts

---

## 9. Component Design Language

### 9.1 Card Component

```css
.card {
  background: var(--gradient-depth);
  border: 1px solid rgba(136, 146, 164, 0.15);
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}
```

### 9.2 Button Hierarchy

| Type | Background | Text | Border | Usage |
|------|-----------|------|--------|-------|
| Primary | Electric Blue | White | None | Main CTAs (Buy, Sell, Execute) |
| Secondary | Transparent | Electric Blue | 1px Blue | Secondary actions (Settings, Filter) |
| Danger | Signal Red | White | None | Destructive actions (Close All, Delete) |
| Ghost | Transparent | Slate Gray | None | Tertiary actions (Cancel, Dismiss) |

### 9.3 Form Elements

| Element | Height | Border Radius | Border | Focus State |
|---------|--------|--------------|--------|-------------|
| Text input | 40px | 6px | 1px `#8892A4` at 30% | Blue glow, border turns Electric Blue |
| Select | 40px | 6px | 1px `#8892A4` at 30% | Same as text input |
| Checkbox | 20×20px | 4px | 1px `#8892A4` | Blue fill when checked |
| Toggle | 44×24px | 12px | None | Blue track when on, gray when off |

### 9.4 Signal Card

The signal card is Alpha Stack's signature component — it displays a trading signal with all context.

```
┌─────────────────────────────────────────┐
│  EURUSD  ● BUY                    ▲ 78% │
│  Entry: 1.0852  SL: 1.0820  TP: 1.0910 │
│  H4 trend ↑ · RSI(14): 62 · SMC: OB   │
│  ████████████████░░░░  Confidence       │
│  [Execute]  [Details]  [Dismiss]        │
└─────────────────────────────────────────┘
```

**Design rules:**
- Direction indicator uses semantic color (green BUY / red SELL)
- Confidence bar uses gradient from Loss Red → Profit Green
- Action buttons follow button hierarchy (Execute = primary, Details = secondary, Dismiss = ghost)
- Compact variant omits details row for notification/banner use

---

## 10. Dark Mode Architecture

### 10.1 Design Rationale

Dark mode is the **default and primary** mode. Reasons:
- Traders use screens for 8+ hours daily
- Dark backgrounds reduce eye strain in low-light environments
- Neon accent colors (green, blue) have higher perceived brightness on dark
- Industry standard for trading platforms (Bloomberg, TradingView, MetaTrader)

### 10.2 Dark Mode Token Map

| Semantic Token | Dark Mode Value | Light Mode Value |
|---------------|-----------------|-----------------|
| `--bg-primary` | `#0A1628` | `#FFFFFF` |
| `--bg-secondary` | `#1A2A4A` | `#F5F7FA` |
| `--bg-tertiary` | `#243454` | `#EBEDF0` |
| `--text-primary` | `#FFFFFF` | `#1A1A2E` |
| `--text-secondary` | `#8892A4` | `#6B7280` |
| `--border` | `rgba(136,146,164,0.15)` | `rgba(0,0,0,0.1)` |
| `--shadow` | `0 2px 8px rgba(0,0,0,0.3)` | `0 2px 8px rgba(0,0,0,0.1)` |

### 10.3 Light Mode Rules

- Light mode is a **derived theme**, not a separate design
- All components must support both modes via CSS custom properties
- Profit/Loss colors remain identical in both modes (semantic, not decorative)
- Charts default to dark background even in light mode (industry convention)

---

## 11. Data Visualization Standards

### 11.1 Chart Color Scheme

| Element | Color | Notes |
|---------|-------|-------|
| Background | `#0A1628` (Deep Navy) | Always dark, even in light mode |
| Grid lines | `rgba(136,146,164,0.1)` | Subtle, non-distracting |
| Bullish candles | `#00E676` (Neon Green) | Filled or hollow, consistent within chart |
| Bearish candles | `#FF3D57` (Signal Red) | Filled |
| Volume bars | `#2D7FF9` at 40% opacity | Below price chart |
| Moving averages | Blue, Gold, Slate (distinct) | Each MA gets unique color |
| Bollinger Bands | `#2D7FF9` at 15% opacity (fill), 40% (lines) | |
| Support/Resistance | `#FFD700` (Gold) dashed | Horizontal lines |
| Signal markers | Semantic (Green BUY / Red SELL) | Triangle arrows on chart |

### 11.2 Chart Typography

- Price axis: JetBrains Mono, 12px, `#8892A4`
- Time axis: Inter, 11px, `#8892A4`
- Tooltip: Inter, 13px, white text on `#1A2A4A` background
- OHLCV display: JetBrains Mono, 14px, color-coded

### 11.3 Non-Chart Data Visualization

| Type | Library | Style |
|------|---------|-------|
| Sparklines | Custom SVG or lightweight lib | Single color (semantic), no axes |
| Progress bars | Custom CSS | Gradient fill, rounded ends |
| Heatmaps | Custom | Deep Navy → Electric Blue → Neon Green scale |
| Gauges | Custom SVG | Arc with gradient, needle indicator |

---

## 12. Motion & Animation

### 12.1 Animation Principles

1. **Functional only** — Every animation serves a purpose (feedback, transition, attention)
2. **Fast** — No animation >300ms for UI feedback, >500ms for transitions
3. **Interruptible** — Animations can be cancelled mid-way
4. **Respectful** — Honor `prefers-reduced-motion` OS setting

### 12.2 Animation Specifications

| Interaction | Duration | Easing | Purpose |
|------------|----------|--------|---------|
| Button press | 100ms | ease-out | Tactile feedback |
| Card hover | 150ms | ease-out | Discoverability |
| Page transition | 250ms | ease-in-out | Spatial orientation |
| Modal open | 200ms | ease-out | Focus direction |
| Signal arrival | 300ms | spring(1, 80, 10) | Attention grab |
| Price update | 150ms | ease-out | Live data feel |
| Toast notification | 200ms in, 150ms out | ease-out | Non-intrusive feedback |

### 12.3 Price Animation

When a price updates:
1. Flash the cell background briefly (150ms) — green for up, red for down
2. Smooth number transition (count up/down) if >0.1% change
3. No animation for minor ticks (<0.01%)

---

## 13. Platform-Specific Adaptations

### 13.1 Desktop (Windows / macOS / Linux)

| Aspect | Specification |
|--------|--------------|
| Window chrome | Custom title bar with wordmark |
| System tray | 16×16 icon, must be recognizable |
| Splash screen | Full logo on Deep Navy background |
| Native menus | Use platform-native menu bar |
| Keyboard shortcuts | Platform conventions (Cmd on Mac, Ctrl on Windows/Linux) |
| Notifications | OS-native notification system |

### 13.2 iOS

| Aspect | Specification |
|--------|--------------|
| Typography | SF Pro for system text, Inter for brand text |
| Navigation | Tab bar (bottom), navigation stack |
| Icon | Squircle mask, "The Stack" design |
| Haptics | Light impact on signal tap, medium on execute |
| Dark mode | Always dark (override system setting) |

### 13.3 Android

| Aspect | Specification |
|--------|--------------|
| Typography | Roboto for system text, Inter for brand text |
| Navigation | Bottom navigation bar or navigation drawer |
| Icon | Adaptive icon (foreground: stack, background: Deep Navy) |
| Material | Material Design 3 with custom color scheme |
| Dark mode | Always dark (override system setting) |

### 13.4 Web

| Aspect | Specification |
|--------|--------------|
| Typography | Inter loaded via Google Fonts or self-hosted |
| Responsive | Mobile-first, breakpoints at 640/1024/1440px |
| Dark mode | Default, with toggle for light mode |
| PWA | Installable, offline-capable dashboard view |
| Favicon | 32×32 and 16×16 "Stacked Alpha" icon |

### 13.5 Bot Avatars (Telegram / Discord)

| Platform | Avatar | Notes |
|----------|--------|-------|
| Telegram | Single stack shape, 512×512 | No text, high contrast |
| Discord | Single stack shape, 512×512 | Same as Telegram |
| Inline embeds | Wordmark + icon | For rich message embeds |

---

## 14. Brand Voice & Copy Guidelines

### 14.1 Voice Spectrum

```
Formal ●━━━━━━━○━━━━ Casual
       We sit here — professional but approachable

Technical ●━━━━━━━━○━ Simple
         We lean technical — traders expect precision

Reserved ●━━━━━○━━━━━ Enthusiastic
         We stay measured — no hype, no emojis in core UI
```

### 14.2 Copy Patterns by Context

| Context | Pattern | Example |
|---------|---------|---------|
| Signal notification | `{PAIR} {DIR} — {CONF}% · {REASON}` | "EURUSD BUY — 78% · H4 trend aligned" |
| Error message | `{WHAT} happened. {ACTION}.` | "Connection lost. Reconnecting in 5s..." |
| Success confirmation | `{ACTION} complete. {DETAILS}.` | "Order filled. Entry: 1.0852, Size: 0.1 lot" |
| Dashboard metric | `{LABEL}: {VALUE} {TREND}` | "Monthly P&L: +$342.50 ↑" |
| Empty state | `{NO_DATA}. {SUGGESTION}.` | "No signals yet. Markets open in 2h." |
| Loading state | `{LOADING}...` | "Scanning 28 pairs..." |

### 14.3 Terminology Standards

| Use | Don't Use |
|-----|-----------|
| Signal | Tip, hint, recommendation |
| Execute | Place, make, do |
| Position | Trade, bet, gamble |
| Drawdown | Loss streak, bad run |
| Strategy | System, bot, algorithm (in user-facing text) |
| Confidence | Accuracy, win rate (when referring to signal strength) |

---

## 15. Asset Management

### 15.1 Asset Directory Structure

```
assets/
├── logo/
│   ├── alpha-stack-logo-full-dark.svg
│   ├── alpha-stack-logo-full-light.svg
│   ├── alpha-stack-icon-{size}.png          # 512, 256, 128, 64, 48, 32, 16
│   └── alpha-stack-mobile-{size}.png        # 1024, 180, 120, 48
├── wordmark/
│   ├── alpha-stack-wordmark.svg
│   └── alpha-stack-wordmark-white.svg
├── icons/
│   ├── trading/                             # Buy, sell, hold, signal icons
│   ├── risk/                                # Risk level indicators
│   ├── nav/                                 # Navigation icons
│   └── status/                              # Connection, sync, error states
├── colors/
│   └── alpha-stack-palette.ase              # Adobe Swatch Exchange
└── guidelines/
    └── alpha-stack-brand-guidelines.pdf
```

### 15.2 Asset Naming Convention

```
{project}-{category}-{variant}-{size}.{ext}

Examples:
alpha-stack-icon-full-512.png
alpha-stack-icon-mono-32.svg
alpha-stack-mobile-dark-1024.png
```

### 15.3 Asset Delivery Formats

| Type | Primary | Fallback | Notes |
|------|---------|----------|-------|
| Logo | SVG | PNG @2x | Vector for scaling |
| Icons | SVG | PNG @2x | Inline SVG for color control |
| App icons | PNG | — | Platform-required sizes |
| Brand colors | ASE + CSS vars | JSON | For design tools and code |

---

## 16. Accessibility Standards

### 16.1 Compliance Target

**WCAG 2.1 Level AA** — minimum for all platforms.

### 16.2 Color Accessibility

| Requirement | Implementation |
|-------------|---------------|
| Contrast ratio (text) | 4.5:1 minimum (AA), 7:1 target (AAA) |
| Contrast ratio (large text) | 3:1 minimum |
| Color independence | All color-coded info also has icon/text indicator |
| Color blindness | Profit/loss distinguished by ↑↓ arrows, not just green/red |

### 16.3 Interaction Accessibility

| Requirement | Implementation |
|-------------|---------------|
| Touch targets | 44×44px minimum |
| Keyboard navigation | Full tab order, visible focus indicators |
| Screen reader | ARIA labels on all interactive elements |
| Motion | Respect `prefers-reduced-motion`, disable non-essential animations |
| Text scaling | Support up to 200% without layout breakage |

### 16.4 Trading-Specific Accessibility

| Concern | Solution |
|---------|----------|
| Color-blind traders | Never rely solely on red/green; always add ↑↓ arrows or BUY/SELL labels |
| Low vision | High-contrast mode with 7:1+ ratios on all text |
| Motor impairment | Keyboard shortcuts for all critical actions (execute, dismiss, navigate) |
| Cognitive load | Progressive disclosure — essential info first, details on demand |

---

## 17. Implementation Roadmap

### Phase 1: Foundation (Week 1–2)

| Task | Deliverable |
|------|-------------|
| CSS custom property system | `tokens.css` with all color, spacing, typography tokens |
| Typography integration | Inter + JetBrains Mono, type scale, tabular figures |
| Base component library | Button, Input, Card, Badge, Toast |
| Dark mode infrastructure | CSS variable switching, system preference detection |
| Logo asset package | All sizes, all variants, SVG + PNG |

### Phase 2: Trading Components (Week 3–4)

| Task | Deliverable |
|------|-------------|
| Signal card component | Full and compact variants |
| Price display component | Monospace, color-coded, flash animation |
| Chart theme | Chart.js / Lightweight Charts color configuration |
| Data table component | Dense, sortable, color-coded cells |
| Dashboard layout | Grid system, responsive breakpoints |

### Phase 3: Platform Adaptation (Week 5–6)

| Task | Deliverable |
|------|-------------|
| Desktop title bar & tray | Custom chrome, icon variants |
| iOS component adaptation | SF Pro integration, haptic specs |
| Android adaptive icon | Foreground/background layers |
| Web PWA manifest | Icons, theme color, splash screen |
| Bot avatar assets | Telegram, Discord optimized |

### Phase 4: Polish & Documentation (Week 7–8)

| Task | Deliverable |
|------|-------------|
| Animation library | All motion specs implemented |
| Accessibility audit | WCAG 2.1 AA verification |
| Brand guidelines PDF | Complete reference document |
| Design token package | NPM package for team distribution |
| Component documentation | Storybook or equivalent |

---

*Architecture document for ALPHA STACK branding and identity system. All design decisions should be validated with target users before external release.*
