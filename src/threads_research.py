"""Social signal dari Threads keyword search.

Catatan penting:
- Butuh scope threads_keyword_search PADA TOKEN (token lama tidak otomatis memilikinya; generate ulang token).
- Menurut dokumentasi Meta, jika app belum disetujui untuk threads_keyword_search,
  pencarian HANYA mencakup postingan milik akun yang terautentikasi. Kode ini mendeteksi
  kondisi itu (semua hasil milik akun sendiri) dan menandainya di log.
- Social signal hanya bahan observasi, bukan bukti fakta.
"""
import os
import re

from common import request_with_retry

KEYWORD_URL = "https://graph.threads.net/keyword_search"
ME_URL = "https://graph.threads.net/v1.0/me"
# Field yang tercantum di dokumentasi resmi keyword search.
FIELDS = "id,text,media_type,permalink,timestamp,username,has_replies,is_quote_post,is_reply"
USER_AGENT = "threads-autopilot/2.0 (+research bot)"


def _clean(text, limit):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:limit]


def _own_username(token):
    try:
        resp = request_with_retry("GET", ME_URL, retries=2, backoff=2,
                                  headers={"User-Agent": USER_AGENT},
                                  params={"fields": "username", "access_token": token}, timeout=15)
        if resp.ok:
            return (resp.json().get("username") or "").lower()
    except Exception:
        pass
    return ""


def _error_message(resp):
    try:
        err = resp.json().get("error", {})
        return f"{err.get('code', resp.status_code)}: {str(err.get('message', resp.text))[:160]}"
    except ValueError:
        return f"{resp.status_code}: {resp.text[:160]}"


def fetch_threads(settings):
    """Kembalikan list item social. Tidak pernah melempar exception ke pemanggil."""
    token = os.getenv("THREADS_ACCESS_TOKEN", "").strip()
    queries = list(settings.get("threads_queries", []))[: int(settings.get("threads_max_queries_per_run", 5))]
    if not token or not queries:
        return []

    own = _own_username(token)
    per_query = int(settings.get("threads_results_per_query", 8))
    items, raw_total, own_total = [], 0, 0

    for query in queries:
        try:
            resp = request_with_retry(
                "GET", KEYWORD_URL, retries=2, backoff=3,
                headers={"User-Agent": USER_AGENT}, timeout=20,
                params={"q": query, "search_type": settings.get("threads_search_type", "TOP"),
                        "fields": FIELDS, "access_token": token},
            )
        except RuntimeError as exc:
            print(f"Threads search '{query}' dilewati: {exc}")
            continue
        if not resp.ok:
            print(f"Threads search '{query}' dilewati ({_error_message(resp)}).")
            # Error izin/token berlaku untuk semua query; hentikan lebih awal.
            if resp.status_code in (400, 401, 403):
                print("Periksa: scope threads_keyword_search pada token, dan status izin app di Meta.")
                break
            continue
        for post in resp.json().get("data", [])[:per_query * 3]:
            raw_total += 1
            username = (post.get("username") or "").lower()
            if own and username == own:
                own_total += 1
                continue
            text = _clean(post.get("text"), 700)
            if len(text) < 60 or post.get("is_reply"):
                continue
            items.append({
                "id": f"threads-{post['id']}", "source": "Threads", "type": "social",
                "category": "threads_social_signal", "title": f"@{post.get('username', 'unknown')}",
                "url": post.get("permalink", ""), "published_at": post.get("timestamp", ""),
                "summary": text, "query": query,
            })
            if sum(1 for i in items if i.get("query") == query) >= per_query:
                break

    if raw_total and raw_total == own_total:
        print("Threads search: semua hasil adalah postingan akun sendiri. Kemungkinan izin "
              "threads_keyword_search belum disetujui Meta (App Review/Advanced Access) atau token belum memuat scope-nya.")
    print(f"Threads search: {len(items)} sinyal dari {len(queries)} query.")
    return items
