# Job Search & Application Tracking Integrations

**Purpose**: Comprehensive catalog of platforms, APIs, and integrations that QuillCV can leverage to help users **find jobs faster** and **land them at a higher rate** — across our 12 target regions (AU, US, UK, CA, NZ, DE, FR, NL, IN, BR, AE, JP).

**Scope**: Discovery, tracking, enrichment, intelligence, and interview prep. Auto-apply is explicitly out of scope (see `business.md` for rationale — legal risk, account bans, ToS violations).

**Last updated**: 2026-04-19

---

## Table of Contents

1. [Strategic framework — how these integrations help users land jobs](#1-strategic-framework)
2. [Job discovery — global aggregator APIs](#2-job-discovery--global-aggregator-apis)
3. [Job discovery — regional boards (per country)](#3-job-discovery--regional-boards)
4. [Job discovery — specialty & niche boards](#4-job-discovery--specialty--niche-boards)
5. [Company ATS direct (Greenhouse, Lever, Workday…)](#5-company-ats-direct)
6. [Application tracking integrations](#6-application-tracking-integrations)
7. [CV enrichment integrations](#7-cv-enrichment-integrations)
8. [Company & role intelligence](#8-company--role-intelligence)
9. [Salary & compensation intelligence](#9-salary--compensation-intelligence)
10. [Interview preparation integrations](#10-interview-preparation-integrations)
11. [Networking & referral signals](#11-networking--referral-signals)
12. [Browser extension — the integration multiplier](#12-browser-extension)
13. [Competitor landscape — what to learn from](#13-competitor-landscape)
14. [Recommended build order](#14-recommended-build-order)
15. [Legal & ToS reference table](#15-legal--tos-reference-table)

---

## 1. Strategic framework

Users land jobs at higher rates when **five things compound**:

| Lever | What QuillCV provides today | Integration opportunity |
|---|---|---|
| **1. Right jobs** | — | Discovery APIs + matching |
| **2. Tailored CV per job** | ✅ Core product | — |
| **3. Application hygiene** (no duplicates, follow-ups sent) | — | Tracker + Gmail parsing |
| **4. Company research** | — | Enrichment APIs |
| **5. Interview prep** | — | LLM-based mock + question banks |

Every integration below maps to one of these five levers. When scoping, ask: *"Does this move the user closer to an offer?"* If not, deprioritize.

---

## 2. Job discovery — global aggregator APIs

These are **legal, documented APIs** that return job listings. Use them to build a match engine: user uploads CV → we score & surface best-fit jobs → user generates tailored CV with one click.

### Tier 1 — build first

| API | Coverage | Free tier | Paid | Fields returned | Notes |
|---|---|---|---|---|---|
| **Adzuna** | 16 countries (AU, US, UK, CA, DE, FR, NL, IN, BR, others) | 1,000 calls/month | From $0.02/call | Title, company, salary, location, description, category | **Best breadth for our 12 regions.** Covers 10 of 12 directly. Clean JSON. |
| **Jooble** | 70+ countries | Free with approval | Custom | Title, company, snippet, location, link | Good AU/EU fill-in. Partner API — apply via email. |
| **TheMuse** | US-heavy, global | Free | — | Job + company profile + culture content | Curated quality, ideal for senior/exec tier. |
| **Arbeitnow** | EU remote | Free, no key | — | Full job data, tags | Great for DE/NL/FR remote. |

### Tier 2 — add when expanding

| API | Coverage | Pricing | Notes |
|---|---|---|---|
| **JSearch** (RapidAPI) | Aggregates LinkedIn, Indeed, Glassdoor, ZipRecruiter | $10–$50/mo | Scrapes upstream — use as fallback, not primary. Upstream ToS risk flows downstream. |
| **Reed** | UK only | Free | If UK becomes a top-3 region. |
| **USAJobs** | US federal | Free, no key | Niche but zero-cost. |
| **Remotive** | Remote-only, global | Free | Small dataset, high quality. |
| **Remote OK** | Remote-only, global | Free JSON | Dev-heavy. |
| **WeWorkRemotely** | Remote-only | RSS/JSON | Small but premium. |
| **Findwork.dev** | Dev-focused global | Free | Good supplement for tech users. |
| **GitHub Jobs** | ❌ Discontinued 2021 | — | Do not plan around it. |
| **Stack Overflow Jobs** | ❌ Discontinued 2022 | — | Do not plan around it. |

### Tier 3 — regional specialists (covered in §3)

---

## 3. Job discovery — regional boards

Per-country boards matter because local candidates use them, and they often have listings that never reach the global aggregators. For each of our 12 regions:

### Australia (AU)
| Board | API? | Notes |
|---|---|---|
| **Seek** | No candidate API (Seek API is for ATS vendors only) | Dominant board — scrape via browser extension only |
| **Jora** | ❌ | Owned by Seek — same coverage |
| **LinkedIn Jobs** | ❌ (see §11) | High-value; capture via extension |
| **Adzuna AU** | ✅ | Primary API |
| **Indeed AU** | ❌ (API deprecated) | — |
| **Workforce Australia** | ❌ | Government portal, limited |

### United States (US)
| Board | API? | Notes |
|---|---|---|
| **Indeed** | ❌ (Publisher API shut down 2023) | Dominant but closed |
| **LinkedIn** | ❌ | — |
| **ZipRecruiter** | ❌ (employer-side only) | — |
| **Glassdoor** | ❌ (owned by Indeed) | — |
| **Monster** | ❌ | Declining relevance |
| **CareerBuilder** | ❌ | Declining |
| **Adzuna US** | ✅ | Primary |
| **USAJobs** | ✅ Free | Federal only |
| **TheMuse** | ✅ | Curated |
| **Dice** | Partner API | Tech-only |
| **AngelList / Wellfound** | ❌ (removed API 2022) | Startup-heavy; capture via extension |
| **BuiltIn** | ❌ | City-based tech boards |

### United Kingdom (UK)
| Board | API? | Notes |
|---|---|---|
| **Reed** | ✅ Free | Use as primary UK source |
| **Totaljobs** | ❌ | — |
| **CV-Library** | Partner API | Worth applying |
| **Indeed UK** | ❌ | — |
| **LinkedIn** | ❌ | — |
| **Adzuna UK** | ✅ | Primary fallback |
| **Gov.uk Find a job** | ❌ | — |

### Canada (CA)
| Board | API? | Notes |
|---|---|---|
| **Job Bank** (Government) | ✅ Open data | Surprisingly comprehensive |
| **Indeed CA** | ❌ | — |
| **LinkedIn** | ❌ | — |
| **Workopolis** | ❌ | Declining |
| **Eluta** | ❌ | Top employer focus |
| **Adzuna CA** | ✅ | Primary |

### New Zealand (NZ)
| Board | API? | Notes |
|---|---|---|
| **Seek NZ** | No candidate API | Dominant — extension only |
| **Trade Me Jobs** | ✅ Partner API (apply) | Worth pursuing |
| **Do.govt.nz** | ❌ | Public sector |
| **MyJobSpace** | ❌ | — |

### Germany (DE)
| Board | API? | Notes |
|---|---|---|
| **StepStone** | ❌ | Dominant paid board |
| **Xing Jobs** | ❌ (Xing API heavily restricted) | Important for DE/AT/CH networking |
| **Indeed DE** | ❌ | — |
| **LinkedIn DE** | ❌ | Growing share |
| **Bundesagentur für Arbeit** | ✅ Free API | Government — excellent free source |
| **Arbeitnow** | ✅ | EU remote focus |
| **Adzuna DE** | ✅ | Primary |
| **kununu** | ❌ | Review platform, not listings |

### France (FR)
| Board | API? | Notes |
|---|---|---|
| **France Travail** (ex-Pôle Emploi) | ✅ Free API (OAuth) | Government — massive, high quality |
| **APEC** | ❌ | Exec/cadre focus |
| **Indeed FR** | ❌ | — |
| **LinkedIn FR** | ❌ | — |
| **Welcome to the Jungle** | ❌ | Hip startup board |
| **Adzuna FR** | ✅ | Primary |
| **HelloWork** | ❌ | Mid-market |

### Netherlands (NL)
| Board | API? | Notes |
|---|---|---|
| **Nationale Vacaturebank** | ❌ | — |
| **Werk.nl** (Government) | ❌ (closed) | — |
| **Indeed NL** | ❌ | — |
| **LinkedIn NL** | ❌ | Dominant for white-collar |
| **Adzuna NL** | ✅ | Primary |
| **Arbeitnow** | ✅ | Good NL coverage |

### India (IN)
| Board | API? | Notes |
|---|---|---|
| **Naukri.com** | ❌ | Dominant — no public API |
| **LinkedIn IN** | ❌ | — |
| **Indeed IN** | ❌ | — |
| **Shine.com** | ❌ | — |
| **Monster India** | ❌ | — |
| **Adzuna IN** | ✅ | Primary |
| **Hirect** | ❌ | Chat-based; mobile only |
| **AngelList India** | ❌ | Startup |

### Brazil (BR)
| Board | API? | Notes |
|---|---|---|
| **Catho** | ❌ | Dominant paid |
| **Vagas.com.br** | ❌ | — |
| **InfoJobs BR** | ❌ | — |
| **LinkedIn BR** | ❌ | Growing |
| **Indeed BR** | ❌ | — |
| **Adzuna BR** | ✅ | Primary |
| **Gupy** | ❌ (ATS, not board) | Many BR companies use Gupy ATS |
| **Trampos.co** | ❌ | Creative/tech niche |

### United Arab Emirates (AE)
| Board | API? | Notes |
|---|---|---|
| **Bayt** | ❌ | Dominant MENA |
| **GulfTalent** | ❌ | Executive |
| **Naukrigulf** | ❌ | IN diaspora |
| **LinkedIn AE** | ❌ | Huge in UAE |
| **Indeed AE** | ❌ | — |
| **Dubizzle Jobs** | ❌ | Classifieds |
| **No Adzuna coverage** | — | AE is a gap for free APIs |

### Japan (JP)
| Board | API? | Notes |
|---|---|---|
| **Rikunabi Next** | ❌ | Dominant graduate/mid |
| **MyNavi** | ❌ | Graduate focus |
| **doda** | ❌ | Mid-career |
| **LinkedIn JP** | ❌ | Foreign-friendly roles |
| **BizReach** | ❌ | Executive |
| **Wantedly** | ❌ | Startup |
| **GaijinPot** | ❌ | English-speaking expats |
| **Daijob** | ❌ | Bilingual |
| **No Adzuna coverage** | — | JP is a gap |

### Regional coverage summary

| Region | API coverage via free sources | Strategy |
|---|---|---|
| AU, US, UK, CA, DE, FR, NL, IN, BR | Adzuna + gov/specialty APIs | Strong — build now |
| NZ | Trade Me partnership | Apply for partnership |
| AE | No free APIs | Scrape via extension; or skip in MVP |
| JP | No free APIs | Scrape via extension; or skip in MVP |

---

## 4. Job discovery — specialty & niche boards

Higher signal-to-noise for specific user segments. Worth adding once core discovery works.

### Developer & tech
| Board | API? | Fit |
|---|---|---|
| **Hacker News "Who's Hiring"** | ✅ HN API (monthly threads) | Senior dev gold |
| **Remote OK** | ✅ JSON | Remote dev |
| **Remotive** | ✅ | Remote dev |
| **We Work Remotely** | ✅ RSS | Remote general |
| **Findwork.dev** | ✅ | Dev |
| **Landing.jobs** | ❌ | EU tech |
| **Working Nomads** | ✅ RSS | Remote |
| **4 Day Week** | ❌ | 32-hour companies |
| **Otta / Welcome to the Jungle** | ❌ | Curated startup |

### Design & creative
| Board | API? | Fit |
|---|---|---|
| **Dribbble Jobs** | ❌ | Design |
| **Behance Jobs** | ❌ | Design |
| **Working Not Working** | ❌ | Creative freelance |
| **Authentic Jobs** | ❌ | Design |

### Executive & senior
| Board | API? | Fit |
|---|---|---|
| **The Ladders** (US) | ❌ | $100k+ |
| **ExecThread** | ❌ | Invite-only exec |
| **Bolster** | ❌ | Fractional exec |

### Remote-first global
| Board | API? |
|---|---|
| **JustRemote** | ❌ |
| **FlexJobs** | ❌ (subscription) |
| **Nomad List Jobs** | ❌ |
| **Himalayas** | ✅ JSON |

### Diversity & inclusion
| Board | API? | Fit |
|---|---|---|
| **Power to Fly** | ❌ | Women in tech |
| **Jopwell** | ❌ | Black, Latinx, Native American |
| **Diversify Tech** | ❌ | Underrepresented in tech |

### Government & non-profit
| Board | API? |
|---|---|
| **USAJobs** | ✅ |
| **Idealist** | ❌ |
| **EU Careers (EPSO)** | ❌ |

---

## 5. Company ATS direct

Thousands of companies host their own careers pages via a handful of ATS platforms. Most expose **structured JSON endpoints** — not scraping, not auth-gated, just public URLs.

| ATS | Public endpoint pattern | Coverage |
|---|---|---|
| **Greenhouse** | `https://boards-api.greenhouse.io/v1/boards/{company}/jobs` | ~4,000 companies (Airbnb, Stripe, DoorDash) |
| **Lever** | `https://api.lever.co/v0/postings/{company}?mode=json` | ~2,000 companies (Netflix, Shopify alumni) |
| **Workable** | `https://apply.workable.com/api/v3/accounts/{company}/jobs` | ~20,000 SMBs |
| **Ashby** | `https://api.ashbyhq.com/posting-api/job-board/{company}` | Growing YC cohort |
| **SmartRecruiters** | `https://api.smartrecruiters.com/v1/companies/{company}/postings` | Enterprise |
| **Recruitee** | `https://{company}.recruitee.com/api/offers/` | EU SMB |
| **Personio** | Per-tenant URLs | DE/EU-heavy |
| **Teamtailor** | `https://{company}.teamtailor.com/jobs.json` | EU |
| **JazzHR** | ❌ Mostly private | — |
| **Workday** | ❌ No public API; auth-gated | Must scrape HTML carefully |
| **Taleo / Oracle HCM** | ❌ | Enterprise pain |
| **SuccessFactors / SAP** | ❌ | Enterprise pain |
| **iCIMS** | ❌ | Enterprise |
| **BambooHR** | Public career pages, structured | SMB-friendly |
| **Gupy** (BR) | ❌ Per-tenant | Dominant in Brazil |

**Strategy**: Build a **company tracker** — user enters a company name, QuillCV detects which ATS it uses (via DNS or page meta), then polls the public endpoint daily. Email user when a matching role opens. Zero scraping risk, huge perceived value.

---

## 6. Application tracking integrations

The **retention moat**. Users apply to 50–200 jobs; whoever helps them stay sane wins.

### Email parsing (Gmail + Outlook)

| Integration | What it parses | Value |
|---|---|---|
| **Gmail API** | Confirmations, rejections, interview invites, recruiter reach-outs | 🔥 Highest-leverage single integration |
| **Outlook Graph API** | Same | For MS-heavy users |
| **IMAP fallback** | Any provider | For Yahoo, ProtonMail, self-hosted |

**Patterns to detect**:
- "Thank you for applying to [Company]" → status: applied confirmed
- "We regret to inform" / "unfortunately" / "decided to move forward with other candidates" → status: rejected
- "Schedule an interview" / "would like to invite you" → status: interview
- "Offer" / "pleased to offer" → status: offer
- Recruiter domains (greenhouse.io, lever.co, workable.com) → categorize source

**Privacy framing matters**: Use OAuth scopes narrowly (`gmail.readonly` + query filter on career-related emails only). Publish a clear privacy policy. This is a trust-make-or-break feature.

### Calendar integrations

| Integration | Use |
|---|---|
| **Google Calendar API** | Auto-create interview events with Zoom/Meet links, company research attached |
| **Microsoft Graph Calendar** | Same for Outlook users |
| **.ics export** | Universal fallback |
| **Cal.com / Calendly** | Webhook-based: recruiter schedules → QuillCV logs interview |

### Task & reminder

| Integration | Use |
|---|---|
| **Native in-app reminders** | Follow up after 7 days, thank-you note after interview |
| **Push notifications** (PWA) | Mobile reminders |
| **Email digest** | Weekly pipeline summary — "3 applications need a follow-up" |
| **Slack / Telegram / Discord** | Power users |

### External tracker sync (export, not replace)

| Tool | Integration |
|---|---|
| **Notion** | API sync — many users track in Notion today |
| **Airtable** | API sync |
| **Trello** | API |
| **Google Sheets** | API + CSV export |
| **CSV export** | Universal |

---

## 7. CV enrichment integrations

Make the CV demonstrably stronger by pulling in verified signals.

### Developer enrichment
| Source | API | Use |
|---|---|---|
| **GitHub** | ✅ Free, OAuth | Pull recent repos, primary languages, contribution stats, starred projects. Surface top projects in CV. |
| **GitLab** | ✅ | Same for GitLab-heavy users |
| **Bitbucket** | ✅ | Less common |
| **Stack Overflow** | ✅ | Reputation, top tags — for senior devs |
| **HackerRank / LeetCode** | ❌ Mostly private | Scrapeable profile URLs only |
| **Kaggle** | ✅ | Data scientists — competitions, notebooks |
| **DEV.to / Hashnode / Medium** | ✅ RSS/API | Thought-leadership content |
| **npm / PyPI / RubyGems** | ✅ | Package authorship = strong signal |

### Professional enrichment
| Source | API | Use |
|---|---|---|
| **LinkedIn** | ❌ | No legal API. Offer "paste your LinkedIn URL" → user uploads PDF export manually |
| **AngelList / Wellfound** | ❌ | — |
| **Crunchbase profile** | ✅ (paid) | Founder/exec roles |
| **Product Hunt** | ✅ | Product people — shipped products |
| **Behance** | ✅ | Designers — portfolio pull |
| **Dribbble** | ✅ | Designers |
| **SoundCloud / Spotify for Artists** | ✅ | Music/audio roles |
| **IMDB** | ❌ | Film/TV roles |
| **ORCID** | ✅ | Academic — publications |
| **Google Scholar** | ❌ | Scrape only |
| **Semantic Scholar** | ✅ | Academic |
| **Coursera / edX / Udemy certificates** | ✅ per platform | Verified credentials |

### Credentials & certifications
| Source | API |
|---|---|
| **Credly (Acclaim)** | ✅ | AWS, Google, Microsoft badges |
| **Accredible** | ✅ | Many bootcamps |
| **LinkedIn Learning** | ❌ | Manual |

---

## 8. Company & role intelligence

Help users **pick which jobs to apply to** and **nail the interview**.

| Source | API | Data |
|---|---|---|
| **Clearbit** | ✅ (free tier via Hunter) | Company size, industry, tech stack, domain |
| **Apollo.io** | ✅ (paid) | Decision-makers, emails, org chart |
| **Hunter.io** | ✅ (free tier) | Find hiring manager email |
| **Crunchbase** | ✅ (paid) | Funding, investors, growth |
| **PitchBook** | ❌ (enterprise) | — |
| **BuiltWith** | ✅ | Tech stack — critical for dev CV tailoring |
| **Wappalyzer** | ✅ | Same |
| **Owler** | ❌ | Competitive intel |
| **Glassdoor** | ❌ | Company reviews, interview questions — scrape carefully |
| **Blind** | ❌ | Anonymous employee chat — scrape only |
| **Kununu** (DE) | ❌ | DE equivalent of Glassdoor |
| **Indeed Reviews** | ❌ | — |
| **Comparably** | ❌ | — |

**High-value use case**: User pastes job URL → QuillCV enriches with:
- Company tech stack (BuiltWith) → adjust CV keywords
- Funding stage (Crunchbase) → set tone (stable vs. scrappy)
- Hiring manager email (Hunter) → "send a follow-up email?" CTA
- Glassdoor rating + common interview questions → interview prep pack

---

## 9. Salary & compensation intelligence

Knowing salary bands → user targets the right roles + negotiates better → higher offer acceptance.

| Source | API | Coverage |
|---|---|---|
| **Levels.fyi** | ❌ (scrape only) | Tech — most accurate for FAANG+ |
| **Payscale** | ❌ (enterprise API) | Global generalist |
| **Salary.com** | ❌ | US |
| **Glassdoor Salaries** | ❌ | Global |
| **LinkedIn Salary** | ❌ | Global |
| **Adzuna** | ✅ Returns salary range in listings | Use directly |
| **BLS (US Bureau of Labor Statistics)** | ✅ Free | US occupational data — slow but authoritative |
| **ONS (UK)** | ✅ | UK |
| **Eurostat** | ✅ | EU |
| **Ravio / Figures** | ❌ (B2B) | European tech comp |

**Feature idea**: "Your target salary is $X — here are 12 open jobs in the top quartile for that range."

---

## 10. Interview preparation integrations

Once the user gets an interview, keep them in QuillCV.

| Source | Integration | Value |
|---|---|---|
| **Claude API** | ✅ Already integrated | Generate mock interview questions from JD + company data |
| **OpenAI Whisper / Deepgram** | ✅ | Transcribe mock interview audio |
| **ElevenLabs / OpenAI TTS** | ✅ | AI interviewer voice |
| **Glassdoor interview questions** | ❌ Scrape | Real questions asked at target company |
| **Leetcode company question lists** | ❌ Scrape | Tech interviews |
| **Pramp / Interviewing.io** | ❌ | Peer mock interviews — link out only |
| **Big Interview / InterviewBuddy** | ❌ | Competitors — don't integrate |

**MVP**: "Practice Mode" → QuillCV generates 10 role-specific questions from the JD, user answers via text or voice, Claude critiques against STAR framework.

---

## 11. Networking & referral signals

Referrals 10x application success rates. QuillCV can't replicate LinkedIn but can amplify it.

| Source | Integration | Value |
|---|---|---|
| **LinkedIn (user-side)** | Browser extension captures "connections at company X" | Show users who they know at the target |
| **Hunter.io** | ✅ | Find hiring manager email → warm intro template |
| **Apollo.io** | ✅ | Same + phone |
| **RocketReach** | ✅ (paid) | Same |
| **Clay** | ✅ (expensive) | Multi-source enrichment |
| **Twitter / X API** | ✅ (paid $100/mo) | Find engineering managers tweeting about hiring |
| **GitHub** | ✅ | "You have 3 mutual followers at Stripe" |
| **Mastodon / Bluesky** | ✅ Free | Emerging alternative |

**Feature idea**: "Do you know anyone at [Company]?" → scan user's LinkedIn (via extension) + GitHub → surface potential warm intros.

---

## 12. Browser extension

**The single highest-leverage integration for QuillCV.** One extension unlocks:

### Capture (read-only)
- **"Save this job"** on any page (LinkedIn, Seek, Indeed, Naukri, Rikunabi, Bayt — anywhere) → extracts title, company, URL, JD, pushes to QuillCV tracker
- **LinkedIn connections scan** at target company → surfaces potential referrals
- **Salary data scrape** from Glassdoor / Levels.fyi pages user already visits

### Assist (user-driven)
- **"Generate tailored CV for this job"** → opens QuillCV with JD pre-filled
- **Autofill application forms** with user's profile (user clicks Submit)
- **Cover letter on demand** for the current JD

### Context
- **Company intel overlay** — when user views a job, show funding, tech stack, Glassdoor rating inline
- **Application tracking nudge** — "You applied to 3 similar roles at this company 2 weeks ago"

**Why this matters**: Every job board with no API (LinkedIn, Seek, Indeed, Naukri, Rikunabi, Bayt, Catho, AngelList) becomes *integratable* because the user's own browser is the integration layer. No ToS violation (user-initiated), no scraping infra to maintain.

---

## 13. Competitor landscape

What to learn from / differentiate against.

| Product | Pricing | Strength | Weakness | Our angle |
|---|---|---|---|---|
| **Teal** | Free + $30/mo | Chrome extension + tracker | Weak CV generator | Our tailored-per-JD CV is stronger |
| **Simplify** | Free + $20/mo | Autofill extension | Generic CV | Ours is region-specific |
| **Jobscan** | $50/mo | ATS scoring | No discovery | We bundle scoring + generation |
| **Huntr** | Free + $10/mo | Beautiful tracker | No CV gen | We integrate tracker + generator |
| **LazyApply** | $99 one-time | Mass auto-apply | Legal risk, low quality | We're the ethical alternative |
| **Sonara** | $50/mo | AI auto-apply | Same as LazyApply | Same |
| **Careerflow** | Free + $15/mo | LinkedIn optimizer + tracker | Scattered UX | We're focused |
| **Kickresume** | $5–$20/mo | Templates | Not ATS-aware | We're ATS-native |
| **Rezi** | $30/mo | ATS-focused | US-only | We're 12 regions |
| **Enhancv** | $25/mo | Design-led | Not ATS | We're both |

**Key insight**: The market is split between **beauty-first** (Enhancv, Kickresume) and **ATS-first** (Rezi, Jobscan). QuillCV's wedge is **ATS-first + regional + integrated tracker** — nobody else covers all three.

---

## 14. Recommended build order

### Phase 1 — Core discovery & capture (Weeks 1–4)
1. **Adzuna integration** → 10 of 12 regions covered, matching engine live
2. **Greenhouse + Lever + Workable + Ashby** public endpoints → company-direct discovery
3. **Chrome extension MVP**: save-job + generate-CV-for-this-JD buttons
4. **In-app tracker** (status pipeline: saved → applied → interview → offer/rejected)

### Phase 2 — Retention layer (Weeks 5–8)
5. **Gmail API** for auto-status updates (biggest retention unlock)
6. **Google Calendar** for interview scheduling
7. **Weekly digest email** with follow-up reminders
8. **Outlook Graph API** for MS users

### Phase 3 — Intelligence layer (Weeks 9–12)
9. **BuiltWith / Wappalyzer** for company tech-stack inference
10. **Hunter.io** for hiring manager email discovery
11. **Company intel overlay** in browser extension
12. **Salary band display** on listings (from Adzuna + BLS/ONS)

### Phase 4 — Enrichment & prep (Weeks 13–16)
13. **GitHub integration** for dev users
14. **LinkedIn PDF import** (user-uploaded)
15. **Credly / Accredible** for verified credentials
16. **Interview prep mode** — Claude-generated questions from JD

### Phase 5 — Regional fill-in (Weeks 17+)
17. **France Travail API** (huge FR source)
18. **Bundesagentur für Arbeit** (huge DE source)
19. **Job Bank CA**
20. **Trade Me NZ partnership application**
21. **Specialty boards** (HN Who's Hiring, Remote OK, Himalayas)

### Deferred / conditional
- **AE and JP regional boards** — no free APIs; rely on extension until demand justifies partnerships
- **Twitter/X API** — paid, low ROI for job search
- **Apollo.io** — expensive; add once users ask for hiring-manager email

---

## 15. Legal & ToS reference table

Quick reference for what's safe vs. risky. Assume ToS changes — re-verify before launch.

| Platform | API scraping | Browser extension | Auto-submit | Safe to build against? |
|---|---|---|---|---|
| **Adzuna, Jooble, Arbeitnow, Himalayas** | ✅ Per ToS | ✅ | N/A | ✅ Yes |
| **Greenhouse, Lever, Ashby, Workable public endpoints** | ✅ Public data | ✅ | N/A | ✅ Yes |
| **Government APIs** (USAJobs, France Travail, BA, Job Bank) | ✅ Designed for it | ✅ | N/A | ✅ Yes |
| **GitHub, GitLab, Stack Overflow** | ✅ Rate-limited | ✅ | N/A | ✅ Yes |
| **LinkedIn** | ❌ Banned | ⚠️ User-initiated only | ❌ Never | ⚠️ Extension only |
| **Seek, Indeed, ZipRecruiter** | ❌ Banned | ⚠️ User-initiated only | ❌ Never | ⚠️ Extension only |
| **Naukri, Bayt, Rikunabi, Catho** | ❌ | ⚠️ User-initiated only | ❌ Never | ⚠️ Extension only |
| **Glassdoor, Blind, Levels.fyi** | ❌ | ⚠️ Display user's own view | ❌ Never | ⚠️ Very cautious |
| **Gmail, Outlook, Google Calendar** | ✅ With OAuth consent | N/A | N/A | ✅ Narrow scopes only |
| **Workday, Taleo, iCIMS, SuccessFactors** | ❌ | ⚠️ Autofill only | ❌ Never | ⚠️ Autofill only |

**Golden rule**: If the data is fetched with the user's own credentials in their own browser, it's defensible. If our servers are hitting the target without that user context, it's scraping and it's risky.

---

## Appendix: Quick-access cheat sheet for users

(Potential in-product content — help users help themselves)

**If you're in AU/NZ**: Primary — Seek, LinkedIn. Niche — AngelList (startups), Hatch.
**If you're in the US**: Primary — LinkedIn, Indeed, Greenhouse-hosted boards. Tech — HN Who's Hiring, Wellfound, Dice.
**If you're in the UK**: Primary — LinkedIn, Reed, Totaljobs. Tech — Otta, LinkedIn.
**If you're in DE/NL/FR**: Primary — LinkedIn, StepStone (DE), France Travail (FR). Tech — Welcome to the Jungle, Arbeitnow.
**If you're in IN**: Primary — Naukri, LinkedIn. Tech — AngelList, Instahyre.
**If you're in BR**: Primary — LinkedIn, Catho, Gupy-hosted boards. Tech — Trampos.
**If you're in AE**: Primary — LinkedIn, Bayt, GulfTalent.
**If you're in JP**: Primary — LinkedIn (bilingual), Rikunabi, BizReach (senior). Expat — GaijinPot, Daijob.
**If you're remote/global**: Remote OK, Remotive, We Work Remotely, Himalayas, 4 Day Week, JustRemote.
