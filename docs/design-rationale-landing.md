# Landing Redesign — Design Rationale

**Direction**: Letterpress Atelier — warm paper, careful ink, editorial restraint.

The brief was to preserve QuillCV's handcrafted DNA (sketchy borders, sticky-notes, Caveat handwriting) while elevating it out of the "sticky-note kindergarten" range and into something that feels like a high-end stationery brand (Baron Fig × Midori × Leuchtturm1917) crossed with editorial magazine layout.

---

## Type system

Three typefaces, each doing distinct work. **No Inter, no Roboto, no Arial.**

- **Fraunces** (variable serif, Google Fonts) — display, headings, numerals, stamp text. Optical sizing axis (`opsz`) lets the hero set at `144` with soft edges (`SOFT: 100`) and irregular warmth (`WONK: 1`), while small section labels use `opsz: 9..14` for tight metrics. Italic axis is used deliberately: emphasised nouns in headings are always italic + plum-colored for editorial weight. Fraunces' expressive italic *is* the brand voice.
- **Manrope** (geometric sans, Google Fonts) — body copy, UI labels, paragraph text. Geometric but warm, avoids the "Vercel Inter" look. Weight range 400–800.
- **Caveat** (handwriting, already loaded in `base.html`) — marginalia, taglines, annotations, and the handnotes next to primary CTAs. Never for primary copy.

## Color system

Two first-class themes. Both ground in paper + ink, not in the prior "dark purple SaaS" palette.

**Light** — warm cream parchment (`#f6efde`) with deep ink (`#1c1820`), sepia body copy (`#574c3b`), vintage stamp red (`#b73e2a`) for accent marks, editorial plum (`#6c2c66`) for italic emphasis, highlighter yellow (`#e9d47a`) for — literal — highlights.

**Dark** — deep night indigo (`#11131c`) with bone white text (`#e8e4d4`), muted pale gold (`#a7a293`) for body, warm coral (`#e06a4a`) replacing the stamp red, and a softened plum (`#c9a5ff`) so italic emphasis still reads on the dark ground.

The existing `--accent` purple stays as interactive primary (buttons, links, focus) so the rest of the app keeps visual continuity.

## Atmosphere

- **Paper grain**: full-viewport fixed overlay using SVG `feTurbulence` noise at low opacity, `mix-blend-mode: multiply` in light, `screen` in dark. Gives every surface a subtle tooth.
- **Shadows**: two-layer paper shadow (`0 20px 50px -20px` for long falloff + `0 4px 14px -4px` for contact) applied to the hero CV sheet and the receipt. Pages feel lifted off the desk, not floated in nothingness.
- **Ruled backgrounds**: the comparison table uses `repeating-linear-gradient` with a faint accent tint every 48px — ledger ruling without being literal.
- **Torn edge**: the pricing teaser `clip-path`s its own bottom into a jagged receipt tear. Visual signature nobody can copy-paste from Figma.

## Layout moves

1. **Hero is a scene, not a screenshot**. Left: headline + CTA. Right: a mocked CV sheet at a slight rotation with two keywords circled in red pen (SVG `::before` with asymmetric border-radius to look hand-drawn), a yellow sticky-note annotation reading `ATS match 94%`, a handwritten `+8 keywords circled` note in the margin, and a pencil doodle leaning in from the top-right. You can *see* what the product does before you scroll.
2. **Proof bar**. A four-column stats strip (`12 countries`, `47 templates`, `$9.99 alpha`, `0 subscriptions`) bookended by hairline rules. Cheap to build, heavy in conversion lift.
3. **How-it-works** uses organic asymmetric radius on the step-number badges (wonky circles) instead of perfect circles. The steps themselves tilt slightly (`rotate: 0.6deg` / `-0.8deg`) and un-tilt on hover — the page breathes.
4. **Countries**. 12 tiles of flag + name in a 6-col grid (4 at tablet, 2 at mobile). Each tile tilts on hover. Turns "we support 12 countries" from a bullet point into an atlas.
5. **Pricing receipt**. The most distinctive element. Genuine ticket layout: stamp badge, dashed rule divider, itemised list with dot leaders (`::after` pseudo filling the gap), total with oversized price, torn-edge bottom via clip-path. Leads into `/pricing` for the full plan details.
6. **Final CTA** ends with a handwritten margin note and a hand-drawn arrow pointing to the button — loops back to the hero's handcrafted DNA.

## Micro-interactions

Kept restrained. Hover transitions are `var(--duration) var(--ease-out)` from tokens. Cards lift and un-tilt; links grow a focus underline; the button's existing `-0.5deg` rotation hover (from Phase 2a) survives.

`prefers-reduced-motion` disables all transforms on the landing page specifically — respected globally already, made explicit here for the heavier scene elements.

## What was preserved

- All SEO content (title, meta description, OG/Twitter tags, schema.org JSON-LD)
- All copy points (3 how-it-works steps, 6 features, 3 trust cards, 5 comparison rows, 3 who-it's-for cards, 2 CTAs)
- The existing `.handwritten` class and Caveat font
- The existing `.btn`/`.btn--primary` system from Phase 2a
- Tokens from `tokens.css` — every color, spacing, radius, shadow, motion value resolves through tokens

## What was retired

- The old `.hero`, `.hero-doodle--*`, `.step-card`, `.feature-card`, `.sticky-note--*`, `.trust-card`, `.who-card`, `.comparison-table` class families on the landing page (still defined in `marketing.css` but no longer referenced here — dead CSS to clean up later)
- The six-color sticky-note grid (yellow/blue/green/pink/lavender/peach) for features — replaced with subtle outlined feature cards and the hand-drawn icon row
- The emoji-free feature doodles — swapped for cleaner stroked SVG icons

## Files

- `app/static/landing.css` — all landing-specific styles (~700 lines)
- `app/templates/landing.html` — rewritten Jinja template; all content preserved, structure redone
- `docs/design-rationale-landing.md` — this document
- No changes to `base.html`, `tokens.css`, `components.css`, `marketing.css`, or any other global file

## Responsive breakpoints

- `1120px+` — full 2-col hero, 3-col grids, 6-col country tiles
- `980px–` — stacked hero, 2-col grids, 4-col country tiles, 2-col proof bar
- `640px–` — everything single-column; hero CV shrinks; receipt tightens; comparison table compresses padding

## Next iteration ideas

If we keep going on polish:
- Animate the hero keyword circles drawing on page-load with `stroke-dasharray` animation
- Add a subtle parallax to the pencil doodle on scroll
- Swap country emoji flags for custom inline SVGs (ATS-safe; emoji rendering varies)
- Replace the feature-card icon set with one custom-drawn, hand-stroked icon family
- Consider an intermediate "proof" section with real alpha user counts once we have them
