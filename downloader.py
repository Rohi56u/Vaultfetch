import os
import re
import asyncio
import yt_dlp
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from config import DOWNLOAD_DIR, MAX_FILE_SIZE_BYTES

# ─── Ensure download directory exists ─────────────────────────────────────────
Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)


# ─── URL Validator ─────────────────────────────────────────────────────────────
def is_valid_url(text: str) -> bool:
    pattern = re.compile(
        r"^(https?://)?"
        r"([\w\-]+\.)+[\w\-]+"
        r"(:\d+)?"
        r"(/[\w\-./?%&=+#@!~:,;*()]*)?$"
    )
    return bool(pattern.match(text.strip()))


# ─── Detect Content Type ───────────────────────────────────────────────────────
def detect_content_type(url: str) -> str:
    """
    Returns 'video', 'audio_possible', or 'article'
    based on URL pattern heuristics.
    """
    video_domains = [
        "youtube.com", "youtu.be", "instagram.com", "tiktok.com",
        "twitter.com", "x.com", "facebook.com", "fb.watch",
        "reddit.com", "vimeo.com", "dailymotion.com", "twitch.tv",
        "soundcloud.com", "bilibili.com", "pinterest.com",
        "streamable.com", "rumble.com", "odysee.com", "bitchute.com",
        "ok.ru", "vk.com", "weibo.com", "kuaishou.com"
    ]
    url_lower = url.lower()
    for domain in video_domains:
        if domain in url_lower:
            return "video"
    return "article"


# ─── yt-dlp Progress Hook Factory ─────────────────────────────────────────────
def make_progress_hook(progress_callback=None):
    def hook(d):
        if d["status"] == "downloading" and progress_callback:
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            speed = d.get("speed", 0)
            eta = d.get("eta", 0)
            if total > 0:
                percent = int(downloaded / total * 100)
                speed_mb = round((speed or 0) / 1024 / 1024, 2)
                asyncio.create_task(
                    progress_callback(percent, speed_mb, eta)
                )
    return hook


# ─── Download Video ────────────────────────────────────────────────────────────
async def download_video(url: str, quality: str = "best", progress_callback=None) -> dict:
    """
    Downloads video using yt-dlp.
    quality options: 'best', '1080p', '720p', '480p', '360p'
    Returns dict with 'success', 'filepath', 'title', 'error', 'filesize'
    """

    # Quality format mapping
    format_map = {
        "best":  "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]",
        "720p":  "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]",
        "480p":  "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best[height<=480]",
        "360p":  "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]/best[height<=360]",
    }

    output_template = os.path.join(DOWNLOAD_DIR, "%(title).60s.%(ext)s")

    ydl_opts = {
        "format": format_map.get(quality, format_map["best"]),
        "outtmpl": output_template,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [make_progress_hook(progress_callback)],
        "noplaylist": True,
        "socket_timeout": 30,
        "retries": 3,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        },
    }

    try:
        loop = asyncio.get_event_loop()

        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filepath = ydl.prepare_filename(info)
                # Handle merged mp4 extension
                if not os.path.exists(filepath):
                    filepath = filepath.rsplit(".", 1)[0] + ".mp4"
                return info, filepath

        info, filepath = await loop.run_in_executor(None, _download)

        # Check file exists
        if not os.path.exists(filepath):
            # Try to find it
            for f in os.listdir(DOWNLOAD_DIR):
                if info.get("title", "")[:20].lower() in f.lower():
                    filepath = os.path.join(DOWNLOAD_DIR, f)
                    break

        filesize = os.path.getsize(filepath) if os.path.exists(filepath) else 0

        return {
            "success": True,
            "filepath": filepath,
            "title": info.get("title", "Unknown"),
            "duration": info.get("duration", 0),
            "thumbnail": info.get("thumbnail", ""),
            "uploader": info.get("uploader", "Unknown"),
            "filesize": filesize,
            "too_large": filesize > MAX_FILE_SIZE_BYTES,
        }

    except yt_dlp.utils.DownloadError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


