# Setup otomatis Mesin Cuan → Google Drive → YouTube

Dokumen ini menjelaskan dua komponen yang bekerja bersama:

- Producer: [Masfu22/mesin-cuan](https://github.com/Masfu22/mesin-cuan)
- Uploader: [Masfu22/mesin-cuan-uploader](https://github.com/Masfu22/mesin-cuan-uploader)

## 1. Alur kerja

1. Jalankan workflow **Mesin Cuan - Produksi Video** dari tab Actions.
2. Pilih satu channel, isi topik, dan pilih Shorts atau Long Form.
3. GitHub Actions menjalankan pipeline: script → TTS → footage → render → thumbnail/metadata → QC.
4. Mesin Cuan mengirim `video.mp4`, `thumbnail.png` (jika ada), dan `metadata.json` ke Google Drive.
5. Uploader memeriksa antrean tiap 5 menit, menunggu `publish_at`, lalu mengunggah ke channel YouTube yang sesuai.
6. Setelah upload berhasil, folder antrean dipindahkan ke folder `done`.

Struktur antrean:

```text
mesin_cuan/
  queue/
    <channel_id>/
      <job_id>/
        video.mp4
        thumbnail.png
        metadata.json
  done/
    <channel_id>/
```

Mesin Cuan membuat folder `mesin_cuan/queue/<channel_id>/<job_id>/` otomatis di Google Drive milik akun OAuth channel tersebut. Uploader menggunakan token channel yang sama untuk membaca antrean dan mengunggah ke channel YouTube yang sama.

## 2. GitHub Actions Secrets di repository Mesin Cuan

Buka **Masfu22/mesin-cuan → Settings → Secrets and variables → Actions**. Tambahkan secrets berikut. Isi hanya API/provider yang memang dipakai.

| Secret | Kegunaan |
|---|---|
| `TOKEN_CH_ID_HORROR` | OAuth JSON untuk channel ch_id_horror |
| `TOKEN_CH_ID_PSYCH` | OAuth JSON untuk channel ch_id_psych |
| `TOKEN_CH_EN_HORROR` | OAuth JSON untuk channel ch_en_horror |
| `TOKEN_CH_EN_PSYCH` | OAuth JSON untuk channel ch_en_psych |
| `GEMINI_API_KEY` atau `GROQ_API_KEY` atau provider AI lain | Generate naskah/QC sesuai konfigurasi |
| `PEXELS_API_KEY` | Footage; Pixabay/Coverr dapat menjadi fallback |
| `YOUTUBE_API_KEY` | Riset/topik YouTube jika fitur tersebut digunakan |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Notifikasi, opsional |
| `ELEVENLABS_API_KEY` | TTS premium, opsional |
| `PIXABAY_API_KEY`, `COVERR_API_KEY`, `COVERR_APP_ID`, `FREESOUND_API_KEY` | Provider footage/audio tambahan, opsional |
| `PROVIDER_A_API_KEY`, `PROVIDER_A_BASE_URL`, `PROVIDER_A_MODEL` | Provider AI A, opsional sesuai konfigurasi |
| `PROVIDER_B_API_KEY`, `PROVIDER_B_BASE_URL`, `PROVIDER_B_MODEL` | Provider AI B, opsional sesuai konfigurasi |
| `ANTHROPIC_API_KEY`, `NVIDIA_API_KEY`, `PERPLEXITY_API_KEY` | Provider tambahan, opsional |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Opsional untuk komponen yang membaca variabel ini; OAuth token channel tetap harus lengkap |

Token OAuth yang digunakan harus berupa authorized-user JSON yang berisi `refresh_token`, `token_uri`, `client_id`, `client_secret`, dan scope yang sesuai. Jangan masukkan token atau API key ke source code, issue, log, atau chat.

Scope minimum yang diperlukan:
- `https://www.googleapis.com/auth/youtube.upload`
- `https://www.googleapis.com/auth/drive.file`

Buat token untuk setiap akun/channel dengan `python setup_auth.py`. Pastikan token tiap channel memang berasal dari akun YouTube dan Google Drive yang tepat. Script setup menghasilkan file JSON; gunakan isi JSON sebagai GitHub Secret. Jangan gunakan file pickle lama.

Catatan: `engine/gdrive_engine.py` membuat folder root berdasarkan nama `mesin_cuan`; variabel `GOOGLE_DRIVE_FOLDER_ID` tidak dipakai oleh implementasi antrean saat ini.

## 3. Environment secrets di hosting uploader

Deploy repository **Masfu22/mesin-cuan-uploader** sebagai Docker web service di Koyeb atau Railway. Lalu tambahkan environment variables di halaman layanan hosting itu sendiri (bukan hanya di repository Mesin Cuan):

| Variable | Nilai |
|---|---|
| `TOKEN_CH_ID_HORROR` | OAuth JSON channel ch_id_horror |
| `TOKEN_CH_ID_PSYCH` | OAuth JSON channel ch_id_psych |
| `TOKEN_CH_EN_HORROR` | OAuth JSON channel ch_en_horror |
| `TOKEN_CH_EN_PSYCH` | OAuth JSON channel ch_en_psych |
| `YOUTUBE_PRIVACY_STATUS` | Mulai dengan `private`; pilih `unlisted` atau `public` hanya setelah uji berhasil |
| `POLL_INTERVAL_SEC` | Opsional; default 300 detik |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Opsional untuk notifikasi |
| `PORT` | Opsional; default 8080 |

Channel yang tokennya belum diisi akan dilewati. Gunakan token yang sama dengan GitHub Secret untuk channel tersebut. Jangan menaruh token di file yang di-commit.

**Penting:** Secrets di repository Mesin Cuan tidak otomatis tersedia di Koyeb/Railway. Kamu perlu mengisi variabel token secara terpisah pada pengaturan environment layanan uploader.

## 4. Privasi dan jadwal publikasi

Uploader sekarang default ke `private`. Ini aman untuk uji pertama. Untuk mempublikasikan video secara otomatis setelah waktu `publish_at`, ubah `YOUTUBE_PRIVACY_STATUS=public` pada hosting uploader. Pengaturan berlaku untuk semua channel pada layanan tersebut.

Uploader menunggu sampai waktu `publish_at` sebelum mengirim video ke YouTube. Jika `publish_at` kosong, antrean yang berstatus `ready` dapat langsung diproses. Jika format `publish_at` tidak valid, antrean dilewati agar tidak terbit terlalu cepat.

## 5. Menjalankan dari HP

1. Buka repository [Masfu22/mesin-cuan](https://github.com/Masfu22/mesin-cuan).
2. Pilih tab **Actions**.
3. Pilih **Mesin Cuan - Produksi Video**.
4. Tekan **Run workflow**.
5. Pilih satu channel, masukkan topik, pilih format.
6. Untuk uji awal tanpa upload ke Drive, aktifkan **dry_run**. Mode ini tetap membuat/render video tetapi tidak membutuhkan token OAuth channel.
7. Untuk integrasi Drive sebenarnya, matikan **dry_run** dan pastikan Secret OAuth channel terpilih sudah diisi.
8. Buka log workflow. Setelah pipeline berhasil, periksa folder antrean Google Drive.
7. Pastikan layanan uploader berstatus sehat dan log menunjukkan antrean diproses.
8. Buka YouTube Studio dan periksa video uji yang seharusnya berstatus private.

## 6. Pemeriksaan sebelum produksi

- Mulai dengan satu video Shorts dan satu channel.
- Pastikan token Google untuk channel itu memiliki scope YouTube Upload dan Drive file.
- Pastikan layanan uploader berjalan dan token channel yang sama sudah dipasang di hosting.
- Periksa video, thumbnail, judul, deskripsi, hak penggunaan footage/audio, serta deklarasi konten sintetis.
- Jangan ubah privasi menjadi public sebelum tes private berhasil.
- Runner GitHub Actions bersifat sementara dan tidak memiliki GPU khusus. Render long-form dapat memakan waktu dan memori.
- Jika upload YouTube sukses tetapi pemindahan folder ke `done` gagal, periksa YouTube Studio sebelum mengulang antrean untuk menghindari duplikasi.

## 7. Status verifikasi

Kode integrasi dan kontrak folder antrean sudah diselaraskan. Workflow validasi uploader menjalankan pemeriksaan sintaks dan unit test saat ada push/PR. Namun, integrasi layanan eksternal belum dapat dinyatakan berhasil sampai:
- GitHub Actions berhasil menghasilkan satu video;
- video dan metadata terlihat pada Google Drive queue;
- uploader membaca antrean dengan OAuth yang benar;
- video uji muncul pada channel YouTube yang sesuai.

Tes terakhir memerlukan secrets dan akses Google milik pemilik akun. Jangan mengirim secrets ke chat.
