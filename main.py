"""
VaultFetch Bot — Phase 3
Database + History + Stats + AI Summarizer + User Preferences
"""

import os
import html
import logging
import asyncio
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode, ChatAction
from telegram.error import BadRequest

from config import (
    BOT_TOKEN,
    DISCLAIMER,
    WELCOME_MESSAGE,
    HELP_MESSAGE,
    ABOUT_MESSAGE,
)
from downloader import (
    is_valid_url,
    download_video,
    download_audio,
    scrape_article,
    cleanup_file,
    format_size,
    format_duration,
)
from url_classifier import classifier, URLClassification
from database import (
    init_db,
    upsert_user,
    log_download,
    get_user_history,
    get_user_stats,
    get_global_stats,
    get_preferences,
    update_preference,
)
from summarizer import summarize_text, get_youtube_transcript

# ─── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("VaultFetch")


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _fmt_bytes(b: int) -> str:
    if b < 1024:          return f"{b} B"
    elif b < 1024**2:     return f"{b/1024:.1f} KB"
    elif b < 1024**3:     return f"{b/1024**2:.1f} MB"
    else:                 return f"{b/1024**3:.2f} GB"

def _h(text: str) -> str:
    """Escape text for HTML parse mode — 100% safe for any dynamic content."""
    if not text:
        return ""
    return html.escape(str(text))

def _register(update: Update):
    """Register/update user in DB on every interaction"""
    u = update.effective_user
    if u:
        upsert_user(u.id, username=u.username, full_name=u.full_name)


# ══════════════════════════════════════════════════════════════════════════════
#  COMMAND HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _register(update)
    user = update.effective_user
    logger.info(f"/start — {user.full_name} ({user.id})")
    await update.message.reply_text(DISCLAIMER, parse_mode=ParseMode.MARKDOWN)
    await asyncio.sleep(0.8)
    await update.message.reply_text(WELCOME_MESSAGE, parse_mode=ParseMode.MARKDOWN)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _register(update)
    await update.message.reply_text(HELP_MESSAGE, parse_mode=ParseMode.MARKDOWN)


async def cmd_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _register(update)
    await update.message.reply_text(ABOUT_MESSAGE, parse_mode=ParseMode.MARKDOWN)


