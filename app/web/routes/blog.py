"""Blog routes: index listing and individual post pages — multilingual (EN, ES, PT)."""

from datetime import date
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.web.templates import templates

router = APIRouter()

SUPPORTED_LANGS = ["en", "es", "pt"]

LANG_LABELS = {
    "en": "English",
    "es": "Español",
    "pt": "Português",
}

POSTS = {
    "en": [
        {
            "slug": "cv-audit-spring-2027",
            "title": "Your Spring CV Audit: 15 Things to Refresh Before the Hiring Season Peaks",
            "description": "Spring is peak hiring season. Here are 15 practical things to update on your CV before the window closes — from refreshing achievements to checking your links still work.",
            "date": "2027-04-15",
            "date_modified": "2027-04-15",
            "publish_date": "2027-04-15",
            "author": "Daniel Zambrano",
            "tags": ["cv-tips", "career-advice", "job-search", "cv-checklist", "diy"],
            "faq": [
                {"q": "When is the best time to update your CV?", "a": "Before you need it. The best time to refresh your CV is between job searches — when you're not stressed and can recall recent achievements clearly. Spring (March–May) and autumn (September–November) are peak hiring seasons, so updating before those windows is ideal."},
                {"q": "What should I update on my CV annually?", "a": "At minimum: your most recent role's achievements, your skills section, any certifications or courses completed, contact details (especially LinkedIn URL), and the year on your professional summary if it mentions one."},
                {"q": "How often should I refresh my CV?", "a": "After any significant project, promotion, or new skill — not just when you're job hunting. A CV updated regularly is far easier to maintain than one you try to reconstruct from memory two years later."},
            ],
        },
        {
            "slug": "2027-job-search-reality-check",
            "title": "The 2027 Job Search Reality Check",
            "description": "What's actually happening in the job market in 2027. Application volumes, AI's role in hiring, time-to-hire trends, and what's working for candidates right now.",
            "date": "2027-04-01",
            "date_modified": "2027-04-01",
            "publish_date": "2027-04-01",
            "author": "Daniel Zambrano",
            "tags": ["job-search", "career-advice", "hiring-trends", "ats"],
            "faq": [
                {"q": "Is the job market improving in 2027?", "a": "It depends heavily on the sector and region. Tech hiring has stabilised after the 2023–2024 contraction. Healthcare, infrastructure, and AI-adjacent roles are strong. White-collar generalist roles remain competitive, with more candidates applying per opening than at any point in the last decade."},
                {"q": "How long does a typical job search take in 2027?", "a": "For professional roles, expect 2–4 months from first application to offer. Executive and senior roles run 3–6 months. The time-to-hire varies enormously by company size: startups move faster, large enterprises slower."},
                {"q": "Are AI-assisted CV tools effective for job applications in 2027?", "a": "Yes — when used correctly. AI tools that tailor CVs to specific job descriptions consistently outperform generic CVs in ATS scoring. The difference is intentionality: AI-tailored applications beat both generic AI-generated ones and untailored manual ones."},
            ],
        },
        {
            "slug": "employment-gap-on-cv",
            "title": "The Employment Gap: Why It Matters Less Than You've Been Told",
            "description": "Career gaps are common, and most employers have adapted. Here's how to address gaps honestly without over-explaining — and when a gap actually is a red flag.",
            "date": "2027-03-15",
            "date_modified": "2027-03-15",
            "publish_date": "2027-03-15",
            "author": "Daniel Zambrano",
            "tags": ["career-advice", "cv-tips", "employment-gap", "job-search"],
            "faq": [
                {"q": "How do I explain a gap in employment on my CV?", "a": "Briefly and honestly. A one-line explanation in your work history or cover letter is enough: 'Career break for family care', 'Took time to travel and retrain in X', or simply 'Career break'. You don't owe a detailed explanation upfront — that's for the interview."},
                {"q": "Should I try to hide a gap on my CV?", "a": "No. Omitting date ranges entirely or using vague language draws more attention to the gap than a straightforward explanation. Hiring managers notice when dates are missing or suspiciously rounded."},
                {"q": "What counts as a significant employment gap?", "a": "Generally anything over six months raises questions. Under three months rarely needs explaining at all — short gaps are normal between roles. The key is that you can speak confidently about what you did during the gap, even if the answer is 'I took time to decompress after a difficult role.'"},
            ],
        },
        {
            "slug": "executive-cv-vs-standard-cv",
            "title": "Executive CV vs Standard CV: When to Level Up Your Format",
            "description": "What changes at Director, VP, and C-suite level — length, achievement framing, board experience, and why the rules you followed for your first CV no longer apply.",
            "date": "2027-03-01",
            "date_modified": "2027-03-01",
            "publish_date": "2027-03-01",
            "author": "Daniel Zambrano",
            "tags": ["executive-cv", "career-advice", "cv-tips", "senior-roles"],
            "faq": [
                {"q": "How long should an executive CV be?", "a": "Two to three pages is standard at Director level and above. The one-page rule does not apply — senior candidates are expected to demonstrate breadth. That said, four pages or more suggests poor editing; every line should earn its place."},
                {"q": "What sections should an executive CV include?", "a": "Executive summary (not 'objective'), career history with strategic achievements, board or advisory roles, education, and any significant publications or speaking engagements. A skills section is optional at senior level — your experience should speak for itself."},
                {"q": "When do I need a professional CV writer?", "a": "If you're targeting C-suite roles, boards, or private equity-backed companies, a professional writer can be worth the investment — not because you can't write well, but because they know the specific conventions and language those audiences expect."},
            ],
        },
        {
            "slug": "how-to-write-cv-from-scratch",
            "title": "How to Write a CV From Scratch: The Complete 2026 Guide",
            "description": "Everything you need to build a strong CV from a blank page — every section, every decision, and the ATS rules that determine whether a human ever reads it.",
            "date": "2027-02-15",
            "date_modified": "2027-02-15",
            "publish_date": "2027-02-15",
            "author": "Daniel Zambrano",
            "tags": ["cv-tips", "ats", "job-search", "career-advice", "how-to", "diy"],
            "faq": [
                {"q": "What sections should a CV have?", "a": "At minimum: contact details, professional summary, work experience, education, and skills. Optional sections depending on your background: certifications, projects, languages, volunteering, publications. Don't include sections you can't fill meaningfully."},
                {"q": "What order should CV sections be in?", "a": "Contact details first, always. Then professional summary. Then work experience (most recent first) for anyone with more than two years of experience. Education moves above work experience only for recent graduates. Skills can go after experience or at the end."},
                {"q": "How long should a CV be?", "a": "One page for under five years of experience; two pages for most professionals. Three pages is acceptable for senior roles or academic CVs. The rule isn't 'shorter is better' — it's 'every line should earn its place.' A strong two-page CV beats a padded one-page every time."},
            ],
        },
        {
            "slug": "what-culture-fit-means",
            "title": "What 'Strong Culture Fit' Really Means on a Job Ad",
            "description": "The phrase nobody defines but everyone uses. What 'culture fit' actually signals in a job posting — and how to decide whether it's an invitation or a warning.",
            "date": "2027-02-01",
            "date_modified": "2027-02-01",
            "publish_date": "2027-02-01",
            "author": "Daniel Zambrano",
            "tags": ["job-search", "career-advice", "hiring", "workplace"],
            "faq": [
                {"q": "What does 'culture fit' mean in a job description?", "a": "It means different things at different companies. At best, it refers to working style — whether you prefer autonomy or collaboration, structure or flexibility. At worst, it's code for demographic homogeneity. The phrase itself tells you nothing; the rest of the job ad, the company's glassdoor reviews, and the interview will."},
                {"q": "How do you address culture fit in your CV?", "a": "You can't and shouldn't try to. Your CV demonstrates competence; culture fit is assessed in conversation. Focus on tailoring your experience to the role. Save the cultural alignment conversation for the interview, where you can also assess whether you'd want to work there."},
                {"q": "Is 'culture fit' sometimes code for discrimination?", "a": "It can be, and this is well-documented. 'Culture fit' rejections disproportionately affect candidates from underrepresented groups. Structured hiring processes (defined criteria, blind review, rubric-based scoring) reduce this. As a candidate, you can't always know which kind of company you're dealing with — but patterns in their team page, leadership, and Glassdoor reviews can give you signals."},
            ],
        },
        {
            "slug": "before-after-cv-rewrite",
            "title": "Before & After: Turning a Generic CV Into an ATS-Optimised One",
            "description": "A real CV rewrite, decision by decision. Here's exactly what was wrong with the original — and why every change to the final version improves its chances.",
            "date": "2027-01-15",
            "date_modified": "2027-01-15",
            "publish_date": "2027-01-15",
            "author": "Daniel Zambrano",
            "tags": ["cv-tips", "ats", "job-search", "before-after", "diy"],
            "faq": [
                {"q": "How do I improve my CV for ATS?", "a": "Match the language of the job description, use standard section headings (Work Experience not Career Journey), remove tables and text boxes, save as a clean PDF or DOCX, and include the specific keywords — including acronyms — that the posting uses."},
                {"q": "What makes a CV ATS-friendly?", "a": "Clean formatting (no columns, tables, or graphics), standard section headings, keyword-matched content, no header/footer text, and consistent date formatting. ATS systems are essentially text parsers — anything that confuses the parse costs you points."},
                {"q": "Should I rewrite my CV for every job application?", "a": "Not completely — but you should tailor it. Your core content (work history, education) stays the same. What changes: the professional summary, the skills section emphasis, and specific achievement bullets adjusted to mirror the language of the target posting."},
            ],
        },
        {
            "slug": "first-job-cv-no-experience",
            "title": "First Job CV: No Experience, No Problem",
            "description": "What to include on a CV when your experience section is thin — and how to frame potential over history when you're applying for your first professional role.",
            "date": "2027-01-01",
            "date_modified": "2027-01-01",
            "publish_date": "2027-01-01",
            "author": "Daniel Zambrano",
            "tags": ["cv-tips", "career-advice", "graduate", "entry-level", "diy"],
            "faq": [
                {"q": "How do I write a CV with no work experience?", "a": "Lead with your education and put it above work experience. Fill experience with any role that demonstrates relevant skills: part-time work, volunteering, internships, academic projects, extracurriculars. Use the same achievement-oriented bullet format even for unpaid or casual roles."},
                {"q": "Should I include my GPA on my CV?", "a": "In the US, yes if it's 3.5 or above and you're within a few years of graduating. In Australia and the UK, grades are less commonly listed but relevant distinctions or honours are worth including. Drop it once you have a few years of experience."},
                {"q": "How long should a graduate CV be?", "a": "One page. You don't have enough history to fill two pages meaningfully, and padding it out with filler works against you. A tight, well-structured one-pager that clearly shows what you offer is far more effective than a padded two-pager."},
            ],
        },
        {
            "slug": "certification-trap",
            "title": "The Certification Trap: When Upskilling Becomes Procrastination",
            "description": "Certifications can help — but the advice to 'just get certified' ignores the real costs. Here's when a cert actually moves the needle and when it's just expensive avoidance.",
            "date": "2026-12-15",
            "date_modified": "2026-12-15",
            "publish_date": "2026-12-15",
            "author": "Daniel Zambrano",
            "tags": ["career-advice", "certifications", "job-search", "upskilling"],
            "faq": [
                {"q": "Are certifications worth it for getting a job?", "a": "It depends entirely on the field and the cert. In cloud computing, cybersecurity, and project management, specific certifications (AWS, CISSP, PMP) are actively screened for. In most other fields, they're a minor positive signal at best and irrelevant at worst."},
                {"q": "Which certifications are most valued by employers?", "a": "In tech: AWS/Azure/GCP certifications, Google Analytics, PMP, Scrum Master. In finance: CFA, CPA, CFP. In project management: PMP, PRINCE2. In healthcare: role-specific clinical certifications. Generic 'leadership' or 'communication' certifications from obscure platforms add almost no value."},
                {"q": "Should I include certifications on my CV?", "a": "Yes, if they're relevant and current. List them in a dedicated 'Certifications' section with the issuing body and completion year. Don't list expired certifications unless you're in a field where the base credential matters (e.g. nursing) even if not current."},
            ],
        },
        {
            "slug": "cv-for-australia-uk-germany",
            "title": "Applying to Jobs in Australia, UK, or Germany? Read This First",
            "description": "Three markets, three different CV expectations. What Australian employers want, what UK hiring managers expect, and what a German Lebenslauf actually requires.",
            "date": "2026-12-01",
            "date_modified": "2026-12-01",
            "publish_date": "2026-12-01",
            "author": "Daniel Zambrano",
            "tags": ["cv-format", "international-jobs", "australia", "uk", "germany"],
            "faq": [
                {"q": "Do I need to localise my CV for Australia?", "a": "Yes. Australian CVs are typically two pages, written in a slightly less formal tone than UK CVs, include a referee section (or 'references available on request'), and omit the personal details expected in European CVs (no photo, no date of birth). The term 'resume' is used interchangeably with 'CV'."},
                {"q": "What is a Lebenslauf and what does it include?", "a": "A Lebenslauf is the German CV format. It typically includes a professional photo, date and place of birth, nationality, marital status, work history (reverse chronological), education, language skills, and a handwritten or digital signature. These details would raise legal red flags in the US or UK."},
                {"q": "Do UK employers expect a cover letter?", "a": "Generally yes, unless the posting explicitly says not to include one. UK cover letters tend to be more formal than their US counterparts and are typically addressed to a named person if possible. A well-written, specific cover letter still differentiates candidates in the UK market."},
            ],
        },
        {
            "slug": "ats-safe-formatting",
            "title": "ATS-Safe Formatting: What to Avoid, What Passes Through",
            "description": "Tables, columns, text boxes, headers and footers, graphics — here's exactly what breaks CV parsers and the safe alternatives that still look professional.",
            "date": "2026-11-15",
            "date_modified": "2026-11-15",
            "publish_date": "2026-11-15",
            "author": "Daniel Zambrano",
            "tags": ["ats", "cv-tips", "formatting", "job-search", "diy"],
            "faq": [
                {"q": "Can ATS read tables in a CV?", "a": "Most modern ATS systems struggle with tables. Text inside table cells is often extracted out of order or dropped entirely. If your CV uses a table for your work history or skills section, there's a real risk the content is being parsed as garbled text or lost completely."},
                {"q": "What font should I use for my CV?", "a": "Any standard system font: Calibri, Arial, Georgia, Garamond, or Times New Roman. Avoid decorative fonts, custom fonts loaded via external services, or icon fonts (Font Awesome, etc.) — these either don't embed correctly or render as blank squares in plain-text extraction."},
                {"q": "Should I use a two-column CV layout?", "a": "Not if you're applying through an online portal or ATS system. Two-column layouts are often read left-to-right row by row, mixing content from both columns into nonsense. If you want a visually structured CV, use a single-column layout with clear section breaks — you get the same visual hierarchy without the parse risk."},
            ],
        },
        {
            "slug": "career-change-cv",
            "title": "Career Change CV: How to Frame a Pivot Without Looking Like a Risk",
            "description": "Changing careers doesn't mean starting from zero. Here's how to present transferable skills, choose the right CV structure, and address the pivot before a recruiter raises it.",
            "date": "2026-11-01",
            "date_modified": "2026-11-01",
            "publish_date": "2026-11-01",
            "author": "Daniel Zambrano",
            "tags": ["career-change", "cv-tips", "career-advice", "transferable-skills"],
            "faq": [
                {"q": "Should I use a functional or chronological CV for a career change?", "a": "Chronological, with a strong professional summary that reframes your experience for the new direction. Functional CVs (skills-based, no dates) are widely known as a way to hide a weak history and often trigger recruiter scepticism. A chronological CV with a well-crafted summary is harder to dismiss."},
                {"q": "How do I explain a career change on my CV?", "a": "In your professional summary, acknowledge the pivot directly and frame it as intentional: 'After ten years in financial services, I'm moving into UX design where I can apply my analytical background to user research.' Don't leave the recruiter to guess — your explanation should get there first."},
                {"q": "What transferable skills should I highlight in a career change?", "a": "Look for the overlap between what you've done and what the new role requires. Communication, stakeholder management, project delivery, data analysis, and client-facing skills transfer broadly. The key is to show them through concrete examples, not just claim them."},
            ],
        },
        {
            "slug": "ghosted-after-interview",
            "title": "Ghosted After an Interview? Here's What Probably Happened",
            "description": "Post-interview silence is frustrating — but it's rarely personal. Here's what actually causes ghosting, what to do about it, and when to move on.",
            "date": "2026-10-15",
            "date_modified": "2026-10-15",
            "publish_date": "2026-10-15",
            "author": "Daniel Zambrano",
            "tags": ["job-search", "career-advice", "hiring", "interview"],
            "faq": [
                {"q": "How long should I wait before following up after an interview?", "a": "Send a thank-you email within 24 hours. If they gave you a timeline and it passes, follow up once — politely, by email. If you hear nothing after a second follow-up, the role has either been filled or paused. At that point, redirect your energy."},
                {"q": "Is ghosting normal in the hiring process?", "a": "Unfortunately yes. High application volumes, internal process delays, sudden budget holds, and internal candidates all contribute. Studies consistently show that a majority of candidates who reach the interview stage never receive a formal rejection. It's not good practice, but it's common."},
                {"q": "Should I take ghosting personally?", "a": "No — and that's not just reassurance. The most common reasons for post-interview ghosting have nothing to do with your performance: the role was put on hold, an internal candidate was selected, the hiring manager left, or the company started a restructure. The silence is usually about their situation, not your interview."},
            ],
        },
        {
            "slug": "photo-on-cv-country-guide",
            "title": "Should You Put a Photo on Your CV? The Country-by-Country Answer",
            "description": "The right answer depends entirely on where you're applying. In some countries a photo is expected; in others it actively hurts your application. Here's the definitive breakdown.",
            "date": "2026-10-01",
            "date_modified": "2026-10-01",
            "publish_date": "2026-10-01",
            "author": "Daniel Zambrano",
            "tags": ["cv-format", "international-jobs", "region-specific", "cv-tips"],
            "faq": [
                {"q": "Should I put a photo on my resume for US jobs?", "a": "No. In the US, including a photo on a resume creates legal exposure for employers under equal opportunity laws, so many HR teams are trained to remove them or discard applications that include them. A photo on a US resume signals unfamiliarity with local conventions."},
                {"q": "What kind of photo is appropriate for a CV?", "a": "A professional headshot: neutral or light background, business-appropriate dress, looking directly at the camera with a relaxed expression. Not a selfie, not a holiday photo cropped to head-and-shoulders, and not your LinkedIn profile picture from five years ago. The photo should convey professionalism without being stiff."},
                {"q": "Do LGBTQ+ candidates face additional risks by including a photo?", "a": "In some markets, yes. In countries where anti-discrimination protections are weak or where bias is documented (parts of the Middle East, some Asian markets), a photo can expose candidates to discrimination based on appearance or perceived identity. The risk varies significantly by country and industry."},
            ],
        },
        {
            "slug": "how-to-write-a-cv-summary",
            "title": "How to Write a CV Summary That Doesn't Sound Generic",
            "description": "Most CV summaries are filler — 'results-driven professional with X years of experience' says nothing. Here's the formula for a summary that actually works, with five rewrites to show you how.",
            "date": "2026-09-15",
            "date_modified": "2026-09-15",
            "publish_date": "2026-09-15",
            "author": "Daniel Zambrano",
            "tags": ["cv-tips", "cv-writing", "job-search", "professional-summary", "diy"],
            "faq": [
                {"q": "Do I need a professional summary on my CV?", "a": "For most candidates with more than two years of experience, yes. A well-written summary does the job of the old objective statement but better — it signals who you are and what you offer before a recruiter reads a single bullet point. Graduate CVs can skip it."},
                {"q": "How long should a CV summary be?", "a": "Three to four lines, maximum. The summary is a hook, not a biography. If you find yourself writing five or more lines, you're either repeating what's in your experience section or padding — neither is useful."},
                {"q": "What's the difference between a CV summary and an objective statement?", "a": "An objective statement describes what you want ('seeking a role where I can...'); a summary describes what you offer. Objective statements are mostly obsolete — they centre your needs over the employer's. A summary leads with value and is almost always the better choice."},
            ],
        },
        {
            "slug": "ats-keywords-you-are-missing",
            "title": "The Keywords You're Missing (And How to Find Them for Free)",
            "description": "ATS keyword matching is simpler than it sounds — and the process for finding the right keywords costs nothing. Here's how to do it manually, and what QuillCV automates.",
            "date": "2026-09-01",
            "date_modified": "2026-09-01",
            "publish_date": "2026-09-01",
            "author": "Daniel Zambrano",
            "tags": ["ats", "keywords", "cv-tips", "job-search", "diy"],
            "faq": [
                {"q": "What are ATS keywords?", "a": "The specific words and phrases that an Applicant Tracking System (or the recruiter reading the parsed output) looks for in your CV. They come directly from the job posting — skills, qualifications, job titles, software names, and industry terminology. The closer your CV language mirrors the posting, the higher your match score."},
                {"q": "Should I keyword-stuff my CV?", "a": "No. Adding keywords that don't reflect your actual experience is dishonest and will be obvious in an interview. The goal is natural integration: use the same language the posting uses for skills you genuinely have. A 'product manager' who lists 'PM' but never 'product manager' may be underselling themselves to an ATS that screens for the full phrase."},
                {"q": "How many keywords do I need to include?", "a": "There's no magic number. Focus on the most important ones — typically the skills and qualifications listed in the 'Requirements' section of the posting. Those appear multiple times in the posting for a reason. Secondary nice-to-haves are worth including but shouldn't crowd out primary terms."},
            ],
        },
        {
            "slug": "job-search-quality-over-quantity",
            "title": "The Job Search Is a Numbers Game — But Not the Way You Think",
            "description": "Everyone tells you to apply to more jobs. The math doesn't support it. Here's the arithmetic that actually determines your job search outcome — and why 20 tailored applications beat 200 generic ones.",
            "date": "2026-08-15",
            "date_modified": "2026-08-15",
            "publish_date": "2026-08-15",
            "author": "Daniel Zambrano",
            "tags": ["job-search", "career-advice", "ats", "applications"],
            "faq": [
                {"q": "How many jobs should I apply to?", "a": "Less than you think. Ten to twenty well-targeted, tailored applications per month is a reasonable cadence for most professionals. Beyond that, quality degrades sharply — you can't research, tailor, and track forty applications properly while also following up, preparing for interviews, and working your network."},
                {"q": "What is a realistic response rate for job applications?", "a": "For tailored applications to roles you're qualified for, 10–20% is achievable. For generic applications, 1–3% is typical. That's the core of the math: twenty tailored applications at 15% gets you three conversations; two hundred generic ones at 1.5% gets you three conversations at ten times the effort."},
                {"q": "Is it really worth tailoring every single application?", "a": "For roles you actually want, yes. For stretch applications or exploratory ones, a lighter touch is fine — update the summary and the top few bullet points. The full tailoring investment is warranted for your target roles. The question to ask is: if they called tomorrow, how prepared would I be to say why I want this specific role?"},
            ],
        },
        {
            "slug": "cv-tips-for-software-engineers",
            "title": "CV Tips for Software Engineers: What Hiring Managers Actually Look For",
            "description": "A dev CV is not just a list of tech stacks. Here's what actually gets a software engineer's CV read — and the mistakes that get even strong candidates filtered out.",
            "date": "2026-08-01",
            "date_modified": "2026-08-01",
            "publish_date": "2026-08-01",
            "author": "Daniel Zambrano",
            "tags": ["software-engineering", "cv-tips", "tech-jobs", "career-advice"],
            "faq": [
                {"q": "Should I list every programming language on my CV?", "a": "No. List the languages you can work in comfortably and are prepared to discuss in depth. A wall of language logos signals 'collected keywords' rather than real depth. Group them by proficiency if it helps: expert, comfortable, familiar. And never list something you learned once and wouldn't confidently use in a take-home test."},
                {"q": "Do software engineers need a portfolio link on their CV?", "a": "A GitHub profile is worth including if it has meaningful, maintained projects. A portfolio site is useful for front-end and product-adjacent roles where design and presentation matter. Neither is mandatory — a strong work history and well-described projects in the CV itself carry more weight than a sparse or unmaintained portfolio."},
                {"q": "How long should a software engineer's CV be?", "a": "One to two pages. Junior engineers: one page. Mid-level and senior: one to two. Staff+ and above: two is fine if the content justifies it. The tech industry skews slightly more tolerant of longer CVs than other fields, but padding with technology lists, skills matrices, and proficiency bars adds length without adding value."},
            ],
        },
        {
            "slug": "how-to-quantify-achievements",
            "title": "How to Quantify Your Achievements (Even If Your Job Isn't Numbers-Driven)",
            "description": "Most CVs list duties. The ones that get interviews list outcomes. Here's the formula for turning what you did into achievement bullets — with before-and-after examples for five different roles.",
            "date": "2026-07-15",
            "date_modified": "2026-07-15",
            "publish_date": "2026-07-15",
            "author": "Daniel Zambrano",
            "tags": ["cv-tips", "cv-writing", "achievements", "job-search", "diy"],
            "faq": [
                {"q": "What if I genuinely don't have metrics to show?", "a": "You have more than you think. Metrics aren't always percentages or revenue — they can be: how many people you managed, the size of projects you delivered, the frequency of something you improved, a timeline you met or shortened, or a problem you eliminated. If you still can't find a number, you can qualify: 'Streamlined the onboarding process, reducing new hire ramp-up time.'"},
                {"q": "How do I write achievement bullets for entry-level roles?", "a": "Use the same formula, scale down the scope. 'Managed social media accounts, growing Instagram following from 200 to 1,400 over six months' is a real achievement that a student or early-career candidate can legitimately claim. The formula (action + context + result) works at every level."},
                {"q": "Should every CV bullet point be an achievement?", "a": "Ideally yes, but pragmatically, not always possible. Aim for at least one achievement bullet per role. Some responsibilities are better described as duties (especially for complex technical or operational roles where the scope itself communicates seniority). The goal is for the reader to see impact, not just presence."},
            ],
        },
        {
            "slug": "au-vs-us-resume-differences",
            "title": "AU vs US Resume: 9 Differences That Actually Matter",
            "description": "Your Australian CV and your American resume are not the same document. Here are the nine differences that matter most — and what happens when you send the wrong version.",
            "date": "2026-07-01",
            "date_modified": "2026-07-01",
            "publish_date": "2026-07-01",
            "author": "Daniel Zambrano",
            "tags": ["cv-format", "australia", "usa", "international-jobs", "region-specific"],
            "faq": [
                {"q": "Can I use the same CV when applying to jobs in Australia and the US?", "a": "Not without adjustment. The differences aren't just cosmetic — date formats, reference expectations, photo rules, document length, and tone all vary. A US resume sent to an Australian employer looks too short and misses expected sections. An Australian CV sent to a US employer includes details that US hiring managers aren't used to seeing."},
                {"q": "Do Australian employers expect references?", "a": "Yes. Including two or three professional referees (name, title, company, contact details) is standard practice in Australia. US resumes typically omit references entirely, with 'references available upon request' being the maximum. In Australia, omitting referees looks unusual."},
                {"q": "What is the right length for an Australian CV?", "a": "Two to three pages for most professionals. One page is generally too short and reads as incomplete. Unlike the strict US one-page convention for early-career candidates, Australian hiring managers expect a more comprehensive document and will read further if the content is strong."},
            ],
        },
        {
            "slug": "why-just-network-more-is-bad-advice",
            "title": "Why 'Just Network More' Is Terrible Advice (And What Actually Works)",
            "description": "The standard career advice ignores introversion, access, and time. Here's why networking works for some people and fails for most — and what to do instead.",
            "date": "2026-06-15",
            "date_modified": "2026-06-15",
            "publish_date": "2026-06-15",
            "author": "Daniel Zambrano",
            "tags": ["networking", "career-advice", "job-search", "career-development"],
            "faq": [
                {"q": "Does networking really matter for finding a job?", "a": "Yes — but not in the way the advice usually frames it. Roughly 70–80% of roles are filled without being publicly advertised, and many of those go to known candidates. But 'networking your way in' requires having the right network, and building that network requires time and access that not everyone has equally."},
                {"q": "How do introverts network effectively?", "a": "One-to-one conversations, online and asynchronous formats, and professional communities built around shared work (open source, industry forums, alumni groups) tend to work better for introverts than large events. Quality over volume applies here too — one strong professional relationship is worth more than fifty LinkedIn connections you've never spoken to."},
                {"q": "Is cold outreach on LinkedIn effective?", "a": "Sometimes. The success rate is low but non-zero, and it improves significantly with personalisation. Reaching out with a specific reason — you read their article, you have a question relevant to their work, you share a connection or background — performs far better than 'I'm looking for opportunities and admire your company.'"},
            ],
        },
        {
            "slug": "how-ats-scores-your-cv",
            "title": "How ATS Scores Your CV (And the 5 Things That Tank It)",
            "description": "Applicant Tracking Systems aren't mysterious black boxes — they do a specific job in a specific way. Here's how ATS scoring actually works, and the five formatting and content mistakes that cost you the most.",
            "date": "2026-06-01",
            "date_modified": "2026-06-01",
            "publish_date": "2026-06-01",
            "author": "Daniel Zambrano",
            "tags": ["ats", "cv-tips", "job-search", "formatting"],
            "faq": [
                {"q": "Does ATS actually read my PDF?", "a": "Most modern ATS platforms can parse PDFs, but not all — and even those that can will sometimes extract text incorrectly from complex layouts. A standard, well-formatted PDF from a modern word processor is generally fine. PDFs generated from design tools (Canva, Adobe InDesign) with layered graphics or unusual fonts are not."},
                {"q": "What keywords should I include in my CV?", "a": "The keywords from the specific job description you're applying to. There's no universal list — a DevOps engineer applying to AWS-heavy shops needs different keywords than one applying to on-premise enterprise environments. Mirror the language the posting uses: if they say 'Kubernetes', use 'Kubernetes', not just 'container orchestration'."},
                {"q": "Do all companies use ATS?", "a": "Larger companies and those with high application volumes almost universally do. Small companies and startups often review CVs manually, especially at early hiring stages. If you're applying to a twenty-person startup through a direct email or referral, ATS optimisation is less critical — but clean formatting and relevant content still matter to the human reader."},
            ],
        },
        {
            "slug": "10-point-cv-checklist",
            "title": "The 10-Point CV Checklist Before You Hit Send",
            "description": "Most CV mistakes are fixed in under ten minutes. This is the checklist to run through before you submit any application — the ten things that are most often wrong and easiest to miss.",
            "date": "2026-05-15",
            "date_modified": "2026-05-15",
            "publish_date": "2026-05-15",
            "author": "Daniel Zambrano",
            "tags": ["cv-tips", "cv-checklist", "job-search", "ats", "diy"],
            "faq": [
                {"q": "How long should I spend checking my CV before applying?", "a": "For your base CV, a thorough review once is enough. For each tailored application, ten to fifteen minutes to check keyword alignment, update the summary, and verify contact details is a reasonable investment for a role you actually want."},
                {"q": "What format should I save my CV as?", "a": "PDF, unless the job posting specifically requests DOCX. PDF preserves your formatting across systems and looks the same everywhere. Name the file clearly: FirstName-LastName-CV.pdf, not 'CV-final-v3-USE-THIS-ONE.pdf'."},
                {"q": "Do I really need a different CV for each job?", "a": "Not completely different — but tailored, yes. Your core sections (work history, education) stay the same. What you tailor: the professional summary, the skills section, and which achievements you lead with in each role. The tailoring takes 10–15 minutes per application and consistently improves response rates."},
            ],
        },
        {
            "slug": "your-ats-is-fine-the-system-isnt",
            "title": "Your ATS Is Fine. The System Around It Isn't.",
            "description": "Recruiters say ATS isn't the problem — candidates just need to network more, build projects, get certified. They're not entirely wrong. But they're missing the bigger issue.",
            "date": "2026-05-01",
            "date_modified": "2026-05-01",
            "publish_date": "2026-05-01",
            "author": "Daniel Zambrano",
            "tags": ["ats", "job-search", "career-advice", "hiring"],
            "faq": [
                {"q": "Is ATS really the problem with modern hiring?", "a": "Partially. ATS systems do filter out qualified candidates when CVs aren't formatted or keyworded correctly. But they're also often blamed for outcomes that have more to do with the overall hiring volume, internal candidates, or basic supply-demand imbalance in a given field. The ATS is a tool — the system around it is the bigger story."},
                {"q": "What do recruiters actually want to see in a CV?", "a": "Evidence that you understand the role and have done it before (or something close). That means specific achievements over generic duties, language that mirrors the job posting, and a format that makes the relevant experience easy to find quickly. Recruiters spend seconds on a first pass — the job of your CV is to survive that pass."},
                {"q": "How much does networking actually help in a job search?", "a": "Significantly — but unevenly. Candidates with strong professional networks get referred to roles before they're posted, skip the ATS entirely, and have warmer introductions to hiring teams. Those without established networks face the full friction of the public application process. The advice to 'just network' ignores that networks take years to build and access to them is not equally distributed."},
            ],
        },
        {
            "slug": "cv-formats-around-the-world",
            "title": "CV Formats Around the World: Why One Resume Doesn't Work in 12 Countries",
            "description": "Your US resume isn't a German Lebenslauf. It isn't a Japanese rirekisho. Here's what actually changes country by country — and why sending the same CV everywhere quietly kills your application.",
            "date": "2026-04-16",
            "date_modified": "2026-04-16",
            "author": "Daniel Zambrano",
            "tags": ["cv-format", "international-jobs", "region-specific", "cv-tips"],
            "faq": [
                {
                    "q": "Are a CV and a resume the same thing?",
                    "a": "Depends where you are. In the US and Canada, a résumé is the short sales document and 'CV' is reserved for academic use. In the UK, Australia, and most of Europe, the word 'CV' is used for what Americans call a résumé. The formats also differ meaningfully — length, photo, personal details, and tone all vary by country.",
                },
                {
                    "q": "Do I need a different CV for every country I apply to?",
                    "a": "Yes, if you're applying across regions. A US résumé sent to a German employer looks incomplete (no photo, no date of birth, no signature). A German Lebenslauf sent to a US employer creates legal problems by including protected characteristics. Translating isn't enough — the format has to change.",
                },
                {
                    "q": "Which countries still expect a photo on a CV?",
                    "a": "Germany, France, Brazil, India, the UAE, and Japan generally expect or strongly prefer a professional photo. The US, UK, Canada, Australia, and New Zealand specifically do not — in those countries photos can trigger anti-discrimination concerns and are routinely stripped by recruiters.",
                },
                {
                    "q": "How long should a CV be in each country?",
                    "a": "One page in the US for under a decade of experience; two pages elsewhere. Two to three pages is standard in the UK, Australia, Germany, and France. Indian CVs run two to four pages. Japanese rirekisho are form-bound so length isn't really a choice.",
                },
                {
                    "q": "Do I need to translate my CV or rewrite it?",
                    "a": "Rewrite it. Translating is the most common mistake — the words land, but the format, fields, and tone will all be wrong for the target country. A good multi-country CV tool will produce the right format per region, not just a translated version of the same document.",
                },
            ],
        },
        {
            "slug": "why-ai-cover-letters-get-ignored",
            "title": "Why Most AI Cover Letters Get Ignored (and How to Fix Yours)",
            "description": "Generic openings, fabricated achievements, and copy-paste enthusiasm. The three ways AI cover letters fail — and what actually gets a recruiter to read past the first paragraph.",
            "date": "2026-04-16",
            "date_modified": "2026-04-16",
            "author": "Daniel Zambrano",
            "tags": ["cover-letters", "ai-writing", "job-applications", "career-advice"],
            "faq": [
                {
                    "q": "Are AI-generated cover letters effective in 2026?",
                    "a": "Only if used carefully. A cover letter written with AI defaults — generic opener, invented metrics, LinkedIn-style enthusiasm — gets filtered instantly because recruiters now see hundreds of identical ones every week. AI is useful as a structuring and polishing tool, not as a content-generating one.",
                },
                {
                    "q": "Can hiring managers tell if a cover letter is written by AI?",
                    "a": "Often yes, because AI models converge on similar phrasings for similar prompts. Openers like 'I am writing to express my keen interest' and 'with over a decade of experience' appear in dozens of cover letters per week and function as immediate signal that the candidate didn't personalise the draft.",
                },
                {
                    "q": "What's the biggest mistake people make with AI cover letters?",
                    "a": "Fabricated achievements. When the AI is given a vague prompt it invents plausible-sounding metrics that the candidate can't defend in an interview. Always feed the AI your actual achievements and let it help you phrase them — never let it invent numbers.",
                },
                {
                    "q": "Should I include a cover letter if the job says it's optional?",
                    "a": "If it's a role you actually want, yes. A short, specific cover letter differentiates you from the majority who skip it or send a generic one. The key word is 'specific' — a generic cover letter signals less effort than no cover letter at all.",
                },
                {
                    "q": "How do I make an AI cover letter sound authentic?",
                    "a": "Give the AI real context — your specific achievements, the specific job posting, and the company's tone. Then edit the output: the opening line should reference something only this company would care about; the middle should use your actual numbers; the tone should match the company's voice, not LinkedIn's.",
                },
            ],
        },
        {
            "slug": "why-auto-apply-is-hurting-your-job-search",
            "title": "Why Auto-Apply Tools Are Hurting Your Job Search",
            "description": "Mass-applying to hundreds of jobs sounds efficient, but it kills your chances. Here's why intentional, tailored applications still win — and how to do it without the grind.",
            "date": "2026-03-28",
            "date_modified": "2026-03-28",
            "author": "Daniel Zambrano",
            "tags": ["job-search", "cv-tips", "career-advice", "ats"],
            "faq": [
                {
                    "q": "Do auto-apply tools actually work for job searching?",
                    "a": "Generally no. Mass-applying sends generic CVs that score poorly in Applicant Tracking Systems and signal low interest to hiring managers. Tailored applications consistently outperform high-volume generic ones.",
                },
                {
                    "q": "How many jobs should I apply to per week?",
                    "a": "Quality matters more than quantity. Ten well-researched, tailored applications will outperform two hundred generic ones. Focus on roles you genuinely want and customise your CV for each.",
                },
                {
                    "q": "Why does my CV get rejected by ATS systems?",
                    "a": "ATS systems scan for specific keywords and phrases from the job description. A generic CV that hasn't been tailored to the posting will score low, even if you're highly qualified for the role.",
                },
                {
                    "q": "What's the best way to tailor a CV for each job?",
                    "a": "Read the full job description, identify the key skills and requirements, and adjust your CV to emphasise matching experience. Use the same language the posting uses. Tools like QuillCV can automate this tailoring using AI.",
                },
                {
                    "q": "Is it worth spending more time on fewer job applications?",
                    "a": "Yes. Hiring managers can immediately spot generic applications. A thoughtful application that addresses the specific role and company stands out far more than volume ever will.",
                },
            ],
        },
        {
            "slug": "why-pii-matters-in-cv-builders",
            "title": "Why Your Personal Information Matters More Than You Think When Building a CV",
            "description": "Most CV builders ask for sensitive details — your address, phone, ID number. Here's why that should concern you, and what to look for.",
            "date": "2026-03-15",
            "date_modified": "2026-03-15",
            "author": "Daniel Zambrano",
            "tags": ["privacy", "cv-tips", "data-protection"],
            "faq": [
                {
                    "q": "Can I delete my data completely from a CV builder?",
                    "a": "Look for platforms that offer true deletion — not just account deactivation. Your data should be removed from the database, backups, and analytics systems when you delete your account.",
                },
                {
                    "q": "Should my personal information be encrypted in a CV builder?",
                    "a": "Yes. Look for encryption at rest, ideally with a key derived from your password so even the platform operator cannot read your personal details.",
                },
                {
                    "q": "Do CV builders sell data to third parties?",
                    "a": "Some do. Check the privacy policy for terms like 'partners', 'affiliates', or 'third-party services'. If the language is vague, assume the worst.",
                },
                {
                    "q": "What happens to my CV data after I cancel?",
                    "a": "Many platforms retain data for 30 days or more after cancellation. Look for platforms with zero-retention policies that delete data immediately.",
                },
                {
                    "q": "Do CV builders use my resume to train AI?",
                    "a": "Some platforms use uploaded CVs as training data. Look for platforms that explicitly state they do not train AI models on user content.",
                },
            ],
        },
    ],
    "es": [
        {
            "slug": "formatos-de-cv-en-el-mundo",
            "title": "Formatos de CV en el Mundo: Por Qué Un Solo Currículum No Funciona en 12 Países",
            "description": "Tu CV estadounidense no es un Lebenslauf alemán. No es un rirekisho japonés. Acá te contamos qué cambia realmente país por país — y por qué mandar el mismo CV a todas partes arruina tu postulación en silencio.",
            "date": "2026-04-16",
            "date_modified": "2026-04-16",
            "author": "Daniel Zambrano",
            "tags": ["formato-cv", "trabajo-internacional", "cv-por-país", "consejos-cv"],
            "faq": [
                {
                    "q": "¿Por qué en EE.UU. usan la palabra 'resume' en vez de 'CV'?",
                    "a": "En inglés estadounidense, 'resume' (del francés 'résumé') es el documento corto de ventas profesional, y 'CV' se reserva para uso académico. En el resto del mundo, 'CV' es el término habitual para ambos casos. Más allá del nombre, el formato cambia: extensión, foto, datos personales y tono varían según el país.",
                },
                {
                    "q": "¿Necesito un CV diferente para cada país al que postule?",
                    "a": "Sí, si postulás a varias regiones. Un CV estadounidense enviado a un empleador alemán parece incompleto (sin foto, sin fecha de nacimiento, sin firma). Un Lebenslauf alemán enviado a un empleador estadounidense genera problemas legales al incluir características protegidas. Traducir no alcanza — el formato tiene que cambiar.",
                },
                {
                    "q": "¿Qué países todavía esperan foto en el CV?",
                    "a": "Alemania, Francia, Brasil, India, EAU y Japón generalmente esperan o prefieren fuertemente una foto profesional. EE.UU., Reino Unido, Canadá, Australia y Nueva Zelanda específicamente no — en esos países las fotos pueden generar problemas de discriminación y las eliminan los reclutadores.",
                },
                {
                    "q": "¿Qué extensión debe tener un CV en cada país?",
                    "a": "Una página en EE.UU. para menos de una década de experiencia; dos páginas en otras partes. Dos o tres páginas es estándar en Reino Unido, Australia, Alemania y Francia. Los CVs indios tienen de dos a cuatro páginas. Los rirekisho japoneses usan un formulario estandarizado, así que la extensión no se elige.",
                },
                {
                    "q": "¿Tengo que traducir mi CV o reescribirlo?",
                    "a": "Reescribirlo. Traducir es el error más común — las palabras funcionan, pero el formato, los campos y el tono van a estar mal para el país objetivo. Una buena herramienta multi-país produce el formato correcto por región, no sólo una versión traducida del mismo documento.",
                },
            ],
        },
        {
            "slug": "por-que-ignoran-tus-cartas-de-presentacion-con-ia",
            "title": "Por Qué Ignoran la Mayoría de las Cartas de Presentación con IA (y Cómo Arreglar la Tuya)",
            "description": "Aperturas genéricas, logros inventados y entusiasmo copiado. Las tres formas en que las cartas con IA fallan — y qué hace que un reclutador pase del primer párrafo.",
            "date": "2026-04-16",
            "date_modified": "2026-04-16",
            "author": "Daniel Zambrano",
            "tags": ["carta-de-presentación", "ia-redacción", "postulaciones", "carrera-profesional"],
            "faq": [
                {
                    "q": "¿Son efectivas las cartas de presentación generadas con IA en 2026?",
                    "a": "Sólo si se usan con cuidado. Una carta escrita con los defaults de IA — apertura genérica, métricas inventadas, entusiasmo al estilo LinkedIn — se filtra al instante porque los reclutadores hoy ven cientos iguales por semana. La IA es útil como herramienta para estructurar y pulir, no como generadora de contenido.",
                },
                {
                    "q": "¿Pueden los reclutadores detectar si una carta fue escrita por IA?",
                    "a": "Con frecuencia sí, porque los modelos de IA convergen en frases parecidas ante prompts parecidos. Aperturas como 'Por medio de la presente expreso mi marcado interés' y 'con más de una década de experiencia' aparecen en decenas de cartas por semana y funcionan como señal inmediata de que el candidato no personalizó el borrador.",
                },
                {
                    "q": "¿Cuál es el error más grande con las cartas con IA?",
                    "a": "Inventar logros. Cuando le das a la IA un prompt vago, inventa métricas verosimiles pero falsas que no podés defender en una entrevista. Alimentá siempre a la IA con tus logros reales y dejale que te ayude a redactarlos — nunca la dejes inventar números.",
                },
                {
                    "q": "¿Debo incluir carta de presentación si la oferta dice que es opcional?",
                    "a": "Si es un rol que realmente te interesa, sí. Una carta corta y específica te diferencia de la mayoría que la omite o manda una genérica. La palabra clave es 'específica' — una carta genérica señala menos esfuerzo que no enviar ninguna.",
                },
                {
                    "q": "¿Cómo hago que una carta con IA suene auténtica?",
                    "a": "Dale a la IA contexto real — tus logros específicos, la oferta específica, y el tono de la empresa. Después editá la salida: la primera línea debe referir algo que sólo a esta empresa le importe; el medio debe usar tus números reales; el tono debe coincidir con la voz de la empresa, no con LinkedIn.",
                },
            ],
        },
        {
            "slug": "por-que-aplicar-en-masa-perjudica-tu-busqueda-de-empleo",
            "title": "Por Qué Aplicar en Masa Perjudica Tu Búsqueda de Empleo",
            "description": "Las herramientas de postulación automática prometen enviar cientos de solicitudes, pero arruinan tus chances. Descubrí por qué las postulaciones pensadas siguen ganando.",
            "date": "2026-03-28",
            "date_modified": "2026-03-28",
            "author": "Daniel Zambrano",
            "tags": ["búsqueda-de-empleo", "consejos-cv", "carrera-profesional", "ats"],
            "faq": [
                {
                    "q": "¿Las herramientas de postulación automática realmente funcionan?",
                    "a": "En general no. Postular en masa envía CVs genéricos que puntúan bajo en los sistemas de seguimiento de candidatos y señalan poco interés a los reclutadores. Las postulaciones personalizadas consistentemente superan a las genéricas de alto volumen.",
                },
                {
                    "q": "¿A cuántos trabajos debería postularme por semana?",
                    "a": "La calidad importa más que la cantidad. Diez postulaciones bien investigadas y personalizadas superan a doscientas genéricas. Enfocate en puestos que realmente te interesen y adaptá tu CV para cada uno.",
                },
                {
                    "q": "¿Por qué mi CV es rechazado por los sistemas ATS?",
                    "a": "Los sistemas ATS buscan palabras clave y frases específicas de la descripción del puesto. Un CV genérico que no fue adaptado a la oferta puntúa bajo, incluso si estás altamente calificado para el rol.",
                },
                {
                    "q": "¿Cuál es la mejor forma de adaptar un CV para cada trabajo?",
                    "a": "Leé la descripción completa del puesto, identificá las habilidades y requisitos clave, y ajustá tu CV para enfatizar la experiencia que coincide. Usá el mismo lenguaje que usa la oferta. Herramientas como QuillCV pueden automatizar esta adaptación con IA.",
                },
                {
                    "q": "¿Vale la pena dedicar más tiempo a menos postulaciones?",
                    "a": "Sí. Los reclutadores detectan las postulaciones genéricas al instante. Una postulación pensada que aborda el puesto y la empresa específica se destaca mucho más que el volumen.",
                },
            ],
        },
        {
            "slug": "por-que-importan-tus-datos-personales-en-un-cv",
            "title": "Por Qué Tus Datos Personales Importan Más de lo Que Crees al Crear un CV",
            "description": "La mayoría de los creadores de CV piden datos sensibles — tu dirección, teléfono, número de identificación. Aquí te explicamos por qué debería importarte y qué buscar.",
            "date": "2026-03-15",
            "date_modified": "2026-03-15",
            "author": "Daniel Zambrano",
            "tags": ["privacidad", "consejos-cv", "protección-de-datos"],
            "faq": [
                {
                    "q": "¿Puedo eliminar mis datos completamente de un creador de CV?",
                    "a": "Busca plataformas que ofrezcan eliminación real, no solo desactivación de cuenta. Tus datos deben borrarse de la base de datos, las copias de seguridad y los sistemas de analítica cuando eliminas tu cuenta.",
                },
                {
                    "q": "¿Debería estar cifrada mi información personal en un creador de CV?",
                    "a": "Sí. Busca cifrado en reposo, idealmente con una clave derivada de tu contraseña para que ni el propio operador de la plataforma pueda leer tus datos personales.",
                },
                {
                    "q": "¿Los creadores de CV venden datos a terceros?",
                    "a": "Algunos sí. Revisa la política de privacidad en busca de términos como 'socios', 'afiliados' o 'servicios de terceros'. Si el lenguaje es vago, asume lo peor.",
                },
                {
                    "q": "¿Qué pasa con mis datos después de cancelar?",
                    "a": "Muchas plataformas retienen los datos durante 30 días o más tras la cancelación. Busca plataformas con políticas de retención cero que eliminen los datos de inmediato.",
                },
                {
                    "q": "¿Los creadores de CV usan mi currículum para entrenar IA?",
                    "a": "Algunas plataformas usan los CVs subidos como datos de entrenamiento. Busca plataformas que indiquen explícitamente que no entrenan modelos de IA con el contenido de los usuarios.",
                },
            ],
        },
    ],
    "pt": [
        {
            "slug": "formatos-de-curriculo-pelo-mundo",
            "title": "Formatos de Currículo pelo Mundo: Por Que Um Único Currículo Não Funciona em 12 Países",
            "description": "Seu currículo americano não é um Lebenslauf alemão. Não é um rirekisho japonês. Veja o que realmente muda país a país — e por que mandar o mesmo currículo para todo lado mata sua candidatura em silêncio.",
            "date": "2026-04-16",
            "date_modified": "2026-04-16",
            "author": "Daniel Zambrano",
            "tags": ["formato-currículo", "trabalho-internacional", "currículo-por-país", "dicas-cv"],
            "faq": [
                {
                    "q": "Por que nos EUA usam a palavra 'resume' em vez de 'CV'?",
                    "a": "Em inglês americano, 'resume' (do francês 'résumé') é o documento curto de vendas profissional, e 'CV' é reservado para uso acadêmico. No resto do mundo, 'CV' é o termo usado em ambos os casos. Além do nome, o formato muda: extensão, foto, dados pessoais e tom variam conforme o país.",
                },
                {
                    "q": "Preciso de um currículo diferente para cada país?",
                    "a": "Sim, se você se candidata em várias regiões. Um currículo americano enviado a um empregador alemão parece incompleto (sem foto, sem data de nascimento, sem assinatura). Um Lebenslauf alemão enviado a um empregador americano gera problemas legais por incluir características protegidas. Traduzir não basta — o formato precisa mudar.",
                },
                {
                    "q": "Quais países ainda esperam foto no currículo?",
                    "a": "Alemanha, França, Brasil, Índia, EAU e Japão geralmente esperam ou preferem fortemente uma foto profissional. EUA, Reino Unido, Canadá, Austrália e Nova Zelândia especificamente não — nesses países fotos podem gerar problemas de discriminação e são removidas pelos recrutadores.",
                },
                {
                    "q": "Qual a extensão de um currículo em cada país?",
                    "a": "Uma página nos EUA para menos de uma década de experiência; duas páginas em outros lugares. Duas a três páginas é padrão em Reino Unido, Austrália, Alemanha e França. Currículos indianos têm de duas a quatro páginas. Os rirekisho japoneses usam um formulário padronizado, então a extensão não é uma escolha.",
                },
                {
                    "q": "Preciso traduzir meu currículo ou reescrevê-lo?",
                    "a": "Reescrever. Traduzir é o erro mais comum — as palavras funcionam, mas o formato, os campos e o tom vão estar errados para o país-alvo. Uma boa ferramenta multi-país produz o formato certo por região, não apenas uma versão traduzida do mesmo documento.",
                },
            ],
        },
        {
            "slug": "por-que-ignoram-suas-cartas-de-apresentacao-com-ia",
            "title": "Por Que Ignoram a Maioria das Cartas de Apresentação com IA (e Como Arrumar a Sua)",
            "description": "Aberturas genéricas, realizações inventadas e entusiasmo copiado. As três formas pelas quais cartas com IA falham — e o que faz um recrutador ler além do primeiro parágrafo.",
            "date": "2026-04-16",
            "date_modified": "2026-04-16",
            "author": "Daniel Zambrano",
            "tags": ["carta-de-apresentação", "ia-escrita", "candidaturas", "carreira-profissional"],
            "faq": [
                {
                    "q": "Cartas de apresentação geradas por IA são eficazes em 2026?",
                    "a": "Só se usadas com cuidado. Uma carta escrita com defaults de IA — abertura genérica, métricas inventadas, entusiasmo estilo LinkedIn — é filtrada na hora porque os recrutadores hoje veem centenas iguais por semana. A IA é útil como ferramenta para estruturar e polir, não como geradora de conteúdo.",
                },
                {
                    "q": "Os recrutadores conseguem detectar se uma carta foi escrita por IA?",
                    "a": "Muitas vezes sim, porque modelos de IA convergem para frases parecidas em prompts parecidos. Aberturas como 'Venho por meio desta expressar meu grande interesse' e 'com mais de uma década de experiência' aparecem em dezenas de cartas por semana e funcionam como sinal imediato de que o candidato não personalizou o rascunho.",
                },
                {
                    "q": "Qual o maior erro com cartas de IA?",
                    "a": "Inventar realizações. Quando você dá à IA um prompt vago, ela inventa métricas plausíveis, porém falsas, que você não consegue defender numa entrevista. Alimente sempre a IA com suas realizações reais e deixe que ela te ajude a formular — nunca deixe que invente números.",
                },
                {
                    "q": "Devo incluir carta de apresentação se a vaga diz que é opcional?",
                    "a": "Se é uma vaga que você realmente quer, sim. Uma carta curta e específica te diferencia da maioria que pula ou manda uma genérica. A palavra-chave é 'específica' — uma carta genérica sinaliza menos esforço do que não enviar nenhuma.",
                },
                {
                    "q": "Como faço uma carta com IA soar autêntica?",
                    "a": "Dê à IA contexto real — suas realizações específicas, a vaga específica, e o tom da empresa. Depois edite a saída: a primeira linha deve citar algo que só essa empresa se importaria; o meio deve usar seus números reais; o tom deve combinar com a voz da empresa, não com a do LinkedIn.",
                },
            ],
        },
        {
            "slug": "por-que-se-candidatar-em-massa-prejudica-sua-busca-de-emprego",
            "title": "Por Que Se Candidatar em Massa Prejudica Sua Busca de Emprego",
            "description": "Ferramentas de candidatura automática prometem enviar centenas de candidaturas, mas destroem suas chances. Entenda por que candidaturas pensadas ainda vencem.",
            "date": "2026-03-28",
            "date_modified": "2026-03-28",
            "author": "Daniel Zambrano",
            "tags": ["busca-de-emprego", "dicas-cv", "carreira-profissional", "ats"],
            "faq": [
                {
                    "q": "Ferramentas de candidatura automática realmente funcionam?",
                    "a": "No geral, não. Candidatar-se em massa envia currículos genéricos que pontuam baixo nos sistemas de rastreamento de candidatos e sinalizam pouco interesse aos recrutadores. Candidaturas personalizadas consistentemente superam as genéricas de alto volume.",
                },
                {
                    "q": "A quantas vagas devo me candidatar por semana?",
                    "a": "Qualidade importa mais que quantidade. Dez candidaturas bem pesquisadas e personalizadas superam duzentas genéricas. Foque em vagas que realmente te interessam e adapte seu currículo para cada uma.",
                },
                {
                    "q": "Por que meu currículo é rejeitado pelos sistemas ATS?",
                    "a": "Sistemas ATS procuram palavras-chave e frases específicas da descrição da vaga. Um currículo genérico que não foi adaptado à vaga pontua baixo, mesmo que você seja altamente qualificado para o cargo.",
                },
                {
                    "q": "Qual a melhor forma de adaptar um currículo para cada vaga?",
                    "a": "Leia a descrição completa da vaga, identifique as habilidades e requisitos-chave, e ajuste seu currículo para enfatizar a experiência relevante. Use a mesma linguagem da vaga. Ferramentas como QuillCV podem automatizar essa adaptação com IA.",
                },
                {
                    "q": "Vale a pena dedicar mais tempo a menos candidaturas?",
                    "a": "Sim. Recrutadores identificam candidaturas genéricas na hora. Uma candidatura pensada que aborda o cargo e a empresa específica se destaca muito mais do que volume.",
                },
            ],
        },
        {
            "slug": "por-que-seus-dados-pessoais-importam-em-um-curriculo",
            "title": "Por Que Seus Dados Pessoais Importam Mais do Que Você Imagina ao Criar um Currículo",
            "description": "A maioria dos criadores de currículo pede dados sensíveis — seu endereço, telefone, número de identificação. Veja por que isso deve te preocupar e o que procurar.",
            "date": "2026-03-15",
            "date_modified": "2026-03-15",
            "author": "Daniel Zambrano",
            "tags": ["privacidade", "dicas-cv", "proteção-de-dados"],
            "faq": [
                {
                    "q": "Consigo excluir meus dados completamente de um criador de currículo?",
                    "a": "Procure plataformas que ofereçam exclusão de verdade — não apenas desativação de conta. Seus dados devem ser removidos do banco de dados, dos backups e dos sistemas de análise quando você exclui sua conta.",
                },
                {
                    "q": "Minhas informações pessoais devem ser criptografadas em um criador de currículo?",
                    "a": "Sim. Procure criptografia em repouso, idealmente com uma chave derivada da sua senha, para que nem o operador da plataforma consiga ler seus dados pessoais.",
                },
                {
                    "q": "Os criadores de currículo vendem dados para terceiros?",
                    "a": "Alguns vendem. Verifique a política de privacidade em busca de termos como 'parceiros', 'afiliados' ou 'serviços de terceiros'. Se a linguagem for vaga, presuma o pior.",
                },
                {
                    "q": "O que acontece com meus dados depois que cancelo?",
                    "a": "Muitas plataformas retêm dados por 30 dias ou mais após o cancelamento. Procure plataformas com políticas de retenção zero que excluam os dados imediatamente.",
                },
                {
                    "q": "Os criadores de currículo usam meu currículo para treinar IA?",
                    "a": "Algumas plataformas usam currículos enviados como dados de treinamento. Procure plataformas que declarem explicitamente que não treinam modelos de IA com o conteúdo dos usuários.",
                },
            ],
        },
    ],
}

