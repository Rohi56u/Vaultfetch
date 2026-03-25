"""
VaultFetch — Phase 3
AI Summarizer Module
Uses Grok API (xAI) to summarize articles & video transcripts
"""

import logging
import asyncio
import httpx
from database import get_cached_summary, save_summary

logger = logging.getLogger("VaultFetch.AI")

# ─── Grok API Config ───────────────────────────────────────────────────────────
GROK_API_URL = "https://api.x.ai/v1/chat/completions"
GROK_MODEL   = "grok-3"  # or "grok-2" — change if needed
GROK_API_KEY = "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"  # 🔑 Grok API Key


# ══════════════════════════════════════════════════════════════════════════════
#  CORE SUMMARIZER
# ══════════════════════════════════════════════════════════════════════════════

async def summarize_text(
    text: str,
    title: str = "",
    content_type: str = "article",
    telegram_id: int = 0,
    url: str = "",
) -> dict:
    """
    Summarizes content using Grok AI.
    Returns dict with 'success', 'summary', 'cached', 'error'
    """

    # ── Check cache first ──────────────────────────────────────────────────
    if url:
        cached = get_cached_summary(url)
        if cached:
            logger.info(f"Cache hit for: {url[:50]}")
            return {
                "success": True,
                "summary": cached.summary_text,
                "cached": True,
            }

    # ── Truncate very long text ────────────────────────────────────────────
    max_chars = 8000
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[Content truncated for summarization...]"

    # ── Build prompt ───────────────────────────────────────────────────────
    if content_type == "article":
        prompt = f"""You are a smart content assistant inside a Telegram bot called VaultFetch.

A user has scraped the following article and wants a summary.

Title: {title or 'Unknown'}
URL: {url or 'N/A'}

Content:
{text}

Please provide a structured summary in this EXACT format:

📝 SUMMARY:
[3-5 clear and informative sentences summarizing the article]

🔑 KEY POINTS:
• [Most important point]
• [Second key point]
• [Third key point]
• [Fourth key point]
• [Fifth key point if relevant]

🏷️ TAGS: tag1, tag2, tag3, tag4, tag5

📊 SENTIMENT: [Positive / Neutral / Negative]
⏱️ READ TIME: [X] minutes"""

    else:
        prompt = f"""You are a smart content assistant inside a Telegram bot called VaultFetch.

A user has video/transcript content from: {title or 'Unknown'}

Content/Transcript:
{text}

Please provide a structured summary in this EXACT format:

📝 SUMMARY:
[3-5 clear sentences summarizing the video content]

🔑 KEY POINTS:
• [Most important point]
• [Second key point]
• [Third key point]
• [Fourth key point]

🏷️ TAGS: tag1, tag2, tag3, tag4, tag5

⏱️ WATCH TIME WORTH: [Yes, worth watching fully / Watch highlights only / Skip]"""

    # ── Call Grok API ──────────────────────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=40.0) as client:
            response = await client.post(
                GROK_API_URL,
                headers={
                    "Content-Type":  "application/json",
                    "Authorization": f"Bearer {GROK_API_KEY}",
                },
                json={
                    "model": GROK_MODEL,
                    "max_tokens": 1024,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are VaultFetch AI, a smart summarization assistant "
                                "inside a Telegram bot. Be concise, clear, and structured. "
                                "Always follow the exact output format requested."
                            ),
                        },
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                },
            )

        if response.status_code == 401:
            logger.error("Grok API: Invalid API key")
            return {"success": False, "error": "Invalid Grok API key. Check config."}

        if response.status_code == 429:
            return {"success": False, "error": "Grok API rate limit hit. Try again later."}

        if response.status_code != 200:
            logger.error(f"Grok API Error {response.status_code}: {response.text[:200]}")
            return {"success": False, "error": f"Grok API Error: {response.status_code}"}

        data    = response.json()
        summary = data["choices"][0]["message"]["content"].strip()

        # ── Save to cache ──────────────────────────────────────────────────
        if url and telegram_id:
            try:
                save_summary(telegram_id, url, title, summary)
                logger.info(f"Summary cached for: {url[:50]}")
            except Exception as e:
                logger.warning(f"Cache save failed: {e}")

        return {
            "success": True,
            "summary": summary,
            "cached":  False,
        }

    except httpx.TimeoutException:
        return {"success": False, "error": "Grok AI timed out. Try again!"}
    except httpx.ConnectError:
        return {"success": False, "error": "Cannot connect to Grok API. Check internet."}
    except Exception as e:
        logger.error(f"Summarizer error: {e}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


# ══════════════════════════════════════════════════════════════════════════════
#  TRANSCRIPT FETCHER (YouTube)
# ══════════════════════════════════════════════════════════════════════════════

async def get_youtube_transcript(url: str) -> dict:
    """
    Fetches YouTube video transcript using yt-dlp subtitles.
    Returns dict with 'success', 'transcript', 'title', 'duration', 'error'
    """
    import yt_dlp
    import tempfile
    import glob

    try:
        loop = asyncio.get_event_loop()

        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts = {
                "skip_download":    True,
                "writesubtitles":   True,
                "writeautomaticsub": True,
                "subtitlesformat":  "vtt",
                "subtitleslangs":   ["en", "en-US", "en-GB"],
                "outtmpl":          f"{tmpdir}/%(id)s",
                "quiet":            True,
                "no_warnings":      True,
            }

            def _fetch():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=True)

            info = await loop.run_in_executor(None, _fetch)

            vtt_files = glob.glob(f"{tmpdir}/*.vtt")
            if not vtt_files:
                return {"success": False, "error": "No subtitles/transcript available for this video."}

            with open(vtt_files[0], "r", encoding="utf-8", errors="ignore") as f:
                raw = f.read()

            transcript = _parse_vtt(raw)
            if not transcript.strip():
                return {"success": False, "error": "Transcript is empty."}

            return {
                "success":    True,
                "transcript": transcript,
                "title":      info.get("title", "Unknown"),
                "duration":   info.get("duration", 0),
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def _parse_vtt(vtt_content: str) -> str:
    """Parse VTT subtitle file into clean readable text"""
    import re
    lines = vtt_content.split("\n")
    text_lines = []
    seen = set()

    for line in lines:
        line = line.strip()
        if not line or line.startswith("WEBVTT") or "-->" in line:
            continue
        if re.match(r"^\d+$", line):
            continue
        # Remove HTML/VTT tags
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"&amp;", "&", line)
        line = re.sub(r"&lt;",  "<", line)
        line = re.sub(r"&gt;",  ">", line)
        line = line.strip()
        if line and line not in seen:
            seen.add(line)
            text_lines.append(line)

    return " ".join(text_lines)
