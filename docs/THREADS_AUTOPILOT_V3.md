# Threads Autopilot V3 — Threads-Only Content Engine

## Executive decision

Change the content engine from:

RSS/news → research → Threads post

to:

Threads keyword search → conversation mining → angle extraction → Indonesian Threads-native post

### Recommended positioning

**Tech + Internet Culture + Digital Work**

AI remains an important pillar, but the account is NOT an AI news account.

The account should feel like:

> a tech-curious Indonesian freelancer / internet worker noticing interesting things people are arguing about online.

The content should be driven by conversation, tension, relatability, curiosity, disagreement, and observations.

---

## Why this direction

The current repository already supports Threads keyword search, but treats Threads as `social` signal rather than the primary research source. `research.py` collects Threads items, while the generation prompt explicitly says `[S*]` is only social observation and the primary assignment is one post per `[R*]` research source.

This is the core reason the output still feels editorial/journalistic.

Current config also explicitly defines the niche around AI developments and their impact, which naturally biases the system toward explaining developments rather than participating in conversations.

Recent Indonesian Threads social-listening data supports a broader conversational niche:

- Productivity & work automation: large share and strong engagement.
- Business & entrepreneurship: high engagement.
- Career/job search: high reply potential.
- Creative content & side hustles: high engagement despite smaller volume.
- Critical/skeptical AI discussion: disproportionately strong engagement.
- Startup/AI conversations include AI tools, automation, vibe coding, SaaS and founder discussions.

Sources:
- Intura, ChatGPT Threads Indonesia Q1 2026.
- Intura, Indonesian ChatGPT Threads organic traffic 2025–2026.
- Intura, Startup Indonesia Threads social listening Q1 2026.

---

# 1. New content pillars

Use these as the main topic universe.

## P1 — AI in real life

Not AI news.

Focus on:
- AI changing how people work
- AI habits
- AI overuse
- AI skepticism
- useful vs useless AI
- AI replacing tasks rather than entire jobs
- AI-generated content fatigue
- people using AI badly
- weird AI behavior
- AI expectations vs reality

## P2 — Digital Work

- freelancing
- remote work
- clients
- pricing
- proposals
- portfolio
- getting work
- career changes
- junior vs senior
- digital skills
- workplace behavior
- async work
- productivity

## P3 — Builder / Tech Culture

- vibe coding
- coding with AI
- no-code / low-code
- SaaS
- indie hacking
- automation
- n8n
- AI agents
- developer tools
- shipping products
- "build in public"
- startup culture

## P4 — Internet Culture

- things people do online
- creator economy
- social media behavior
- algorithm anxiety
- personal branding
- online arguments
- digital status games
- internet trends
- weird business models
- "everyone is doing X now"

## P5 — Opportunity Radar

Not "cara cepat kaya".

Focus on:
- emerging digital work
- new services created by technology
- new creator formats
- new tools changing workflows
- under-discussed opportunities
- changing client expectations
- new skills becoming valuable

## P6 — Contrarian / Skeptical

This should be a meaningful share of the feed.

Examples:
- "Everyone says X. I'm not convinced."
- "This AI feature sounds useful until..."
- "Vibe coding solves one problem and creates another."
- "Remote work didn't remove office politics."
- "Personal branding is becoming another full-time job."

Do not manufacture controversy. The source conversation must contain a real tension.

---

# 2. Keyword universe

Do NOT search only broad keywords such as `AI`.

Broad queries create noise.

Use a rotating keyword pool.

## Tier A — high priority

```text
AI
ChatGPT
Claude
Gemini
AI agent
AI agents
vibe coding
AI coding
automation
freelance
freelancer
remote work
side hustle
creator
SaaS
startup
developer
coding
productivity
```

## Tier B — work / career

```text
kerja
freelance
freelancer
remote
remote work
WFH
kerja remote
job
jobs
career
karir
PHK
layoff
junior developer
senior developer
portfolio
CV
client
klien
pricing
rate
salary
gaji
```

## Tier C — creator / internet

```text
creator
content creator
personal branding
branding
content
konten
Threads
Instagram
TikTok
algorithm
algoritma
viral
engagement
followers
audience
creator economy
digital product
newsletter
```

## Tier D — builder

```text
vibe coding
Lovable
Bolt
Cursor
Claude Code
Codex
Replit
n8n
Make
Zapier
MCP
AI agent
micro SaaS
micro-SaaS
indie hacker
indie hacking
build in public
shipping
startup
SaaS
```

## Tier E — tension / discussion keywords

These are especially important because they search for conversations rather than subjects.

```text
hot take
unpopular opinion
am I the only one
I disagree
overrated
underrated
actually
honestly
nobody talks about
stop
why do people
is it just me
problem with
worst
best
changed my mind
I was wrong
not worth
worth it
```

## Tier F — Indonesian conversational terms

