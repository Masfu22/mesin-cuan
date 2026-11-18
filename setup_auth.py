"""Generate Google OAuth authorized-user tokens for selected Mesin Cuan channels.

Run:
  python setup_auth.py --channel ch_id_horror
  python setup_auth.py                 # interactive selection of all channels

Token JSON is written only to the ignored config/credentials directory.
Never paste token contents into chat, issues, or source code.
"""
import argparse
import json
import os
from pathlib import Path

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/drive.file",
]


def setup_channel(channel: dict) -> str | None:
    ch_id = channel["id"]
    ch_name = channel["name"]
    secret_file = channel.get("google_client_secret", "config/google_client_secret.json")
    token_file = channel["credentials_file"].replace("_token.json", "_v2.json")

    print("\n" + "=" * 54)
    print("Setup OAuth: " + ch_name + " (" + ch_id + ")")
    print("Client JSON: " + secret_file)
    print("=" * 54)
    if not os.path.isfile(secret_file):
        print("File OAuth client tidak ditemukan: " + secret_file)
        print("Unduh OAuth client JSON tipe Desktop app dari Google Cloud Console.")
        print("Simpan file tersebut pada lokasi di atas, lalu jalankan ulang.")
        return None

    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(secret_file, SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)
    if not creds.refresh_token:
        raise RuntimeError(
            ch_id + ": refresh_token tidak diterbitkan. Periksa consent screen "
            "dan pastikan akses offline diberikan; ulangi otorisasi bila perlu."
        )

    Path(token_file).parent.mkdir(parents=True, exist_ok=True)
    Path(token_file).write_text(creds.to_json(), encoding="utf-8")
    try:
        os.chmod(token_file, 0o600)
    except OSError:
        pass

    print("Token berhasil dibuat: " + token_file)
    print("File ini berisi rahasia OAuth. Jangan unggah ke GitHub sebagai file.")
    print("Salin isi JSON secara langsung ke GitHub Actions Secret dan Railway Variable")
    print("yang bernama TOKEN_" + ch_id.upper() + " (hanya untuk channel ini).")
    return token_file


def main():
    parser = argparse.ArgumentParser(description="Buat token OAuth per channel Mesin Cuan.")
    parser.add_argument("--channel", help="ID channel; jika kosong, proses semua channel.")
    args = parser.parse_args()

    with open("config/settings.json", "r", encoding="utf-8") as handle:
        channels = json.load(handle).get("channels", [])

    allowed = {"ch_id_horror", "ch_id_psych", "ch_en_horror", "ch_en_psych"}
    channels = [channel for channel in channels if channel.get("id") in allowed]
    if args.channel:
        channels = [channel for channel in channels if channel.get("id") == args.channel]
        if not channels:
            parser.error("Channel tidak dikenal: " + args.channel)

    if not channels:
        raise SystemExit("Tidak ada channel yang dapat diproses.")

    for channel in channels:
        setup_channel(channel)

    print("\nSelesai. Jangan kirim token ke chat atau commit ke repository.")


if __name__ == "__main__":
    main()