# ─── Download Audio (MP3) ──────────────────────────────────────────────────────
async def download_audio(url: str, progress_callback=None) -> dict:
    """
    Downloads and converts to MP3 using yt-dlp + ffmpeg.
    """
    output_template = os.path.join(DOWNLOAD_DIR, "%(title).60s.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 30,
        "retries": 3,
        "progress_hooks": [make_progress_hook(progress_callback)],
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        },
    }

    try:
        loop = asyncio.get_event_loop()

        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                base = ydl.prepare_filename(info).rsplit(".", 1)[0]
                filepath = base + ".mp3"
                return info, filepath

        info, filepath = await loop.run_in_executor(None, _download)

        filesize = os.path.getsize(filepath) if os.path.exists(filepath) else 0

        return {
            "success": True,
            "filepath": filepath,
            "title": info.get("title", "Unknown"),
            "duration": info.get("duration", 0),
            "uploader": info.get("uploader", "Unknown"),
            "filesize": filesize,
            "too_large": filesize > MAX_FILE_SIZE_BYTES,
        }

    except yt_dlp.utils.DownloadError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


# ─── Scrape Article ────────────────────────────────────────────────────────────
async def scrape_article(url: str) -> dict:
    """
    Scrapes article/webpage content using requests + BeautifulSoup.
    Returns cleaned text content.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        loop = asyncio.get_event_loop()

        def _scrape():
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            # Remove unwanted tags
            for tag in soup(["script", "style", "nav", "footer",
                             "header", "aside", "advertisement",
                             "iframe", "form", "button", "noscript"]):
                tag.decompose()

            # Try to get title
            title = ""
            if soup.title:
                title = soup.title.string or ""
            if not title and soup.find("h1"):
                title = soup.find("h1").get_text(strip=True)

            # Try article tag first, then main, then body
            content_tag = (
                soup.find("article") or
                soup.find("main") or
                soup.find(class_=re.compile(r"content|article|post|entry", re.I)) or
                soup.find("body")
            )

            if content_tag:
                # Get all paragraphs
                paragraphs = content_tag.find_all(["p", "h1", "h2", "h3", "h4", "li"])
                lines = []
                for tag in paragraphs:
                    text = tag.get_text(separator=" ", strip=True)
                    if len(text) > 30:  # skip very short/nav items
                        if tag.name in ["h1", "h2", "h3", "h4"]:
                            lines.append(f"\n{'#' * int(tag.name[1])} {text}\n")
                        else:
                            lines.append(text)
                content = "\n\n".join(lines)
            else:
                content = soup.get_text(separator="\n", strip=True)

            return title.strip(), content.strip()

        title, content = await loop.run_in_executor(None, _scrape)

        if not content:
            return {"success": False, "error": "No readable content found on this page."}

        # Save as txt file
        safe_title = re.sub(r'[^\w\s-]', '', title)[:50] or "article"
        filepath = os.path.join(DOWNLOAD_DIR, f"{safe_title}.txt")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"🔗 Source: {url}\n")
            f.write(f"📌 Title: {title}\n")
            f.write("━" * 50 + "\n\n")
            f.write(content)

        return {
            "success": True,
            "filepath": filepath,
            "title": title,
            "content_preview": content[:500],
            "word_count": len(content.split()),
        }

    except requests.exceptions.Timeout:
        return {"success": False, "error": "Request timed out. Site is too slow."}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Could not connect to the URL."}
    except requests.exceptions.HTTPError as e:
        return {"success": False, "error": f"HTTP Error: {e}"}
    except Exception as e:
        return {"success": False, "error": f"Scraping failed: {str(e)}"}


# ─── Cleanup File ──────────────────────────────────────────────────────────────
def cleanup_file(filepath: str):
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
    except Exception:
        pass


# ─── Format File Size ──────────────────────────────────────────────────────────
def format_size(bytes_size: int) -> str:
    if bytes_size < 1024:
        return f"{bytes_size} B"
    elif bytes_size < 1024 ** 2:
        return f"{bytes_size / 1024:.1f} KB"
    elif bytes_size < 1024 ** 3:
        return f"{bytes_size / (1024**2):.1f} MB"
    else:
        return f"{bytes_size / (1024**3):.2f} GB"


# ─── Format Duration ───────────────────────────────────────────────────────────
def format_duration(seconds: int) -> str:
    if not seconds:
        return "Unknown"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