```text
menurut gue
menurutku
menurut kamu
nggak
ga
gak
aneh
jujur
ternyata
masalahnya
cape
capek
bingung
relate
setuju
nggak setuju
bener juga
sumpah
serius
```

These should be tested carefully because keyword-search behavior may be language-sensitive.

---

# 3. Query rotation

Do not fire all keywords every run.

Current code already limits Threads queries per run to 5.

Keep that safety limit initially.

Recommended:

### Run A — AI / tech
```text
AI
vibe coding
AI agents
ChatGPT
Claude
```

### Run B — work
```text
freelance
remote work
career
client
side hustle
```

### Run C — creator
```text
creator
personal branding
content
algorithm
creator economy
```

### Run D — builder
```text
SaaS
n8n
automation
indie hacker
build in public
```

### Run E — tension
```text
hot take
unpopular opinion
overrated
I disagree
worth it
```

Rotate query groups across generation runs rather than trying to search everything simultaneously.

---

# 4. New research pipeline

## Current

```text
RSS
Google News
HTML
X
Threads
    ↓
research.json
    ↓
articles = primary
social = secondary
    ↓
LLM
```

## V3

```text
Threads keyword search
        ↓
raw posts
        ↓
dedupe
        ↓
recency filter
        ↓
conversation scoring
        ↓
topic clustering
        ↓
angle extraction
        ↓
LLM writer
        ↓
Threads-native quality gate
        ↓
Telegram approval
```

No RSS.

No Google News.

No X.

No external article.

If a post needs factual verification, the generator should not silently fetch external sources. The account is participating in the conversation, not publishing a news report.

---

# 5. Conversation scoring

Each Threads result should receive an internal score.

Suggested fields:

```text
recency_score
conversation_score
relatability_score
tension_score
specificity_score
originality_score
topic_fit_score
```

Important principle:

**Do not optimize for likes alone.**

A post with 2,000 likes but no meaningful discussion may be less useful than a post with 300 likes and 500 replies.

If the API does not expose engagement metrics, use available signals such as:
- has_replies
- quote status
- timestamp
- search ranking (`TOP`)
- text patterns
- topic match

If engagement metrics become available through a supported API field later, add them as a scoring layer.

---

# 6. Conversation clustering

Do not generate one post per source.

That is another reason the old system feels like a news feed.

Instead:

```text
50 Threads posts
        ↓
cluster similar conversations
        ↓
Cluster: "AI is replacing junior devs"
Cluster: "vibe coding is surprisingly good"
Cluster: "AI makes people lazy"
Cluster: "remote work is weird"
        ↓
choose the most interesting cluster
        ↓
write ONE post
```

This avoids five near-identical posts from five people discussing the same subject.

---

# 7. Angle extraction

For each cluster, ask the model:

```text
What is the actual conversation?

What tension exists?

What assumption are people making?

What is interesting but under-discussed?

What would make an Indonesian tech-curious person stop scrolling?

What position could be added without pretending to have personal experience?

Possible angles:
- agree
- disagree
- nuance
- unexpected implication
- relatable observation
- absurdity
- practical consequence
- question worth discussing
```

The model must choose ONE.

---

# 8. Writer behavior

The writer should NOT summarize the source.

Old behavior:

```text
People are discussing X.
X is important because...
Here are three implications...
```

New behavior:

```text
I keep seeing people argue about X.

The interesting part isn't X.

It's Y.

Because...
```

But do not force this exact structure.

The target is conversational unpredictability.

---

# 9. Important anti-AI rules

Do not over-specify slang.

Do not force:
- "gue"
- "bro"
- "anjir"
- "wkwk"
- "ternyata"
- rhetorical questions
- punchlines

Natural language can be understated.

Avoid:
- motivational endings
- educational headings
- "3 hal yang..."
- "pelajarannya..."
- "intinya..."
- "yang perlu kamu pahami..."
- generic CTA
- fake personal stories
- fake experiments
- fake opinions presented as personal experience

---

# 10. New post types

Replace article-like formats with conversation-native modes.

Recommended weighted distribution:

```text
observation              25%
strong_opinion           20%
relatable_tech_behavior  15%
contrarian               15%
unexpected_implication   10%
discussion                10%
help_seeking               5%
```

Avoid:
- myth vs reality
- comparison article
- listicle
- tutorial unless the source conversation itself is tutorial-oriented

---

# 11. Engagement model

Do not require a question at the end.

A post succeeds if it makes the reader think:

```text
"gue juga begitu"
"nah ini"
"nggak setuju"
"bener juga"
"lah iya"
"ini kejadian di kerjaan gue"
"wait..."
```

These are better engagement targets than:

```text
"Menurut kamu gimana?"
```

---

# 12. Example transformation

SOURCE CONVERSATION:

"AI coding tools are making junior developers obsolete."

BAD:

