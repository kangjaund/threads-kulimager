# Threads Autopilot

Pipeline otomatis (bukan AI agent): **generate konten (Gemini) -> antrean -> posting terjadwal ke Threads**, semuanya di GitHub Actions.

```
generate.yml  (1x/hari)   -> src/generate.py -> data/posts.json (status pending/approved)
post.yml      (beberapa x/hari) -> src/post.py -> Threads API   -> status posted
refresh-token.yml (mingguan) -> src/refresh_token.py -> update secret token
```

## 1. Siapkan repo
1. Buat repo **privat** di GitHub, upload seluruh isi folder ini.
2. Pastikan branch default berisi file `.github/workflows/*` (workflow terjadwal hanya jalan dari branch default).
3. Settings -> Actions -> General -> Workflow permissions: izinkan workflow menulis ke repo (jika organisasi membatasi).

## 2. Siapkan Meta / Threads API
1. Di Meta for Developers buat app dan tambahkan use case Threads API.
2. Aktifkan permission `threads_basic` dan `threads_content_publish`.
3. Daftarkan akun Threads-mu sebagai tester app, lalu terima undangannya dari aplikasi Threads.
4. Buat user access token (short-lived), lalu tukar jadi long-lived (berlaku ~60 hari):
   ```
   curl "https://graph.threads.net/access_token?grant_type=th_exchange_token&client_secret=APP_SECRET&access_token=SHORT_LIVED_TOKEN"
   ```
5. Ambil user id:
   ```
   curl "https://graph.threads.net/v1.0/me?fields=id,username&access_token=LONG_LIVED_TOKEN"
   ```
Nama menu di dashboard Meta bisa berubah; ikuti dokumentasi resmi Threads API bila ada perbedaan.

## 3. Isi GitHub Secrets
Settings -> Secrets and variables -> Actions -> New repository secret:

| Secret | Isi |
|---|---|
| `GEMINI_API_KEY` | API key dari Google AI Studio |
| `THREADS_USER_ID` | id akun Threads (langkah 2.5) |
| `THREADS_ACCESS_TOKEN` | long-lived token (langkah 2.4) |
| `GH_PAT` | Personal Access Token GitHub yang boleh menulis secret repo ini (fine-grained: repo ini saja, permission **Secrets: Read and write**) |

## 4. Tes bertahap
1. Actions -> **Generate konten** -> Run workflow. Cek `data/posts.json`: postingan baru berstatus `pending`.
2. Ubah `"status": "pending"` menjadi `"approved"` pada postingan yang kamu setujui (edit langsung di GitHub). Set `require_approval` ke `false` di `config.json` kalau mau semua otomatis approved.
3. Actions -> **Posting ke Threads** -> Run workflow dengan `dry_run = true`. Pastikan teks yang akan diposting benar.
4. Jalankan lagi dengan `dry_run = false` untuk posting sungguhan.
5. Actions -> **Refresh token Threads** -> Run workflow. Catatan: token baru bisa di-refresh setelah berumur minimal 24 jam, jadi tes ini bisa gagal di hari pertama.

## 5. Mengatur frekuensi & gaya
- **Frekuensi posting**: ubah baris `cron` di `.github/workflows/post.yml` (jam dalam UTC, WIB = UTC+7). Contoh 6x/hari: `"0 0,3,6,9,12,15 * * *"`.
- **Batas harian**: `max_posts_per_day` di `config.json`.
- **Gaya**: atur bobot di `style_weights`. Set satu gaya ke 1 dan lainnya ke 0 untuk memakai gaya tunggal. Tambah gaya baru di `styles`.
- **Topik & format**: edit `pillars` dan `formats`. Generator memilih yang paling jarang dipakai agar variatif.
- **Aturan konten**: edit `rules`. Ini yang menjaga konten tetap evergreen dan tanpa klaim penghasilan.
- **Model**: `model` di `config.json` (default `gemini-flash-latest`). Cek daftar model terbaru di Google AI Studio.

## 6. Catatan penting
- Jadwal cron GitHub tidak presisi (bisa molor beberapa menit hingga belasan menit).
- Postingan gagal dicoba maksimal 3x, lalu berstatus `failed` agar tidak memblokir antrean. Lihat `last_error` di `posts.json`.
- Free tier Gemini boleh dipakai Google untuk meningkatkan produknya; jangan kirim data pribadi.
- Jangan pernah commit token atau API key ke repo. Semuanya lewat GitHub Secrets.
- Batas teks Threads 500 karakter; config memakai 450 sebagai margin aman.
