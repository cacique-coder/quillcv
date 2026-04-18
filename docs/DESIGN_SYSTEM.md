# QuillCV Design System

Living document for the QuillCV visual language. Phase 1 focuses on **standardisation** (no visual change). Later phases refine the look.

---

## Principles

1. **Hand-drawn, handcrafted** — QuillCV's visual signature is sketchy borders, wavy dividers, sticky-note cards, and the Caveat handwriting font. Polish without losing warmth.
2. **ATS-safe on CV output** — CV templates must render as clean, parseable documents. No system-level weirdness should leak into generated PDFs.
3. **Dual theme** — Light (paper / notebook) and dark (ink / late-night). Both are first-class.
4. **Tokens over literals** — every color, size, radius, and shadow in app UI should resolve to a token.

---

## Token categories

All tokens live in `app/static/tokens.css` and are available everywhere via CSS custom properties.

### Color — semantic (UI)

| Token | Dark | Light | Purpose |
|---|---|---|---|
| `--bg` | `#0f1117` | `#f0eeea` | Page background |
| `--surface` | `#1c1f2b` | `#f7f6f3` | Card / panel background |
| `--border` | `#2e3142` | `#dbd8d2` | Dividers, borders |
| `--text` | `#e1e4ed` | `#2c2c3a` | Primary text |
| `--text-muted` | `#8b8fa3` | `#71717f` | Secondary text, captions |
| `--accent` | `#6c63ff` | `#5b52e0` | Brand / interactive |
| `--accent-hover` | `#5a52d5` | `#4a42c0` | Hover state |
| `--green` | `#34d399` | `#059669` | Success, positive metrics |
| `--yellow` | `#fbbf24` | `#d97706` | Caution |
| `--red` | `#f87171` | `#dc2626` | Error, destructive |
| `--warning` | `#f59e0b` | `#d97706` | Warning callouts |

### Typography

| Token | Value | Use |
|---|---|---|
| `--font-sans` | `-apple-system, "Segoe UI", Roboto, sans-serif` | App UI default |
| `--font-serif` | `Georgia, "Times New Roman", serif` | Classic/academic CV templates |
| `--font-mono` | `"SF Mono", Menlo, Consolas, monospace` | Code, data tables |
| `--font-hand` | `"Caveat", cursive` | Landing/pricing handwritten annotations |
| `--text-xs` | `0.75rem` | Small caption |
| `--text-sm` | `0.85rem` | Secondary UI |
| `--text-base` | `1rem` | Body |
| `--text-lg` | `1.125rem` | Emphasised body |
| `--text-xl` | `1.25rem` | Subheading |
| `--text-2xl` | `1.5rem` | H3 |
| `--text-3xl` | `1.875rem` | H2 |
| `--text-4xl` | `2.25rem` | H1 |
| `--leading-tight` | `1.2` | Headings |
| `--leading-normal` | `1.6` | Body |
| `--weight-regular` | `400` | Body |
| `--weight-medium` | `500` | Buttons, labels |
| `--weight-semibold` | `600` | Subheadings |
| `--weight-bold` | `700` | Headings |

### Spacing (4 px base)

| Token | Value | Typical use |
|---|---|---|
| `--space-0` | `0` | — |
| `--space-1` | `0.25rem` (4px) | Tight inline |
| `--space-2` | `0.5rem` (8px) | Small gap |
| `--space-3` | `0.75rem` (12px) | Form field gap |
| `--space-4` | `1rem` (16px) | Default gap |
| `--space-5` | `1.25rem` (20px) | Section-internal |
| `--space-6` | `1.5rem` (24px) | Between related blocks |
| `--space-8` | `2rem` (32px) | Between unrelated blocks |
| `--space-10` | `2.5rem` (40px) | Large gap |
| `--space-12` | `3rem` (48px) | Section break |
| `--space-16` | `4rem` (64px) | Page-level |