# Maps (lang, slug) -> {other_lang: other_slug} for hreflang on post pages
TRANSLATIONS = {
    ("en", "cv-formats-around-the-world"): {
        "es": "formatos-de-cv-en-el-mundo",
        "pt": "formatos-de-curriculo-pelo-mundo",
    },
    ("es", "formatos-de-cv-en-el-mundo"): {
        "en": "cv-formats-around-the-world",
        "pt": "formatos-de-curriculo-pelo-mundo",
    },
    ("pt", "formatos-de-curriculo-pelo-mundo"): {
        "en": "cv-formats-around-the-world",
        "es": "formatos-de-cv-en-el-mundo",
    },
    ("en", "why-ai-cover-letters-get-ignored"): {
        "es": "por-que-ignoran-tus-cartas-de-presentacion-con-ia",
        "pt": "por-que-ignoram-suas-cartas-de-apresentacao-com-ia",
    },
    ("es", "por-que-ignoran-tus-cartas-de-presentacion-con-ia"): {
        "en": "why-ai-cover-letters-get-ignored",
        "pt": "por-que-ignoram-suas-cartas-de-apresentacao-com-ia",
    },
    ("pt", "por-que-ignoram-suas-cartas-de-apresentacao-com-ia"): {
        "en": "why-ai-cover-letters-get-ignored",
        "es": "por-que-ignoran-tus-cartas-de-presentacion-con-ia",
    },
    ("en", "why-auto-apply-is-hurting-your-job-search"): {
        "es": "por-que-aplicar-en-masa-perjudica-tu-busqueda-de-empleo",
        "pt": "por-que-se-candidatar-em-massa-prejudica-sua-busca-de-emprego",
    },
    ("es", "por-que-aplicar-en-masa-perjudica-tu-busqueda-de-empleo"): {
        "en": "why-auto-apply-is-hurting-your-job-search",
        "pt": "por-que-se-candidatar-em-massa-prejudica-sua-busca-de-emprego",
    },
    ("pt", "por-que-se-candidatar-em-massa-prejudica-sua-busca-de-emprego"): {
        "en": "why-auto-apply-is-hurting-your-job-search",
        "es": "por-que-aplicar-en-masa-perjudica-tu-busqueda-de-empleo",
    },
    ("en", "why-pii-matters-in-cv-builders"): {
        "es": "por-que-importan-tus-datos-personales-en-un-cv",
        "pt": "por-que-seus-dados-pessoais-importam-em-um-curriculo",
    },
    ("es", "por-que-importan-tus-datos-personales-en-un-cv"): {
        "en": "why-pii-matters-in-cv-builders",
        "pt": "por-que-seus-dados-pessoais-importam-em-um-curriculo",
    },
    ("pt", "por-que-seus-dados-pessoais-importam-em-um-curriculo"): {
        "en": "why-pii-matters-in-cv-builders",
        "es": "por-que-importan-tus-datos-personales-en-un-cv",
    },
}

