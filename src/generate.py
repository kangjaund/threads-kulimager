"""Generate Threads-first content with Groq, quality-gate it, and queue it."""
import json
import random
import re
import sys
from collections import Counter
from difflib import SequenceMatcher

from common import load_config, load_posts, now_iso, request_with_retry, require_env, save_posts

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MAX_ROUNDS = 4
SIMILARITY_LIMIT = 0.68
MIN_CHARS = 45
BANNED_GENERIC_STARTS = (
    "banyak orang", "di era digital", "di zaman sekarang", "jika kamu ingin",
    "tahukah kamu", "berikut beberapa", "pernahkah kamu", "tidak bisa dipungkiri",
    "yang perlu kamu pahami", "ada beberapa hal", "kunci sukses adalah",
    "salah satu cara", "pada akhirnya", "dalam dunia freelance", "menjadi freelancer bukanlah",
    "semoga bermanfaat", "tetap semangat", "lesson:", "myth:", "bandingkan:", "realitanya:", "pertanyaannya:"
)


def pick_style(cfg):
    weights = {k: v for k, v in cfg["style_weights"].items() if v > 0 and k in cfg["styles"]}
    if not weights:
        sys.exit("ERROR: style_weights kosong, semuanya 0, atau tidak cocok dengan 'styles'.")
    return random.choices(list(weights), weights=list(weights.values()))[0]


def least_used(options, history):
    counts = Counter(history)
    lowest = min(counts.get(o, 0) for o in options)
    return random.choice([o for o in options if counts.get(o, 0) == lowest])


def build_assignments(cfg, recent, n):
    pillars, formats = list(cfg["pillars"]), list(cfg["formats"])
    pillar_hist = [p.get("pillar") for p in recent]
    format_hist = [p.get("format") for p in recent]
    out = []
    for _ in range(n):
        pillar = least_used(pillars, pillar_hist)
        fmt = least_used(formats, format_hist)
        # Style dipilih berdasarkan bobot style_weights di config.json.
        out.append({"pillar": pillar, "format": fmt, "style": pick_style(cfg)})
        pillar_hist.append(pillar)
        format_hist.append(fmt)
    return out


def build_prompt(cfg, assignments, avoid_texts):
    used_styles = sorted({a["style"] for a in assignments})
    used_pillars = sorted({a["pillar"] for a in assignments})
    used_formats = sorted({a["format"] for a in assignments})
    v = cfg["voice"]

    lines = [
        "Kamu adalah penulis Threads untuk akun freelancer tech-savvy Indonesia.",
        f"Niche: {cfg['niche']}.",
        f"Audiens: {cfg['audience']}.",
        f"Bahasa: {cfg['language']}.",
        "",
        "IDENTITAS SUARA:",
        "Akun ini bukan guru cari uang, bukan motivator, dan bukan akun corporate.",
        "Posisinya adalah freelancer yang tech-curious, observatif, skeptis terhadap hype, dan berani punya opini.",
        "Skala voice (0 = sangat rendah, 1 = sangat tinggi): " + ", ".join(f"{k}={val}" for k, val in v.items()) + ".",
        "",
        "WRITING DNA:",
        *[f"- {x}" for x in cfg["writing_dna"]],
        "",
        "HOOK ENGINE:",
        "Gunakan salah satu mekanisme hook berikut bila cocok: " + ", ".join(cfg["hook_engine"]["preferred"]) + ".",
        *[f"- {x}" for x in cfg["hook_engine"]["rules"]],
        "",
        "ANTI-AI / ANTI-GENERIC:",
        "Jangan gunakan pola atau frasa pembuka berikut kecuali konteks benar-benar memerlukannya:",
        "- " + "\n- ".join(cfg["banned_patterns"]),
        "Jangan membuat semua post terdengar seperti template yang sama.",
        "Jangan menggunakan frasa 'yang perlu kamu pahami' atau 'pada akhirnya' sebagai filler.",
        "",
        "ATURAN WAJIB:",
        f"- Maksimal {cfg['max_chars']} karakter per postingan termasuk spasi dan emoji.",
    ]
    lines += [f"- {rule}" for rule in cfg["rules"]]
    lines += ["", "PANDUAN PILAR:"]
    lines += [f"- {p}: {cfg['pillars'][p]}" for p in used_pillars]
    lines += ["", "PANDUAN FORMAT:"]
    lines += [f"- {f}: {cfg['formats'][f]}" for f in used_formats]
    lines += ["", "PANDUAN STYLE:"]
    lines += [f"- {s}: {cfg['styles'][s]}" for s in used_styles]

    if avoid_texts:
        lines += ["", "RECENT POSTS — jangan mengulang ide, angle, hook, atau struktur kalimatnya:"]
        lines += [f"- {t[:180].replace(chr(10), ' ')}" for t in avoid_texts[-cfg["history_window"]:]]

    lines += ["", f"Buat {len(assignments)} postingan. Setiap post harus punya angle yang berbeda."]
    for i, a in enumerate(assignments, 1):
        lines.append(f"{i}. pillar={a['pillar']} | format={a['format']} | style={a['style']}")

    lines += [
        "",
        "SELF-EDIT SEBELUM OUTPUT:",
        "1. Apakah kalimat pertama membuat orang ingin lanjut membaca?",
        "2. Apakah ada point of view atau insight yang spesifik?",
        "3. Apakah tulisan ini masih terasa seperti AI jika nama akun dihapus? Jika ya, rewrite.",
        "4. Apakah ada filler yang bisa dipotong? Potong.",
        "5. Apakah punchline/ending terasa earned, bukan template?",
        "6. Pastikan tidak ada dua post yang memakai hook/struktur yang terlalu mirip.",
        "",
        'Keluarkan HANYA JSON array berisi objek {"text": "..."} sesuai urutan. Jangan tambahkan markdown atau penjelasan.'
    ]
    return "\n".join(lines)