### Radius

| Token | Value | Use |
|---|---|---|
| `--radius-sm` | `4px` | Badges, tags |
| `--radius` | `8px` | Inputs, buttons, small cards |
| `--radius-md` | `12px` | Cards |
| `--radius-lg` | `16px` | Large panels |
| `--radius-pill` | `999px` | Pills, chips |

Note: QuillCV's hand-drawn aesthetic deliberately uses **asymmetric radii** in places (e.g., `12px 18px 10px 14px`). Those stay as literals because they're design intent, not arbitrary values.

### Shadow

| Token | Value | Use |
|---|---|---|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.08)` | Subtle depth |
| `--shadow` | `0 2px 8px rgba(0,0,0,0.12)` | Cards |
| `--shadow-md` | `0 4px 16px rgba(0,0,0,0.15)` | Modal, elevated cards |
| `--shadow-lg` | `0 8px 32px rgba(0,0,0,0.2)` | Sticky-note lift |

### Motion

| Token | Value | Use |
|---|---|---|
| `--ease-out` | `cubic-bezier(0.2, 0.8, 0.2, 1)` | Most transitions |
| `--ease-in-out` | `cubic-bezier(0.4, 0, 0.2, 1)` | Symmetric |
| `--duration-fast` | `120ms` | Tiny UI feedback |
| `--duration` | `200ms` | Default |
| `--duration-slow` | `400ms` | Complex transitions |

### Z-index scale

| Token | Value | Use |
|---|---|---|
| `--z-base` | `0` | Default |
| `--z-sticky` | `10` | Sticky headers inside containers |
| `--z-header` | `100` | Site header |
| `--z-dropdown` | `200` | Menus |
| `--z-modal` | `1000` | Modals, overlays |
| `--z-toast` | `1100` | Toasts above modals |

---

## Components (target state)

Phase 2 introduces these. Tracking here so the plan is visible.

### Button — two intentional families

The app has two button visual languages that serve different roles. They are **not** unified because their aesthetics are genuinely different.

**Marketing family** (`.btn` + BEM modifiers, in `components.css`) — landing, pricing, auth, demo, onboarding. Hand-drawn sketchy feel.

- `.btn` base — `padding: 0.9rem 2.2rem`, asymmetric `border-radius: 6px 10px 8px 12px`, `font-size: 1rem`
- `.btn--primary` — gradient accent, shadow, hover rotation `-0.5deg`
- `.btn--secondary` — outlined accent (2px border)
- `.btn--ghost` — muted outline (1px border-color)
- `.btn--sm` — smaller padding (`0.5rem 1.2rem`), smaller font (`0.85rem`)
- `.btn--full` — full-width centered
- `.btn--disabled` — 50% opacity, not-allowed

Migrated in Phase 2a: `.btn-cta`, `.btn-cta--small`, `.btn-cta--full`, `.btn-cta--secondary`, `.btn-cta--outline`, `.btn-cta--disabled`.

**App utility family** (flat legacy classes, in `app-ui.css` / `style.css` / `wizard.css`) — account, my-cvs, jobs, wizard, builder. Clean, compact, functional.

- `.btn-primary` — flat accent background (context-scoped in `.cv-card-actions` and `.my-cvs-empty-actions`)
- `.btn-secondary` — surface bg, subtle border, accent text, small padding (`0.5rem 1rem`)
- `.btn-danger` — red background, small padding (`0.55rem 1.2rem`)
- `.btn-sm` — size modifier (`0.4rem 0.9rem`, `0.82rem` font)
- `.btn-next` / `.btn-back` / `.btn-generate` — wizard nav, unique asymmetric radius `5px 7px 6px 4px`
- `.btn-download` / `.btn-download--secondary` — job download actions
- `.btn-social--google` / `.btn-social--github` — OAuth buttons
- `.bld-btn-next|prev|save|cancel|pdf` — builder-scoped, self-contained
- `.cookie-btn|--accept|--decline` — cookie banner, self-contained

**Rule for new buttons**:
- New marketing/CTA button? Use the `.btn .btn--*` family.
- New app-page button? Match the nearby context's legacy class convention.
- Phase 4 polish may unify further when intentional visual refresh happens.

### Card / Panel
Base `.card` + modifiers:
- `.card--sticky` (sticky-note, rotated)
- `.card--elevated` (shadow-md)
- `.card--outlined` (border, no shadow)

### Form field
Already solid via `macros/ui.html`. Phase 2 formalises error/disabled states.

### Badge
`.badge` + `.badge--success | --warning | --danger | --info | --neutral`.

---

## CV template contract (target state)

All 47 CV templates share primitives via `cv-base.css`:
- `.cv-page` — outer layout
- `.cv-header`, `.cv-name`, `.cv-title`, `.cv-contact`
- `.cv-photo`
- `.cv-body h2` (section headings)
- `.cv-list`, `.cv-list--dashed`, `.cv-list--bullet`
- `.cv-timeline`, `.cv-timeline__entry`

Per-template CSS keeps only:
- Unique layout (one-column vs two-column vs sidebar)
- Accent color pick (via CV-scoped variables, e.g., `--cv-accent: var(--cv-accent-blue)`)
- Font family pair

### CV-specific color tokens
The 126 ad-hoc hex codes across CV templates collapse into ~14 semantic tokens:

| Token | Approx value | Used by |
|---|---|---|
| `--cv-accent-blue` | `#1a73e8` | modern, intern |
| `--cv-accent-navy` | `#1a365d` | academic, executive |
| `--cv-accent-cyan` | `#0ea5e9` | tech |
| `--cv-accent-purple` | `#7c3aed` | creative, infographic |
| `--cv-accent-green` | `#059669` | environmental |
| `--cv-accent-gold` | `#b45309` | hoja-de-vida |
| `--cv-text-primary` | `#1a1a1a` | body text |
| `--cv-text-secondary` | `#444` | subheadings |
| `--cv-text-muted` | `#888` | dates, meta |
| `--cv-border` | `#e5e7eb` | dividers |
| `--cv-bg-subtle` | `#f5f5f5` | skill pills |