# Index-level i18n strings passed to the template
INDEX_STRINGS = {
    "en": {
        "title": "The QuillCV Blog",
        "tagline": "tips, privacy, and career advice",
        "read_more": "Read more \u2192",
        "page_title": "Blog \u2014 QuillCV | CV Tips, Privacy & Career Advice",
        "page_description": "Tips, privacy advice, and career insights from the QuillCV team.",
    },
    "es": {
        "title": "El Blog de QuillCV",
        "tagline": "consejos, privacidad y carrera profesional",
        "read_more": "Leer más \u2192",
        "page_title": "Blog \u2014 QuillCV | Consejos de CV, Privacidad y Carrera",
        "page_description": "Consejos, privacidad y orientación profesional del equipo de QuillCV.",
    },
    "pt": {
        "title": "O Blog do QuillCV",
        "tagline": "dicas, privacidade e carreira profissional",
        "read_more": "Ler mais \u2192",
        "page_title": "Blog \u2014 QuillCV | Dicas de Currículo, Privacidade e Carreira",
        "page_description": "Dicas, privacidade e orientação profissional da equipe do QuillCV.",
    },
}

_POSTS_BY_LANG_SLUG: dict[str, dict[str, dict]] = {
    lang: {p["slug"]: p for p in posts}
    for lang, posts in POSTS.items()
}


