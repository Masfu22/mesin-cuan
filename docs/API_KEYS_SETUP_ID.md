# Panduan GitHub Secrets — Mesin Cuan

Repository: `Masfu22/mesin-cuan`

## Cara menambahkan Secret
Buka **Settings → Secrets and variables → Actions → New repository secret**. Isi nama dan nilai, lalu tekan **Add secret**. Ulangi untuk setiap secret yang diperlukan.

## AI — minimal satu provider aktif
| Secret | Kegunaan | Sumber |
|---|---|---|
| `GEMINI_API_KEY` | AI utama yang direkomendasikan | https://aistudio.google.com/apikey |
| `GROQ_API_KEY` | AI alternatif/fallback | https://console.groq.com/keys |
| `PROVIDER_A_API_KEY` | Provider A | Portal resmi provider |
| `PROVIDER_A_BASE_URL` | Endpoint Provider A | Portal resmi provider |
| `PROVIDER_A_MODEL` | Nama model Provider A | Portal resmi provider |
| `PROVIDER_B_API_KEY` | Provider B | Portal resmi provider |
| `PROVIDER_B_BASE_URL` | Endpoint Provider B | Portal resmi provider |
| `PROVIDER_B_MODEL` | Nama model Provider B | Portal resmi provider |
| `ANTHROPIC_API_KEY` | AI fallback | https://console.anthropic.com/ |

Isi minimal satu jalur AI yang benar-benar didukung konfigurasi aplikasi. Jangan menebak BASE_URL atau MODEL.

## YouTube dan Google Drive
| Secret | Kegunaan |
|---|---|
| `YOUTUBE_API_KEY` | YouTube Data API |
| `GOOGLE_CLIENT_ID` | OAuth Google |
| `GOOGLE_CLIENT_SECRET` | OAuth Google |
| `GOOGLE_DRIVE_FOLDER_ID` | ID folder antrean Google Drive |
| `TOKEN_CH_ID_HORROR` | OAuth refresh token channel ch_id_horror |
| `TOKEN_CH_ID_PSYCH` | OAuth refresh token channel ch_id_psych |
| `TOKEN_CH_EN_HORROR` | OAuth refresh token channel ch_en_horror |
| `TOKEN_CH_EN_PSYCH` | OAuth refresh token channel ch_en_psych |

Setiap TOKEN_CH_* harus berupa JSON OAuth authorized-user lengkap yang memiliki `refresh_token`, bukan hanya access token. Isi secret token untuk channel yang akan dijalankan. Jangan kirim token ke chat.

## Footage — opsional
| Secret | Kegunaan |
|---|---|
| `PIXABAY_API_KEY` | API footage tambahan |
| `COVERR_API_KEY` | API Coverr jika akses API tersedia |
| `COVERR_APP_ID` | Pasangan Coverr jika diminta oleh integrasi |
| `PEXELS_API_KEY` | Sumber tambahan; tidak wajib |

**Tidak ada API Key yang dibutuhkan untuk fallback publik baru:** Mixkit scraper dan pencarian gambar Wikimedia Commons berjalan tanpa key. FFmpeg sudah dipasang oleh workflow GitHub Actions. Scraper bergantung pada struktur halaman publik yang dapat berubah.

## Fitur tambahan opsional
- `PERPLEXITY_API_KEY` — riset web.
- `NVIDIA_API_KEY` — layanan AI/Vision alternatif.
- `FREESOUND_API_KEY` — efek suara.
- `ELEVENLABS_API_KEY` — TTS premium.
- `ASSEMBLYAI_API_KEY` — transkripsi.
- `CLOUDFLARE_ACCOUNT_ID` dan `CLOUDFLARE_API_TOKEN` — layanan Cloudflare.
- `TELEGRAM_BOT_TOKEN` dan `TELEGRAM_CHAT_ID` — notifikasi.

## Langkah dari HP Android
1. Buka https://github.com/Masfu22/mesin-cuan
2. Buka **Settings** repository.
3. Pilih **Secrets and variables → Actions**.
4. Tekan **New repository secret**.
5. Masukkan nama persis seperti tabel dan tempel nilainya.
6. Tekan **Add secret**.

## Pengujian aman
Jalankan workflow **Mesin Cuan - Produksi Video** dengan `dry_run = true` untuk menguji render tanpa upload ke Google Drive. Dry run melewati validasi token OAuth channel. Pengujian upload sesungguhnya memerlukan token channel yang benar dan workflow non-dry-run.

## Keamanan
Jika key pernah masuk Git history, menghapus file saja tidak cukup. Cabut/rotasi key dan token lama di penyedia masing-masing, lalu simpan nilai baru hanya di GitHub Secrets.
