# Pemantauan BTC/USD SMC Otomatis

Workflow `.github/workflows/btcusd-smc-monitor.yml` berjalan terjadwal setiap 5 menit dan dapat dijalankan manual dari tab Actions.

## Yang diperiksa
- OHLC BTC/USD spot dari Kraken Public API (tanpa API key).
- Arah EMA20/EMA50 pada H4, H1, dan M15 harus searah.
- M5 harus menunjukkan liquidity sweep pada pool 12 candle sebelumnya, lalu candle konfirmasi menutup melewati struktur internal (CHoCH).
- Hanya setup baru yang dikirim ke Telegram; fingerprint disimpan dalam GitHub Actions cache untuk mengurangi notifikasi berulang.

## GitHub Secrets
Workflow menggunakan secret yang juga dipakai workflow utama:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Tidak perlu memasukkan Exness password, investor password, API key trading, atau kredensial akun ke repository.

## Batasan penting
- Ini monitor dan pemberi peringatan read-only; tidak membuka/menutup posisi.
- Data Kraken BTC/USD spot bukan kuotasi BTCUSD Exness. Periksa spread, harga, dan kondisi kontrak Exness sebelum mengambil keputusan.
- Jadwal GitHub Actions 5 menit adalah best-effort, bukan feed tick atau jaminan eksekusi tepat waktu. GitHub dapat menunda scheduled run.
- Sinyal teknikal dapat gagal; entry, SL, dan TP adalah level referensi berdasarkan candle yang sudah tutup, bukan jaminan hasil.
