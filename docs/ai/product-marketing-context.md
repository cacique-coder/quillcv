# Product Marketing Context

*Last updated: 2026-05-04*

---

## Product Overview

**One-liner:** ATS-optimized CV builder that tailors your CV to a job description with region-specific formatting for 12 countries.

**What it does:** QuillCV reads a job description and your existing CV, then rewrites your CV to pass Applicant Tracking Systems — matching keywords, applying the correct country conventions, and still sounding like you wrote it. It also includes ATS scoring, quality review with fix suggestions, and a manual CV builder with 47 templates.

**Product category:** CV builder / resume builder (how customers search); sits adjacent to "AI resume writer" and "ATS optimizer"

**Product type:** SaaS (credit-based, not subscription)

**Business model:** One-time credit packs. Alpha: $9.99 for 15 CVs. Post-alpha: Starter $15/15cr, Standard $29/35cr, Pro $49/65cr. Top-up: +10 credits for $4.99. Free tier: manual builder only (no AI), all templates, PDF download. Credits never expire. No auto-renew.

---

## Target Audience

**Primary markets:** Australia, US, UK, Canada, New Zealand, Germany, France, Netherlands, India, Brazil, UAE, Japan

**Decision-makers:** Individual job seekers (B2C); no enterprise or HR buyer

**Primary use case:** Tailoring an existing CV to a specific job description so it passes ATS filters and gets shortlisted

**Jobs to be done:**
- "Help me pass the ATS so a human even sees my CV"
- "Tell me what keywords I'm missing and add them for me"
- "Format my CV correctly for the country I'm applying in — I don't know the local conventions"
- "Let me spin up a tailored CV per job posting in under 3 minutes without starting from scratch"

**Use cases:**
- International applicant relocating (e.g. Bangalore → Berlin, AU → US)
- Career changer reframing experience for a new role or industry
- Tech professional tailoring per job posting (frameworks, languages, certifications)
- Active job seeker generating many applications quickly
- Returning applicant who hasn't job-hunted in years

---

## Personas

| Persona | Goal | Primary Pain | Value we promise |
|---------|------|--------------|------------------|
| **International applicant** (Maya, 31, Berlin → Sydney) | A CV that looks right to AU recruiters without hiring a local coach | "I don't know what Australians expect on a CV" | Correct country format baked in — photo rules, DOB, references, paper size, section order |
| **Career changer** (Rafael, 38, ops → tech PM) | Reframe 10 years of ops as transferable to PM | "Recruiters skim and miss the relevant parts" | AI rewrites achievements in target-role language |
| **Tech professional** (Jin, 27, senior eng) | Tailor fast per job posting, not one generic CV | "I have one CV and keep emailing the wrong version" | AI extraction of frameworks/languages/certs from JD, woven into CV |
| **Returning applicant** (any, 2nd+ search) | New CV for a new job in under 3 minutes | "It feels like I'm starting over every time" | Vault stores profile; regenerate per job in minutes |

---

## Problems & Pain Points

**Core problem:** Job seekers send out CVs tailored to nobody and wonder why they get ghosted. ATS filters reject 75%+ of applications before a human sees them. Most CV builders produce a nice-looking document that still fails the ATS scan.

**Why current solutions fall short:**
- Generic builders (Canva, Google Docs) produce pretty CVs with no ATS awareness
- AI tools (ChatGPT, Claude) don't know country conventions, can't score, no ATS pipeline
- Subscription CV builders (Rezi, Teal, Kickresume) charge $15–30/month even when you're not job-hunting
- No competitor handles multi-country formatting — they're all US-only templates
- Most tools take one input (JD or CV) — not both together for tailoring

**What it costs them:**
- Time: hours rewriting the same CV for each application
- Money: $29/mo subscriptions for a tool used 2 weeks per year
- Opportunity: ATS rejection means the human never sees a qualified candidate

**Emotional tension:** Frustration and self-doubt from sending applications into a black hole — "Am I doing something wrong?" Privacy anxiety: "What are these companies doing with my CV data?"

---

## Competitive Landscape

