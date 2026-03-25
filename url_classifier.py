"""
VaultFetch — Phase 2
AI-Powered URL Classifier
Hybrid: Rule-based (known platforms) + ML (unknown URLs)
"""

import re
import pickle
import os
import numpy as np
from urllib.parse import urlparse, parse_qs
from dataclasses import dataclass
from typing import Optional

# ─── Data Class for Classification Result ─────────────────────────────────────
@dataclass
class URLClassification:
    platform: str           # e.g. "YouTube", "Instagram", "Unknown"
    content_type: str       # "video", "audio", "article", "image", "playlist"
    confidence: float       # 0.0 to 1.0
    suggested_action: str   # "video_best", "audio", "article"
    emoji: str              # Platform emoji
    description: str        # Human-readable description
    auto_downloadable: bool # Can we auto-download without asking?


# ══════════════════════════════════════════════════════════════════════════════
#  RULE-BASED CLASSIFIER (High Confidence — Known Platforms)
# ══════════════════════════════════════════════════════════════════════════════

PLATFORM_RULES = [

    # ── Video Platforms ────────────────────────────────────────────────────
    {
        "platform": "YouTube",
        "emoji": "▶️",
        "patterns": [
            r"youtube\.com/watch",
            r"youtube\.com/shorts",
            r"youtu\.be/",
            r"youtube\.com/live",
            r"m\.youtube\.com",
        ],
        "content_type": "video",
        "suggested_action": "video_best",
        "description": "YouTube Video",
        "auto_downloadable": True,
    },
    {
        "platform": "YouTube Music",
        "emoji": "🎵",
        "patterns": [r"music\.youtube\.com"],
        "content_type": "audio",
        "suggested_action": "audio",
        "description": "YouTube Music Track",
        "auto_downloadable": True,
    },
    {
        "platform": "YouTube Playlist",
        "emoji": "📋",
        "patterns": [r"youtube\.com/playlist"],
        "content_type": "playlist",
        "suggested_action": "video_best",
        "description": "YouTube Playlist",
        "auto_downloadable": False,
    },
    {
        "platform": "Instagram",
        "emoji": "📸",
        "patterns": [
            r"instagram\.com/reel",
            r"instagram\.com/p/",
            r"instagram\.com/tv/",
            r"instagr\.am/",
        ],
        "content_type": "video",
        "suggested_action": "video_best",
        "description": "Instagram Reel/Post",
        "auto_downloadable": True,
    },
    {
        "platform": "TikTok",
        "emoji": "🎵",
        "patterns": [
            r"tiktok\.com/@.*/video",
            r"vm\.tiktok\.com",
            r"tiktok\.com/t/",
            r"vt\.tiktok\.com",
        ],
        "content_type": "video",
        "suggested_action": "video_best",
        "description": "TikTok Video",
        "auto_downloadable": True,
    },
    {
        "platform": "Twitter/X",
        "emoji": "🐦",
        "patterns": [
            r"twitter\.com/.*/status",
            r"x\.com/.*/status",
            r"t\.co/",
        ],
        "content_type": "video",
        "suggested_action": "video_best",
        "description": "Twitter/X Post",
        "auto_downloadable": True,
    },
    {
        "platform": "Facebook",
        "emoji": "📘",
        "patterns": [
            r"facebook\.com/.*/videos",
            r"fb\.watch",
            r"facebook\.com/watch",
            r"fb\.com/",
        ],
        "content_type": "video",
        "suggested_action": "video_best",
        "description": "Facebook Video",
        "auto_downloadable": True,
    },
    {
        "platform": "Reddit",
        "emoji": "🤖",
        "patterns": [
            r"reddit\.com/r/.*/comments",
            r"v\.redd\.it",
            r"redd\.it/",
        ],
        "content_type": "video",
        "suggested_action": "video_best",
        "description": "Reddit Video/Post",
        "auto_downloadable": True,
    },
    {
        "platform": "Vimeo",
        "emoji": "🎬",
        "patterns": [r"vimeo\.com/\d+", r"player\.vimeo\.com"],
        "content_type": "video",
        "suggested_action": "video_best",
        "description": "Vimeo Video",
        "auto_downloadable": True,
    },
    {
        "platform": "Dailymotion",
        "emoji": "📹",
        "patterns": [r"dailymotion\.com/video", r"dai\.ly/"],
        "content_type": "video",
        "suggested_action": "video_best",
        "description": "Dailymotion Video",
        "auto_downloadable": True,
    },
    {
        "platform": "Twitch",
        "emoji": "💜",
        "patterns": [
            r"twitch\.tv/videos",
            r"twitch\.tv/clips",
            r"clips\.twitch\.tv",
        ],
        "content_type": "video",
        "suggested_action": "video_best",
        "description": "Twitch Clip/VOD",
        "auto_downloadable": True,
    },
    {
        "platform": "Twitch Live",
        "emoji": "🔴",
        "patterns": [r"twitch\.tv/(?!videos|clips)[a-zA-Z0-9_]+$"],
        "content_type": "video",
        "suggested_action": "video_best",
        "description": "Twitch Live Stream",
        "auto_downloadable": False,
    },
    {
        "platform": "Pinterest",
        "emoji": "📌",
        "patterns": [r"pinterest\.com/pin/", r"pin\.it/"],
        "content_type": "video",
        "suggested_action": "video_best",
        "description": "Pinterest Video",
        "auto_downloadable": True,
    },
    {
        "platform": "Rumble",
        "emoji": "📹",
        "patterns": [r"rumble\.com/v"],
        "content_type": "video",
        "suggested_action": "video_best",
        "description": "Rumble Video",
        "auto_downloadable": True,
    },
    {
        "platform": "Odysee",
        "emoji": "🌊",
        "patterns": [r"odysee\.com/@"],
        "content_type": "video",
        "suggested_action": "video_best",
        "description": "Odysee Video",
        "auto_downloadable": True,
    },
    {
        "platform": "BitChute",
        "emoji": "📹",
        "patterns": [r"bitchute\.com/video"],
        "content_type": "video",
        "suggested_action": "video_best",
        "description": "BitChute Video",
        "auto_downloadable": True,
    },
    {
        "platform": "Bilibili",
        "emoji": "📺",
        "patterns": [r"bilibili\.com/video", r"b23\.tv/"],
        "content_type": "video",
        "suggested_action": "video_best",
        "description": "Bilibili Video",
        "auto_downloadable": True,
    },
    {
        "platform": "VK",
        "emoji": "💙",
        "patterns": [r"vk\.com/video"],
        "content_type": "video",
        "suggested_action": "video_best",
        "description": "VK Video",
        "auto_downloadable": True,
    },
    {
        "platform": "OK.ru",
        "emoji": "🟠",
        "patterns": [r"ok\.ru/video"],
        "content_type": "video",
        "suggested_action": "video_best",
        "description": "OK.ru Video",
        "auto_downloadable": True,
    },
    {
        "platform": "Streamable",
        "emoji": "▶️",
        "patterns": [r"streamable\.com/"],
        "content_type": "video",
        "suggested_action": "video_best",
        "description": "Streamable Video",
        "auto_downloadable": True,
    },
    {
        "platform": "Likee",
        "emoji": "❤️",
        "patterns": [r"likee\.video/", r"l\.likee\.video/"],
        "content_type": "video",
        "suggested_action": "video_best",
        "description": "Likee Video",
        "auto_downloadable": True,
    },
    {
        "platform": "Snapchat",
        "emoji": "👻",
        "patterns": [r"snapchat\.com/spotlight", r"t\.snapchat\.com/"],
        "content_type": "video",
        "suggested_action": "video_best",
        "description": "Snapchat Spotlight",
        "auto_downloadable": True,
    },
    {
        "platform": "Moj",
        "emoji": "🎬",
        "patterns": [r"mojapp\.in/", r"moj\.tv/"],
        "content_type": "video",
        "suggested_action": "video_best",
        "description": "Moj Short Video",
        "auto_downloadable": True,
    },
    {
        "platform": "Josh",
        "emoji": "🎵",
        "patterns": [r"josh\.moe/", r"joshapp\.com/"],
        "content_type": "video",
        "suggested_action": "video_best",
        "description": "Josh Short Video",
        "auto_downloadable": True,
    },
    {
        "platform": "MX TakaTak",
        "emoji": "📱",
        "patterns": [r"mxtakatak\.com/"],
        "content_type": "video",
        "suggested_action": "video_best",
        "description": "MX TakaTak Video",
        "auto_downloadable": True,
    },
    {
        "platform": "ShareChat",
        "emoji": "🟢",
        "patterns": [r"sharechat\.com/"],
        "content_type": "video",
        "suggested_action": "video_best",
        "description": "ShareChat Video",
        "auto_downloadable": True,
    },
    {
        "platform": "Chingari",
        "emoji": "🔥",
        "patterns": [r"chingari\.io/"],
        "content_type": "video",
        "suggested_action": "video_best",
        "description": "Chingari Video",
        "auto_downloadable": True,
    },
    # ── Audio Platforms ────────────────────────────────────────────────────
    {
        "platform": "SoundCloud",
        "emoji": "🎧",
        "patterns": [r"soundcloud\.com/[^/]+/[^/]+"],
        "content_type": "audio",
        "suggested_action": "audio",
        "description": "SoundCloud Track",
        "auto_downloadable": True,
    },
    {
        "platform": "Spotify",
        "emoji": "🎶",
        "patterns": [r"open\.spotify\.com/track", r"spotify\.com/track"],
        "content_type": "audio",
        "suggested_action": "audio",
        "description": "Spotify Track",
        "auto_downloadable": True,
    },
    {
        "platform": "Bandcamp",
        "emoji": "🎸",
        "patterns": [r"bandcamp\.com/track", r"\.bandcamp\.com/track"],
        "content_type": "audio",
        "suggested_action": "audio",
        "description": "Bandcamp Track",
        "auto_downloadable": True,
    },
    {
        "platform": "Mixcloud",
        "emoji": "🎛️",
        "patterns": [r"mixcloud\.com/"],
        "content_type": "audio",
        "suggested_action": "audio",
        "description": "Mixcloud Mix",
        "auto_downloadable": True,
    },
    # ── Direct File Links ──────────────────────────────────────────────────
    {
        "platform": "Direct Video File",
        "emoji": "📽️",
        "patterns": [r"\.(mp4|mkv|avi|mov|webm|flv|wmv|m4v|3gp)(\?.*)?$"],
        "content_type": "video",
        "suggested_action": "video_best",
        "description": "Direct Video File",
        "auto_downloadable": True,
    },
    {
        "platform": "Direct Audio File",
        "emoji": "🎵",
        "patterns": [r"\.(mp3|wav|flac|aac|ogg|m4a|wma|opus)(\?.*)?$"],
        "content_type": "audio",
        "suggested_action": "audio",
        "description": "Direct Audio File",
        "auto_downloadable": True,
    },
    # ── News & Article Sites ───────────────────────────────────────────────
    {
        "platform": "Medium",
        "emoji": "📝",
        "patterns": [r"medium\.com/", r"\.medium\.com/"],
        "content_type": "article",
        "suggested_action": "article",
        "description": "Medium Article",
        "auto_downloadable": True,
    },
    {
        "platform": "Wikipedia",
        "emoji": "📚",
        "patterns": [r"wikipedia\.org/wiki/"],
        "content_type": "article",
        "suggested_action": "article",
        "description": "Wikipedia Article",
        "auto_downloadable": True,
    },
    {
        "platform": "Substack",
        "emoji": "📧",
        "patterns": [r"substack\.com/p/"],
        "content_type": "article",
        "suggested_action": "article",
        "description": "Substack Post",
        "auto_downloadable": True,
    },
    {
        "platform": "Dev.to",
        "emoji": "👨‍💻",
        "patterns": [r"dev\.to/"],
        "content_type": "article",
        "suggested_action": "article",
        "description": "Dev.to Article",
        "auto_downloadable": True,
    },
    {
        "platform": "Hashnode",
        "emoji": "🔵",
        "patterns": [r"hashnode\.dev/", r"\.hashnode\.dev/"],
        "content_type": "article",
        "suggested_action": "article",
        "description": "Hashnode Blog Post",
        "auto_downloadable": True,
    },
]


