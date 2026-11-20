"""
qc_vision_engine.py - AI Video Quality Control menggunakan Gemini Vision

Alur:
  1. Upload video ke Gemini File API
  2. Gemini "menonton" video dan analisa semua aspek
  3. Return keputusan: APPROVED atau NEEDS_FIX + daftar masalah + saran
  4. Kalau NEEDS_FIX → auto-fix 1x → langsung upload ke GDrive
  5. Hapus file dari Gemini setelah selesai

Aspek yang dicek:
  - Subtitle posisi & keterbacaan (safe zone UI YouTube Shorts)
  - Aspect ratio & black bars
  - Hook text (3 detik pertama)
  - Kesesuaian footage dengan narasi/topik
  - Kualitas & keterbacaan thumbnail
  - Kualitas audio (noise, volume)
  - Pacing & transisi

Model: gemini-1.5-flash (fallback: gemini-3.5-flash-lite kalau deprecated)
"""

import os
import json
import time
import subprocess
import tempfile
from engine.utils import get_logger, get_gemini_api_keys

logger = get_logger("qc_vision")

# Model yang dipakai (urutan fallback)
GEMINI_MODELS = [
    os.getenv("GEMINI_MODEL", "").strip(),
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
]

# Batas waktu tunggu video diproses Gemini (detik)
PROCESSING_TIMEOUT = 90
QC_TOTAL_TIMEOUT = 240


# ─── Public: review ──────────────────────────────────────────────────────────

def review_video(video_path: str, thumbnail_path: str,
                 script_data: dict, channel: dict, profile: str = "shorts") -> dict:
    """Review video via modern google-genai SDK; never approve an unreviewed file."""
    if not os.path.exists(video_path):
        return _qc_error(f"Video tidak ditemukan: {video_path}")
    keys = get_gemini_api_keys()
    if not keys:
        return _qc_error("Tidak ada Gemini API key untuk QC Vision")

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        return _qc_error(f"SDK google-genai tidak tersedia: {exc}")

    prompt = _build_qc_prompt(script_data, channel, profile)
    models = list(dict.fromkeys(model for model in GEMINI_MODELS if model))
    errors = []
    total_deadline = time.time() + QC_TOTAL_TIMEOUT

    logger.info(f"[{channel['id']}] QC Vision modern SDK; tersedia {len(keys)} Gemini key")
    for key_index, api_key in enumerate(keys, start=1):
        client = None
        video_file = None
        try:
            remaining_ms = max(1000, min(45000, int((total_deadline - time.time()) * 1000)))
            if time.time() >= total_deadline:
                break
            client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=remaining_ms))
            size_mb = os.path.getsize(video_path) / (1024 * 1024)
            logger.info(f"Upload video QC ({size_mb:.1f} MB), key slot {key_index}")
            video_file = client.files.upload(file=video_path)
            deadline = time.time() + PROCESSING_TIMEOUT
            while True:
                state = getattr(getattr(video_file, "state", None), "name", str(getattr(video_file, "state", ""))).upper()
                if state.endswith("ACTIVE"):
                    break
                if state.endswith("FAILED"):
                    raise RuntimeError("Gemini gagal memproses file video")
                if not state.endswith("PROCESSING"):
                    # Some SDK responses omit state once the file is ready.
                    if state:
                        break
                if time.time() >= min(deadline, total_deadline):
                    raise TimeoutError("Timeout pemrosesan video Gemini")
                time.sleep(5)
                video_file = client.files.get(name=video_file.name)

            for model_name in models:
                try:
                    logger.info(f"QC mencoba model {model_name}, key slot {key_index}")
                    response = client.models.generate_content(
                        model=model_name,
                        contents=[video_file, prompt],
                        config=types.GenerateContentConfig(temperature=0.2),
                    )
                    raw = getattr(response, "text", None)
                    if not isinstance(raw, str) or not raw.strip():
                        raise ValueError("Respons QC Gemini kosong")
                    result = _parse_qc_response(raw, model_name)
                    if result.get("status") not in ("APPROVED", "NEEDS_FIX"):
                        raise ValueError(result.get("summary", "Respons QC tidak valid"))
                    logger.info(f"QC selesai: {result['status']} | {result['score']}/10 | {model_name}")
                    return result
                except Exception as exc:
                    errors.append(f"key{key_index}/{model_name}:{type(exc).__name__}")
                    logger.warning(f"QC model {model_name}, key slot {key_index} gagal: {type(exc).__name__}")
        except Exception as exc:
            errors.append(f"key{key_index}:{type(exc).__name__}")
            logger.warning(f"QC key slot {key_index} gagal: {type(exc).__name__}")
        finally:
            if video_file is not None and client is not None:
                try:
                    client.files.delete(name=video_file.name)
                except Exception as exc:
                    logger.warning(f"Gagal menghapus file QC Gemini: {type(exc).__name__}")

    return _qc_error("Semua percobaan QC Gemini gagal/timeout: " + ", ".join(errors))


