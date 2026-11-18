# Menjalankan Mesin Cuan dari GitHub Actions

Workflow: `.github/workflows/run-mesin-cuan.yml`

Workflow ini dapat dijalankan dari aplikasi/browser GitHub di HP. Workflow menjalankan pipeline `main.py --channel ... --topic ...` dan menyimpan hasil/log sebagai GitHub Actions Artifact selama 7 hari.

## 1. Tambahkan GitHub Actions Secrets

Buka repository **Settings → Secrets and variables → Actions → New repository secret**.

Tambahkan secrets berikut sesuai API yang benar-benar kamu gunakan:

| Secret | Kegunaan |
|---|---|
| `TOKEN_CH_ID_HORROR` | Isi lengkap JSON token OAuth Google untuk channel Horror Facts ID |
| `TOKEN_CH_ID_PSYCH` | Isi lengkap JSON token OAuth Google untuk channel Psikologi ID |
| `TOKEN_CH_EN_HORROR` | Isi lengkap JSON token OAuth Google untuk channel Horror Facts EN |
| `TOKEN_CH_EN_PSYCH` | Isi lengkap JSON token OAuth Google untuk channel Psychology EN |
| `YOUTUBE_API_KEY` | YouTube Data API key untuk riset/topik |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `GOOGLE_DRIVE_FOLDER_ID` | Folder Drive tujuan jika dipakai konfigurasi aplikasi |
| `PROVIDER_A_API_KEY` | API key provider AI A |
| `PROVIDER_A_BASE_URL` | Base URL provider AI A, contoh sesuai akun/provider |
| `PROVIDER_A_MODEL` | Nama model provider AI A |
| `PROVIDER_B_API_KEY` | API key provider AI B |
| `PROVIDER_B_BASE_URL` | Base URL provider AI B |
| `PROVIDER_B_MODEL` | Nama model provider AI B |
| `GEMINI_API_KEY` | API key Gemini jika dipakai |
| `GROQ_API_KEY` | API key Groq jika dipakai |
| `ANTHROPIC_API_KEY` | API key Anthropic jika dipakai |
| `NVIDIA_API_KEY` | API key NVIDIA jika dipakai |
| `PERPLEXITY_API_KEY` | API key Perplexity jika dipakai |
| `PEXELS_API_KEY` | API key Pexels untuk footage |
| `PIXABAY_API_KEY` | API key Pixabay untuk footage |
| `COVERR_API_KEY` | API key Coverr jika dipakai |
| `COVERR_APP_ID` | App ID Coverr jika dipakai |
| `FREESOUND_API_KEY` | API key Freesound jika dipakai |
| `ELEVENLABS_API_KEY` | API key ElevenLabs jika dipakai |
| `TELEGRAM_BOT_TOKEN` | Token bot Telegram jika notifikasi dipakai |
| `TELEGRAM_CHAT_ID` | Chat ID Telegram jika notifikasi dipakai |

Secret yang ditandai 'jika dipakai' boleh dikosongkan jika provider tersebut tidak digunakan. Minimal isi token OAuth channel yang dipilih, provider AI aktif, dan API footage yang dibutuhkan.

### Format token OAuth

Secret token harus berisi **isi JSON token**, bukan nama file dan bukan Base64. Contoh struktur (gunakan token asli milikmu, jangan salin contoh ini):

```json
{
  "token": "ACCESS_TOKEN",
  "refresh_token": "REFRESH_TOKEN",
  "token_uri": "https://oauth2.googleapis.com/token",
  "client_id": "CLIENT_ID",
  "client_secret": "CLIENT_SECRET",
  "scopes": [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/drive.file"
  ]
}
```

Buat token melalui `python setup_auth.py` pada perangkat yang dapat menyelesaikan login Google OAuth. Jangan pernah menaruh token atau API key di file yang di-commit ke repository, issue, atau chat publik. Jangan mengirim secret kepada orang lain.

Alias `ch_horror_id` menggunakan token yang sama dengan `ch_id_horror`, sesuai `config/settings.json`.

## 2. Jalankan dari HP

1. Buka repository `Masfu22/mesin-cuan` di GitHub.
2. Masuk tab **Actions**.
3. Pilih workflow **Mesin Cuan - Produksi Video**.
4. Tekan **Run workflow**.
5. Pilih channel, masukkan topik, pilih `shorts` atau `long_form`, lalu jalankan.
6. Buka proses yang berjalan untuk melihat log.
7. Jika selesai, unduh artifact untuk mengambil output/log yang tersimpan.

## 3. Alur upload YouTube

Workflow ini mengikuti arsitektur repository saat ini: `main.py` memproduksi video dan `engine/gdrive_engine.py` mengirim video beserta metadata ke folder antrean Google Drive. README proyek menyebut layanan terpisah `mesin-cuan-uploader` di Koyeb/Railway yang mengambil antrean itu dan mengunggah ke YouTube sesuai jadwal.

**Artinya workflow ini belum mengunggah langsung ke YouTube.** Upload otomatis ke YouTube baru berjalan jika layanan uploader terpisah sudah aktif, memiliki akses Google Drive/YouTube yang valid, dan memantau folder antrean yang sama.

## 4. Catatan operasional

- Mulai dari satu video Shorts untuk menguji konfigurasi sebelum menjalankan long-form atau banyak video.
- GitHub-hosted runner bersifat sementara; file lokal akan hilang setelah job selesai kecuali disimpan sebagai artifact atau diunggah ke Drive.
- Rendering video dapat memakan waktu dan RAM. Runner GitHub standar tidak menyediakan GPU khusus.
- Workflow memakai Edge TTS dan preset render `fast` untuk menghindari ketergantungan pada GPU lokal.
- Jangan aktifkan jadwal publikasi massal sebelum memeriksa hasil video, metadata, disclosure konten sintetis, hak footage/audio, serta pengaturan privasi YouTube.
- Jangan menaruh kredensial OAuth atau API key di log. Jika token pernah terpublikasi, cabut/revoke dan buat token baru.