> AI coding tools semakin berkembang dan dapat membantu developer menyelesaikan pekerjaan lebih cepat. Hal ini menimbulkan pertanyaan apakah junior developer masih dibutuhkan di masa depan...

GOOD:

> Mungkin AI bukan yang bikin junior developer susah masuk industri.

> Yang bikin susah adalah standar "junior" sekarang mulai berubah.

> Dulu cukup bisa coding.
> Sekarang mungkin harus bisa coding + ngerti cara kerja AI.

This is still factual enough without pretending the account personally experienced it.

---

# 13. Example: vibe coding

SOURCE:

Several people debate whether vibe coding is "real development".

Potential output:

> Debat "vibe coding itu coding beneran atau bukan" agak melelahkan.

> Pertanyaan yang lebih menarik:
> kalau hasil akhirnya bekerja, siapa yang sebenarnya peduli kamu nulis berapa baris kode?

> Kecuali... kamu harus maintain-nya enam bulan kemudian.

This creates tension without needing a news article.

---

# 14. Example: remote work

SOURCE:

People complaining that remote work creates more meetings.

Potential output:

> Remote work ternyata nggak menghilangkan meeting.

> Meeting-nya cuma pindah dari ruang rapat ke kalender.

> Dan entah kenapa, sekarang semua orang bisa mengundang kita tanpa perlu jalan ke meja kita.

---

# 15. Configuration direction

Recommended top-level config:

```json
{
  "niche": "Tech, internet culture, dan digital work dari perspektif orang Indonesia yang tech-curious",
  "audience": "Freelancer, remote worker, creator, developer, builder, dan orang yang bekerja di internet",
  "language": "Bahasa Indonesia percakapan yang natural dan observatif",
  "max_chars": 450
}
```

Research:

```json
{
  "research": {
    "enabled": true,
    "source_mode": "threads_only",
    "threads_only": true,
    "threads_max_queries_per_run": 5,
    "threads_search_type": "TOP",
    "threads_results_per_query": 10
  }
}
```

Disable:

```text
rss_feeds
html_index
google_news_queries
x_queries
```

Do not delete the old code immediately. Keep it available behind `source_mode`.

---

# 16. Architectural change required

The most important code change is NOT `config.json`.

Current:

```python
articles, socials = select_batch(...)
```

and generation assigns posts to research articles.

V3 should conceptually become:

```python
threads_posts = collect_threads(...)
clusters = cluster_conversations(threads_posts)
angles = extract_angles(clusters)
assignments = select_angles(angles)
drafts = generate_from_conversations(assignments)
```

`threads_research.py` becomes the primary research collector.

`research.py` should support:

```text
source_mode = threads_only
```

rather than assuming article-first selection.

---

# 17. Quality gate V3

Add deterministic checks for:

### Newsiness
Reject if the post contains patterns such as:

```text
"baru saja meluncurkan"
"menurut laporan"
"perusahaan X mengumumkan"
"berdasarkan penelitian"
"dalam perkembangan terbaru"
```

Some are already present; retain them.

### Article structure
Reject if:

```text
"1."
"2."
"3."
"kesimpulan:"
"pelajaran:"
"berikut adalah"
```

unless explicitly allowed by the source/format.

### Engagement bait
Reject:

```text
"setuju nggak?"
"menurut kamu?"
"apa pendapat kalian?"
"share kalau..."
"follow untuk..."
```

unless the post genuinely requires discussion.

### Fake first person

Reject unsupported:

```text
"saya mencoba..."
"gue nyobain..."
"aku pakai..."
"pengalaman saya..."
```

### Source imitation

Continue rejecting long verbatim sequences.

---

# 18. Testing protocol

Before changing the production workflow:

Generate 30 posts.

### Batch A
Current RSS system.

### Batch B
Threads-only, current prompt.

### Batch C
Threads-only + conversation mining + new prompt.

Blind-test them.

For each post, score:

```text
Would I stop scrolling?       1–5
Would I read to the end?     1–5
Would I reply?               1–5
Feels human?                 1–5
Feels like journalism?       1–5 (reverse)
Feels like AI?               1–5 (reverse)
```

The target is not merely a higher writing score.

The target is:

**higher "I'd reply" score + lower "journalism" score.**

---

# 19. Final recommendation

Do NOT optimize the current RSS engine further yet.

Build the Threads-only mode first.

The experiment should answer one question:

> Can an account become more engaging simply by changing the raw material from "articles about topics" to "people talking about topics"?

I expect the answer to be yes.

The strongest initial niche is:

**Tech / Internet Culture / Digital Work**

with these primary conversation zones:

1. AI in real life
2. Digital work / freelancing
3. Vibe coding / builder culture
4. Creator / internet culture
5. Career / work
6. Skeptical / contrarian tech takes

AI remains central enough to retain the existing account identity, but the account stops behaving like an AI news channel.
