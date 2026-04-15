"""Blog routes: index listing and individual post pages — multilingual (EN, ES, PT)."""

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
    lang_posts = POSTS[lang]
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
