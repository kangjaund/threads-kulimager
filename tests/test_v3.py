"""Test offline V3 (tanpa jaringan, Groq di-mock). Jalankan: python -m unittest discover -s tests -v"""
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import conversation as conv  # noqa: E402
import generate  # noqa: E402
from rss_sources import research_settings  # noqa: E402


def ts(days=0.5):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")


def mk(i, text, user, days=0.5, **kw):
    return {"id": f"threads-{i}", "source": "Threads", "type": "social", "title": f"@{user}", "username": user,
            "summary": text, "published_at": ts(days), "url": f"https://threads.net/p/{i}", "rank": kw.pop("rank", 1),
            "has_replies": kw.pop("has_replies", True), "search_type": "TOP", **kw}


ITEMS = [
    mk(1, "Jujur capek banget debat vibe coding itu coding beneran atau bukan. Hasil akhirnya jalan tapi maintain-nya mimpi buruk", "a"),
    mk(2, "Vibe coding itu overrated menurut gue, masalahnya begitu project membesar kodenya nggak ada yang ngerti lagi", "b"),
    mk(3, "Orang ribut soal vibe coding padahal yang penting produknya jalan dan user mau bayar, tapi ya maintain-nya gimana", "c"),
    mk(4, "Remote work ternyata nggak menghilangkan meeting, cuma pindah ke kalender. Capek banget sumpah", "d"),
    mk(5, "Kerja remote tapi meeting terus, bingung sebenarnya bedanya sama kantor apa selain macet", "e"),
    mk(6, "Open order jasa desain murah! DM aku sekarang, diskon 50% link in bio", "spam"),
    mk(7, "AI coding tools bikin standar junior developer berubah, tapi nggak semua perusahaan sadar soal itu", "f", days=40),
]
SETTINGS = research_settings(json.loads((ROOT / "config.json").read_text(encoding="utf-8")))


class TestMining(unittest.TestCase):
    def test_settings_mode(self):
        self.assertEqual(SETTINGS["source_mode"], "threads_only")

    def test_spam_and_old_filtered_and_clustered(self):
        cl = conv.select_clusters(SETTINGS, ITEMS, [], 5)
        ids = {i["id"] for c in cl for i in c["items"]}
        self.assertNotIn("threads-6", ids)  # spam
        self.assertNotIn("threads-7", ids)  # terlalu lama
        labels = [c["label"] for c in cl]
        self.assertTrue(any("vibe_coding" in l for l in labels), labels)
        vibe = next(c for c in cl if "vibe_coding" in c["tags"])
        self.assertGreaterEqual(len(vibe["items"]), 2)

    def test_score_reacts_to_tension(self):
        a = conv.score_item(ITEMS[1])["tension"]
        b = conv.score_item(mk(9, "Hari ini saya menulis laporan mingguan untuk tim", "z"))["tension"]
        self.assertGreater(a, b)


class TestGate(unittest.TestCase):
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

    def reasons(self, text, ptype="observation", recent=()):
        return generate.v3_reasons(" ".join(text.split()), text, self.cfg, ptype, recent)

    def test_rejects(self):
        self.assertIn("newsy", self.reasons("OpenAI mengumumkan model baru"))
        self.assertIn("article-structure", self.reasons("Kesimpulan: AI itu penting"))
        self.assertIn("list-structure", self.reasons("1. satu\n\n2. dua\n\n3. tiga"))
        self.assertIn("engagement-bait", self.reasons("Vibe coding capek. Setuju nggak?"))
        self.assertNotIn("engagement-bait", self.reasons("Vibe coding capek. Menurut kamu?", "discussion"))
        self.assertIn("engagement-bait", self.reasons("Follow untuk tips AI"))
        self.assertIn("fake-first-person", self.reasons("Kemarin gue nyobain Cursor seharian"))
        self.assertIn("fake-first-person", self.reasons("Klien gue minta revisi terus"))
        self.assertIn("unsourced-stat", self.reasons("Sekitar 70% freelancer pakai AI"))

    def test_accepts_normal(self):
        self.assertEqual(self.reasons("Remote work nggak menghilangkan meeting.\n\nMeetingnya cuma pindah ke kalender."), [])

    def test_slang_overuse(self):
        recent = ["gue pikir begitu"] * 5
        self.assertIn("slang-overuse:gue", self.reasons("Menurut gue ini aneh", recent=recent))


def fake_groq_factory(good=True):
    def fake(cfg, system, user, name, schema, max_tokens=None, static_chars=0):
        if name == "angle_extraction":
            ids = [l[1:3] for l in user.splitlines() if l.startswith("[C")]
            return {"clusters": [{"id": i, "skip": False, "skip_reason": "", "conversation": "debat",
                                  "tension": "dua kubu", "assumption": "a", "underdiscussed": "maintain",
                                  "angle": "nuance", "angle_note": "soroti maintenance", "pillar": "builder_culture"}
                                 for i in ids]}
        ids = [l.split(":")[0] for l in user.splitlines() if l[:2] == "C1" or l[:2] == "C2" or l[:2] == "C3" or l[:2] == "C4"]
        ids = sorted({i for i in ids if i.startswith("C")})
        text1 = ("Pertanyaan soal vibe coding itu bukan coding beneran atau bukan.", "Yang menarik justru siapa yang maintain nanti.",
                 "Hasil jalan hari ini belum tentu jalan enam bulan lagi.")
        bad = ("Kemarin gue nyobain Cursor dan hasilnya bagus.", "Menurut laporan terbaru ini penting.", "Setuju nggak?")
        t = text1 if good else bad
        return {"posts": [{"source_id": i, "skip": False, "skip_reason": "", "pillar": "builder_culture",
                           "block_1": t[0], "block_2": t[1], "block_3": t[2], "block_4": "", "block_5": "",
                           "thread_2": "", "thread_3": "", "thread_4": ""} for i in ids[:2]]}
    return fake


class TestPipeline(unittest.TestCase):
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

    def run_with(self, good):
        items = json.loads(json.dumps(ITEMS))
        generate.load_research = lambda: items
        generate.groq_chat = fake_groq_factory(good)
        generate.throttle = lambda *a, **k: None
        return generate.run_threads_only(self.cfg, [], [], 4)

    def test_good_posts_accepted(self):
        accepted, marks, failures = self.run_with(True)
        self.assertGreaterEqual(len(accepted), 1)
        a = accepted[0]
        self.assertIn("conversation", a)
        self.assertIn(a["format"], self.cfg["v3"]["post_types"])
        self.assertTrue(all(k in marks for k in a["research_item_ids"]))
        self.assertEqual(failures, 0)

    def test_bad_posts_rejected(self):
        accepted, marks, failures = self.run_with(False)
        self.assertEqual(accepted, [])


if __name__ == "__main__":
    unittest.main()
