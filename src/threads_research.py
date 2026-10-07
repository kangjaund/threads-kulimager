"""Social signal / bahan mentah percakapan dari Threads keyword search.

V3 (source_mode = threads_only): modul ini adalah kolektor riset UTAMA. Query dirotasi per run
(grup A..E di research.threads_query_groups) dan state rotasi disimpan di data/research_state.json
(ikut ter-commit oleh workflow lewat `git add -A data`).

Catatan penting:
- Butuh scope threads_keyword_search PADA TOKEN (token lama tidak otomatis memilikinya; generate ulang token).
- Menurut dokumentasi Meta, jika app belum disetujui untuk threads_keyword_search,
  pencarian HANYA mencakup postingan milik akun yang terautentikasi. Kode ini mendeteksi
  kondisi itu (semua hasil milik akun sendiri) dan menandainya di log.
- Social signal hanya bahan observasi, bukan bukti fakta.
"""
import json
import os
import re

from common import ROOT, request_with_retry

KEYWORD_URL = "https://graph.threads.net/keyword_search"
ME_URL = "https://graph.threads.net/v1.0/me"
# Field yang tercantum di dokumentasi resmi keyword search.
FIELDS = "id,text,media_type,permalink,timestamp,username,has_replies,is_quote_post,is_reply"
USER_AGENT = "threads-autopilot/3.0 (+research bot)"
STATE_PATH = ROOT / "data" / "research_state.json"


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


def _load_state():
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(state):
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"State rotasi query tidak tersimpan: {type(exc).__name__}")


def pick_queries(settings):
    """Return (nama_grup, daftar_query, index_grup_berikutnya_atau_None).

    Mode threads_only dengan threads_query_groups -> rotasi grup. Override manual lewat env
    THREADS_QUERY_GROUP (huruf awal/nama grup, mis. 'B' atau 'B_work'; 'auto' = rotasi).
    Selain itu dipakai threads_queries (perilaku V2).
    """
    limit = int(settings.get("threads_max_queries_per_run", 5))
    groups = settings.get("threads_query_groups") or {}
    if settings.get("source_mode") != "threads_only" or not groups:
        return "flat", list(settings.get("threads_queries", []))[:limit], None
    names = list(groups)
    forced = os.getenv("THREADS_QUERY_GROUP", "").strip().lower()
    if forced and forced != "auto":
        for name in names:
            if name.lower() == forced or name.lower().startswith(forced + "_") or name.lower()[:1] == forced[:1] and len(forced) == 1:
                return name, list(groups[name])[:limit], None
    idx = int(_load_state().get("query_group_index", 0)) % len(names)
    name = names[idx]
    return name, list(groups[name])[:limit], (idx + 1) % len(names)


def fetch_threads(settings):
    """Kembalikan list item social. Tidak pernah melempar exception ke pemanggil."""
    token = os.getenv("THREADS_ACCESS_TOKEN", "").strip()
    group, queries, next_idx = pick_queries(settings)
    if not token or not queries:
        return []
    print(f"Threads search: grup '{group}' -> {queries}")
    aborted = False

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
                aborted = True
                break
            continue
        for rank, post in enumerate(resp.json().get("data", [])[:per_query * 3]):
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
                # metadata percakapan untuk conversation scoring (V3)
                "username": username, "rank": rank, "query_group": group,
                "search_type": settings.get("threads_search_type", "TOP"),
                "has_replies": bool(post.get("has_replies")),
                "is_quote_post": bool(post.get("is_quote_post")),
            })
            if sum(1 for i in items if i.get("query") == query) >= per_query:
                break

    if raw_total and raw_total == own_total:
        print("Threads search: semua hasil adalah postingan akun sendiri. Kemungkinan izin "
              "threads_keyword_search belum disetujui Meta (App Review/Advanced Access) atau token belum memuat scope-nya.")
    print(f"Threads search: {len(items)} sinyal dari {len(queries)} query.")
    if next_idx is not None and not aborted and raw_total:
        _save_state({**_load_state(), "query_group_index": next_idx, "last_group": group})
    return items
