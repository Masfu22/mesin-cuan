"""Public media discovery without paid API keys."""
from __future__ import annotations
import json
import logging
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import quote_plus, urlparse
import requests

logger = logging.getLogger("public_media_engine")
TIMEOUT = 20
USER_AGENT = "MesinCuanPublicMedia/1.0 (public-media discovery)"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
MIXKIT_SEARCH = "https://mixkit.co/free-stock-video/"

def _safe_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme == "https" and bool(parsed.netloc)
    except Exception:
        return False

def _extract_mp4_urls(html: str) -> list[str]:
    if not isinstance(html, str):
        return []
    found = re.findall(r"""https?://[^\s"'<>\\]+?\.mp4(?:\?[^\s"'<>\\]*)?""", html, flags=re.I)
    unique = []
    for url in found:
        url = url.replace("&amp;", "&")
        if _safe_http_url(url) and url not in unique:
            unique.append(url)
    return unique

def search_mixkit(keyword: str, limit: int = 5) -> list[dict]:
    """Best-effort scrape of publicly accessible Mixkit search HTML."""
    if not (keyword or "").strip():
        return []
    try:
        response = requests.get(
            MIXKIT_SEARCH, params={"q": keyword},
            headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT,
        )
        response.raise_for_status()
        return [
            {"id": "mixkit_" + str(abs(hash(url))), "url": url,
             "media_type": "video", "source": "Mixkit"}
            for url in _extract_mp4_urls(response.text)[:max(0, limit)]
        ]
    except Exception as exc:
        logger.info("Mixkit search unavailable for %r: %s", keyword, exc)
        return []

def search_commons_images(keyword: str, limit: int = 5) -> list[dict]:
    """Search Wikimedia Commons public API; no API key required."""
    if not (keyword or "").strip():
        return []
    try:
        response = requests.get(
            COMMONS_API,
            params={
                "action": "query", "format": "json", "generator": "search",
                "gsrsearch": "filetype:bitmap " + keyword, "gsrnamespace": 6,
                "gsrlimit": min(max(int(limit), 1), 20),
                "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": 1600,
            },
            headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT,
        )
        response.raise_for_status()
        pages = response.json().get("query", {}).get("pages", {})
        results = []
        for page in pages.values():
            info = (page.get("imageinfo") or [{}])[0]
            image_url = info.get("thumburl") or info.get("url")
            if not _safe_http_url(image_url or ""):
                continue
            meta = info.get("extmetadata") or {}
            def meta_value(key: str) -> str:
                item = meta.get(key) or {}
                raw = item.get("value", "") if isinstance(item, dict) else ""
                return re.sub(r"<[^>]+>", " ", str(raw)).strip()
            results.append({
                "id": "commons_" + str(page.get("pageid", abs(hash(image_url)))),
                "url": image_url, "media_type": "image",
                "source": "Wikimedia Commons", "title": page.get("title", ""),
                "page_url": info.get("descriptionurl", ""),
                "license": meta_value("LicenseShortName") or meta_value("UsageTerms") or "Periksa halaman sumber",
                "artist": meta_value("Artist") or "Tidak dicantumkan",
            })
            if len(results) >= limit:
                break
        return results
    except Exception as exc:
        logger.info("Commons search unavailable for %r: %s", keyword, exc)
        return []

def search_public_media(keyword: str, limit: int = 5) -> list[dict]:
    """Mixkit public-page scraper, then Commons images."""
    results = search_mixkit(keyword, limit)
    if len(results) < limit:
        results.extend(search_commons_images(keyword, limit - len(results)))
    return results[:limit]

def download_image_as_video(image_url: str, output_path: str,
                            orientation: str = "portrait",
                            attribution: dict | None = None) -> bool:
    """Download an image and create a five-second Ken Burns MP4 with FFmpeg."""
    if not _safe_http_url(image_url) or not shutil.which("ffmpeg"):
        return False
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    image_path = output.with_suffix(".source.jpg")
    try:
        with requests.get(image_url, headers={"User-Agent": USER_AGENT},
                          stream=True, timeout=60) as response:
            response.raise_for_status()
            ctype = response.headers.get("Content-Type", "").lower()
            if ctype and not ctype.startswith("image/"):
                return False
            with image_path.open("wb") as handle:
                for chunk in response.iter_content(256 * 1024):
                    if chunk:
                        handle.write(chunk)
        if image_path.stat().st_size < 2048:
            return False
        width, height = (720, 1280) if orientation == "portrait" else (1280, 720)
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"zoompan=z='min(zoom+0.0008,1.08)':d=150:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"s={width}x{height}:fps=30,format=yuv420p"
        )
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
               "-loop", "1", "-i", str(image_path), "-vf", vf, "-t", "5",
               "-r", "30", "-an", "-c:v", "libx264", "-preset", "veryfast",
               "-pix_fmt", "yuv420p", str(output)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if result.returncode or not output.exists() or output.stat().st_size < 1024:
            logger.warning("FFmpeg image-to-video failed: %s", result.stderr[-500:])
            output.unlink(missing_ok=True)
            return False
        if attribution:
            output.with_suffix(".license.json").write_text(
                json.dumps(attribution, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return True
    except Exception as exc:
        logger.warning("Image-to-video failed: %s", exc)
        output.unlink(missing_ok=True)
        return False
    finally:
        image_path.unlink(missing_ok=True)
