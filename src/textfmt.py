"""Penegakan format paragraf Threads secara deterministik.

Aturan di prompt sering diabaikan model (hasilnya satu paragraf panjang). Karena itu format ditegakkan
di kode: model dipaksa mengisi blok terpisah lewat schema, lalu `reflow` merapikan sisanya, dan
`check_format` menolak yang masih melanggar. Dipakai oleh generate.py (draft baru) dan post.py
(pengaman terakhir untuk draft lama yang sudah ada di antrean).

Default di sini lebih ketat daripada config.json dan selalu berlaku (config yang lebih ketat tetap menang).
Override opsional di config.json -> formatting.strict:
  max_blocks, max_sentences_per_block, block_max_chars, hook_max_chars, hook_hard_chars,
  min_blocks_over_chars, three_blocks_over_chars
"""
import re

SEPARATOR = "\n\n"
BLOCK_KEYS = ("block_1", "block_2", "block_3", "block_4", "block_5")
_ABBR = re.compile(r"\b(vs|dr|mr|mrs|ms|no|etc|dll|dsb|dst|yg|dgn|tsb|spt|sbg)\.", re.IGNORECASE)
_SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+(?=[A-Z0-9\"“‘'(\[])")


def strict_rules(cfg):
    fmt = cfg.get("formatting", {}) if cfg else {}
    strict = fmt.get("strict", {})
    return {
        "max_blocks": min(int(fmt.get("max_paragraphs", 5)), int(strict.get("max_blocks", 5))),
        "max_sentences": min(int(fmt.get("max_sentences_per_paragraph", 2)), int(strict.get("max_sentences_per_block", 2))),
        "block_max_chars": int(strict.get("block_max_chars", 200)),
        "hook_max_chars": int(strict.get("hook_max_chars", 120)),
        "hook_hard_chars": int(strict.get("hook_hard_chars", 160)),
        "two_blocks_over": min(int(fmt.get("min_paragraphs_if_over_chars", 180)), int(strict.get("min_blocks_over_chars", 140))),
        "three_blocks_over": int(strict.get("three_blocks_over_chars", 260)),
    }


def split_sentences(text):
    protected = text.replace("e.g.", "e\u0001g\u0001").replace("i.e.", "i\u0001e\u0001")
    protected = _ABBR.sub(lambda m: m.group(1) + "\u0001", protected)
    parts = [p.replace("\u0001", ".").strip() for p in _SENT_SPLIT.split(protected)]
    return [p for p in parts if p]


def count_sentences(block):
    return len(split_sentences(block))


def blocks_of(text):
    return [b.strip() for b in re.split(r"\n+", text.strip()) if b.strip()]


def assemble_blocks(entry):
    """Gabungkan field block_1..block_5 (atau 'text' lama) menjadi satu teks berblok."""
    parts = [str(entry.get(k) or "").strip() for k in BLOCK_KEYS]
    parts = [p for p in parts if p]
    if parts:
        return SEPARATOR.join(parts)
    return str(entry.get("text") or "").strip()


def _chunk(sentences, rules):
    chunks, cur = [], []
    for sent in sentences:
        if cur and (len(cur) >= rules["max_sentences"] or len(" ".join(cur + [sent])) > rules["block_max_chars"]):
            chunks.append(" ".join(cur))
            cur = []
        cur.append(sent)
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def required_blocks(total_chars, rules):
    if total_chars > rules["three_blocks_over"]:
        return 3
    if total_chars > rules["two_blocks_over"]:
        return 2
    return 1


def reflow(text, rules):
    """Pecah teks menjadi blok pendek yang dipisah baris kosong. Idempoten."""
    text = (text or "").replace("\r", "").strip()
    seeds = [re.sub(r"[ \t]+", " ", b).strip() for b in re.split(r"\n+", text) if b.strip()]
    blocks = []
    for seed in seeds:
        blocks += _chunk(split_sentences(seed), rules)
    if not blocks:
        return text
    # Hook: kalimat pertama berdiri sendiri.
    first = split_sentences(blocks[0])
    if len(first) > 1 and len(first[0]) <= rules["hook_hard_chars"]:
        blocks[0:1] = [first[0], " ".join(first[1:])]
    # Pastikan jumlah blok minimal sesuai panjang.
    need = required_blocks(sum(len(b) for b in blocks), rules)
    while len(blocks) < need:
        candidates = [i for i, b in enumerate(blocks) if count_sentences(b) > 1]
        if not candidates:
            break
        idx = max(candidates, key=lambda i: len(blocks[i]))
        sents = split_sentences(blocks[idx])
        blocks[idx:idx + 1] = [sents[0], " ".join(sents[1:])]
    return SEPARATOR.join(blocks)


def check_format(text, rules, root=True):
    """Return daftar alasan penolakan (kosong = format lolos)."""
    reasons = []
    blocks = blocks_of(text)
    if not blocks:
        return ["empty"]
    total = sum(len(b) for b in blocks)
    if len(blocks) > rules["max_blocks"]:
        reasons.append("too-many-blocks")
    if len(blocks) < required_blocks(total, rules):
        reasons.append("wall-of-text")
    if any(count_sentences(b) > rules["max_sentences"] for b in blocks):
        reasons.append("long-block")
    if any(len(b) > rules["block_max_chars"] * 1.1 for b in blocks):
        reasons.append("block-too-long")
    first = split_sentences(blocks[0])
    if root and first and len(first[0]) > rules["hook_hard_chars"]:
        reasons.append("hook-too-long")
    if "\n" in text.strip() and SEPARATOR not in text.strip():
        reasons.append("no-blank-line")
    return reasons


def thread_settings(cfg):
    """Utas (multi-post). Default di kode; override opsional di config.json -> thread."""
    t = cfg.get("thread", {}) if cfg else {}
    return {"enabled": bool(t.get("enabled", True)), "max_parts": max(1, min(int(t.get("max_parts", 4)), 6))}


def split_into_parts(text, max_chars, max_parts):
    """Pecah teks yang kepanjangan menjadi beberapa post pada batas blok. None jika tidak bisa."""
    blocks = blocks_of(text)
    if any(len(b) > max_chars for b in blocks):
        return None
    parts, cur = [], []
    for b in blocks:
        if cur and len(SEPARATOR.join(cur + [b])) > max_chars:
            parts.append(cur)
            cur = [b]
        else:
            cur.append(b)
    if cur:
        parts.append(cur)
    # Hindari bagian terakhir yang terlalu pendek: pinjam satu blok dari bagian sebelumnya.
    if len(parts) > 1 and len(SEPARATOR.join(parts[-1])) < 80 and len(parts[-2]) > 1:
        moved = parts[-2][-1]
        if len(SEPARATOR.join([moved] + parts[-1])) <= max_chars:
            parts[-1].insert(0, parts[-2].pop())
    joined = [SEPARATOR.join(p) for p in parts]
    return joined if 1 <= len(joined) <= max_parts else None