**Direct competitors** (same problem, same solution):
- **Rezi** — Best ATS scoring, but $29/mo subscription, US-only, no multi-country
- **Teal+** — Good ATS + job tracking suite, but $29/mo, US-centric
- **Wobo** — Good ATS optimizer, $24.99/mo, no country support
- **Kickresume** — Cheaper ($8–24/mo) but weak ATS, partial tailoring, no country support

**Secondary competitors** (same problem, different solution):
- **ChatGPT / Claude** — People hack together CV tailoring in chat, but no ATS scoring, no country formats, no structured pipeline
- **Professional CV writers** — Human service, $200–500 per CV, slow, no ATS guarantee

**Indirect competitors** (conflicting approach):
- **"One CV for all jobs"** mindset — biggest competitor; many job seekers still send a single generic CV
- **LinkedIn Easy Apply** — encourages low-effort mass applying without tailoring

**How they fall short for customers:**
- No competitor supports multi-country CV conventions
- No competitor offers credit-based pricing (pay when you need it, not every month)
- No competitor offers zero-knowledge encryption on personal data

---

## Differentiation

**Key differentiators:**
1. **Multi-country format support** — 12 countries with local conventions (photo rules, DOB, references, date formats, page length, section ordering). No competitor offers this.
2. **Zero-knowledge PII encryption** — Personal data encrypted with user's own password. We physically cannot read it. No competitor does this.
3. **Credit-based anti-subscription pricing** — Pay once, use when you need it. Credits never expire.
4. **Combined JD + CV parsing** — Both inputs used together for genuine tailoring. Competitors use one or the other.
5. **Non-English CV generation** — Spanish, Portuguese, Japanese, German, French, Dutch. Competitors are English-only.

**How we do it differently:** Parse both the job description and the user's CV, extract keywords + conventions for the target country, then rewrite — not just a form with fancy fonts.

**Why that's better:** A recruiter in Sydney and a recruiter in Dubai expect completely different CV structures. A Python engineer and a project manager need completely different keyword sets. Generic builders ignore both dimensions.

**Why customers choose us:** International job seekers have no alternative. Credit-based pricing is structurally better for the job search lifecycle (punctuated, not continuous). Privacy-first is increasingly valued.

---

## Objections

| Objection | Response |
|-----------|----------|
| "Will my CV still sound like me?" | "Yes. QuillCV matches your existing voice and only adds keywords when they're truthful to your experience. You can always edit, reject, or regenerate any part of the output." |
| "How is this different from ChatGPT?" | "ChatGPT doesn't know what an ATS scans for, doesn't handle 12 country conventions, and can't score your CV. QuillCV is purpose-built for the job application pipeline." |
| "Is my data actually private?" | "Yes. Your personal details are encrypted with your password — we physically can't read them. Delete your account and everything is gone, no 30-day grace period, no backups." |
| "Why would I pay when ChatGPT is free?" | "You'd spend 30–60 minutes prompting and formatting in ChatGPT what QuillCV produces in 3 minutes, with ATS scoring and country formatting that ChatGPT can't do." |
| "What if I only need one CV?" | "Free tier gives you the manual builder. Buy alpha credits only when you want AI tailoring." |