def _qc_error(reason: str) -> dict:
    """QC_ERROR is deliberately not an approval; pipeline must stop before upload."""
    logger.error("QC tidak dapat memverifikasi video: %s", reason)
    return {
        "status": "QC_ERROR",
        "score": 0,
        "summary": reason,
        "issues": [{"aspect": "QC system", "severity": "HIGH", "problem": reason,
                    "suggestion": "Perbaiki koneksi/API Gemini lalu jalankan ulang QC."}],
        "auto_fixable": [],
        "approved_aspects": [],
        "model_used": "none",
    }

# ─── Auto-fix ────────────────────────────────────────────────────────────────

def auto_fix(video_path: str, thumbnail_path: str,
             qc_result: dict, channel: dict, profile: str = "shorts") -> dict:
    """
    Auto-fix masalah yang bisa diperbaiki secara otomatis.
    Hanya 1x revisi — tidak ada loop.

    Return: {
        "video_path": str,
        "thumbnail_path": str,
        "fixes_applied": [str, ...]
    }
    """
    fixes_applied = []
    current_video = video_path
    current_thumb = thumbnail_path

    auto_fixable = qc_result.get("auto_fixable", [])

    if not auto_fixable:
        logger.info("Tidak ada masalah yang bisa di-fix otomatis")
        return {
            "video_path":     current_video,
            "thumbnail_path": current_thumb,
            "fixes_applied":  [],
        }

    logger.info(f"Auto-fix: {len(auto_fixable)} masalah akan diperbaiki...")

    for fix_type in auto_fixable:
        try:
            if fix_type == "subtitle_position":
                fixed = _fix_subtitle_position(current_video, profile)
                if fixed:
                    current_video = fixed
                    fixes_applied.append("subtitle_position")

            elif fix_type == "loudnorm":
                fixed = _fix_audio_loudnorm(current_video)
                if fixed:
                    current_video = fixed
                    fixes_applied.append("loudnorm")

            elif fix_type == "thumbnail_contrast":
                fixed = _fix_thumbnail_contrast(current_thumb)
                if fixed:
                    current_thumb = fixed
                    fixes_applied.append("thumbnail_contrast")

        except Exception as e:
            logger.warning(f"Auto-fix '{fix_type}' gagal: {e}")

    if fixes_applied:
        logger.info(f"Auto-fix selesai: {fixes_applied}")
    else:
        logger.info("Tidak ada fix yang berhasil diterapkan")

    return {
        "video_path":     current_video,
        "thumbnail_path": current_thumb,
        "fixes_applied":  fixes_applied,
    }


# ─── Gemini File API ──────────────────────────────────────────────────────────

# File upload, polling, and cleanup are handled by the modern genai.Client in review_video().

# ─── QC Prompt ───────────────────────────────────────────────────────────────