---

## File layout (target)

```
app/static/
├── tokens.css        # design tokens (single source of truth)
├── base.css          # reset, body, typography base
├── layout.css        # header, footer, grid containers
├── components.css    # btn, card, badge, form, nav
├── wizard.css        # wizard-specific (5 steps, progress, panels)
├── marketing.css     # landing, pricing, blog
├── cv-base.css       # shared CV primitives
└── style.css         # legacy bucket — shrinks each refactor pass
```

Load order in `base.html`:
1. `tokens.css`
2. `base.css`
3. `layout.css`
4. `components.css`
5. Page-specific CSS (`wizard.css`, `marketing.css`)
6. `style.css` (legacy, highest specificity by virtue of load order)

---

## Phase roadmap

| Phase | Scope | Visual change? | Status |
|---|---|---|---|
| **1a** | Tokens file + design system docs | No | ✅ shipped |
| **1b** | Split `style.css` into logical files | No | ✅ shipped |
| **2a** | Marketing CTA button family → `.btn` + BEM modifiers | No | ✅ shipped |
| **2b** | App utility button family unification | Minimal | 📋 deferred to Phase 4 — treating app-page and marketing buttons as two intentional families for now |
| **3** | CV template base + CV color tokens | No (templates identical) | pending |
| **4** | 2026 polish — typography rhythm, density, microinteractions, button family unification | Yes (intentional) | pending |

---

## Contributing

- New color? Add it to `tokens.css` as a semantic token, not a literal hex in a component.
- New component? Document it here before building.
- Breaking change to a token? Bump `?v=` on the CSS link in `base.html` and update CV templates that depend on it.