# ── ML Fallback Feature Keywords ──────────────────────────────────────────────
VIDEO_KEYWORDS = [
    "watch", "video", "reel", "shorts", "clip", "stream",
    "play", "embed", "player", "media", "film", "movie",
    "episode", "vod", "live", "webinar", "mp4", "mkv"
]

AUDIO_KEYWORDS = [
    "track", "music", "song", "audio", "podcast", "listen",
    "album", "playlist", "sound", "mp3", "wav", "beat"
]

ARTICLE_KEYWORDS = [
    "article", "blog", "post", "news", "story", "read",
    "wiki", "docs", "guide", "tutorial", "how-to", "review",
    "opinion", "analysis", "report", "press", "journal"
]


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN CLASSIFIER CLASS
# ══════════════════════════════════════════════════════════════════════════════

class URLClassifier:

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile all regex patterns for speed"""
        self._compiled_rules = []
        for rule in PLATFORM_RULES:
            compiled = [re.compile(p, re.IGNORECASE) for p in rule["patterns"]]
            self._compiled_rules.append({**rule, "_compiled": compiled})

    def _extract_features(self, url: str) -> dict:
        """Extract useful features from URL"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().replace("www.", "")
            path = parsed.path.lower()
            query = parsed.query.lower()
            full = url.lower()
            return {
                "domain": domain,
                "path": path,
                "query": query,
                "full": full,
                "extension": os.path.splitext(path)[1].lower(),
                "path_segments": [s for s in path.split("/") if s],
            }
        except Exception:
            return {"domain": "", "path": "", "query": "", "full": url.lower(),
                    "extension": "", "path_segments": []}

    def _ml_fallback(self, features: dict) -> URLClassification:
        """
        Simple keyword-based ML fallback for unknown URLs.
        Scores each content type and picks the highest.
        """
        full_text = f"{features['domain']} {features['path']} {features['query']}"

        video_score = sum(1 for kw in VIDEO_KEYWORDS if kw in full_text)
        audio_score = sum(1 for kw in AUDIO_KEYWORDS if kw in full_text)
        article_score = sum(1 for kw in ARTICLE_KEYWORDS if kw in full_text)

        # Extension-based boost
        if features["extension"] in [".mp4", ".mkv", ".avi", ".mov", ".webm"]:
            video_score += 5
        elif features["extension"] in [".mp3", ".wav", ".flac", ".aac"]:
            audio_score += 5

        total = max(video_score + audio_score + article_score, 1)
        max_score = max(video_score, audio_score, article_score)

        if max_score == 0:
            # Default to article for unknown
            return URLClassification(
                platform="Unknown Website",
                content_type="article",
                confidence=0.4,
                suggested_action="article",
                emoji="🌐",
                description="Unknown Web Page",
                auto_downloadable=False,
            )

        confidence = round(max_score / total, 2)

        if video_score >= audio_score and video_score >= article_score:
            return URLClassification(
                platform=f"Unknown ({features['domain']})",
                content_type="video",
                confidence=confidence,
                suggested_action="video_best",
                emoji="🎬",
                description="Possible Video Content",
                auto_downloadable=False,
            )
        elif audio_score >= article_score:
            return URLClassification(
                platform=f"Unknown ({features['domain']})",
                content_type="audio",
                confidence=confidence,
                suggested_action="audio",
                emoji="🎵",
                description="Possible Audio Content",
                auto_downloadable=False,
            )
        else:
            return URLClassification(
                platform=f"Unknown ({features['domain']})",
                content_type="article",
                confidence=confidence,
                suggested_action="article",
                emoji="📄",
                description="Possible Article/Webpage",
                auto_downloadable=False,
            )

    def classify(self, url: str) -> URLClassification:
        """
        Main classification method.
        Returns URLClassification with full details.
        """
        if not url.startswith("http"):
            url = "https://" + url

        features = self._extract_features(url)

        # ── Rule-based matching (high confidence) ─────────────────────────
        for rule in self._compiled_rules:
            for pattern in rule["_compiled"]:
                if pattern.search(url):
                    return URLClassification(
                        platform=rule["platform"],
                        content_type=rule["content_type"],
                        confidence=0.98,
                        suggested_action=rule["suggested_action"],
                        emoji=rule["emoji"],
                        description=rule["description"],
                        auto_downloadable=rule["auto_downloadable"],
                    )

        # ── ML Fallback (unknown URLs) ─────────────────────────────────────
        return self._ml_fallback(features)

    def get_smart_message(self, classification: URLClassification, url: str) -> str:
        """
        Generates a smart user-facing message based on classification.
        Uses HTML formatting — safe for any URL or platform name.
        """
        import html as _html
        conf_bar = self._confidence_bar(classification.confidence)
        short_url = url[:55] + "..." if len(url) > 55 else url

        return (
            f"{classification.emoji} <b>{_html.escape(classification.platform)} Detected!</b>\n\n"
            f"🔗 <code>{_html.escape(short_url)}</code>\n"
            f"📦 Type: <code>{_html.escape(classification.description)}</code>\n"
            f"🤖 AI Confidence: {conf_bar} <code>{int(classification.confidence * 100)}%</code>\n\n"
        )

    def _confidence_bar(self, confidence: float) -> str:
        filled = int(confidence * 10)
        return "█" * filled + "░" * (10 - filled)


# ─── Singleton Instance ────────────────────────────────────────────────────────
classifier = URLClassifier()
