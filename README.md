# Threads Autopilot V2

Pipeline semi-autopilot untuk akun Threads:

**Groq → Content DNA + Hook Engine → Quality Gate → Telegram Approval → Queue → Threads API**

Generator membuat draft dan mengirimnya ke Telegram. Defaultnya **mode veto**: draft diposting otomatis di slot berikutnya **kecuali kamu menekan Reject**. Tekan Approve hanya bila ingin sebuah draft naik lebih dulu.

## Cara kerja

```text
08:00 WIB
Generate kandidat
      ↓
Content DNA / Hook Engine
      ↓
Quality Gate
      ↓
🟡 PENDING
      ↓
Telegram
[ Approve ] [ Reject ]
      ↓
🟢 APPROVED
      ↓
Threads API
```

Approval diproses oleh GitHub Actions tepat sebelum tiap jadwal posting (bukan polling terus-menerus), sehingga hemat kuota menit GitHub Actions gratis. Approval dari HP tidak membutuhkan dashboard baru. Inline keyboard digunakan untuk action utama; slash command `/approve ID` dan `/reject ID` tetap tersedia sebagai fallback. Telegram memang mendukung callback query untuk inline buttons, dan `getUpdates` dapat dipakai untuk long polling. citeturn0search8turn0search2

## 1. Setup satu kali

1. Buat repo **private** di GitHub dan upload seluruh isi folder.
2. Pastikan branch default berisi `.github/workflows/*`.
3. Settings → Actions → General → Workflow permissions: izinkan workflow menulis ke repo jika organisasi/repo membatasinya.
4. Buat Telegram bot melalui **@BotFather**.
5. Buka chat pribadi dengan bot tersebut dan kirim `/start`.
6. Isi GitHub Secrets:

| Secret | Isi |
|---|---|
| `GROQ_API_KEY` | API key GroqCloud |
| `THREADS_USER_ID` | ID akun Threads |
| `THREADS_ACCESS_TOKEN` | Access token Threads |
| `TELEGRAM_BOT_TOKEN` | Token bot dari BotFather |
| `TELEGRAM_CHAT_ID` | ID chat Telegram pribadi yang akan menerima approval |
| `GH_PAT` | PAT GitHub yang diperlukan workflow refresh token untuk update secret |

**Penting:** `TELEGRAM_CHAT_ID` adalah allowlist. Callback dari chat lain akan ditolak.

## 2. Approval flow

Setiap draft baru dibuat dengan:

```json
"status": "pending"
```

Script `src/telegram_approval.py` dijalankan di dua tempat:

1. **`generate.yml`** (setelah generate): mengirim draft `pending` yang belum pernah dinotifikasi ke Telegram.
2. **`post.yml`** (sebelum posting): mengambil tombol Approve/Reject yang kamu tekan sejak run terakhir, lalu langsung memposting item `approved` berikutnya.

Artinya, approve **sebelum jam posting** (misalnya sebelum 09:00 WIB untuk post jam 09:00). Approval yang masuk setelahnya diproses di jadwal posting berikutnya. Kalau Telegram sedang bermasalah, langkah ini tidak menghentikan posting draft yang sudah `approved`.

Pesan Telegram berbentuk:

```text
🤖 Draft Threads #123

<draft>

────────────
Score: 89/100
Hook: 9/10 · Specificity: 8/10
Boldness: 9/10 · AI-ish: 1/10

Pillar: freelance
Format: strong_opinion

[ ✅ Approve ] [ ❌ Reject ]
```

Score tersebut adalah **heuristic transparan**, bukan penilaian LLM. Tujuannya hanya membantu scanning cepat dari HP.

Setelah `Approve`:

```text
pending → approved → posted
```

Setelah `Reject`:

```text
pending → rejected
```

Pada mode veto, workflow posting mengambil draft `approved` atau `pending` yang sudah lewat jendela veto (lihat bagian *Mode veto*). Draft `rejected` tidak akan pernah diposting.

## Mode veto (default)

Tiap slot posting memilih draft berikutnya (id terkecil lebih dulu) yang memenuhi salah satu syarat:

- statusnya `approved` (kamu menekan Approve), atau
- statusnya `pending`, **sudah terkirim ke Telegram**, dan sudah lewat jendela veto (default **30 menit** sejak terkirim).

Artinya: kamu cukup menekan **Reject** pada draft yang tidak kamu mau, sebelum jam posting. Sisanya terbit sendiri.

Pengaman:

- Draft yang belum pernah terkirim ke Telegram **tidak pernah** diposting otomatis. Kalau Telegram bermasalah, tidak ada yang terbit tanpa kesempatan veto.
- Tombol Reject diproses tepat sebelum tiap run posting, jadi Reject yang kamu tekan sebelum jam posting selalu menang.
- Postingan otomatis diberi tanda `auto_approved_at` di `posts.json`.

Pengaturan opsional (tidak wajib ada di `config.json`; kalau tidak ada, default di bawah dipakai):

```json
"approval_mode": "veto",
"veto_window_minutes": 30
```

- `"approval_mode": "manual"` mengembalikan ke perilaku lama: hanya draft `approved` yang diposting.
- `"require_approval": false` (yang sudah ada di config) membuat draft langsung `approved` sejak dibuat, alias full otomatis tanpa review.

## 3. Jadwal default

GitHub Actions memakai UTC. Jadwal V2 dikonversi ke WIB (UTC+7):

- Generate: **08:00 WIB setiap hari**
- Approval Telegram diproses sebelum tiap run posting (lihat bagian 2)
- Post: **09:00 WIB**
- Post: **13:00 WIB**
- Post: **17:00 WIB**
- Post: **21:00 WIB**