def parse_items(raw):
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE)
    data = json.loads(raw)
    if isinstance(data, dict):
        data = data.get("posts") or data.get("items") or []
    texts = []
    for item in data:
        if isinstance(item, str):
            texts.append(item)
        elif isinstance(item, dict) and isinstance(item.get("text"), str):
            texts.append(item["text"])
    return texts


def call_groq(cfg, prompt):
    """Generate structured JSON through Groq's OpenAI-compatible Chat Completions API."""
    key = require_env("GROQ_API_KEY")
    schema = {
        "type": "object",
        "properties": {
            "posts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["posts"],
        "additionalProperties": False,
    }
    body = {
        "model": cfg["model"],
        "messages": [
            {
                "role": "system",
                "content": (
                    "Kamu adalah penulis Threads berbahasa Indonesia. "
                    "Ikuti instruksi user dengan ketat dan keluarkan hanya JSON sesuai schema."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": cfg.get("temperature", 1.0),
        "max_completion_tokens": cfg.get("max_completion_tokens", 3000),
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "threads_posts",
                "strict": True,
                "schema": schema,
            },
        },
    }
    if cfg.get("reasoning_effort"):
        body["reasoning_effort"] = cfg["reasoning_effort"]

    resp = request_with_retry(
        "POST",
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json=body,
    )
    if not resp.ok:
        raise RuntimeError(f"Groq error {resp.status_code}: {resp.text[:400]}")
    try:
        data = resp.json()
        raw = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError):
        raise RuntimeError(f"Respons Groq tidak terduga: {str(data)[:400]}")
    return parse_items(raw)


def quality_check(text, pool, max_chars):
    """Cheap deterministic gate: reject obvious AI slop before it reaches the queue."""
    reasons = []
    clean = re.sub(r"\s+", " ", text.strip())
    low = clean.lower()
    if not (MIN_CHARS <= len(clean) <= max_chars):
        reasons.append("length")
    if any(low.startswith(x) for x in BANNED_GENERIC_STARTS):
        reasons.append("generic-opening")
    if clean.count("!") > 2:
        reasons.append("too-many-exclamations")
    if clean.count("?") > 2:
        reasons.append("too-many-questions")
    if clean.count("#") > 1:
        reasons.append("too-many-hashtags")
    words = re.findall(r"\b[\w'-]+\b", low)
    if len(words) >= 35 and len(set(words)) / len(words) < 0.46:
        reasons.append("repetitive-words")
    if any(SequenceMatcher(None, low, other.lower()).ratio() >= SIMILARITY_LIMIT for other in pool):
        reasons.append("too-similar")
    # Threads-first checks: reject common article/template patterns.
    if re.match(r"^(lesson|myth|bandingkan|realitanya|pertanyaannya)\s*[:：]", low):
        reasons.append("template-opening")
    if re.match(r"^(saya|aku)\s+(pernah|sering|sempat)\b", low):
        reasons.append("unsupported-first-person")
    if low.count("padahal") >= 2 or low.count("realitanya") >= 2:
        reasons.append("repeated-transition")
    # A post should contain at least one sentence boundary or line break; this avoids bland one-liners.
    if len(clean) > 100 and "." not in clean and "\n" not in text and "?" not in clean and "!" not in clean:
        reasons.append("flat-sentence")
    return (not reasons), reasons


def main():
    cfg = load_config()
    posts = load_posts()
    open_count = sum(1 for p in posts if p["status"] in ("pending", "approved"))
    if open_count >= cfg["queue_target"]:
        print(f"Antrean sudah {open_count} (target {cfg['queue_target']}). Lewati generate.")
        return

    need = min(cfg["posts_per_generate"], cfg["queue_target"] - open_count)
    recent = [p for p in posts if p["status"] != "failed"][-cfg["history_window"]:]
    avoid_texts = [p["text"] for p in recent]
    accepted = []

    for round_no in range(1, MAX_ROUNDS + 1):
        remaining = need - len(accepted)
        if remaining <= 0:
            break
        # Ask for extra candidates on later rounds so the quality gate has room to be selective.
        batch_size = remaining if round_no == 1 else min(remaining + 2, need)
        assignments = build_assignments(cfg, recent + accepted, batch_size)
        prompt = build_prompt(cfg, assignments, avoid_texts + [a["text"] for a in accepted])
        try:
            texts = call_groq(cfg, prompt)
        except (RuntimeError, ValueError) as exc:
            print(f"Putaran {round_no} gagal: {exc}")
            continue
        for assignment, text in zip(assignments, texts):
            text = text.strip()
            pool = avoid_texts + [a["text"] for a in accepted]
            ok, reasons = quality_check(text, pool, cfg["max_chars"])
            if ok and len(accepted) < need:
                accepted.append({**assignment, "text": text})
            else:
                print(f"Dibuang ({', '.join(reasons)}): {text[:80]!r}")

    if not accepted:
        sys.exit("ERROR: tidak ada postingan yang lolos quality gate.")

    status = "pending" if cfg["require_approval"] else "approved"
    next_id = max((p["id"] for p in posts), default=0) + 1
    for item in accepted:
        posts.append({
            "id": next_id, "text": item["text"], "pillar": item["pillar"],
            "format": item["format"], "style": item["style"], "status": status,
            "attempts": 0, "created_at": now_iso(),
        })
        next_id += 1
    save_posts(posts)
    print(f"Menambahkan {len(accepted)} postingan baru dengan status '{status}'.")


if __name__ == "__main__":
    main()