def _build_qc_prompt(script_data: dict, channel: dict, profile: str) -> str:
    title    = script_data.get("title", "")
    niche    = channel.get("niche", "")
    language = channel.get("language", "id")
    is_id    = language == "id"

    aspect_guide = """
ASPEK YANG HARUS DICEK:

1. SUBTITLE SAFE ZONE
   - Apakah subtitle berada di area yang aman? (tidak terpotong UI YouTube Shorts di bagian bawah ~20% layar)
   - Apakah teks subtitle cukup besar dan terbaca?
   - Apakah highlight kata aktif terlihat jelas?

2. ASPECT RATIO & BLACK BARS
   - Apakah ada black bars (area hitam) yang berlebihan?
   - Apakah footage mengisi layar dengan baik (blurred background technique)?

3. HOOK TEXT (3 DETIK PERTAMA)
   - Apakah ada hook text di bagian atas layar?
   - Apakah hook text terbaca jelas dan menarik?
   - Apakah posisinya tidak bentrok dengan elemen lain?

4. KESESUAIAN FOOTAGE DENGAN NARASI
   - Apakah visual yang ditampilkan relevan dengan topik yang dibahas?
   - Apakah ada momen di mana footage tidak nyambung dengan audio?
   - Sebutkan timestamp spesifik jika ada ketidaksesuaian.

5. KUALITAS AUDIO
   - Apakah volume narasi konsisten dan cukup keras?
   - Apakah musik background terlalu keras atau terlalu pelan?
   - Apakah ada noise atau distorsi yang mengganggu?

6. PACING & TRANSISI
   - Apakah kecepatan narasi nyaman diikuti?
   - Apakah pergantian footage terasa natural?
   - Apakah ada bagian yang terlalu cepat atau terlalu lambat?

7. THUMBNAIL (frame pertama video atau yang ditampilkan)
   - Apakah teks pada thumbnail terbaca jelas?
   - Apakah kontras warna cukup baik?
   - Apakah thumbnail menarik dan relevan?
"""

    output_format = """
BERIKAN RESPONSE DALAM FORMAT JSON BERIKUT (tidak ada teks lain di luar JSON):
{
  "status": "APPROVED" atau "NEEDS_FIX",
  "score": <angka 1-10>,
  "summary": "<ringkasan singkat penilaian keseluruhan>",
  "issues": [
    {
      "aspect": "<nama aspek>",
      "severity": "HIGH" atau "MEDIUM" atau "LOW",
      "problem": "<deskripsi masalah spesifik>",
      "timestamp": "<timestamp video jika relevan, misal '0:05'>",
      "suggestion": "<saran perbaikan konkret>"
    }
  ],
  "auto_fixable": ["subtitle_position", "loudnorm", "thumbnail_contrast"],
  "approved_aspects": ["<aspek yang sudah bagus>"]
}

CATATAN:
- "auto_fixable" hanya isi dengan item dari list ini yang memang bermasalah:
  ["subtitle_position", "loudnorm", "thumbnail_contrast"]
- Score 8-10 = APPROVED, Score 1-7 = NEEDS_FIX
- Jika tidak ada masalah, "issues" = [] dan "auto_fixable" = []
- Berikan saran yang spesifik dan actionable, bukan saran umum
"""

    return f"""Kamu adalah seorang profesional editor video YouTube Shorts dengan pengalaman 10 tahun.
Tugasmu adalah me-review video ini secara kritis dan memberikan penilaian objektif.

INFO VIDEO:
- Judul: {title}
- Niche: {niche}
- Bahasa: {"Indonesia" if is_id else "English"}
- Format: {profile}

{aspect_guide}

{output_format}"""


# ─── Parse response ───────────────────────────────────────────────────────────