**Anti-persona:** Someone who applies to 1–2 jobs per decade and has a strong recruiter network. Also: HR professionals and hiring managers (they're the ATS — not the audience).

---

## Switching Dynamics

**Push** (frustrations with current approach):
- Getting ghosted repeatedly despite being qualified
- Spending hours tailoring CVs manually that still fail ATS
- Paying $29/mo for Teal/Rezi when actively job-hunting for only 4–6 weeks
- Not knowing country-specific conventions when relocating

**Pull** (what attracts them to QuillCV):
- "87% ATS match vs 32% before" — concrete before/after proof
- One-time price vs ongoing subscription
- Country-specific formatting handled automatically
- Privacy: encrypted vault, no data sold

**Habit** (what keeps them stuck):
- "I've always used my Word template" — familiar, low effort
- "I'll just use ChatGPT" — already have the tool
- "A recruiter friend said my CV was fine" — social validation of existing approach

**Anxiety** (worries about switching):
- "Will it make my CV sound robotic or keyword-stuffed?"
- "Is this just another SaaS that stores my personal data forever?"
- "What if the AI gets my experience wrong?"
- "How do I know the ATS score is accurate?"

---

## Customer Language

**How they describe the problem:**
- "I've been ghosted 12 times in a row"
- "I don't know what [country] recruiters expect"
- "My CV looks the same as everyone else's"
- "I keep emailing the wrong version of my CV"
- "I spend hours tweaking and never know if it's working"
- "The ATS is filtering me out before a human sees it"

**How they describe the solution:**
- "Same résumé, different country format — three replies in a week" (Priya R., Bangalore → Berlin)
- "It rewrites it to match the job"
- "Passes the bots, still reads like me"

**Words to use:**
- "tailored", "ATS-optimized", "keywords", "pass the filter", "get shortlisted", "country format", "land interviews", "credits", "never expire", "one-time", "your data stays yours"

**Words to avoid:**
- "resume" (use "CV" in non-US markets — AU, UK, EU strongly prefer CV)
- "subscription" (negative framing for us — we're anti-subscription)
- "AI-generated" (implies robotic, not human-sounding — say "AI-tailored" or "AI-rewritten")
- "templates" as the lead value prop (commoditized — lead with tailoring and ATS)

**Glossary:**

| Term | Meaning |
|------|---------|
| ATS | Applicant Tracking System — software recruiters use to filter CVs |
| Generation / credit | One AI tailoring run (JD + CV → tailored CV) |
| Vault | Encrypted personal info store (pre-fills CVs) |
| Country format | Region-specific CV conventions (photo, DOB, references, paper size, etc.) |
| ATS match score | % of job description keywords present in the CV |
| Tailoring | Rewriting a CV to match a specific job description |

---

## Brand Voice

**Tone:** Honest, direct, slightly warm. Not corporate SaaS. Not overly casual. Like a smart friend who builds tools and tells you the truth about pricing.

**Style:** Conversational with moments of editorial restraint. Short sentences. Minimal jargon. Handcrafted details (hand-drawn doodles, editorial typography, paper textures) signal craft over polish.

**Personality:** Trustworthy, transparent, results-focused, quietly confident, anti-dark-patterns

**Signature markers:**
- Plain language about pricing ("No auto-renew. No dark patterns.")
- Direct admissions ("If anything feels off on the payment page, that's a bug — email us.")
- First-person plural, founder-voice ("we built the thing we wish existed")
- Privacy stated simply, not as legalese

---

## Proof Points

**Metrics:**
- 87% ATS match (vs 32% before) — before/after example
- 72% off alpha pricing vs planned post-alpha price
- 12 country formats (no competitor matches this)
- 47 templates
- 15 CVs per alpha pack ($0.67/CV vs $1.25–1.45/CV for competitors)

**Testimonials:**
> "I'd been ghosted twelve times in a row. First QuillCV CV — three replies in a week. Same résumé, different country format." — Priya R. · Bangalore → Berlin · Senior backend

**Value themes:**

| Theme | Proof |
|-------|-------|
| Gets you past the ATS | 32% → 87% ATS match in before/after |
| Right format for your target country | 12 country formats with local conventions |
| Cheaper than subscriptions | $0.67/CV alpha vs $1.25–1.45/CV competitors |
| Privacy-first | Zero-knowledge encryption — we cannot read your data |
| No commitment | Credits never expire, no subscription, refund policy |

---

## Goals

**Business goal:** Sign up the first 100 alpha founders at $9.99, validate product-market fit, then transition to post-alpha credit packs.

**Key conversion actions (in priority order):**
1. Sign up (free, no credit card)
2. Complete onboarding (vault setup)
3. Generate first CV (activation)
4. Purchase alpha credits ($9.99)
5. Refer a friend / leave a testimonial

**Current metrics (alpha stage):**
- Alpha pricing: $9.99/15 credits
- Target: first 100 users
- Free tier available (manual builder, no AI)
- No paid acquisition yet — organic + word of mouth