@router.get("/blog", response_class=HTMLResponse)
async def blog_redirect():
    return RedirectResponse("/blog/en", status_code=301)


@router.get("/blog/{lang}", response_class=HTMLResponse)
async def blog_index(request: Request, lang: str):
    if lang not in SUPPORTED_LANGS:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "message": "Language not supported."},
            status_code=404,
        )

    strings = INDEX_STRINGS[lang]
    alternate_urls = {lang: f"/blog/{lang}" for lang in SUPPORTED_LANGS}
    dev_mode = getattr(request.app.state, "dev_mode", False)
    today = date.today().isoformat()
    lang_posts = sorted(
        [p for p in POSTS[lang] if dev_mode or p.get("publish_date", p["date"]) <= today],
        key=lambda p: p.get("publish_date", p["date"]),
        reverse=True,
    )
    page_description = strings["page_description"]
    in_language_map = {"en": "en", "es": "es", "pt": "pt-BR"}

    structured_data = {
        "@context": "https://schema.org",
        "@type": "Blog",
        "name": strings["title"],
        "url": f"https://quillcv.com/blog/{lang}",
        "description": page_description,
        "inLanguage": in_language_map.get(lang, lang),
        "publisher": {
            "@type": "Organization",
            "name": "QuillCV",
            "url": "https://quillcv.com",
        },
        "blogPost": [
            {
                "@type": "BlogPosting",
                "headline": p["title"],
                "url": f"https://quillcv.com/blog/{lang}/{p['slug']}",
                "datePublished": p["date"],
            }
            for p in lang_posts
        ],
    }

    response = templates.TemplateResponse(
        "blog_index.html",
        {
            "request": request,
            "lang": lang,
            "lang_labels": LANG_LABELS,
            "supported_langs": SUPPORTED_LANGS,
            "posts": lang_posts,
            "strings": strings,
            "alternate_urls": alternate_urls,
            "page_title": strings["page_title"],
            "page_description": page_description,
            "structured_data": structured_data,
            "html_lang": in_language_map.get(lang, lang),
        },
    )
    response.headers["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=3600"
    return response


@router.get("/blog/{lang}/{slug}", response_class=HTMLResponse)
async def blog_post(request: Request, lang: str, slug: str):
    if lang not in SUPPORTED_LANGS:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "message": "Language not supported."},
            status_code=404,
        )

    post = _POSTS_BY_LANG_SLUG.get(lang, {}).get(slug)
    if post is None:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "message": "Post not found."},
            status_code=404,
        )

    dev_mode = getattr(request.app.state, "dev_mode", False)
    today = date.today().isoformat()
    if not dev_mode and post.get("publish_date", post["date"]) > today:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "message": "Post not found."},
            status_code=404,
        )

    # Build alternate_urls for hreflang and language switcher
    translation_map = TRANSLATIONS.get((lang, slug), {})
    alternate_urls: dict[str, str] = {lang: f"/blog/{lang}/{slug}"}
    for other_lang, other_slug in translation_map.items():
        alternate_urls[other_lang] = f"/blog/{other_lang}/{other_slug}"

    in_language_map = {"en": "en", "es": "es", "pt": "pt-BR"}
    blog_index_names = {"en": "Blog", "es": "Blog", "pt": "Blog"}

    breadcrumb_schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://quillcv.com"},
            {"@type": "ListItem", "position": 2, "name": blog_index_names.get(lang, "Blog"), "item": f"https://quillcv.com/blog/{lang}"},
            {"@type": "ListItem", "position": 3, "name": post["title"]},
        ],
    }

    blogposting_schema = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": post["title"],
        "description": post["description"],
        "datePublished": post["date"],
        "dateModified": post["date_modified"],
        "inLanguage": in_language_map.get(lang, lang),
        "author": {
            "@type": "Person",
            "name": post.get("author", "Daniel Zambrano"),
        },
        "publisher": {
            "@type": "Organization",
            "name": "QuillCV",
            "url": "https://quillcv.com",
        },
        "url": f"https://quillcv.com/blog/{lang}/{post['slug']}",
    }

    structured_data = [breadcrumb_schema, blogposting_schema]

    if post.get("faq"):
        structured_data.append({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": faq["q"],
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": faq["a"],
                    },
                }
                for faq in post["faq"]
            ],
        })

    response = templates.TemplateResponse(
        f"blog/{lang}/{slug}.html",
        {
            "request": request,
            "lang": lang,
            "lang_labels": LANG_LABELS,
            "supported_langs": SUPPORTED_LANGS,
            "post": post,
            "alternate_urls": alternate_urls,
            "page_title": f"{post['title']} — QuillCV Blog",
            "page_description": post["description"],
            "structured_data": structured_data,
            "html_lang": in_language_map.get(lang, lang),
        },
    )
    response.headers["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=3600"
    return response