GitHub cron tidak menjamin presisi sampai detik dan dapat mengalami delay.

**Catatan kuota:** repo privat di akun GitHub Free mendapat 2.000 menit Actions per bulan dan tiap job dibulatkan ke atas ke menit penuh. Dengan jadwal ini pemakaian sekitar 150-200 menit per bulan. Jangan menambah cron yang berjalan sangat sering (misalnya tiap 5 menit) di repo privat.

## 4. Content Engine V2 (Groq)

Generator menggunakan Groq melalui OpenAI-compatible Chat Completions API.

Model default:

```json
"model": "openai/gpt-oss-120b",
"reasoning_effort": "low",
"max_completion_tokens": 3000
```

API key dibaca dari `GROQ_API_KEY`. Jangan menaruh key di `config.json` atau source code.

Generator menggunakan Structured Outputs dengan JSON Schema strict agar hasil model tidak bergantung pada Markdown/code fence.

## 5. Perubahan penting pada voice

Versi sebelumnya sudah memiliki Hook Engine, tetapi contoh hasil menunjukkan model masih cenderung membuat **mini-artikel**:

- `Pernah dengar...`
- `Padahal...`
- `Realitanya...`
- `Lesson:`
- `Myth:`
- `Bandingkan:`
- pertanyaan generik di akhir

V2 sekarang secara eksplisit meminta:

- kalimat pertama harus bisa berdiri sebagai hook;
- tension / POV muncul sejak awal;
- ritme pendek dan whitespace strategis;
- satu kalimat yang quotable;
- tidak membuka dengan definisi topik;
- tidak memakai label format secara literal;
- tidak selalu mengakhiri post dengan pertanyaan;
- tidak mengarang pengalaman pribadi.

Quality gate juga menolak beberapa pola tersebut secara deterministic.

## 6. Mengapa hasil contoh sebelumnya belum cukup Threads-first

Beberapa contoh yang kamu kirim memang masih punya masalah:

**#1** — `Pernah dengar orang bilang...` masih terasa seperti pembuka artikel edukasi. Insight-nya masuk akal, tetapi hook tidak cukup tajam.

**#2** — lebih baik karena ada kontras `sunset over lake` vs niche industri, tetapi ending `Tren foto Instagram itu cuma ilusi profit cepat` masih terdengar seperti slogan.

**#3** — struktur ceritanya cocok untuk Threads, tetapi kalimat `Saya pernah...` melanggar aturan source karena automation tidak punya fakta bahwa pengalaman itu benar-benar terjadi.

**#4** — `Lesson:` membuat format terlalu terlihat. Selain itu, `Saya pernah habiskan...` juga merupakan fabricated first-person experience jika tidak ada sumber.

**#5** — cukup usable, tetapi terlalu seperti comparison article. Perlu POV yang lebih tajam dan tidak sekadar menyajikan trade-off dua sisi.

**#6** — `Myth:` terlalu template-like dan contoh pengalaman pribadi juga tidak bersumber.

**#7** — insight cukup konkret, tetapi penutup `seberapa penting...` terasa seperti engagement bait.

**#8** — `Platform A` dan `Platform B` dengan angka royalti terlihat seperti fakta, padahal tidak ada sumber. Ini sekarang secara eksplisit dilarang.

Jadi saya tidak hanya menaikkan `temperature` atau `boldness`. Problem utamanya ada pada **instruction hierarchy + format priors + quality gate**, bukan kecepatan API.

## 7. Mengatur karakter akun

`style_weights` menentukan seberapa sering tiap style dipakai (dipilih acak berbobot). Semua nilai di `voice` (boldness, directness, opinionated, playfulness, sarcasm, specificity) dikirim ke prompt.


Mayoritas tuning dilakukan di `config.json`.

Jika output masih terlalu aman:

```json
"boldness": 0.85,
"opinionated": 0.80,
"directness": 0.90
```

Jika terlalu edgy, turunkan `boldness` atau `sarcasm`.

Jika terlalu generik, naikkan `specificity` dan tambahkan contoh voice yang benar-benar kamu sukai ke `writing_dna`.

## 8. Mengatur frekuensi

Saat ini targetnya 4 post/hari.

Sesuaikan:

- `max_posts_per_day` di `config.json`
- cron di `.github/workflows/post.yml`
- `queue_target` dan `posts_per_generate` jika ingin buffer lebih besar/kecil

Untuk tahap ini, **4 post/hari + Telegram approval + queue 16** lebih aman daripada full autopilot.

## 9. Token Threads

`refresh-token.yml` tetap disediakan untuk workflow refresh token mingguan. Pastikan `GH_PAT` mempunyai permission yang benar untuk memperbarui secret repository.

## 10. Keamanan

- Jangan commit API key/token ke repo.
- Gunakan GitHub Secrets.
- Repo sebaiknya private.
- Jangan memasukkan data pribadi ke prompt/history.
- Jangan memakai Telegram group sebagai approval channel kecuali memang diperlukan. Untuk penggunaan pribadi, private chat lebih sederhana.
- Jika bot pernah dipasang webhook, hapus webhook terlebih dahulu karena Telegram tidak mengizinkan `getUpdates` berjalan bersamaan dengan outgoing webhook. citeturn0search4turn0search8

### Mendapatkan `TELEGRAM_CHAT_ID`

Setelah membuat bot, kirim `/start` ke bot. Dari mesin lokal yang memiliki `TELEGRAM_BOT_TOKEN`, jalankan:

```bash
TELEGRAM_BOT_TOKEN="TOKEN_DARI_BOTFATHER" python src/telegram_setup.py
```

Script hanya membaca update yang masuk dan mencetak `chat_id`; tidak menyimpan token atau mengubah state approval.
