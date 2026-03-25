import os

# ─── Bot Configuration ─────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "your-telegram-bot-token-here")
# ─── Download Settings ─────────────────────────────────────────────────────────
DOWNLOAD_DIR = "downloads"
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB — Telegram Bot limit

# ─── Messages ──────────────────────────────────────────────────────────────────
DISCLAIMER = (
    "⚠️ *DISCLAIMER*\n\n"
    "VaultFetch is strictly for *personal use only*.\n\n"
    "• You are *solely responsible* for what you download\n"
    "• Respect copyright laws applicable in your country\n"
    "• Do *NOT* use downloaded content commercially\n"
    "• The developer holds *zero liability* for any misuse\n\n"
    "By using this bot, you *agree* to all above terms.\n"
    "━━━━━━━━━━━━━━━━━━━"
)

WELCOME_MESSAGE = (
    "🔐 *Welcome to VaultFetch!*\n"
    "_Your Universal Content Downloader_\n\n"
    "━━━━━━━━━━━━━━━━━━━\n"
    "📥 *Supported Content:*\n"
    "• 🎬 Videos — YouTube, Instagram, TikTok,\n"
    "   Twitter/X, Facebook, Reddit + *1000+ sites*\n"
    "• 🎵 Audio — Extract MP3 from any video\n"
    "• 📄 Articles — Scrape & read any webpage\n\n"
    "━━━━━━━━━━━━━━━━━━━\n"
    "🚀 *How to Use:*\n"
    "Just paste any URL — I'll do the rest!\n\n"
    "━━━━━━━━━━━━━━━━━━━\n"
    "📌 *Commands:*\n"
    "/start — Welcome screen\n"
    "/help  — Detailed help\n"
    "/about — About VaultFetch\n\n"
    "⚠️ _Personal use only. You are responsible for your downloads._"
)

HELP_MESSAGE = (
    "📖 *VaultFetch — Help Guide*\n\n"
    "━━━━━━━━━━━━━━━━━━━\n"
    "🎬 *Download Video:*\n"
    "Paste a video URL → Choose quality → Done!\n\n"
    "🎵 *Download Audio (MP3):*\n"
    "Paste a video URL → Choose 🎵 Audio → MP3 saved!\n\n"
    "📄 *Scrape Article:*\n"
    "Paste any article/blog URL → Get clean text!\n\n"
    "━━━━━━━━━━━━━━━━━━━\n"
    "🌐 *Supported Platforms (partial list):*\n"
    "YouTube • Instagram • TikTok • Twitter/X\n"
    "Facebook • Reddit • Dailymotion • Vimeo\n"
    "Twitch • SoundCloud • Pinterest + *1000 more!*\n\n"
    "━━━━━━━━━━━━━━━━━━━\n"
    "⚡ *Tips:*\n"
    "• Best quality is selected by default for video\n"
    "• Files above 50MB will get a direct download link\n"
    "• Articles are sent as clean formatted text files\n"
)

ABOUT_MESSAGE = (
    "🔐 *VaultFetch* v3.0\n\n"
    "_Universal AI-Powered Content Downloader_\n\n"
    "━━━━━━━━━━━━━━━━━━━\n"
    "⚙️ *Powered By:*\n"
    "• `yt-dlp` — 1000+ site downloader engine\n"
    "• `BeautifulSoup4` — Web article scraper\n"
    "• `Claude AI` — Summarization & intelligence\n"
    "• `SQLAlchemy` — Download history database\n"
    "• `python-telegram-bot` — Bot framework\n\n"
    "━━━━━━━━━━━━━━━━━━━\n"
    "✅ Phase 1 — Core Downloader\n"
    "✅ Phase 2 — AI URL Intelligence\n"
    "✅ Phase 3 — Summaries, History & Stats\n"
    "🚧 Phase 4 — Production Deploy _(Coming Soon)_\n\n"
    "━━━━━━━━━━━━━━━━━━━\n"
    "📌 *Commands:*\n"
    "/history — Your recent downloads\n"
    "/stats — Your download stats\n"
    "/botstats — Global bot stats\n"
    "/settings — Your preferences\n"
    "/summarize — AI summarize any URL\n"
)