def _parse_qc_response(raw: str, model_used: str) -> dict:
    """Parse and validate the QC decision; malformed output is never approved."""
    import re
    clean = (raw or "").replace("```json", "").replace("```", "").strip()
    if not clean.startswith("{"):
        match = re.search(r"\{.*\}", clean, re.DOTALL)
        if not match:
            return _qc_error("Respons Gemini tidak berisi JSON QC yang valid")
        clean = match.group()
    try:
        data = json.loads(clean)
    except json.JSONDecodeError as exc:
        return _qc_error(f"JSON QC tidak valid: {exc}")
    status = str(data.get("status", "")).upper()
    if status not in ("APPROVED", "NEEDS_FIX"):
        return _qc_error("Field status QC hilang atau tidak valid")
    try:
        score = int(data.get("score"))
    except (TypeError, ValueError):
        return _qc_error("Field score QC hilang atau bukan angka")
    if not 1 <= score <= 10:
        return _qc_error("Score QC harus berada pada rentang 1-10")
    if score < 8:
        status = "NEEDS_FIX"
    elif status == "APPROVED":
        status = "APPROVED"
    else:
        status = "NEEDS_FIX"
    data["status"] = status
    data["score"] = score
    data["summary"] = str(data.get("summary", ""))
    data["issues"] = data.get("issues") if isinstance(data.get("issues"), list) else []
    data["auto_fixable"] = data.get("auto_fixable") if isinstance(data.get("auto_fixable"), list) else []
    data["approved_aspects"] = data.get("approved_aspects") if isinstance(data.get("approved_aspects"), list) else []
    data["model_used"] = model_used
    return data

# ─── Auto-fix implementations ─────────────────────────────────────────────────

def _fix_subtitle_position(video_path: str, profile: str) -> str | None:
    """
    Naikkan posisi subtitle agar lebih jauh dari bawah layar.
    Burn ulang subtitle dengan margin_v lebih tinggi.
    """
    # Cek apakah ada file .ass subtitle yang bisa di-edit
    base = os.path.splitext(video_path)[0]
    ass_candidates = [
        f"{base}.ass",
        video_path.replace("_sub.mp4", ".ass"),
    ]

    ass_file = next((f for f in ass_candidates if os.path.exists(f)), None)

    if not ass_file:
        logger.info("File .ass subtitle tidak ditemukan untuk di-fix, skip")
        return None

    # Baca dan naikkan MarginV
    with open(ass_file, "r", encoding="utf-8") as f:
        content = f.read()

    import re
    h_match = re.search(r'PlayResY:\s*(\d+)', content)
    if not h_match:
        return None

    h          = int(h_match.group(1))
    new_margin = int(h * 0.30)  # naikkan ke 30% dari bawah

    # Replace MarginV di Style line
    content_fixed = re.sub(
        r'(Style: Default.*?)(\d+)(,1\n)',
        lambda m: f"{m.group(1)}{new_margin}{m.group(3)}",
        content
    )

    # Simpan .ass yang sudah difix
    with open(ass_file, "w", encoding="utf-8") as f:
        f.write(content_fixed)

    # Burn ulang subtitle
    out_path = video_path.replace(".mp4", "_fixed_sub.mp4")
    ass_escaped = ass_file.replace("\\", "/").replace(":", "\\:")
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", f"ass='{ass_escaped}'",
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        "-c:a", "copy",
        out_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        logger.info(f"Subtitle position fixed: {out_path}")
        return out_path
    return None


def _fix_audio_loudnorm(video_path: str) -> str | None:
    """Normalize ulang volume audio ke -14 LUFS."""
    out_path = video_path.replace(".mp4", "_loudnorm.mp4")
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        out_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        logger.info(f"Audio loudnorm fixed: {out_path}")
        return out_path
    return None


def _fix_thumbnail_contrast(thumbnail_path: str) -> str | None:
    """Tingkatkan kontras thumbnail."""
    if not thumbnail_path or not os.path.exists(thumbnail_path):
        return None

    try:
        from PIL import Image, ImageEnhance
        img       = Image.open(thumbnail_path)
        enhancer  = ImageEnhance.Contrast(img)
        img_fixed = enhancer.enhance(1.3)  # +30% kontras
        out_path  = thumbnail_path.replace(".png", "_fixed.png")
        img_fixed.save(out_path, "PNG")
        logger.info(f"Thumbnail contrast fixed: {out_path}")
        return out_path
    except Exception as e:
        logger.warning(f"Thumbnail fix gagal: {e}")
        return None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _approved_result(reason: str = "") -> dict:
    """Legacy helper kept for imports; failures now return QC_ERROR, never APPROVED."""
    return _qc_error(reason or "QC tidak dapat dijalankan")