# ─── /history ─────────────────────────────────────────────────────────────────
async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _register(update)
    uid = update.effective_user.id
    history = get_user_history(uid, limit=10)

    if not history:
        await update.message.reply_text(
            "📭 *No download history yet!*\n\nSend any URL to get started 🚀",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    lines = ["📜 <b>Your Last 10 Downloads:</b>\n\n━━━━━━━━━━━━━━━━━━━"]
    for i, dl in enumerate(history, 1):
        emoji  = "🎬" if dl.content_type == "video" else ("🎵" if dl.content_type == "audio" else "📄")
        title  = _h((dl.title or "Unknown")[:40])
        date   = dl.downloaded_at.strftime("%d %b, %H:%M") if dl.downloaded_at else "N/A"
        size   = _fmt_bytes(dl.filesize) if dl.filesize else "N/A"
        lines.append(
            f"{i}. {emoji} <code>{title}</code>\n"
            f"   🌐 {_h(dl.platform or 'Unknown')}  |  📦 {size}  |  🕒 {date}"
        )

    lines.append("\n━━━━━━━━━━━━━━━━━━━\n<i>Use /stats to see your full stats!</i>")
    await update.message.reply_text("\n\n".join(lines), parse_mode=ParseMode.HTML)


# ─── /stats ───────────────────────────────────────────────────────────────────
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _register(update)
    uid   = update.effective_user.id
    uname = update.effective_user.first_name or "You"
    stats = get_user_stats(uid)
    by    = stats.get("by_type", {})

    text = (
        f"📊 <b>Your VaultFetch Stats</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>User:</b> {_h(uname)}\n\n"
        f"📥 <b>Total Downloads:</b> <code>{stats['total']}</code>\n"
        f"🎬 Videos:  <code>{by.get('video', 0)}</code>\n"
        f"🎵 Audio:   <code>{by.get('audio', 0)}</code>\n"
        f"📄 Articles: <code>{by.get('article', 0)}</code>\n\n"
        f"🏆 <b>Top Platform:</b> <code>{_h(stats['top_platform'])}</code> ({stats['top_platform_count']} times)\n"
        f"💾 <b>Total Data:</b> <code>{_fmt_bytes(stats['total_bytes'])}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Use /history to see recent downloads</i>"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ─── /botstats (global) ───────────────────────────────────────────────────────
async def cmd_botstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _register(update)
    gs = get_global_stats()
    platforms = "\n".join(
        f"  {i+1}. <code>{_h(p)}</code> — {c} downloads"
        for i, (p, c) in enumerate(gs["top_platforms"])
    )
    text = (
        f"🌍 <b>VaultFetch Global Stats</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Total Users:     <code>{gs['total_users']:,}</code>\n"
        f"📥 Total Downloads: <code>{gs['total_downloads']:,}</code>\n"
        f"💾 Total Data:      <code>{_fmt_bytes(gs['total_bytes'])}</code>\n\n"
        f"🏆 <b>Top Platforms:</b>\n{platforms if platforms else 'No data yet'}\n"
        f"━━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ─── /settings ────────────────────────────────────────────────────────────────
async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _register(update)
    uid  = update.effective_user.id
    pref = get_preferences(uid)

    keyboard = [
        [
            InlineKeyboardButton("📹 Default Quality", callback_data="setting_quality"),
        ],
        [
            InlineKeyboardButton(
                f"🤖 Auto-Download: {'✅ ON' if pref.auto_download else '❌ OFF'}",
                callback_data="setting_toggle_auto",
            ),
        ],
        [InlineKeyboardButton("❌ Close", callback_data="cancel")],
    ]

    await update.message.reply_text(
        f"⚙️ *Your Preferences*\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📹 Default Quality: `{pref.default_quality.upper()}`\n"
        f"🤖 Auto-Download:   `{'ON ✅' if pref.auto_download else 'OFF ❌'}`\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"_Tap below to change settings_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ─── /summarize ───────────────────────────────────────────────────────────────
async def cmd_summarize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _register(update)
    args = context.args
    uid  = update.effective_user.id

    if not args:
        await update.message.reply_text(
            "🤖 *AI Summarizer*\n\n"
            "Usage: `/summarize <URL>`\n\n"
            "Works for:\n"
            "• 📄 Articles & Blog posts\n"
            "• ▶️ YouTube videos (via transcript)\n"
            "• 🌐 Any webpage with text content",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    url = args[0].strip()
    if not url.startswith("http"):
        url = "https://" + url

    status = await update.message.reply_text(
        f"🤖 <b>AI is reading and summarizing...</b>\n\n"
        f"🔗 <code>{_h(url[:60])}...</code>\n\n"
        f"⏳ <i>This may take 10-20 seconds...</i>",
        parse_mode=ParseMode.HTML,
    )

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    # Classify URL
    clf = classifier.classify(url)

    # Attempt transcript for YouTube, else scrape article
    if "youtube" in url.lower() or "youtu.be" in url.lower():
        await status.edit_text(
            f"▶️ *Fetching YouTube transcript...*\n\n"
            f"⏳ _Extracting subtitles..._",
            parse_mode=ParseMode.MARKDOWN,
        )
        transcript_result = await get_youtube_transcript(url)
        if transcript_result["success"]:
            content = transcript_result["transcript"]
            title   = transcript_result.get("title", "YouTube Video")
            await status.edit_text(
                f"🤖 *Transcript fetched! Summarizing with AI...*\n\n⏳",
                parse_mode=ParseMode.MARKDOWN,
            )
            result = await summarize_text(
                content, title=title, content_type="video",
                telegram_id=uid, url=url,
            )
        else:
            await status.edit_text(
                f"⚠️ *Transcript unavailable.*\n\n"
                f"_Scraping page instead..._",
                parse_mode=ParseMode.MARKDOWN,
            )
            scraped = await scrape_article(url)
            if scraped["success"]:
                with open(scraped["filepath"], "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                cleanup_file(scraped["filepath"])
                result = await summarize_text(
                    content, title=scraped["title"], content_type="article",
                    telegram_id=uid, url=url,
                )
            else:
                result = {"success": False, "error": "Could not fetch content for summarization."}
    else:
        # Scrape article then summarize
        scraped = await scrape_article(url)
        if scraped["success"]:
            with open(scraped["filepath"], "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            cleanup_file(scraped["filepath"])
            await status.edit_text(
                f"🤖 *Content scraped! AI summarizing...*\n\n⏳",
                parse_mode=ParseMode.MARKDOWN,
            )
            result = await summarize_text(
                content, title=scraped["title"], content_type="article",
                telegram_id=uid, url=url,
            )
        else:
            result = {"success": False, "error": scraped.get("error", "Scraping failed")}

    if result["success"]:
        cached_tag = "<i>(cached ⚡)</i>" if result.get("cached") else ""
        await status.edit_text(
            f"🤖 <b>AI Summary</b> {cached_tag}\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"{_h(result['summary'])}\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 <a href='{_h(url)}'>Source</a>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    else:
        await status.edit_text(
            f"❌ <b>Summarization Failed!</b>\n\n<code>{_h(result.get('error', 'Unknown error'))}</code>",
            parse_mode=ParseMode.HTML,
        )


# ══════════════════════════════════════════════════════════════════════════════
#  URL HANDLER
# ══════════════════════════════════════════════════════════════════════════════

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _register(update)
    text = update.message.text.strip()

    if not text.startswith("http"):
        text = "https://" + text

    if not is_valid_url(text):
        await update.message.reply_text(
            "❌ *Invalid URL!*\n\nSend a valid link or use /help",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    context.user_data["url"] = text
    clf: URLClassification = classifier.classify(text)
    smart_msg = classifier.get_smart_message(clf, text)
    keyboard  = _build_keyboard(clf)

    logger.info(f"URL: {clf.platform} | {clf.content_type} | {int(clf.confidence*100)}%")

    await update.message.reply_text(
        smart_msg + _action_hint(clf),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


def _action_hint(clf: URLClassification) -> str:
    if clf.auto_downloadable and clf.confidence >= 0.95:
        return "✅ <b>Auto-detected!</b> Tap ⚡ to download instantly.\n<i>Or choose another format below.</i>"
    elif clf.confidence >= 0.7:
        return f"🤖 <b>AI Suggestion:</b> <code>{_h(clf.description)}</code>\n<i>Choose an option:</i>"
    return "🤔 <b>Unknown site — choose manually:</b>"


def _build_keyboard(clf: URLClassification) -> list:
    suggested = clf.suggested_action
    row1 = []
    if suggested == "video_best":
        row1.append(InlineKeyboardButton("⚡ Download Video (Best)", callback_data="video_best"))
    elif suggested == "audio":
        row1.append(InlineKeyboardButton("⚡ Download Audio MP3", callback_data="audio"))
    elif suggested == "article":
        row1.append(InlineKeyboardButton("⚡ Scrape Article", callback_data="article"))

    row2 = [
        InlineKeyboardButton("🎬 Best",  callback_data="video_best"),
        InlineKeyboardButton("📹 720p",  callback_data="video_720p"),
        InlineKeyboardButton("📹 480p",  callback_data="video_480p"),
        InlineKeyboardButton("📹 360p",  callback_data="video_360p"),
    ]
    row3 = [
        InlineKeyboardButton("🎵 Audio MP3",      callback_data="audio"),
        InlineKeyboardButton("📄 Scrape Article",  callback_data="article"),
    ]
    row4 = [
        InlineKeyboardButton("🤖 AI Summary",  callback_data="ai_summary"),
        InlineKeyboardButton("❌ Cancel",       callback_data="cancel"),
    ]
    return [row1, row2, row3, row4]


# ══════════════════════════════════════════════════════════════════════════════
#  CALLBACK HANDLER
# ══════════════════════════════════════════════════════════════════════════════

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    url  = context.user_data.get("url")
    uid  = query.from_user.id

    if data == "cancel":
        await query.edit_message_text("❌ *Cancelled.* Send another URL anytime! 🚀", parse_mode=ParseMode.MARKDOWN)
        return

    if not url:
        await query.edit_message_text("⚠️ Session expired. Please send the URL again.", parse_mode=ParseMode.MARKDOWN)
        return

    clf: URLClassification = classifier.classify(url)

    # ── Settings callbacks ──────────────────────────────────────────────────
    if data == "setting_toggle_auto":
        pref = get_preferences(uid)
        update_preference(uid, auto_download=not pref.auto_download)
        new_state = not pref.auto_download
        keyboard = [
            [InlineKeyboardButton("📹 Default Quality", callback_data="setting_quality")],
            [InlineKeyboardButton(
                f"🤖 Auto-Download: {'✅ ON' if new_state else '❌ OFF'}",
                callback_data="setting_toggle_auto",
            )],
            [InlineKeyboardButton("❌ Close", callback_data="cancel")],
        ]
        await query.edit_message_text(
            f"⚙️ *Settings Updated!*\n\n🤖 Auto-Download: `{'ON ✅' if new_state else 'OFF ❌'}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if data == "setting_quality":
        keyboard = [
            [
                InlineKeyboardButton("🏆 Best",  callback_data="setq_best"),
                InlineKeyboardButton("📹 1080p", callback_data="setq_1080p"),
                InlineKeyboardButton("📹 720p",  callback_data="setq_720p"),
            ],
            [
                InlineKeyboardButton("📹 480p", callback_data="setq_480p"),
                InlineKeyboardButton("📹 360p", callback_data="setq_360p"),
            ],
            [InlineKeyboardButton("◀️ Back", callback_data="cancel")],
        ]
        await query.edit_message_text(
            "📹 *Choose Default Quality:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if data.startswith("setq_"):
        q = data.replace("setq_", "")
        update_preference(uid, default_quality=q)
        await query.edit_message_text(
            f"✅ *Default quality set to:* `{q.upper()}`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # ── AI Summary ────────────────────────────────────────────────────────
    if data == "ai_summary":
        status_msg = await query.edit_message_text(
            f"🤖 <b>AI Summarizing...</b>\n\n"
            f"{clf.emoji} <b>{_h(clf.platform)}</b>\n"
            f"⏳ <i>Reading content, please wait...</i>",
            parse_mode=ParseMode.HTML,
        )
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.TYPING)

        if "youtube" in url.lower() or "youtu.be" in url.lower():
            tr = await get_youtube_transcript(url)
            if tr["success"]:
                res = await summarize_text(tr["transcript"], title=tr.get("title",""), content_type="video", telegram_id=uid, url=url)
            else:
                sc = await scrape_article(url)
                if sc["success"]:
                    with open(sc["filepath"], "r", encoding="utf-8") as f:
                        content = f.read()
                    cleanup_file(sc["filepath"])
                    res = await summarize_text(content, title=sc["title"], content_type="article", telegram_id=uid, url=url)
                else:
                    res = {"success": False, "error": "Could not fetch content."}
        else:
            sc = await scrape_article(url)
            if sc["success"]:
                with open(sc["filepath"], "r", encoding="utf-8") as f:
                    content = f.read()
                cleanup_file(sc["filepath"])
                res = await summarize_text(content, title=sc["title"], content_type="article", telegram_id=uid, url=url)
            else:
                res = {"success": False, "error": sc.get("error", "Scraping failed")}

        if res["success"]:
            cached_tag = "<i>(cached ⚡)</i>" if res.get("cached") else ""
            await status_msg.edit_text(
                f"🤖 <b>AI Summary</b> {cached_tag}\n\n"
                f"━━━━━━━━━━━━━━━━━━━\n\n"
                f"{_h(res['summary'])}\n\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"🔗 <a href='{_h(url)}'>Source</a>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        else:
            await status_msg.edit_text(
                f"❌ <b>Summarization Failed!</b>\n\n<code>{_h(res.get('error','Unknown'))}</code>",
                parse_mode=ParseMode.HTML,
            )
        return

    # ── Video ──────────────────────────────────────────────────────────────
    if data.startswith("video_"):
        quality_map = {
            "video_best":  ("best",  "Best Quality"),
            "video_1080p": ("1080p", "1080p HD"),
            "video_720p":  ("720p",  "720p HD"),
            "video_480p":  ("480p",  "480p"),
            "video_360p":  ("360p",  "360p"),
        }
        quality, label = quality_map.get(data, ("best", "Best"))

        status_msg = await query.edit_message_text(
            f"⏳ <b>Downloading...</b>\n\n"
            f"{clf.emoji} <b>{_h(clf.platform)}</b> | 🎬 <code>{label}</code>\n"
            f"🤖 AI: <code>{int(clf.confidence*100)}%</code> confident\n\n"
            f"⏳ <i>Please wait...</i>",
            parse_mode=ParseMode.HTML,
        )
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.UPLOAD_VIDEO)
        dl = await download_video(url, quality=quality)
        await _send_video_result(query, context, dl, status_msg, clf, uid)

    # ── Audio ──────────────────────────────────────────────────────────────
    elif data == "audio":
        status_msg = await query.edit_message_text(
            f"⏳ <b>Extracting Audio...</b>\n\n"
            f"{clf.emoji} <b>{_h(clf.platform)}</b> | 🎵 <code>MP3 192kbps</code>\n\n"
            f"⏳ <i>Converting, please wait...</i>",
            parse_mode=ParseMode.HTML,
        )
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.UPLOAD_VOICE)
        dl = await download_audio(url)
        await _send_audio_result(query, context, dl, status_msg, clf, uid)

    # ── Article ────────────────────────────────────────────────────────────
    elif data == "article":
        status_msg = await query.edit_message_text(
            f"⏳ <b>Scraping...</b>\n\n"
            f"{clf.emoji} <b>{_h(clf.platform)}</b> | 📄 Article\n\n"
            f"⏳ <i>Extracting content...</i>",
            parse_mode=ParseMode.HTML,
        )
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.TYPING)
        dl = await scrape_article(url)
        await _send_article_result(query, context, dl, status_msg, clf, uid)


# ══════════════════════════════════════════════════════════════════════════════
#  RESULT SENDERS (with DB logging)
# ══════════════════════════════════════════════════════════════════════════════

async def _send_video_result(query, context, result: dict, status_msg, clf, uid: int):
    chat_id = query.message.chat_id

    if not result["success"]:
        err = result.get("error", "Unknown").split("\n")[0][:200]
        log_download(uid, context.user_data.get("url",""), clf.platform, "video",
                     "video", success=False, error_msg=err, ai_confidence=clf.confidence)
        await status_msg.edit_text(
            f"❌ <b>Download Failed!</b>\n\n<code>{_h(err)}</code>\n\n💡 <i>Try lower quality or Scrape Article.</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    filepath = result["filepath"]
    title    = result["title"]
    filesize = result["filesize"]
    duration = result.get("duration", 0)
    uploader = result.get("uploader", "Unknown")

    await status_msg.edit_text(
        f"✅ <b>Download Complete!</b>\n\n"
        f"{clf.emoji} <b>{_h(clf.platform)}</b>\n"
        f"📌 <code>{_h(title[:60])}</code>\n"
        f"👤 {_h(uploader)}  |  ⏱ {format_duration(duration)}\n"
        f"📦 {format_size(filesize)}\n\n📤 <i>Uploading...</i>",
        parse_mode=ParseMode.HTML,
    )

    try:
        if result.get("too_large"):
            await status_msg.edit_text(
                f"⚠️ <b>File Too Large!</b>\n\n<code>{format_size(filesize)}</code> &gt; 50MB Telegram limit\n\n💡 <i>Try 360p or 480p.</i>",
                parse_mode=ParseMode.HTML,
            )
            cleanup_file(filepath)
            return

        with open(filepath, "rb") as vf:
            await context.bot.send_video(
                chat_id=chat_id, video=vf,
                caption=(
                    f"{clf.emoji} <b>{_h(title[:100])}</b>\n"
                    f"👤 {_h(uploader)}  |  ⏱ {format_duration(duration)}\n"
                    f"📦 {format_size(filesize)}\n\n<i>Downloaded via @VaultFetch_bot</i>"
                ),
                parse_mode=ParseMode.HTML,
                supports_streaming=True,
                read_timeout=120, write_timeout=120,
            )

        log_download(uid, context.user_data.get("url",""), clf.platform, "video",
                     "video", title=title, uploader=uploader,
                     filesize=filesize, duration=duration,
                     success=True, ai_confidence=clf.confidence)

        await status_msg.edit_text(
            f"✅ <b>Video Sent!</b> 🎬\n\n📌 <code>{_h(title[:60])}</code>\n📦 {format_size(filesize)}\n\n<i>Send another URL anytime!</i> 🚀",
            parse_mode=ParseMode.HTML,
        )

    except BadRequest as e:
        await status_msg.edit_text(f"❌ <b>Upload Error:</b> <code>{_h(str(e))}</code>", parse_mode=ParseMode.HTML)
    finally:
        cleanup_file(filepath)


async def _send_audio_result(query, context, result: dict, status_msg, clf, uid: int):
    chat_id = query.message.chat_id

    if not result["success"]:
        err = result.get("error", "Unknown").split("\n")[0][:200]
        log_download(uid, context.user_data.get("url",""), clf.platform, "audio",
                     "audio", success=False, error_msg=err, ai_confidence=clf.confidence)
        await status_msg.edit_text(f"❌ <b>Audio Failed!</b>\n\n<code>{_h(err)}</code>", parse_mode=ParseMode.HTML)
        return

    filepath = result["filepath"]
    title    = result["title"]
    filesize = result["filesize"]
    duration = result.get("duration", 0)
    uploader = result.get("uploader", "Unknown")

    await status_msg.edit_text(
        f"✅ <b>Audio Ready!</b>\n\n{clf.emoji} <b>{_h(clf.platform)}</b>\n"
        f"📌 <code>{_h(title[:60])}</code>\n📦 {format_size(filesize)}\n\n📤 <i>Uploading...</i>",
        parse_mode=ParseMode.HTML,
    )

    try:
        if result.get("too_large"):
            await status_msg.edit_text(f"⚠️ <b>Too Large!</b> <code>{format_size(filesize)}</code> &gt; 50MB", parse_mode=ParseMode.HTML)
            cleanup_file(filepath)
            return

        with open(filepath, "rb") as af:
            await context.bot.send_audio(
                chat_id=chat_id, audio=af,
                title=title[:64], performer=uploader[:64],
                caption=(
                    f"{clf.emoji} <b>{_h(title[:100])}</b>\n"
                    f"👤 {_h(uploader)}  |  ⏱ {format_duration(duration)}\n\n"
                    f"<i>Downloaded via @VaultFetch_bot</i>"
                ),
                parse_mode=ParseMode.HTML,
                read_timeout=120, write_timeout=120,
            )

        log_download(uid, context.user_data.get("url",""), clf.platform, "audio",
                     "audio", title=title, uploader=uploader,
                     filesize=filesize, duration=duration,
                     success=True, ai_confidence=clf.confidence)

        await status_msg.edit_text(
            f"✅ <b>Audio Sent!</b> 🎵\n\n📌 <code>{_h(title[:60])}</code>\n\n<i>Send another URL anytime!</i> 🚀",
            parse_mode=ParseMode.HTML,
        )

    except Exception as e:
        await status_msg.edit_text(f"❌ <b>Upload Error:</b> <code>{_h(str(e))}</code>", parse_mode=ParseMode.HTML)
    finally:
        cleanup_file(filepath)


async def _send_article_result(query, context, result: dict, status_msg, clf, uid: int):
    chat_id = query.message.chat_id

    if not result["success"]:
        log_download(uid, context.user_data.get("url",""), clf.platform, "article",
                     "article", success=False,
                     error_msg=result.get("error"), ai_confidence=clf.confidence)
        await status_msg.edit_text(
            f"❌ <b>Scraping Failed!</b>\n\n<code>{_h(result.get('error','Unknown'))}</code>\n\n💡 <i>Try Video/Audio instead.</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    filepath   = result["filepath"]
    title      = result["title"]
    word_count = result.get("word_count", 0)
    preview    = result.get("content_preview", "")[:300]

    await status_msg.edit_text(
        f"✅ <b>Scraped!</b>\n\n{clf.emoji} <b>{_h(clf.platform)}</b>\n"
        f"📌 <code>{_h(title[:60])}</code>\n📝 {word_count:,} words\n\n📤 <i>Sending...</i>",
        parse_mode=ParseMode.HTML,
    )

    try:
        with open(filepath, "rb") as df:
            await context.bot.send_document(
                chat_id=chat_id, document=df,
                filename=os.path.basename(filepath),
                caption=(
                    f"{clf.emoji} <b>{_h(title[:100])}</b>\n"
                    f"📝 {word_count:,} words\n\n<i>Scraped via @VaultFetch_bot</i>"
                ),
                parse_mode=ParseMode.HTML,
            )

        if preview:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"👀 <b>Preview:</b>\n\n<i>{_h(preview)}...</i>",
                parse_mode=ParseMode.HTML,
            )

        log_download(uid, context.user_data.get("url",""), clf.platform, "article",
                     "article", title=title, success=True, ai_confidence=clf.confidence)

        await status_msg.edit_text(
            f"✅ <b>Article Sent!</b> 📄\n\n📌 <code>{_h(title[:60])}</code>\n\n<i>Send another URL anytime!</i> 🚀",
            parse_mode=ParseMode.HTML,
        )

    except Exception as e:
        await status_msg.edit_text(f"❌ <b>Error:</b> <code>{_h(str(e))}</code>", parse_mode=ParseMode.HTML)
    finally:
        cleanup_file(filepath)


# ══════════════════════════════════════════════════════════════════════════════
#  FALLBACK + ERROR
# ══════════════════════════════════════════════════════════════════════════════

async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤔 *Send me any URL!*\n\nUse /help for commands.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ <b>Unexpected error!</b> Please try again.",
            parse_mode=ParseMode.HTML,
        )


# ══════════════════════════════════════════════════════════════════════════════
#  BOT STARTUP
# ══════════════════════════════════════════════════════════════════════════════

def main():
    logger.info("🔐 Starting VaultFetch — Phase 3...")
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("help",      cmd_help))
    app.add_handler(CommandHandler("about",     cmd_about))
    app.add_handler(CommandHandler("history",   cmd_history))
    app.add_handler(CommandHandler("stats",     cmd_stats))
    app.add_handler(CommandHandler("botstats",  cmd_botstats))
    app.add_handler(CommandHandler("settings",  cmd_settings))
    app.add_handler(CommandHandler("summarize", cmd_summarize))

    # URL + Callbacks
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(handle_callback))

    app.add_error_handler(error_handler)

    logger.info("✅ VaultFetch Phase 3 is LIVE! 🚀")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
