# Setup aman Mesin Cuan → Google Drive → YouTube

Dokumen ini menjelaskan dua komponen:
- Producer: https://github.com/Masfu22/mesin-cuan
- Uploader: https://github.com/Masfu22/mesin-cuan-uploader

## 1. Alur integrasi

1. Jalankan workflow **Mesin Cuan - Produksi Video** dari tab Actions.
2. Pilih satu channel, isi topik, dan pilih Shorts atau Long Form.
3. GitHub Actions menjalankan pipeline produksi.
4. Producer mengirim video, thumbnail opsional, dan metadata ke Google Drive queue.
5. Uploader di Railway membaca antrean dengan token channel yang sama.
6. Uploader mengunggah ke channel YouTube yang cocok, lalu mengarsipkan job ke folder done.

## 2. Pemisahan rahasia

**Jangan pernah menaruh credential di source code, file yang di-commit, issue, log, screenshot, atau chat.** Nilai rahasia harus dimasukkan langsung melalui halaman pengaturan masing-masing layanan.

### GitHub Actions — repository Producer

Buka repository Masfu22/mesin-cuan → Settings → Secrets and variables → Actions. Tambahkan hanya secrets yang memang digunakan:

| Secret | Kegunaan |
|---|---|
| TOKEN_CH_ID_HORROR | OAuth authorized-user JSON channel ch_id_horror |
| TOKEN_CH_ID_PSYCH | OAuth authorized-user JSON channel ch_id_psych |
| TOKEN_CH_EN_HORROR | OAuth authorized-user JSON channel ch_en_horror |
| TOKEN_CH_EN_PSYCH | OAuth authorized-user JSON channel ch_en_psych |
| GEMINI_API_KEY / provider AI aktif | Pembuatan naskah dan QC sesuai konfigurasi |
| PEXELS_API_KEY | Footage utama |
| YOUTUBE_API_KEY | Riset/topik YouTube jika dipakai |
| TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID | Notifikasi opsional |
| Provider lain | Isi hanya jika fitur/provider tersebut digunakan |

OAuth token harus berupa JSON authorized-user yang memiliki refresh_token, token_uri, client_id, client_secret, dan scope yang dibutuhkan. Token yang sama untuk channel yang sama perlu dimasukkan secara terpisah ke Railway; GitHub Secrets tidak otomatis tersinkron ke Railway.

### Railway — repository Uploader

Buka Railway → service Uploader → Variables. Tambahkan:

| Variable | Nilai |
|---|---|
| TOKEN_CH_ID_HORROR | OAuth JSON untuk channel tersebut |
| TOKEN_CH_ID_PSYCH | OAuth JSON untuk channel tersebut |
| TOKEN_CH_EN_HORROR | OAuth JSON untuk channel tersebut |
| TOKEN_CH_EN_PSYCH | OAuth JSON untuk channel tersebut |
| YOUTUBE_PRIVACY_STATUS | Mulai dari private |
| POLL_INTERVAL_SEC | Opsional, default 300 |
| TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID | Opsional |
| PORT | Biarkan Railway mengatur; aplikasi default 8080 jika tidak disediakan |

Channel yang tokennya belum tersedia akan dilewati. Jangan memasukkan API key Gemini ke Uploader; Gemini dipakai oleh Producer, bukan oleh proses upload.

## 3. Membuat OAuth token dari Android

1. Buat project Google Cloud dan aktifkan YouTube Data API v3 serta Google Drive API.
2. Atur OAuth consent screen. Jika aplikasi masih Testing, tambahkan akun Google channel sebagai test user.
3. Buat OAuth Client ID tipe Desktop app, lalu unduh JSON.
4. Di Termux, tempatkan file client JSON sesuai nama channel, misalnya config/secrets/ch_id_horror_secret.json.
5. Jalankan:
   ```bash
   python setup_auth.py --channel ch_id_horror
   ```
6. Selesaikan login Google di browser. Token tersimpan di config/credentials/ch_id_horror_v2.json.
7. Buka file token itu secara lokal di perangkat dan salin seluruh JSON langsung ke secret TOKEN_CH_ID_HORROR pada GitHub dan variable bernama sama di Railway. Jangan kirim JSON ke chat.
8. Ulangi satu channel per satu channel setelah channel pertama berhasil diuji.

Scope yang digunakan oleh setup script:
- https://www.googleapis.com/auth/youtube.upload
- https://www.googleapis.com/auth/yt-analytics.readonly
- https://www.googleapis.com/auth/drive.file

File client dan token berada di direktori yang diabaikan Git oleh .gitignore. Jangan menghapus aturan ignore tersebut.

## 4. Uji bertahap

1. Jalankan workflow dengan dry_run=true untuk memastikan runner dan pipeline bisa mulai tanpa OAuth/Drive.
2. Untuk tes integrasi, isi token satu channel di GitHub Secrets dan Railway Variables.
3. Jalankan workflow dengan dry_run=false. Periksa apakah job muncul di Google Drive mesin_cuan/queue/<channel_id>/.
4. Pastikan Railway log menunjukkan channel aktif dan antrean dibaca.
5. Uploader default mengunggah sebagai private. Periksa video di YouTube Studio.
6. Jangan ubah ke public sebelum video uji private dan metadata diperiksa.

## 5. Privasi, log, dan pemulihan

- Jangan mencetak environment variable rahasia ke log.
- Jangan mengirim OAuth JSON, API key, atau Base64 token ke chat.
- Jika credential pernah terekspos, cabut/rotasi di penyedia terkait sebelum dipakai lagi.
- Jalankan satu replica Uploader agar dua poller tidak memproses antrean yang sama.
- Jika upload sukses tetapi arsip Drive gagal, periksa YouTube Studio sebelum mengulang job.

## 6. Status verifikasi

Perubahan kode dan konfigurasi tidak sama dengan keberhasilan upload langsung. Integrasi baru dapat dinyatakan lolos setelah workflow GitHub Actions sukses, file queue terlihat di Drive, Railway membaca queue dengan OAuth yang benar, dan video uji private terlihat di channel YouTube yang tepat.
