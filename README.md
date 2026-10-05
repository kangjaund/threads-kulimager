# Threads Autopilot V2

Pipeline otomatis untuk akun Threads:

**Groq → Content DNA + Hook Engine → Quality Gate → Queue → Threads API**

Versi V2 dirancang supaya output tidak terasa seperti artikel AI generik. Generator diberi voice yang lebih berani, mekanisme hook, aturan anti-AI, dan quality gate deterministic sebelum post masuk antrean.

## Cara kerja

```text
08:00 WIB
Generate 8 kandidat
      ↓
Content DNA / Hook Engine
      ↓
Quality Gate
      ↓
Masuk queue sebagai approved
      ↓
09:00 ──┐
13:00   │
17:00   ├── Threads API
21:00 ──┘
```

Queue ditargetkan **16 post**, generator mengisi maksimal **8 post/run**, dan scheduler mempublikasikan maksimal **4 post/hari**.

## 1. Setup satu kali

1. Buat repo **privat** di GitHub dan upload seluruh isi folder.
2. Pastikan branch default berisi `.github/workflows/*`.
3. Settings → Actions → General → Workflow permissions: izinkan workflow menulis ke repo jika organisasi/repo membatasinya.
4. Isi GitHub Secrets:

| Secret | Isi |
|---|---|
| `GROQ_API_KEY` | API key GroqCloud |
| `THREADS_USER_ID` | ID akun Threads |
| `THREADS_ACCESS_TOKEN` | Access token Threads |
| `GH_PAT` | PAT GitHub yang diperlukan workflow refresh token untuk update secret |

## 2. Tes sebelum autopilot

**Jangan langsung membiarkan bot posting tanpa melihat hasil pertamanya.**

1. Actions → **Generate konten** → Run workflow.
2. Buka `data/posts.json` dan baca beberapa hasil.
3. Jika voice sudah cocok, workflow posting berikutnya akan mengambil item berstatus `approved` secara otomatis.
4. Untuk simulasi posting manual: Actions → **Posting ke Threads** → Run workflow → `dry_run=true`.
5. Untuk posting sungguhan secara manual, pilih `dry_run=false`.

Setelah lolos tes awal, kamu tidak perlu menjalankan workflow satu per satu. Schedule akan bekerja otomatis.

## 3. Jadwal default

GitHub Actions memakai UTC. Jadwal V2 dikonversi ke WIB (UTC+7):

- Generate: **08:00 WIB setiap hari**
- Post: **09:00 WIB**
- Post: **13:00 WIB**
- Post: **17:00 WIB**
- Post: **21:00 WIB**

Cron GitHub tidak menjamin presisi sampai detik dan dapat mengalami delay.

## 4. Content Engine V2 (Groq)

`config.json` sekarang punya beberapa lapisan. Generator menggunakan Groq melalui OpenAI-compatible Chat Completions API.

### Voice

```json
"voice": {
  "boldness": 0.78,
  "directness": 0.88,
  "opinionated": 0.72,
  "playfulness": 0.42,
  "sarcasm": 0.18,
  "specificity": 0.86
}
```

Angka ini adalah **instruksi prompt**, bukan parameter API. Artinya kita menggunakannya untuk mengarahkan karakter tulisan.

### Hook Engine

Generator diarahkan untuk memakai mekanisme seperti:

- contrarian
- pattern interrupt
- hard truth
- curiosity gap
- specific observation
- direct challenge
- unexpected comparison
- myth busting

### Anti-AI

Ada daftar pola generik seperti:

- `Banyak orang...`
- `Di era digital...`
- `Jika kamu ingin...`
- `Berikut beberapa...`
- `Pada akhirnya...`
- `Semoga bermanfaat`

Generator diminta menghindari pola tersebut dan quality gate juga menolak beberapa generic opening yang paling jelas.

### Quality Gate

Sebelum masuk queue, post diperiksa untuk:

- panjang minimum/maksimum
- generic opening
- terlalu banyak tanda seru/tanya
- terlalu banyak hashtag
- repetisi kata yang ekstrem
- kemiripan dengan post sebelumnya
- kalimat yang terlalu flat

Ini bukan penilaian kualitas semantik sempurna, tetapi lapisan pengaman agar autopilot tidak langsung memasukkan output jelek ke antrean.

## 5. Mengatur karakter akun

Mayoritas tuning dilakukan di `config.json`, bukan di Python.

Jika output masih terlalu aman:

```json
"boldness": 0.85,
"opinionated": 0.80,
"directness": 0.90
```

Jika terlalu nyinyir/edgy, turunkan `boldness` atau `sarcasm`.

Jika terlalu generik, naikkan `specificity` dan tambahkan contoh voice yang kamu sukai ke `writing_dna`.

## 6. Mengatur frekuensi

Saat ini targetnya 4 post/hari. Untuk mengubahnya, sesuaikan:

- `max_posts_per_day` di `config.json`
- cron di `.github/workflows/post.yml`
- `queue_target` dan `posts_per_generate` jika ingin buffer lebih besar/kecil

Rekomendasi awal: **4 post/hari + queue 16**. Jangan langsung menaikkan frekuensi hanya karena automation sudah tersedia; kualitas dan variasi lebih penting.

## 7. Token Threads

`refresh-token.yml` tetap disediakan untuk workflow refresh token mingguan. Pastikan `GH_PAT` mempunyai permission yang benar untuk memperbarui secret repository.

## 8. Keamanan

- Jangan commit API key/token ke repo.
- Gunakan GitHub Secrets.
- Repo sebaiknya private.
- Jangan memasukkan data pribadi ke prompt/history.
- Review hasil beberapa hari pertama sebelum mempercayakan autopilot sepenuhnya.

\n## 9. Groq\n\nGenerator saat ini menggunakan `openai/gpt-oss-120b` melalui Groq. API key dibaca dari GitHub Secret `GROQ_API_KEY`; jangan menaruh key di `config.json` atau source code. Model dan parameter inference dapat diubah dari `config.json`.\n\nGroq mendukung Structured Outputs untuk model ini, sehingga generator meminta JSON Schema strict dan tidak bergantung pada parsing Markdown/code fence.\n