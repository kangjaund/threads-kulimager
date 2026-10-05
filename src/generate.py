"""Generate postingan baru dengan Gemini dan masukkan ke antrean data/posts.json."""
import json
import random
import re
import sys
from collections import Counter
from difflib import SequenceMatcher

from common import (
    load_config,
    load_posts,
    now_iso,
    request_with_retry,
    require_env,
    save_posts,
)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MAX_ROUNDS = 3
SIMILARITY_LIMIT = 0.7
MIN_CHARS = 20


def pick_style(cfg):
    weights = {k: v for k, v in cfg["style_weights"].items() if v > 0}
    if not weights:
        sys.exit("ERROR: style_weights kosong atau semuanya 0.")
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
        out.append({"pillar": pillar, "format": fmt, "style": pick_style(cfg)})
        pillar_hist.append(pillar)
        format_hist.append(fmt)
    return out


def build_prompt(cfg, assignments, avoid_texts):
    used_styles = sorted({a["style"] for a in assignments})
    used_pillars = sorted({a["pillar"] for a in assignments})
    used_formats = sorted({a["format"] for a in assignments})

    lines = [
        f"Kamu adalah penulis konten Threads untuk akun bertema: {cfg['niche']}.",
        f"Target audiens: {cfg['audience']}.",
        f"Bahasa: {cfg['language']}.",
        "",
        "ATURAN WAJIB:",
        f"- Maksimal {cfg['max_chars']} karakter per postingan (termasuk spasi dan emoji).",
    ]
    lines += [f"- {rule}" for rule in cfg["rules"]]

    lines += ["", "PANDUAN PILAR TOPIK:"]
    lines += [f"- {p}: {cfg['pillars'][p]}" for p in used_pillars]
    lines += ["", "PANDUAN FORMAT:"]
    lines += [f"- {f}: {cfg['formats'][f]}" for f in used_formats]
    lines += ["", "PANDUAN GAYA:"]
    lines += [f"- {s}: {cfg['styles'][s]}" for s in used_styles]

    if avoid_texts:
        lines += ["", "POSTINGAN TERBARU (jangan diulang, jangan mirip topik maupun hook-nya):"]
        lines += [f"- {t[:140].replace(chr(10), ' ')}" for t in avoid_texts]

    lines += ["", f"Buat {len(assignments)} postingan dengan spesifikasi berikut, sesuai urutan:"]
    for i, a in enumerate(assignments, 1):
        lines.append(f"{i}. pilar={a['pillar']} | format={a['format']} | gaya={a['style']}")

    lines += [
        "",
        'Keluarkan HANYA JSON array berisi objek {"text": "..."} sesuai urutan di atas. '
        "Gunakan baris baru (\\n) di dalam teks bila perlu. Jangan tambahkan penjelasan lain.",
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


def call_gemini(cfg, prompt):
    key = require_env("GEMINI_API_KEY")
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": cfg.get("temperature", 0.9),
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {"text": {"type": "STRING"}},
                    "required": ["text"],
                },
            },
        },
    }
    resp = request_with_retry(
        "POST",
        GEMINI_URL.format(model=cfg["model"]),
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json=body,
    )
    if not resp.ok:
        raise RuntimeError(f"Gemini error {resp.status_code}: {resp.text[:400]}")
    data = resp.json()
    try:
        parts = data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError):
        raise RuntimeError(f"Respons Gemini tidak terduga: {str(data)[:400]}")
    raw = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    return parse_items(raw)


def is_acceptable(text, pool, max_chars):
    if not (MIN_CHARS <= len(text) <= max_chars):
        return False
    low = text.lower()
    return all(SequenceMatcher(None, low, other.lower()).ratio() < SIMILARITY_LIMIT for other in pool)


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
        assignments = build_assignments(cfg, recent + accepted, remaining)
        prompt = build_prompt(cfg, assignments, avoid_texts + [a["text"] for a in accepted])
        try:
            texts = call_gemini(cfg, prompt)
        except (RuntimeError, ValueError) as exc:
            print(f"Putaran {round_no} gagal: {exc}")
            continue
        for assignment, text in zip(assignments, texts):
            text = text.strip()
            pool = avoid_texts + [a["text"] for a in accepted]
            if is_acceptable(text, pool, cfg["max_chars"]):
                accepted.append({**assignment, "text": text})
            else:
                print(f"Dibuang (panjang/mirip): {text[:60]!r}")

    if not accepted:
        sys.exit("ERROR: tidak ada postingan valid yang berhasil dibuat.")

    status = "pending" if cfg["require_approval"] else "approved"
    next_id = max((p["id"] for p in posts), default=0) + 1
    for item in accepted:
        posts.append(
            {
                "id": next_id,
                "text": item["text"],
                "pillar": item["pillar"],
                "format": item["format"],
                "style": item["style"],
                "status": status,
                "attempts": 0,
                "created_at": now_iso(),
            }
        )
        next_id += 1

    save_posts(posts)
    print(f"Menambahkan {len(accepted)} postingan baru dengan status '{status}'.")


if __name__ == "__main__":
    main()
