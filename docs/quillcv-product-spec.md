# QuillCV — Product Specification

**Status**: Draft v1 — source of truth for the 2026 design rebuild
**Audience**: Design, product, engineering
**Purpose**: Enumerate every surface of QuillCV with enough detail that a designer can produce high-fidelity screens without opening the codebase. Focus is UI/UX, not AI plumbing.

---

## 0. How to read this document

- **Sections 1–4** set context: vision, personas, journey, sitemap.
- **Section 5** is the bulk — every user-facing feature, one per subsection, each with the same six-part structure:
  1. **Purpose** (why it exists)
  2. **Current state** (what ships today)
  3. **Pain points** (what's wrong)
  4. **Desired state** (what "good" looks like)
  5. **UX principles** (the rules to design against)
  6. **Key screens** (ASCII wireframe or description)
- **Section 6** deep-dives the three priority rebuilds: onboarding, manual builder, cover letter.
- **Section 7** defines design principles that apply everywhere.

Priority markers: `[P0]` = rebuild now, `[P1]` = refine, `[P2]` = polish later.

---

## 1. Product vision

QuillCV helps people land interviews by producing CVs that pass Applicant Tracking Systems (ATS) and read like a human wrote them. It does this in three ways:

1. **AI tailoring** — takes a job description and your existing CV, rewrites yours to match the job's keywords and phrasing, while staying truthful.
2. **Manual building** — a Notion-grade CV editor with 47 ATS-tested templates and 12 country conventions baked in.
3. **Cover letter writing** — given a job and a tailored CV, produces a cover letter in matching voice.

The brand voice is *handcrafted*, not *corporate SaaS*. Editorial typography, paper textures, hand-drawn details. Privacy is a first-class product feature, not a footer link.

## 2. User personas

| Persona | Goal | Primary pain today |
|---|---|---|
| **International applicant** (Maya, 31, moving Berlin → Sydney) | A CV that looks right to AU recruiters without hiring a local coach | "I don't know what Australians expect on a CV" |
| **Career changer** (Rafael, 38, ops → tech) | Reframe 10 years of ops as transferable to a PM role | "Recruiters skim and miss the relevant parts" |
| **Tech professional** (Jin, 27, senior eng) | Tailor fast per job posting without rewriting from scratch | "I have one CV and I keep emailing the wrong version" |
| **Returning applicant** (every persona, 2nd+ CV) | Spin up a new CV for a new job in under 3 minutes | "It feels like I'm starting over every time" |

The shared thread: *low patience, high stakes, multiple attempts, privacy-conscious.*

## 3. End-to-end user journey

```
                    ┌─────────────────────────────────────────────────────────────┐
                    │                    ACQUISITION                              │
                    └──┬──────────────────────────────────────────────────────────┘
                       │
                       ▼
          ┌──────────────────────────┐
          │   1. Landing page        │  Sees value prop, pricing teaser, proof
          │   [P1 — recently redone] │
          └──────────┬───────────────┘
                     │ clicks "Start your first CV"
                     ▼
          ┌──────────────────────────┐
          │   2. Signup              │  Email+password, OAuth (Google, GitHub)
          │   [P1]                   │
          └──────────┬───────────────┘
                     │
                     ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║                     ACTIVATION — "first value in <10 min"                    ║
║                                                                              ║
║     ┌────────────────────────────────────────────────────────────────┐       ║
║     │   3. ONBOARDING  [P0 — full rebuild]                           │       ║
║     │                                                                │       ║
║     │   3a. Welcome (what QuillCV does · 1 screen)                   │       ║
║     │   3b. Privacy & vault setup (why encryption matters · consent) │       ║
║     │   3c. Upload existing CV (parse · confirm extracted data)      │       ║
║     │   3d. Role + region confirmation (extracted · editable)        │       ║
║     │   3e. Generic ATS demo (show score for a sample job in role)   │       ║
║     │   3f. Handoff: "Now tailor to a real job" or "Browse templates"│       ║
║     └──────────┬─────────────────────────────────────────────────────┘       ║
╚════════════════╪═════════════════════════════════════════════════════════════╝
                 │
                 ▼
     ┌─────────────────────────┐
     │    4. Dashboard         │   Hub: credits · my CVs · saved jobs · shortcuts
     │    [P1 — redesign]      │
     └─┬──────┬──────┬────┬────┘
       │      │      │    │
       ▼      ▼      ▼    ▼
    ┌─────┐┌─────┐┌────┐┌─────────┐
    │ AI  ││ MAN ││COV ││ MY CVS  │    Each is a path to producing / reviewing output
    │wiz  ││UAL  ││ER  ││         │
    │[P1] ││BLD  ││LET ││  [P1]   │
    │     ││[P0] ││TER ││         │
    │     ││     ││[P0]││         │
    └─────┘└─────┘└────┘└─────────┘
```

## 4. Information architecture

### 4.1 Public routes (no auth)

| Route | Template | Purpose | Priority |
|---|---|---|---|
| `/` | `landing.html` | Marketing landing page | P1 |
| `/pricing` | `pricing.html` | Plans & credit packs | P1 |
| `/demo` | `demo_index.html` | Browse 12 countries | P2 |
| `/demo/{country}` | `demo_country.html` | Country-specific template grid | P2 |
| `/demo/{country}/{template}` | `demo_preview.html` | Full template preview | P2 |
| `/demo/{country}/{template}/raw` | `cv_templates/*.html` | Bare CV for iframe/PDF | P2 |
| `/about` · `/privacy` · `/terms` · `/ccpa-opt-out` | `*.html` | Legal & marketing | P2 |
| `/blog` · `/blog/{lang}` · `/blog/{lang}/{slug}` | `blog_*.html` | SEO content | P2 |
| `/signup` · `/login` · `/auth/google` · `/auth/github` · `/forgot-password` · `/reset-password` | `auth/*.html` | Auth flows | P1 |

### 4.2 Authenticated routes

| Route | Template | Purpose | Priority |
|---|---|---|---|
| `/onboarding` | `onboarding.html` | Post-signup PII setup | **P0 — full rebuild** |
| `/account` | `account.html` | Profile, billing, passkeys, delete | P1 |
| `/account/pii` | `onboarding.html` (alias) | Vault edit | P1 |
| `/app` | → redirects to `/wizard/step/1` | AI wizard entry | P1 |
| `/wizard/step/{1..5}` | `partials/wizard/step*.html` | 5-step AI tailoring wizard | P1 |
| `/builder` | `builder.html` | Manual CV builder | **P0 — full rebuild** |
| `/builder/edit/{cv_id}` | `builder.html` | Edit saved CV | P0 |
| `/builder/preview` · `/save` · `/download-pdf` · `/download-docx` | HTMX / responses | Builder actions | P0 |
| `/my-cvs` · `/my-cvs/{id}/preview` · `/download` · `/download-docx` | `my_cvs.html` | Saved CVs list | P1 |
| `/jobs` · `/jobs/new` · `/jobs/{id}` | `jobs.html`, `new_job.html`, `job_detail.html` | Job tracking | P1 |
| `/profile` · `/profile/save` | `profile.html` | CV source profile | P1 |
| `/pricing` · `/checkout/alpha` · `/checkout/topup/{pack}` · `/checkout/success` | `pricing.html`, `checkout_success.html` | Stripe flow | P1 |
| `/invite/{code}` · `/invite/{code}/redeem` | `invite.html` | Invitation-based alpha signup | P1 |
| `/admin/*` | `admin*.html` | Internal admin | P2 (internal) |

### 4.3 New routes (proposed)

| Route | Purpose |
|---|---|
| `/dashboard` | Unified authenticated home (currently missing — `/app` jumps straight to the wizard) |
| `/cover-letter/new` | Start a cover letter from a saved job + CV |
| `/cover-letter/{id}` | View / edit existing cover letter |
| `/cover-letter/{id}/download-pdf` · `/download-docx` | Export |
| `/onboarding/step/{1..6}` | Split onboarding into discrete steps (currently one giant page) |

---

## 5. Features

### 5.1 Landing page `[P1]`

**Purpose**. Convert anonymous visitors into signups. Communicate the three-pillar value prop (ATS, 12 countries, AI tailoring) in one viewport.

**Current state**. Recently redesigned (commit `c3ec399`): hero with CV mock scene, proof bar, how-it-works, features, before/after, countries, trust, comparison, who, FAQ, pricing receipt, final CTA. Cool slate + brand purple palette.

**Pain points**.
- Hero CV mock is generic ("Alex Chen") — no chance to personalise for returning visitors.
- No template carousel / visual gallery; a user has to click into `/demo` to see what they're getting.
- Proof bar stats are static numbers; doesn't move.

**Desired state**. Keep current structure; future iterations add a **templates carousel** (horizontal scroll of real thumbnails), an **animated ATS match counter**, and **returning-visitor copy** ("Welcome back, Maya — continue your CV?") when logged in.

**UX principles**. Hand-drawn warmth. One accent color (brand purple). Paper-grain texture. Editorial serif for display. Both themes first-class.

### 5.2 Pricing page `[P1]`

**Purpose**. Show the alpha $9.99 offer and upsell paths (top-up packs, post-alpha subscription).

**Current state**. Handcrafted aesthetic with sticky-notes, pricing cards, FAQ.

**Pain points**. Comparison against competitors is on landing only; user has to cross-reference. Value anchoring not visible on pricing itself.

**Desired state**. Keep the handcrafted style. Add a **side-by-side competitor row** inline on this page. Make credit-pack math explicit ("15 CVs at $0.66 each") so prospects see unit economics.

### 5.3 Auth flows `[P1]`

**Screens**. `/signup`, `/login`, `/auth/google`, `/auth/github`, `/forgot-password`, `/reset-password`.

**Current state**. Separate pages for each; simple forms; OAuth buttons on login only.

**Pain points**.
- Signup and login are separate pages — single-form auth with mode toggle would be faster.
- No visible "what happens next" preview. A user clicking "Sign up" doesn't know they're about to go through onboarding.
- Forgot-password takes a user out of auth context and doesn't return them afterwards.

**Desired state**.
- **Single auth page** with tab toggle (Signup / Login).
- OAuth prominent, email second (reduces friction for known-service users).
- **Post-signup "what's next" card** — 3 bullets explaining the onboarding steps.
- Forgot-password modal (no page change).

**UX principles**. Password-less first (OAuth + magic link later). Email validation inline, not on submit. Show password toggle (eye icon) — don't hide by default for first-time users.

**Key screens**.
```
┌──────────────────────────────────────┐
│  QuillCV                             │
│                                      │
│  [ Sign up ] [ Log in ]              │   Toggle
│                                      │
│  ┌─ Continue with ─────────────┐     │
│  │ [  Google     ]             │     │
│  │ [  GitHub     ]             │     │
│  └─────────────────────────────┘     │
│                                      │
│  — or with email —                   │
│                                      │
│  [ email@you.com                 ]   │
│  [ ••••••••              👁 ]        │
│                                      │
│  [ Create account →    ]             │
│                                      │
│  ✓ Encrypted vault                   │
│  ✓ 15 CVs for $9.99 (alpha)          │
│  ✓ No subscription                   │
└──────────────────────────────────────┘
```

### 5.4 Onboarding `[P0 — full rebuild]`

**→ See Section 6.1 for the deep dive.**

Purpose in brief: take a first-time user from "I just signed up" to "I've seen my CV scored against a job in my role" in under 10 minutes. Explains privacy, captures PII into the vault, parses an existing CV, demos ATS.

### 5.5 Dashboard `[P1 — net-new]`

**Purpose**. A unified home for authenticated users. Currently missing — `/app` jumps straight to the wizard, forcing users to always be "mid-task."

**Current state**. Does not exist. Closest thing is the header nav (credits + My Account link).

**Pain points**. A returning user has no home. They either land on the wizard (mid-task) or `/my-cvs` (list-only). No glance-able status.

**Desired state**. New `/dashboard` with:
- **Credits strip** (balance + top-up button)
- **Active job** (if any mid-wizard or mid-builder) — "Resume in progress: Senior Engineer @ Canva"
- **My CVs shortcut** (latest 3 + link to full list)
- **Saved jobs** (latest 3 + "+ New job" CTA)
- **Quick actions**: Tailor for a new job · Build manually · Write a cover letter
- **Progress nudge** (if onboarding incomplete): "Finish setting up your vault"

**UX principles**. Glance-able at 10 feet. No dead ends — every card links somewhere. Respects whatever the user was last doing ("Resume").

**Key screens**.
```
┌────────────────────────────────────────────────────────────────────────┐
│  Welcome back, Daniel                          [ 8 credits • Top up ] │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌──── Continue where you left off ─────────────────────────────┐      │
│  │ 🖋️  Tailoring CV · Senior Engineer @ Canva · step 3 of 5     │      │
│  │ [ Resume → ]                                                 │      │
│  └──────────────────────────────────────────────────────────────┘      │
│                                                                        │
│  ┌── Quick actions ────────────────────────────────────────────┐       │
│  │ [ Tailor to a job ]  [ Build manually ]  [ Cover letter ]   │       │
│  └─────────────────────────────────────────────────────────────┘       │
│                                                                        │
│  ┌── Recent CVs ────────────────┐  ┌── Saved jobs ───────────────┐     │
│  │ · Senior Eng @ Canva  (AU)   │  │ · Senior Eng @ Canva         │     │
│  │ · Tech Lead @ Atlassian (AU) │  │ · Tech Lead @ Atlassian      │     │
│  │ · Staff Eng @ Stripe  (US)   │  │ · Staff Eng @ Stripe         │     │
│  │ [ View all → ]               │  │ [ + New job ]  [ View all → ]│     │
│  └──────────────────────────────┘  └──────────────────────────────┘     │
│                                                                        │
│  ┌── Your vault ───────────────────────────────────────────────┐       │
│  │  🔒 Personal data · Last updated 3 days ago · [ Review → ]  │       │
│  └─────────────────────────────────────────────────────────────┘       │
└────────────────────────────────────────────────────────────────────────┘
```

### 5.6 AI tailoring wizard `[P1]`

**Purpose**. Turn "I found a job posting" into "here's a tailored ATS-optimised CV" in 5 structured steps.

**Current state**. `/wizard/step/1..5`:
1. Country selection
2. Personal details (inc. photo where required)
3. Document upload (CV + optional extras like cover letter source)
4. Template selection
5. Review + generate

**Pain points**.
- 5 steps is too many for returning users — they know what they want. No "express mode."
- Personal details in step 2 duplicate the vault; should auto-populate from vault and let user override.
- Template selection (step 4) surfaces 47 templates without filtering by role/region — overwhelming.
- Step 5 review layout is cramped.

**Desired state**.
- **Compact mode** for returning users: pre-fills everything from last session, one-click regenerate with new job description.
- **Template recommendations** shown first (3 curated for the user's role + region), 47-full-list collapsed.
- **Auto-pull from vault** in step 2; read-only by default, "Edit for this CV" unlocks.

**UX principles**. Every step has a clear "why this matters" line. Progress always visible. "Back" never loses data. Step indicators clickable (jump).

### 5.7 Manual CV builder `[P0 — full rebuild]`

**→ See Section 6.2 for the deep dive.**

In brief: the current split-pane (form left, preview right) feels cramped because the preview column is ~45% of the viewport and users can't read their CV properly. Full rebuild with a WYSIWYG paper-sheet editor.

### 5.8 Cover letter generator `[P0 — net-new]`

**→ See Section 6.3 for the deep dive.**

In brief: a cover letter is always paired with a (job, CV) combination. The UX lives inside the Jobs detail view, not as a standalone island.

### 5.9 My CVs (library) `[P1]`

**Purpose**. Find and act on saved CVs — preview, download, edit, duplicate, delete.

**Current state**. `/my-cvs` — a list with Edit / Preview / Download buttons. 48-line template (minimal).

**Pain points**.
- No filtering (country, template, date, job linked).
- No sort.
- No duplicate ("clone this CV for a different job") — users manually restart the wizard.
- No thumbnails — just text rows.

**Desired state**.
- **Grid of card thumbnails** (actual CV rendered at 1:3 scale).
- **Filter chips**: country, template, last-edited date, linked-to-job.
- **Row actions on hover**: Duplicate · Link to job · Export PDF · Export DOCX · Delete.
- **Empty state**: "No CVs yet — [Start with AI] or [Build manually]."

**Key screens**.
```
┌──────────────────────────────────────────────────────────────────────┐
│  My CVs                                              [ + New CV ▾ ]  │
│                                                                      │
│  🇦🇺 Australia ▾   🎨 All templates ▾   📅 Updated ▾   🔗 Jobs ▾    │
│                                                                      │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐                      │
│  │ ■■■■■■ │  │ ■■■■■■ │  │ ■■■■■■ │  │ ■■■■■■ │   grid of thumbs    │
│  │ ■ ■■ ■ │  │ ■ ■■ ■ │  │ ■ ■■ ■ │  │ ■ ■■ ■ │                      │
│  │ ■■■■■■ │  │ ■■■■■■ │  │ ■■■■■■ │  │ ■■■■■■ │                      │
│  │        │  │        │  │        │  │        │                      │
│  │ Senior │  │ Tech   │  │ Staff  │  │ Solu-  │                      │
│  │ Eng @  │  │ Lead @ │  │ Eng @  │  │ tions  │                      │
│  │ Canva  │  │ Atlas- │  │ Stripe │  │ Eng @  │                      │
│  │ (AU)   │  │ sian   │  │ (US)   │  │ Canva  │                      │
│  └────────┘  └────────┘  └────────┘  └────────┘                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 5.10 Jobs dashboard `[P1]`

**Purpose**. Track applications — which jobs the user is targeting, what CV they tailored for each, what cover letter accompanied it.

**Current state**. `/jobs` list, `/jobs/new` multi-step wizard, `/jobs/{id}` detail page with generate / download actions.

**Pain points**.
- Job detail page mixes CV download and cover-letter download but the cover letter is generated on the fly, not stored as its own artifact. Users can't iterate on the letter independently.
- New job wizard duplicates concepts from the CV wizard.
- No status tracking (applied / interview / rejected / offer) — just a passive record.

**Desired state**.
- Add **status field**: `saved · applying · applied · interview · rejected · offer`.
- Job detail becomes **the hub** for that application: paired CV, paired cover letter, notes, status, deadline.
- Kanban-style filter on `/jobs` (columns = status).

**Key screens** (job detail redesign).
```
┌──────────────────────────────────────────────────────────────────────┐
│  ← Jobs                                                              │
│                                                                      │
│  Senior Software Engineer · Canva                       ◉ Applying ▾ │
│  Sydney, AU · Posted 3 days ago · Closes in 18 days                  │
│                                                                      │
│  ┌── Job description ─────────┐  ┌── Your CV ─────────────┐          │
│  │ [truncated text + expand]  │  │ [thumbnail]            │          │
│  │                            │  │ Tailored · ATS 94%     │          │
│  │                            │  │ [View] [Download]      │          │
│  └────────────────────────────┘  │ [Regenerate]           │          │
│                                  └────────────────────────┘          │
│  ┌── Cover letter ────────────┐  ┌── Notes ────────────────┐         │
│  │ [thumbnail]                │  │ Referred by Jamie       │         │
│  │ [View] [Download]          │  │ Mentioned team values   │         │
│  │ [Regenerate] [Write now]   │  │ shipping speed          │         │
│  └────────────────────────────┘  └─────────────────────────┘         │
└──────────────────────────────────────────────────────────────────────┘
```

### 5.11 Profile (CV source) `[P1]`

**Purpose**. The user's master "source CV" that every tailoring attempt starts from. Personal details, experience, education, skills.

**Current state**. `/profile` form-based editor.

**Pain points**. Separate from both the builder and the vault — three places to manage "stuff about me" confuses users.

**Desired state**. Merge with **vault** conceptually: the vault holds encrypted PII (name, email, phone, address), the profile holds the CV source (experience, education, skills). Both accessible from a single "My data" hub.

### 5.12 Vault (PII) `[P1]`

**Purpose**. Encrypted storage for sensitive personal info. Password-derived key — the server cannot decrypt without the user's password.

**Current state**. `/account/pii` form; accessible from header nav. Set up during onboarding.

**Pain points**. Users don't understand *why* a separate vault exists. The onboarding explanation is text-heavy; the distinction between "public CV data" and "private vault" isn't visual.

**Desired state**.
- **Visual trust indicators** — padlock SVG, "encrypted with your password" reassurance, "stored in Sydney" (or user's region) transparency.
- **Progressive disclosure** — show only the fields the user's selected country needs.
- **Inline editing** (click-to-edit each field) instead of a big form.

### 5.13 Account & billing `[P1]`

**Purpose**. Profile settings, password, OAuth, passkeys, credits, delete account.

**Current state**. `/account` monolithic page.

**Pain points**. Too much on one page; danger zone (delete) sits next to billing (buy credits) without visual separation.

**Desired state**. Tabbed or sectioned:
- **Profile** — name, email, preferred region/template defaults
- **Security** — password, OAuth, passkeys
- **Billing** — credits, transaction history, invoices
- **Privacy** — CCPA opt-out, data export, danger zone (delete)

### 5.14 Templates gallery (`/demo`) `[P2]`

**Purpose**. Browse 47 templates across 12 countries without signing up (SEO + conversion).

**Current state**. Country grid → country detail → template preview.

**Pain points**.
- A logged-in user using this to pick a template for a CV has to manually remember the name and use it in the wizard/builder.
- Search / filter is limited (country only).

**Desired state**. For logged-in users, **"Use this template"** button on each preview jumps straight into the builder or wizard with that template pre-selected.

### 5.15 Blog `[P2]`

**Purpose**. SEO + education. Articles on country-specific CV conventions, ATS tips, cover letter guides.

**Current state**. `/blog` index; `/blog/{lang}/{slug}` posts.

**Pain points**. Presentation is functional but not editorial; no navigation between related posts.

**Desired state**. "Read next" suggestions; per-country landing pages ("Writing a CV for Australia"); author bylines (builds trust).

### 5.16 Admin `[P2 — internal]`

Not user-facing. Skipping detailed spec.

---

## 6. Priority rebuilds — deep dive

### 6.1 Onboarding `[P0]`

**Goal**: in under 10 minutes, a user has (a) set up their vault, (b) uploaded an existing CV, (c) confirmed their role, (d) seen a concrete ATS score, (e) knows what to do next.

**Why the current onboarding is broken**:
- One 528-line template = one giant form = scroll fatigue.
- Privacy explained via paragraphs, not visuals.
- CV upload is optional and buried; many users skip it.
- Terminates without concrete demonstration of value.

**Proposed flow** — 6 steps, each one screen:

#### Step 1 — Welcome

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│    Welcome to QuillCV, Daniel.                                   │
│                                                                  │
│    In the next 10 minutes we'll:                                 │
│                                                                  │
│       1. Set up your private vault (60s)                         │
│       2. Import your current CV (60s)                            │
│       3. Score it against a sample job in your role (60s)        │
│       4. Hand you off to tailor to a real job (whenever ready)   │
│                                                                  │
│                                                                  │
│                             [ Let's go → ]                       │
│                                                                  │
│                             [ Skip onboarding ]                  │
│                                                                  │
│                                   1 of 6 ●○○○○○                  │
└──────────────────────────────────────────────────────────────────┘
```

**Why**: set expectations, give a time budget, show the shape of the journey. Skip option for power users.

#### Step 2 — Privacy & vault

Two-column layout: left explains *why*, right captures the password-derived vault key.

```
┌──────────────────────────────────────────────────────────────────┐
│  🔒  Your vault                                                  │
│                                                                  │
│  Why a vault?                              ┌─────────────────┐   │
│                                            │                 │   │
│  Your name, email, phone, address          │  Derive my key  │   │
│  never leave your device unencrypted.      │                 │   │
│                                            │  Password:      │   │
│  We encrypt them using a key derived       │  [ •••••••• ]   │   │
│  from your password. Even we can't         │                 │   │
│  read them.                                │  [ Set up → ]   │   │
│                                            │                 │   │
│  When you delete your account, the         └─────────────────┘   │
│  encrypted blob is destroyed — there's                           │
│  nothing for us to hand over in a          ☐ I understand if I   │
│  subpoena.                                   lose my password,   │
│                                              my vault is gone    │
│  [ Learn more → ]                                                │
│                                                                  │
│                                                   2 of 6 ●●○○○○  │
└──────────────────────────────────────────────────────────────────┘
```

**UX note**: the "I understand" checkbox is non-negotiable — prevents support tickets later.

#### Step 3 — Upload your CV

```
┌──────────────────────────────────────────────────────────────────┐
│  📄  Bring your existing CV                                      │
│                                                                  │
│  We'll extract your experience, skills, and achievements —       │
│  so you don't have to retype them.                               │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                                                          │    │
│  │             ⬆  Drop your CV here                         │    │
│  │                or [ browse files ]                       │    │
│  │                                                          │    │
│  │             PDF · DOCX · TXT · LinkedIn PDF export       │    │
│  │                                                          │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Don't have one? [ Skip — I'll start from scratch ]              │
│                                                                  │
│                                                   3 of 6 ●●●○○○  │
└──────────────────────────────────────────────────────────────────┘
```

After drop → parsing spinner → **Step 3b: Confirm extracted data** (below).

#### Step 3b — Confirm extracted data

Shows parsed sections inline and editable. Reduces the "did it get me right?" anxiety.

```
┌──────────────────────────────────────────────────────────────────┐
│  📄  Here's what we pulled from your CV                          │
│                                                                  │
│  ┌── Contact ──────────────────────────────────────────┐         │
│  │ Name · Daniel Zambrano              ✎               │         │
│  │ Email · daniel@example.com          ✎               │         │
│  │ Phone · not found — [ Add ]                         │         │
│  └─────────────────────────────────────────────────────┘         │
│                                                                  │
│  ┌── Experience (5 roles) ─────────────────────────────┐         │
│  │ ● Tech Lead · 2RK · 2021 – Present                  │         │
│  │ ● Senior Eng · Previous · 2018 – 2021               │         │
│  │ ● …                                                 │         │
│  │ [ Expand all ]                                      │         │
│  └─────────────────────────────────────────────────────┘         │
│                                                                  │
│  ┌── Skills (19) ──────────────────────────────────────┐         │
│  │ Ruby · Rails · Python · AWS · TDD · …               │         │
│  └─────────────────────────────────────────────────────┘         │
│                                                                  │
│  [ ← Upload different CV ]             [ Looks right → ]         │
│                                                   3b of 6 ●●●○○○ │
└──────────────────────────────────────────────────────────────────┘
```

#### Step 4 — Role & region

```
┌──────────────────────────────────────────────────────────────────┐
│  🎯  Your role and where you're applying                         │
│                                                                  │
│  We detected:                                                    │
│                                                                  │
│     Role       [ Software Engineer            ▾ ]                │
│     Seniority  [ Senior                       ▾ ]                │
│     Region     [ 🇦🇺 Australia                ▾ ]                │
│                                                                  │
│  These drive template recommendations and ATS scoring.           │
│  You can change them per-CV later.                               │
│                                                                  │
│  [ Save & continue → ]                                           │
│                                                   4 of 6 ●●●●○○  │
└──────────────────────────────────────────────────────────────────┘
```

#### Step 5 — Your first ATS score (the "aha")

This is the moment we prove value before asking for money.

```
┌──────────────────────────────────────────────────────────────────┐
│  📊  Here's how your CV scores against a typical                 │
│      Senior Software Engineer role in Australia                  │
│                                                                  │
│  ┌──────────────── ATS match ────────────────┐                   │
│  │                                            │                  │
│  │           64 / 100                         │                  │
│  │           ▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░           │                  │
│  │                                            │                  │
│  │  Matched keywords   18 / 32                │                  │
│  │  Sections present   4 / 4                  │                  │
│  │  Format issues      2                      │                  │
│  │                                            │                  │
│  └────────────────────────────────────────────┘                  │
│                                                                  │
│  We could get this to 90+ by tailoring to a specific job.        │
│                                                                  │
│  ┌── What'd raise this score ────────────────────────┐           │
│  │ + Add keywords: kubernetes, distributed systems…  │           │
│  │ + Fix: CV is 4 pages — AU recruiters prefer 2     │           │
│  │ + Add: explicit tech stack in summary             │           │
│  └───────────────────────────────────────────────────┘           │
│                                                                  │
│  [ Tailor to a real job → ]   [ Skip — take me to dashboard ]    │
│                                                   5 of 6 ●●●●●○  │
└──────────────────────────────────────────────────────────────────┘
```

**Why this matters**: the user has now *seen* what the product does. Conversion lift vs. "set up your vault" → "here's a dashboard."

#### Step 6 — Handoff

```
┌──────────────────────────────────────────────────────────────────┐
│  You're set up ✓                                                 │
│                                                                  │
│  What do you want to do next?                                    │
│                                                                  │
│  ┌──────────────────────┐  ┌──────────────────────┐              │
│  │ 🎯 Tailor to a job   │  │ 🖋️ Build manually    │              │
│  │                      │  │                      │              │
│  │ Paste a description, │  │ Pick a template and  │              │
│  │ AI tailors your CV   │  │ fill in the fields   │              │
│  │                      │  │                      │              │
│  │ [ Start → ]          │  │ [ Start → ]          │              │
│  └──────────────────────┘  └──────────────────────┘              │
│                                                                  │
│  ┌──────────────────────┐  ┌──────────────────────┐              │
│  │ 💼 Browse templates  │  │ ✉️ Write cover letter│              │
│  │                      │  │                      │              │
│  │ See 47 options       │  │ Given a job + CV     │              │
│  │ across 12 countries  │  │ we draft the letter  │              │
│  │                      │  │                      │              │
│  │ [ Browse → ]         │  │ [ Start → ]          │              │
│  └──────────────────────┘  └──────────────────────┘              │
│                                                                  │
│                                                   6 of 6 ●●●●●●  │
└──────────────────────────────────────────────────────────────────┘
```

---

### 6.2 Manual CV builder `[P0]`

**The problem**. Today's `builder.html` is 766 lines. Layout: form on left (fields by section), preview on right. The preview column is ~45% viewport, so A4 proportions mean the CV displays at ~60% readable size — users zoom, squint, scroll, and lose orientation. Context switches between "editing a field" and "checking the preview" break flow.

**Design target**. A single WYSIWYG sheet-of-paper canvas. Click anywhere on the CV to edit that content *inline*. A right-rail inspector only shows up when you need it (template switch, country switch, sections add/remove). Preview is reality — no second render.

**Layout — desktop**

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ← My CVs   ·   Untitled CV  ✎                        [ Save ]  [ Download ▾]│
│─────────────────────────────────────────────────────────────────────────────│
│ LEFT RAIL (240px)    │        CV CANVAS (A4 sheet, full-fidelity)            │
│                      │                                                        │
│ 📄 Document          │   ╔═══════════════════════════════════════════╗        │
│   Title: Untitled    │   ║                                           ║        │
│                      │   ║   Daniel Zambrano            [photo]      ║        │
│ 🌍 Region            │   ║   Senior Software Engineer                ║        │
│   [🇦🇺 Australia ▾]  │   ║   ───────────────────────────────         ║        │
│                      │   ║   daniel@…  +61 …  Sydney, AU             ║        │
│ 🎨 Template          │   ║                                           ║        │
│   [ Modern      ▾]   │   ║   SUMMARY                                 ║        │
│   See all →          │   ║   [click to edit summary]                 ║        │
│                      │   ║                                           ║        │
│ 📝 Sections          │   ║   EXPERIENCE                              ║        │
│   ☑ Summary          │   ║   [click to edit roles]                   ║        │
│   ☑ Experience       │   ║                                           ║        │
│   ☑ Education        │   ║   EDUCATION                               ║        │
│   ☑ Skills           │   ║   …                                       ║        │
│   ☐ Projects         │   ║                                           ║        │
│   ☐ Certifications   │   ╚═══════════════════════════════════════════╝        │
│   ☐ References       │                                                        │
│   ☐ Languages        │   Page 1 of 1                                          │
│   [ + Add section ]  │                                                        │
│                      │                                                        │
│ 👤 Personal data     │                                                        │
│   Pulled from vault  │                                                        │
│   [ Review → ]       │                                                        │
└──────────────────────┴────────────────────────────────────────────────────────┘
```

**Click into the CV canvas → inline edit mode**:

```
║  EXPERIENCE                                                       ║
║                                                                   ║
║  ┌─────────────────────────────────────────────────────────┐      ║
║  │  Tech Lead   ·   2RK   ·   2021 – Present  ✎            │      ║
║  │                                                         │      ║
║  │  • [Led migration of payment service to AWS Lambda…]    │      ║
║  │  • [Mentored 5 engineers through pair programming…]     │      ║
║  │  • [+ Add bullet ]                                      │      ║
║  │                                                         │      ║
║  │  [ Move up ] [ Duplicate ] [ Delete ]                   │      ║
║  └─────────────────────────────────────────────────────────┘      ║
║                                                                   ║
║  [ + Add role ]                                                   ║
```

**Right-rail inspector** (appears when section clicked):

```
─────────────────────────┐
│  Experience            │
│                        │
│  Role title            │
│  [ Tech Lead         ] │
│                        │
│  Company               │
│  [ 2RK               ] │
│                        │
│  Location              │
│  [ Sydney, AU        ] │
│                        │
│  Dates                 │
│  [ 2021 ] – [ Present ]│
│                        │
│  Tech                  │
│  [ Ruby, Rails, AWS  ] │
│                        │
│  ─── ATS hint ──────   │
│  💡 Add "distributed   │
│     systems" — it's    │
│     in your target     │
│     job description    │
│                        │
└────────────────────────┘
```

**Mobile layout** — canvas full-width, bottom sheet for inspector when a section is tapped.

**UX principles**.
- **WYSIWYG is the law**: if it's on the CV, you edit it *on* the CV. No separate form-then-render.
- **One inspector at a time** — the right rail shows the context of what was last clicked, not every field.
- **Template switch preserves content** — changing from Modern to Classic doesn't reset the data, it just reflows. Undo supported.
- **Country switch prompts conventions** — "AU CVs typically don't include a photo. Want me to remove it?" — suggestion, not forced.
- **Inline validation** — if a required field is missing (e.g., DE requires birthdate), show inline "missing" marker, not a validation error on save.
- **Sections are draggable** — reorder with a handle in the right rail.
- **Always-on autosave** — "Saved 3s ago · last change: Summary".
- **Zoom controls** — keyboard shortcut `Ctrl+0` to fit, `Ctrl±` to zoom. 
- **Desktop-first** but mobile usable — the canvas is the primary surface, inspector adapts.

**Key interactions**.
- Click **section heading** → inspector lets you rename section, toggle visibility, reorder.
- Click **body text** → inline rich-text editor (bold, italic, bullet, no other formatting).
- Click **photo** → upload dialog; drag-to-reposition inside frame; remove.
- `Tab` from a field → jumps to next logical field.
- `Esc` → closes inspector, deselects.
- `Ctrl+Z` / `Ctrl+Y` → undo / redo (required; 50+ step history).

**Technical notes for implementers** (not UX but important):
- The canvas is `contenteditable` in scoped islands — not the whole page.
- Autosave via HTMX `hx-post` on blur + debounced `hx-post` every 5s.
- Template switch = re-render CSS scope (keeps same data model).
- Right rail state lives in URL fragment (`#section=experience&role=0`) so a copy-paste link reopens the same state.

---

### 6.3 Cover letter generator `[P0]`

**The shape**.
- A cover letter is always bound to a **(job, CV)** pair. It doesn't make sense standalone.
- Lives as a first-class artifact in the Jobs detail page.
- Has its own templates (formal, modern, casual), short/medium/long variants.
- Editable WYSIWYG, same editing model as the CV builder.
- Exportable as PDF / DOCX, matches visual tone of the paired CV.

**Entry points**.
1. From a **Job detail page** — "Write a cover letter for this application" button (primary entry).
2. From the **Dashboard quick actions** — shows "pick a job" modal if not coming from a job context.
3. From the **onboarding handoff** (step 6) — for users who already uploaded a CV.

**Flow**.

```
            ┌─────────────────────────────────┐
            │  Job detail — Canva SE         │
            │  "Write a cover letter" button  │
            └──────────────┬──────────────────┘
                           ▼
        ┌──────────────────────────────────────────┐
        │  Cover letter setup (1 screen)            │
        │                                          │
        │  Tone:       [ Professional    ▾ ]       │
        │  Length:     ● Short · ○ Med · ○ Long    │
        │  Focus on:   ☑ Experience                │
        │              ☑ Skills match              │
        │              ☐ Culture fit               │
        │              ☐ Specific bullet           │
        │                                          │
        │  [ Draft the letter ]                    │
        └──────────────┬───────────────────────────┘
                       ▼
        ┌──────────────────────────────────────────┐
        │  Split editor: Letter | Job | CV         │
        │  (see below)                             │
        └──────────────────────────────────────────┘
```

**Split editor**.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ← Job: Canva SE        Cover letter · draft 1            [ Save ]  [ PDF ]  │
│──────────────────────────────────────────────────────────────────────────────│
│                                    │                          │              │
│  ╔═══════════════════════════╗     │  Job description         │ Your CV      │
│  ║                           ║     │  (collapsed sections)    │ (thumbnail)  │
│  ║  Dear Hiring Team,        ║     │                          │              │
│  ║                           ║     │  About the role          │ [thumb]      │
│  ║  I'm writing to apply     ║     │  [expand]                │              │
│  ║  for the Senior Engineer  ║     │                          │ ATS 94%      │
│  ║  role at Canva. With 8    ║     │  Requirements            │              │
│  ║  years of building        ║     │  [expand]                │ [ View ]     │
│  ║  distributed systems…     ║     │                          │              │
│  ║                           ║     │  Nice-to-have            │              │
│  ║  [click to edit]          ║     │  [expand]                │              │
│  ║                           ║     │                          │              │
│  ║  Sincerely,               ║     │  💡 AI highlighted 8     │              │
│  ║  Daniel                   ║     │     keywords you could   │              │
│  ║                           ║     │     address              │              │
│  ╚═══════════════════════════╝     │                          │              │
│                                    │                          │              │
│  [ Regenerate ] [ Tone ▾ ]         │                          │              │
└────────────────────────────────────┴──────────────────────────┴──────────────┘
```

**Key behaviours**.
- **Highlight sync** — hovering a paragraph in the letter highlights the CV bullet / job-description line it references. Visible thread between the three panels.
- **Keyword badge on job description** — each ATS keyword from the job description gets a chip (green = mentioned in letter, grey = not). Click the chip to insert a sentence referencing it.
- **Tone slider**, not dropdown — "More formal ⇠⇢ More personal". Regenerates in place with debounce.
- **Length toggle** — 3 buttons; regenerates the letter at that length preserving structure where possible.
- **Version history** — every regenerate saves a draft. "Compare with draft 2" side-by-side.
- **"Match my CV voice"** — analyses the user's existing CV bullets for tone; applies the same cadence.

**Templates**.
- Formal (default): block paragraphs, conservative salutation.
- Modern: tighter, bullet-ed middle section.
- Casual: first-name salutation, 3-paragraph structure.

**Export**. Same PDF / DOCX pipeline as the CV. Visually matches the paired CV template's palette.

**Empty state**.

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│             ✉️                                                    │
│                                                                  │
│          No cover letter for this job yet                        │
│                                                                  │
│     Pair this job description with your CV                       │
│     and we'll draft a letter in your voice.                      │
│                                                                  │
│                  [ Write a cover letter → ]                      │
│                                                                  │
│                  [ Import from file ]                            │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 7. Design principles (apply everywhere)

1. **Handcrafted, not corporate.** Paper grain, hand-drawn SVG, asymmetric radii stay as signature. We're *not* Resume.io.
2. **One accent colour.** Brand purple (`--accent`). Semantic status (green/red) only when it means something.
3. **Tokens over literals.** Every spacing, radius, shadow resolves through `tokens.css`. See `docs/DESIGN_SYSTEM.md`.
4. **Density with restraint.** Content-dense on content surfaces (builder, job detail), generous on marketing surfaces (landing, pricing).
5. **Skip-ability.** Any multi-step flow (onboarding, wizard) has a skip path. Power users shouldn't pay a first-time-user tax.
6. **WYSIWYG where possible.** If a user sees it rendered, they should edit it rendered.
7. **Privacy visible.** The padlock, the vault, the "encrypted with your password" badge — first-class UI elements, not footnotes.
8. **Autosave is the default.** No explicit save button on any editor surface (keep the button for completeness but autosave runs in the background).
9. **Both themes.** Every screen designed in both light and dark from the start, not as an afterthought.
10. **Keyboard is a first-class input.** Every action reachable without a mouse; Tab order is meaningful; `?` opens shortcuts.

---

## 8. Cross-cutting concerns

### 8.1 Accessibility

Target: **WCAG 2.2 AA.**
- Colour contrast ≥ 4.5:1 for body, ≥ 3:1 for UI/large text.
- All interactive controls keyboard-reachable; visible focus (already in `components.css`).
- Form inputs have associated `<label>`s or `aria-label`.
- Skip-to-content link (already in `base.html`).
- Reduced motion respected (already in `components.css`).
- Screen reader: semantic HTML; `aria-live` regions for HTMX updates.

### 8.2 Responsive breakpoints

| Breakpoint | Width | Behaviour |
|---|---|---|
| Mobile | < 640px | Single column, inspector becomes bottom sheet, wizard full-height |
| Tablet | 640–980 | Two-column where reasonable; right rail collapses |
| Desktop | 981–1400 | Primary target; full split layouts |
| Large | > 1400 | Capped at 1400px with generous gutters |

### 8.3 Performance

- First paint < 1.2s on 3G (landing / pricing / auth).
- Authed surfaces may be heavier (editor canvas) but first paint still < 2.5s.
- CSS is per-page where possible (landing has `landing.css`, builder will have `builder.css`).
- No JS framework. HTMX for interactivity. Vanilla JS for micro-interactions only.

### 8.4 Brand voice (copy)

Words we use: *craft, tailor, pass, sharp, confident, honest, private*.
Words we avoid: *revolutionary, AI-powered (as a badge), next-gen, supercharged, delightful*.

Sentences end with intent. The CTA is always a verb starting the phrase. "Start your first CV," not "Click here to begin your first CV creation journey."

---

## 9. Out of scope (this doc)

- AI internals: model choice, prompt engineering, token budgeting. Handled in engineering docs.
- Backend architecture: database schema, migrations, encryption algorithm. Handled in `docs/ai/` and code.
- Marketing campaigns, analytics strategy, A/B tests.
- Pricing strategy beyond the alpha offer.
- Admin tooling UX.

---

## 10. Open questions

These are decisions I'd flag before design work starts:

1. **Onboarding split into discrete routes or a single `/onboarding` page with step state?** Discrete routes give clean URLs and skip support; single page allows progressive reveal and is simpler to build.
2. **Dashboard — does it replace `/app`, or do we keep `/app` as a wizard shortcut and `/dashboard` as the hub?** I recommend the former: `/app` redirects to `/dashboard`; the wizard is `/app/tailor` or `/wizard`.
3. **Cover letter as its own route (`/cover-letter/{id}`) or a section of `/jobs/{job_id}`?** I recommend keeping it inside the job (URL: `/jobs/{job_id}/cover-letter`) since it's always bound.
4. **Builder WYSIWYG scope — rich text or plain?** I recommend plain (bullets, bold only). Rich formatting hurts ATS parsing and explodes template compatibility.
5. **Templates on the ATS score demo in onboarding** — use the user's actual uploaded CV or a fabricated "similar profile" CV? Using the user's CV is higher-impact but requires the parse to have succeeded.

---

## 11. Next steps

1. **Review this doc.** Disagreements / corrections land here as comments.
2. **Wireframes for the three P0 rebuilds** — higher fidelity than the ASCII in §6.
3. **Build sequence**: Onboarding first (highest drop-off risk) → Manual builder (highest daily-use pain) → Cover letter (highest new-revenue potential) → Dashboard (ties them together).
4. **Per-feature spec tickets** in YouTrack, one per §5 subsection marked `[P0]` or `[P1]`.
