"""Daftar sumber research + pengaturan default.

Semua daftar di sini bisa dioverride dari config.json lewat blok "research"
(kunci: rss_feeds, html_index, google_news_queries, threads_queries, x_queries, dan setting angka).
Kalau config.json tidak memilikinya, default di file ini dipakai. Jadi config.json tidak perlu diubah.

Kategori (urutan prioritas sama dengan research.source_priority di config.json):
  official_research, official_product_blog, research_paper, reputable_tech_media,
  rss_discovery, threads_social_signal
"""

SOURCE_PRIORITY = [
    "official_research",
    "official_product_blog",
    "research_paper",
    "reputable_tech_media",
    "rss_discovery",
    "threads_social_signal",
]

# Feed RSS/Atom. Satu feed yang gagal tidak menghentikan yang lain.
FEEDS = [
    # --- Lab & riset resmi ---
    {"name": "Google DeepMind", "url": "https://deepmind.google/blog/rss.xml", "category": "official_research"},
    {"name": "Google Research", "url": "https://research.google/blog/rss/", "category": "official_research"},
    {"name": "Microsoft Research", "url": "https://www.microsoft.com/en-us/research/feed/", "category": "official_research"},
    {"name": "Hugging Face", "url": "https://huggingface.co/blog/feed.xml", "category": "official_research"},
    # --- Blog produk resmi ---
    {"name": "OpenAI", "url": "https://openai.com/news/rss.xml", "category": "official_product_blog"},
    {"name": "Google AI", "url": "https://blog.google/technology/ai/rss/", "category": "official_product_blog"},
    {"name": "GitHub Blog (AI & ML)", "url": "https://github.blog/ai-and-ml/feed/", "category": "official_product_blog"},
    {"name": "AWS Machine Learning", "url": "https://aws.amazon.com/blogs/machine-learning/feed/", "category": "official_product_blog"},
    {"name": "Cloudflare (AI)", "url": "https://blog.cloudflare.com/tag/ai/rss/", "category": "official_product_blog"},
    # --- Media teknologi kredibel ---
    {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/", "category": "reputable_tech_media"},
    {"name": "The Verge AI", "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "category": "reputable_tech_media"},
    {"name": "Ars Technica AI", "url": "https://arstechnica.com/ai/feed/", "category": "reputable_tech_media"},
    {"name": "MIT Technology Review AI", "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed", "category": "reputable_tech_media"},
    {"name": "VentureBeat AI", "url": "https://venturebeat.com/category/ai/feed/", "category": "reputable_tech_media"},
    {"name": "WIRED AI", "url": "https://www.wired.com/feed/tag/ai/latest/rss", "category": "reputable_tech_media"},
    # --- Discovery / komentar komunitas ---
    {"name": "Simon Willison", "url": "https://simonwillison.net/atom/everything/", "category": "rss_discovery"},
    {"name": "Import AI", "url": "https://importai.substack.com/feed", "category": "rss_discovery"},
    {"name": "Latent Space", "url": "https://www.latent.space/feed", "category": "rss_discovery"},
    {"name": "Hacker News: AI", "url": "https://hnrss.org/frontpage?q=AI", "category": "rss_discovery"},
    {"name": "Hacker News: LLM", "url": "https://hnrss.org/frontpage?q=LLM", "category": "rss_discovery"},
]

# Lab tanpa RSS resmi: ambil halaman indeks, cocokkan pola link, lalu baca tiap artikelnya.
# Struktur situs bisa berubah; kalau gagal, sumber ini dilewati tanpa menghentikan yang lain.
HTML_INDEX = [
    {"name": "Anthropic", "url": "https://www.anthropic.com/news", "category": "official_product_blog",
     "link_pattern": r"^/news/[a-z0-9][a-z0-9-]+/?$", "limit": 5},
    {"name": "Meta AI", "url": "https://ai.meta.com/blog/", "category": "official_research",
     "link_pattern": r"^/blog/[a-z0-9][a-z0-9-]+/?$", "limit": 4},
    {"name": "Mistral AI", "url": "https://mistral.ai/news", "category": "official_product_blog",
     "link_pattern": r"^/news/[a-z0-9][a-z0-9-]+/?$", "limit": 4},
]

# Hanya judul + penerbit (link Google News tidak bisa dibuka isinya). Dipakai sebagai sinyal topik, bukan sumber fakta.
GOOGLE_NEWS_QUERIES = [
    "Anthropic Claude",
    "OpenAI ChatGPT",
    "Google Gemini",
    "AI agents",
    "AI coding assistant",
    "AI freelancers jobs",
]

# Threads keyword search (butuh permission threads_keyword_search). Dibatasi per run agar hemat kuota.
THREADS_QUERIES = [
    "AI agent",
    "Claude",
    "ChatGPT",
    "vibe coding",
    "AI freelancer",
]

# X API opsional (butuh X_BEARER_TOKEN; free tier umumnya tidak cukup). Kosong = dilewati.
X_QUERIES = []

DEFAULTS = {
    "items_per_feed": 6,
    "items_per_query": 5,
    "article_enrich_items": 18,
    "article_max_chars": 6000,
    "stored_content_chars": 3500,
    "max_research_items": 80,
    "max_stored_items": 160,
    "retention_days": 14,
    "threads_max_queries_per_run": 5,
    "threads_results_per_query": 8,
    "threads_search_type": "TOP",
    "x_max_results": 10,
    # Research Packet (dijaga kecil karena batas Groq free tier 8K token/menit)
    "packet_max_items": 4,
    "packet_excerpt_chars": 1100,
    "packet_social_items": 4,
    "packet_social_chars": 260,
    "max_items_per_source": 2,
}


def research_settings(cfg):
    """Gabungkan default dengan blok cfg['research'] (config menang)."""
    rcfg = dict(cfg.get("research", {}))
    out = dict(DEFAULTS)
    out.update({k: v for k, v in rcfg.items() if k in DEFAULTS})
    out["rss_feeds"] = rcfg.get("rss_feeds", FEEDS)
    out["html_index"] = rcfg.get("html_index", HTML_INDEX)
    out["google_news_queries"] = rcfg.get("google_news_queries", GOOGLE_NEWS_QUERIES)
    out["threads_queries"] = rcfg.get("threads_queries", THREADS_QUERIES)
    out["x_queries"] = rcfg.get("x_queries", X_QUERIES)
    out["source_priority"] = rcfg.get("source_priority", SOURCE_PRIORITY)
    fresh = rcfg.get("freshness", {})
    out["prefer_recent_days"] = int(fresh.get("prefer_recent_days", 7))
    out["max_source_age_days"] = int(fresh.get("max_source_age_days", 30))
    out["enabled"] = bool(rcfg.get("enabled", True))
    return out
