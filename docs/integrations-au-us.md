# Integrations Plan — Australia & United States

**Purpose**: Tactical build plan for QuillCV's two primary markets. Concrete endpoints, sample payloads, coverage estimates, and prioritized work.

**Scope**: Job discovery, application tracking, enrichment — AU and US only. All other regions deferred.

**Related**: See `job-search-integrations.md` for the global catalog.

**Last updated**: 2026-04-19

---

## Table of Contents

1. [Market reality for AU & US](#1-market-reality)
2. [Coverage strategy: the three-layer stack](#2-coverage-strategy)
3. [Layer 1 — Legal APIs (Adzuna, USAJobs, TheMuse)](#3-layer-1--legal-apis)
4. [Layer 2 — ATS public endpoints (Greenhouse, Lever, Ashby, Workable)](#4-layer-2--ats-public-endpoints)
5. [Layer 3 — Browser extension (LinkedIn, Seek, Indeed)](#5-layer-3--browser-extension)
6. [Application tracking — Gmail + Calendar](#6-application-tracking)
7. [AU-specific playbook](#7-au-specific-playbook)
8. [US-specific playbook](#8-us-specific-playbook)
9. [Technical architecture](#9-technical-architecture)
10. [Build order (10 weeks)](#10-build-order)
11. [Cost model](#11-cost-model)
12. [Success metrics](#12-success-metrics)

---

## 1. Market reality

### Australia
| Board | Market share (est.) | API? | Our access |
|---|---|---|---|
| **Seek** | ~55% | ❌ No candidate API | Extension only |
| **LinkedIn Jobs** | ~25% | ❌ | Extension only |
| **Indeed AU** | ~10% | ❌ (API deprecated 2023) | Extension only |
| **Jora** | ~5% (Seek-owned) | ❌ | Skip — duplicates Seek |
| **Company career pages** | ~5% | ✅ (ATS endpoints) | **Direct API** |

**Reality check**: Seek + LinkedIn own ~80% of AU listings. Neither has a public API. Extension is non-negotiable for this market.

### United States
| Board | Market share (est.) | API? | Our access |
|---|---|---|---|
| **LinkedIn Jobs** | ~35% | ❌ | Extension only |
| **Indeed** | ~30% | ❌ (Publisher API killed 2023) | Extension only |
| **Company career pages** | ~15% | ✅ Mostly ATS-based | **Direct API** |
| **ZipRecruiter** | ~8% | ❌ (employer-side only) | Extension only |
| **Glassdoor** | ~5% (Indeed-owned) | ❌ | Skip — duplicates Indeed |
| **Wellfound / AngelList** | ~2% (startups) | ❌ (API removed 2022) | Extension only |
| **USAJobs** | ~3% federal | ✅ Free | **Direct API** |
| **Specialty** (Dice, HN, Otta) | ~2% | Mixed | **Mixed** |

**Reality check**: LinkedIn + Indeed own ~65%. Company career pages are the biggest under-indexed opportunity — thousands use Greenhouse/Lever/Ashby with **public JSON endpoints**.

### Bottom line

Free APIs alone cover **<15% of listings** in AU and **<25% in US**. The ATS direct layer and the browser extension are what make QuillCV competitive. **All three layers are required**.

---

## 2. Coverage strategy

Three layers, each unlocking a different share of the market. Each layer can ship independently.

```
┌─────────────────────────────────────────────────────────────┐
│ LAYER 3 — Browser Extension (user-initiated)                │
│ Unlocks: LinkedIn, Seek, Indeed, Wellfound, any page         │
│ Share: 80%+ of listings; hardest to build; highest retention │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ LAYER 2 — ATS Public Endpoints (server-side polling)        │
│ Unlocks: Greenhouse, Lever, Ashby, Workable, SmartRecruiters │
│ Share: ~15% of listings; medium build; high quality signal   │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ LAYER 1 — Legal Aggregator APIs (server-side)               │
│ Unlocks: Adzuna, USAJobs, TheMuse, HN Who's Hiring          │
│ Share: ~5–10% unique coverage; easiest to build              │
└─────────────────────────────────────────────────────────────┘
```

**Build order**: Layer 1 → Layer 2 → Layer 3. Layer 1 proves matching quality with minimal complexity; Layer 2 adds depth; Layer 3 unlocks the dominant boards.

---

## 3. Layer 1 — Legal APIs

### Adzuna (primary for both regions)

**Endpoint**: `https://api.adzuna.com/v1/api/jobs/{country}/search/{page}`
- `{country}`: `au` or `us`
- Free tier: 1,000 calls/month per account
- Paid: $0.02/call, pay-as-you-go

**Signup**: https://developer.adzuna.com — register app, get `app_id` + `app_key`

**Sample request**:
```
GET https://api.adzuna.com/v1/api/jobs/au/search/1
  ?app_id={APP_ID}
  &app_key={APP_KEY}
  &results_per_page=50
  &what=senior+rails+engineer
  &where=sydney
  &distance=20
  &salary_min=120000
  &sort_by=date
```

**Sample response shape**:
```json
{
  "count": 1247,
  "results": [
    {
      "id": "4829301821",
      "title": "Senior Rails Engineer",
      "company": { "display_name": "Canva" },
      "location": { "area": ["Australia", "New South Wales", "Sydney"] },
      "salary_min": 150000, "salary_max": 190000,
      "description": "We're looking for...",
      "redirect_url": "https://api.adzuna.com/v1/api/jobs/redirect/...",
      "created": "2026-04-17T09:22:00Z",
      "category": { "tag": "it-jobs" }
    }
  ]
}
```

**Strengths**: Salary data present ~60% of listings, clean taxonomy, historical data.
**Weaknesses**: Aggregates from many sources — some stale/duplicate listings; no direct apply URL (goes through their redirect).

**Usage pattern**:
- Daily batch: fetch all new listings matching user's saved searches
- On-demand: user types query → 1 call
- Dedup against Layer 2 by normalizing company + title + created date

### USAJobs (US only)

**Endpoint**: `https://data.usajobs.gov/api/search`
- Free, no key required (just a User-Agent header with your email)
- Covers ~40,000 active US federal positions

**Sample request**:
```
GET https://data.usajobs.gov/api/search
  ?Keyword=software+engineer
  &LocationName=Washington,+DC
  &ResultsPerPage=50
Headers:
  Host: data.usajobs.gov
  User-Agent: daniel@2rk.co
  Authorization-Key: {API_KEY}  # from usajobs.gov/Developer
```

**Use case**: Users targeting GS-level roles, security-cleared work, or stable-employer angle. Small slice but zero competition — most CV tools ignore federal.

### TheMuse (US + remote)

**Endpoint**: `https://www.themuse.com/api/public/jobs`
- Free, rate-limited (~500/hour)

**Sample request**:
```
GET https://www.themuse.com/api/public/jobs
  ?category=Engineering
  &level=Senior+Level
  &location=New+York,+NY
  &page=0
```

**Strengths**: Curated — lower volume, higher quality. Company profiles included (culture, values) → useful for tailoring cover letters.
**Best for**: Mid-senior roles at mid-sized US companies.

### Hacker News "Who's Hiring" (US-heavy, global, senior tech)

**Endpoint**: `https://hn.algolia.com/api/v1/search`

Monthly threads at `https://news.ycombinator.com/submitted?id=whoishiring`. Parse comments where:
- Top-level comment from a user at a company
- First line usually: `Company | Role | Location | Remote/Onsite | Comp`

**Sample**:
```
GET https://hn.algolia.com/api/v1/search
  ?query=whoishiring
  &tags=story
  &hitsPerPage=5
```

Then for each thread ID:
```
GET https://hn.algolia.com/api/v1/items/{storyId}
```

**Strengths**: Where senior devs actually look. Salary almost always disclosed. Remote-friendly.
**Build**: A monthly scraper that runs on the 1st of each month.

### Summary — Layer 1

| API | Region | Free tier | Est. unique coverage |
|---|---|---|---|
| Adzuna AU | AU | 1k/mo | ~40k active listings |
| Adzuna US | US | 1k/mo | ~300k active listings |
| USAJobs | US | Unlimited | ~40k |
| TheMuse | US | 500/hr | ~5k curated |
| HN Who's Hiring | Both | Free | ~500/mo (high quality) |

**Total build effort**: ~1 week for all four. Ship as Layer 1 MVP.

---

## 4. Layer 2 — ATS public endpoints

Thousands of companies host careers at public JSON endpoints. No scraping — these are documented partner APIs.

### Greenhouse (biggest single slice in both AU and US)

**Pattern**: `https://boards-api.greenhouse.io/v1/boards/{company}/jobs`

**Sample**: `https://boards-api.greenhouse.io/v1/boards/airbnb/jobs?content=true`

**Known AU/US companies on Greenhouse** (partial):
- **AU**: Canva, Atlassian, Culture Amp, SafetyCulture, Linktree, Deputy
- **US**: Airbnb, Stripe, DoorDash, Instacart, Reddit, Robinhood, Coinbase, Figma, Notion, Discord, Webflow, 1Password, Vercel, Cloudflare

**Response shape**:
```json
{
  "jobs": [
    {
      "id": 4521829,
      "title": "Staff Software Engineer, Payments",
      "location": { "name": "Sydney, Australia" },
      "departments": [{ "name": "Engineering" }],
      "offices": [{ "name": "Sydney" }],
      "updated_at": "2026-04-15T10:00:00Z",
      "absolute_url": "https://boards.greenhouse.io/canva/jobs/4521829",
      "content": "<p>We're looking for...</p>"
    }
  ],
  "meta": { "total": 47 }
}
```

**Coverage**: ~4,000 companies globally, heavily skewed to US tech + Australian scale-ups.

### Lever

**Pattern**: `https://api.lever.co/v0/postings/{company}?mode=json`

**Known AU/US companies on Lever**:
- **AU**: Employment Hero, Go1, Deputy (some orgs)
- **US**: Netflix (historical), Shopify alumni companies, many YC cohort startups

**Sample**: `https://api.lever.co/v0/postings/netflix?mode=json`

**Coverage**: ~2,000 companies globally.

### Ashby (fast-growing YC-backed)

**Pattern**: `https://api.ashbyhq.com/posting-api/job-board/{company}`

**Known on Ashby**:
- **US**: Linear, Ramp, Mercury, Posthog, Vanta, Modal, Supabase, Retool
- **AU**: Smaller footprint, growing

**Sample**: `https://api.ashbyhq.com/posting-api/job-board/linear`

**Why it matters**: Ashby is the ATS of choice for well-funded 2023–2026 startups. High-quality roles, often remote-friendly with good comp.

### Workable

**Pattern**: `https://apply.workable.com/api/v3/accounts/{company}/jobs`

**Coverage**: ~20,000 SMBs globally — less famous names but huge volume.

### SmartRecruiters

**Pattern**: `https://api.smartrecruiters.com/v1/companies/{company}/postings`

**Coverage**: Enterprise-heavy. Visa, Bosch, Ikea, McDonald's, etc.

### Rippling (newer entrant)

**Pattern**: Per-tenant subdomain, static HTML → parse carefully.

### Workday (important but hard)

**Reality**: No public API. Each Workday instance is at `{company}.wd1.myworkdayjobs.com/en-US/{careers-site}`. Pages are JS-rendered. Requires headless browser to scrape — **only do this via the user's browser extension**, never server-side.

**Known Workday users**:
- **AU**: Commonwealth Bank, Westpac, Telstra, Woolworths, Qantas, BHP
- **US**: Walmart, Target, Bank of America, Accenture, Deloitte, Salesforce

**Strategy**: Skip Workday in Layer 2. Handle via extension in Layer 3.

### The "company directory" problem

To use Layer 2, QuillCV needs to know *which ATS each company uses*. Solutions:

1. **Seed list** — maintain a curated JSON of ~500 AU + 2,000 US companies with their ATS → endpoint mapping. Manual but high-quality.
2. **ATS detection** — when user enters a company name, resolve its career page, inspect DOM/headers for ATS signatures (Greenhouse uses `boards.greenhouse.io`, Lever uses `jobs.lever.co`, etc.).
3. **BuiltWith API** — queries a company domain, returns tech stack including ATS. Free tier available.

**Recommendation**: Start with a curated seed list of 500 high-signal AU/US companies. Add ATS detection later.

### Summary — Layer 2

| ATS | Est. AU companies | Est. US companies | Endpoint |
|---|---|---|---|
| Greenhouse | ~80 | ~2,500 | `boards-api.greenhouse.io/v1/boards/{co}/jobs` |
| Lever | ~30 | ~1,200 | `api.lever.co/v0/postings/{co}` |
| Ashby | ~15 | ~400 | `api.ashbyhq.com/posting-api/job-board/{co}` |
| Workable | ~200 | ~8,000 | `apply.workable.com/api/v3/accounts/{co}/jobs` |
| SmartRecruiters | ~50 | ~800 | `api.smartrecruiters.com/v1/companies/{co}/postings` |
| **Total** | ~375 | ~13,000 | |

**Build effort**: ~2 weeks including seed list curation.

---

## 5. Layer 3 — Browser extension

This is the unlock for LinkedIn, Seek, Indeed, Wellfound, and any company career page without a supported ATS (especially Workday).

### Architecture

**Tech**: Manifest V3 Chrome extension, TypeScript, Vite build. Works in Chrome, Edge, Brave. Firefox compatible with minor manifest tweaks.

**Components**:
- **Content scripts** — run on job board domains, extract structured data from DOM
- **Background service worker** — sync captures to QuillCV backend
- **Popup UI** — logged-in state, quick actions
- **Options page** — profile, saved searches

### Site-specific parsers

Each board needs a parser that extracts `{ title, company, location, description, url, salary?, posted_date? }` from its DOM. Selectors break when boards redesign — plan for monthly maintenance.

| Site | Parser complexity | DOM stability |
|---|---|---|
| **Seek (AU)** | Medium — good semantic HTML | Stable, redesign ~every 18 months |
| **LinkedIn Jobs** | High — aggressive A/B testing, lazy-loaded | Unstable, expect monthly tweaks |
| **Indeed** | Medium — has JSON-LD schema | Moderate |
| **Wellfound** | Low — React app, easy to hook | Moderate |
| **Workday instances** | Low-medium — consistent across tenants | Stable |
| **Greenhouse / Lever / Ashby hosted pages** | Trivial — already have JSON endpoint, extension just detects "you're on X job page" | Trivial |
| **Company custom pages** | Fallback: JSON-LD `JobPosting` schema (many sites include it) | Varies |

### Core features (MVP)

1. **"Save job" button** — floats on supported sites, captures → QuillCV tracker
2. **"Tailor CV for this job" button** — sends JD to backend, opens QuillCV editor in new tab
3. **LinkedIn profile exporter** — when user visits their own profile, offer "import into QuillCV" (single-click → parses profile → pre-fills user's CV)
4. **Application autofill** — fills `firstName`, `lastName`, `email`, `phone`, `linkedin`, `resume` fields with saved profile. User always clicks Submit.
5. **Status reminders** — when user visits a company's site where they previously applied, toast: "You applied here 14 days ago — follow up?"

### What it must NOT do

- Submit applications without user click
- Scrape entire boards (only the page the user is actively viewing)
- Store raw DOM on QuillCV servers (keep only structured extracted fields)
- Run on non-job pages (scope by `host_permissions` to supported sites)

### Privacy & trust

- Extension lists all supported sites transparently in the Chrome Web Store description
- OAuth/session token stored locally only
- No "analytics" that track general browsing — only events on supported sites
- Open-source the content scripts so security-conscious users can audit

### Build effort

~3 weeks for MVP covering Seek + LinkedIn + Indeed + Greenhouse-hosted pages. Each additional site ~2 days.

---

## 6. Application tracking

Tracking is where QuillCV transitions from CV generator to **job-search OS**. Gmail integration is the moat.

### Gmail API (highest ROI integration)

**OAuth scope**: `https://www.googleapis.com/auth/gmail.readonly` (narrowest scope that reads messages). Justification copy in consent screen: *"QuillCV reads only career-related emails to update your application tracker. We never send, delete, or modify your messages."*

**Query filter (server-side)**:
```
after:2026/01/01
(from:(greenhouse.io OR lever.co OR workable.com OR ashbyhq.com OR smartrecruiters.com)
 OR subject:(application OR interview OR "thank you for applying" OR "regret to inform" OR "next steps"))
```

**Classification patterns** (keep simple — LLM for edge cases, regex for confidence):

| Status | High-confidence regex | LLM fallback |
|---|---|---|
| **Applied (confirmed)** | `thank you for (your application\|applying)` | Email confirms application receipt |
| **Rejected** | `(regret to inform\|decided to move forward with other\|unfortunately.*not)` | Rejection language |
| **Interview invite** | `(schedule an interview\|would like to invite you\|set up a (call\|chat))` | Interview request |
| **Offer** | `(pleased to offer\|formal offer\|offer letter)` | Offer extended |
| **Recruiter outreach** | Sender is a recruiter, no prior application | Cold recruiter contact |

**Dedup strategy**: Extract company + role from email (subject line + signature), match against existing tracker rows within 60 days. If match, update status; if no match, create new row with status=`applied (detected)`.

**Edge cases Claude handles well**:
- Auto-responders vs. genuine applied confirmations
- Spanish/Portuguese/French emails (US users with Hispanic names, AU users from NZ/UK companies)
- Multi-stage: "your onsite is scheduled" ≠ new interview, it's a stage 2

**Build effort**: 2 weeks including OAuth flow, polling worker, classification, dedup.

### Google Calendar

**OAuth scope**: `https://www.googleapis.com/auth/calendar.events` (can create events QuillCV creates; cannot modify user's other events).

**Use**:
- Auto-create event when interview invite detected: "Interview with {Company} — {Role}"
- Attach QuillCV context: CV used, cover letter, company intel, likely questions
- 1-hour reminder includes: "Review your answer to 'Tell me about yourself' — rehearsed 2 days ago"

### Outlook / Microsoft Graph

Same patterns, via Graph API. Share 30% of US users, 15% of AU. Ship after Gmail proves out.

### IMAP fallback

For Yahoo, ProtonMail, self-hosted: offer manual forwarding address `track+{userId}@parse.quillcv.com` — user forwards relevant emails, Mailgun/Postmark inbound webhooks → same classifier.

### In-app tracker states

```
  Saved ──→ Applied ──→ Screening ──→ Interview(s) ──→ Offer ──→ Accepted/Declined
                │                                        │
                └──→ Rejected ←─────────────────────────┘
                      (from any state)
                      
  Ghosted (no response 21 days after applied)
```

Auto-advance based on Gmail signals. User can override.

---

## 7. AU-specific playbook

### The Seek problem

Seek is ~55% of the AU market and has zero API access. Options:

1. **Official Seek API** — exists but is **employer/ATS-only**. Applying as a B2C tool is a multi-year sales cycle with no guarantee. Skip.
2. **Scrape server-side** — bannable. Australia has weak CFAA-equivalent protection but Seek's ToS is enforced with IP bans. Risk > reward.
3. **Browser extension** — user visits Seek, extension captures. Legal, resilient. **This is the only path.**

**Recommendation**: Extension handles Seek. In marketing, position as "one-click save from Seek" — AU users immediately understand.

### AU government & specialty sources

| Source | API | Value |
|---|---|---|
| **Workforce Australia** (jobactive successor) | ❌ Limited | Low — mostly lower-skilled; skip |
| **APS Jobs** (Australian Public Service) | ❌ RSS feed | Niche but easy |
| **Defence Jobs** | ❌ | Niche |
| **EthicalJobs.com.au** | ❌ | NFP/purpose — worth scraping monthly |
| **GradConnection** | ❌ | Graduate only |
| **Hatch** | ❌ | Entry-level Sydney/Melbourne |
| **Escape the City AU** | ❌ | Career-change niche |

### AU market quirks that affect CV tailoring

- **Visa sponsorship flag** — critical for ~30% of users. QuillCV should let user filter listings by "sponsorship available" (parseable from JD).
- **Federal vs. state government** — different CV formats expected. `cv-format-sources.md` should cover this.
- **Melbourne / Sydney split** — tech = Sydney, finance = Melbourne traditionally (blurring now).
- **Contract rates common** — display daily rate next to annual where available.
- **Superannuation** sometimes included, sometimes separate — normalize in display.

### AU CV conventions (affects integration with ATS)

- 2–3 pages is normal (not the US 1-page convention)
- No photo, no date of birth, no marital status
- References: "Available on request" is standard
- Date format: DD/MM/YYYY (matters for ATS parsing validation)

### AU company seed list (Layer 2 priority targets)

High-Greenhouse density:
- Canva, Atlassian, Culture Amp, SafetyCulture, Linktree, Deputy, Go1, Employment Hero, Rokt, Airwallex, Immutable, Zeller, Athena, Up, Judo Bank

High-Workday density (→ extension required):
- Commonwealth Bank, Westpac, ANZ, NAB, Telstra, Optus, Qantas, Woolworths, Coles, BHP, Rio Tinto

High-custom-ATS density:
- Government (APS), Universities (Uni of Melbourne, Sydney, ANU), Hospitals (major health networks)

---

## 8. US-specific playbook

### The LinkedIn + Indeed duopoly

~65% of the US market, neither with an API.

**Strategy same as AU**: Extension captures what the user views. Don't fight the ToS.

### US government sources

| Source | API | Value |
|---|---|---|
| **USAJobs.gov** | ✅ Free, documented | Cover in Layer 1 |
| **State job portals** | ❌ Per-state, 50 different sites | Skip — low ROI |
| **Federal News Network jobs** | ❌ | Skip |

### US specialty sources worth integrating

| Source | API | Priority |
|---|---|---|
| **HN Who's Hiring** | ✅ via Algolia | **High** — senior dev gold |
| **Wellfound / AngelList** | ❌ (extension only) | **Medium** — startup users |
| **Otta / Welcome to the Jungle** | ❌ | Low — curated, small volume |
| **Dice** | Partner API | Medium for tech-only users |
| **FlexJobs** | ❌ (paywall) | Skip |
| **Remote OK / Remotive / WWR** | ✅ Free JSON | **Medium** — remote users |
| **Himalayas** | ✅ Free JSON | **Medium** — remote |
| **4 Day Week** | ❌ (HTML) | Low — niche |
| **Power to Fly** | ❌ | Medium — diversity angle |
| **Underdog.io** | ❌ (invite-only) | Skip |
| **Triplebyte / Karat** | N/A (assessments, not listings) | Skip |

### US market quirks that affect CV tailoring

- **1-page resume** is expected for most roles; 2 pages only for senior/exec
- **No photo**, no age, no marital status (EEO compliance)
- **Keyword-stuffing** is more normalized than in AU (ATS-gaming culture)
- **Dollar ranges** now required by law in many states (CA, NY, CO, WA) — parse and surface
- **H1B / visa status** — many US users need this filter
- **Security clearance** (SECRET, TS/SCI) — federal and defense contractor roles
- **Cover letter optional** for tech; often required for finance, consulting, non-profit

### US company seed list (Layer 2 priority targets)

**Greenhouse heavyweights**:
- Airbnb, Stripe, DoorDash, Instacart, Reddit, Robinhood, Coinbase, Figma, Notion, Discord, Webflow, 1Password, Vercel, Cloudflare, Datadog, Snowflake, Rippling, Gusto, Plaid, Chime

**Lever**:
- Shopify, many YC cohort (Airtable alumni, Mixpanel, Segment's descendants)

**Ashby (fast-growing)**:
- Linear, Ramp, Mercury, Posthog, Vanta, Modal, Supabase, Retool, Clerk, Cursor (Anysphere), Cognition

**Workable**:
- Long tail of SMBs — aggregate via ATS endpoint

**Workday (extension required)**:
- Walmart, Target, Amazon, Meta (some divisions), Apple, Salesforce, Oracle, Accenture, Deloitte, McKinsey, Bain, BCG, JP Morgan, Goldman Sachs, Bank of America, Wells Fargo

---

## 9. Technical architecture

### Backend additions

```
app/
├── services/
│   ├── discovery/
│   │   ├── adzuna.py              # Layer 1
│   │   ├── usajobs.py             # Layer 1 (US only)
│   │   ├── themuse.py             # Layer 1 (US)
│   │   ├── hn_whoishiring.py      # Layer 1 (monthly)
│   │   ├── greenhouse.py          # Layer 2
│   │   ├── lever.py               # Layer 2
│   │   ├── ashby.py               # Layer 2
│   │   ├── workable.py            # Layer 2
│   │   ├── smartrecruiters.py     # Layer 2
│   │   └── aggregator.py          # Dedup + match scoring
│   ├── tracking/
│   │   ├── gmail_oauth.py
│   │   ├── gmail_classifier.py
│   │   ├── calendar_sync.py
│   │   └── status_machine.py
│   └── company/
│       ├── seed_list.py           # AU + US curated seed
│       ├── ats_detector.py
│       └── enrichment.py          # BuiltWith, Hunter (later)
├── workers/
│   ├── discovery_poller.py        # Daily: Layer 1 + 2
│   ├── gmail_poller.py            # Every 15 min per active user
│   └── followup_reminder.py       # Daily: find stale applications
└── models/
    ├── job_listing.py
    ├── application.py
    ├── company.py
    └── saved_search.py
```

### Data model sketch

```
JobListing
  id, source (adzuna/greenhouse/..), source_id, company_id, title,
  location, country, remote?, salary_min/max/currency, description,
  apply_url, posted_at, expires_at, raw (json)

Company
  id, name, canonical_domain, ats_provider, ats_slug, size_estimate,
  funding_stage, tech_stack (json), hq_country

Application
  id, user_id, job_listing_id, status, status_history (json),
  applied_at, resume_version_id, cover_letter_version_id,
  gmail_thread_ids (array), next_followup_at

SavedSearch
  id, user_id, query, location, country, salary_min, filters (json),
  notification_frequency
```

### Dedup logic

Multiple layers will surface the same role. Fingerprint each listing:
```
fingerprint = sha1(
  normalize(company_name) + "|" +
  normalize(title) + "|" +
  first_200_chars(description)
)
```

When the same fingerprint arrives from Layer 2 (Greenhouse direct) and Layer 1 (Adzuna redirect), prefer Layer 2 — cleaner data, direct apply URL.

### Match scoring

Given a user's CV + saved search + a new listing:
```
score = 
  0.40 * cosine_sim(cv_skills_embedding, jd_skills_embedding) +
  0.20 * location_match +
  0.15 * salary_match +
  0.15 * seniority_match +
  0.10 * recency
```

Surface jobs with `score > 0.75` as daily recommendations.

---

## 10. Build order

### Phase 1 — Layer 1 MVP (Week 1–2)
- [ ] Adzuna integration (AU + US)
- [ ] USAJobs integration
- [ ] TheMuse integration
- [ ] HN Who's Hiring monthly ingester
- [ ] `job_listing` + `saved_search` models
- [ ] Daily poller worker
- [ ] Simple "Jobs for you" feed in-app
- [ ] Match scoring v1 (embedding similarity only)

**Ships**: User pastes a CV, sees 20+ matched AU/US jobs within 1 minute.

### Phase 2 — Tracker foundation (Week 3–4)
- [ ] `application` model + status machine
- [ ] Manual "I applied" flow (user pastes URL or adds from feed)
- [ ] Tracker UI (pipeline view)
- [ ] Follow-up reminder worker
- [ ] CSV export

**Ships**: User can track applications manually.

### Phase 3 — Layer 2 ATS direct (Week 5–6)
- [ ] Greenhouse, Lever, Ashby, Workable, SmartRecruiters ingesters
- [ ] Company seed list (500 AU + 2,000 US)
- [ ] Dedup logic
- [ ] Company model with ATS detection

**Ships**: 10x increase in matched listings per user; direct apply URLs.

### Phase 4 — Gmail integration (Week 7–8)
- [ ] Gmail OAuth flow
- [ ] Email classifier (regex + Claude fallback)
- [ ] Auto-status updates
- [ ] Dedup against existing tracker rows
- [ ] Privacy policy + consent copy

**Ships**: Tracker auto-updates. The retention unlock.

### Phase 5 — Browser extension MVP (Week 9–10)
- [ ] Manifest V3 skeleton
- [ ] Parsers: Seek, LinkedIn, Indeed, Greenhouse-hosted, Lever-hosted
- [ ] "Save job" + "Tailor CV" buttons
- [ ] Autofill profile fields
- [ ] Chrome Web Store submission

**Ships**: Dominant boards captured. Full loop complete.

### Deferred (post-MVP)
- Outlook Graph API
- Calendar auto-events
- Interview prep mode
- Enrichment (BuiltWith, Hunter)
- Workday scraper in extension
- Wellfound parser in extension

---

## 11. Cost model

### External API costs (per 1,000 monthly active users)

Assume 1k MAU, each doing 20 searches/month + 30 tracked applications + Gmail poll every 15 min.

| Service | Usage | Cost |
|---|---|---|
| **Adzuna** | 20k searches × 2 pages = 40k calls/mo. First 1k free, rest $0.02 | **$780** |
| **USAJobs** | 5k calls/mo | **$0** |
| **TheMuse** | 5k calls/mo | **$0** |
| **HN API** | ~30 calls/mo | **$0** |
| **ATS endpoints** (Greenhouse et al.) | ~50k calls/mo (polling 2k companies daily) | **$0** |
| **Gmail API** | 1k users × 96 polls/day × 30 days = 2.9M calls. Free up to 1B/day. | **$0** |
| **Claude API** (classifier fallback + CV gen) | ~30k classifier calls + 500 gen calls | **~$400** |
| **Embedding API** (match scoring) | 1M embeddings/month | **~$100** |
| **Infra** (worker compute, DB, R2) | — | **~$200** |
| **Total** | | **~$1,480/mo** |

**Unit economics**: At $9.99 alpha → gross margin break-even ~150 MAU. Post-alpha $15–29/mo tier → healthy margins.

### Development cost

- 10 weeks × 1 FTE = the dominant cost
- Ongoing: ~1 day/week on extension selector maintenance (boards redesign)

---

## 12. Success metrics

### Discovery layer
- **Coverage**: ≥70% of jobs a user clicks on (anywhere) are already in QuillCV's feed
- **Match precision**: User marks ≥40% of top-20 matches as "interested"
- **Freshness**: ≥80% of listings shown are <7 days old

### Tracker layer
- **Gmail auto-classification accuracy**: ≥92% on held-out eval set
- **Dedup accuracy**: <3% duplicate tracker rows per user
- **Follow-up adoption**: ≥60% of users act on at least one follow-up reminder per month

### Extension
- **Install rate**: ≥40% of active QuillCV users install extension within 30 days
- **Capture rate**: Extension-installed users save ≥3× more jobs than non-extension users
- **Retention delta**: Extension users have ≥2× 90-day retention

### North-star
- **Interview rate**: QuillCV-tailored CVs → interview invite at ≥2× the rate of user's pre-QuillCV baseline (self-reported)
- **Offer rate**: ≥15% of users report receiving an offer within 90 days of signup

---

## Appendix A — Quick links

### API signups
- Adzuna: https://developer.adzuna.com
- USAJobs: https://developer.usajobs.gov
- TheMuse: https://www.themuse.com/developers/api/v2
- Algolia HN: https://hn.algolia.com/api
- Google OAuth / Gmail: https://console.cloud.google.com
- Microsoft Graph: https://portal.azure.com

### ATS docs
- Greenhouse: https://developers.greenhouse.io/job-board.html
- Lever: https://help.lever.co/hc/en-us/articles/360042988632
- Ashby: https://developers.ashbyhq.com/reference/public-job-board-api
- Workable: https://workable.readme.io/reference
- SmartRecruiters: https://developers.smartrecruiters.com/reference/postingdetails

### Chrome Web Store
- Developer dashboard: https://chrome.google.com/webstore/devconsole
- Manifest V3 migration: https://developer.chrome.com/docs/extensions/migrating
