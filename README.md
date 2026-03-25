# 🔐 VaultFetch Bot — Final Build (Phase 1 + 2 + 3)

**@VaultFetch_bot — Universal AI-Powered Content Downloader**

---

## 📁 Project Structure

```
VaultFetch/
├── main.py            ← Bot entry point — all commands & handlers
├── downloader.py      ← yt-dlp + article scraper (Phase 1)
├── url_classifier.py  ← AI URL classifier — 50+ platforms (Phase 2)
├── database.py        ← SQLite DB — history, stats, preferences (Phase 3)
├── summarizer.py      ← Grok AI summarizer (Phase 3)
├── config.py          ← Token, messages, settings
├── requirements.txt   ← All dependencies
└── downloads/         ← Temp folder (auto-created)
```

---

## ⚙️ Setup — Step by Step

### Step 1 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 2 — Install FFmpeg (audio ke liye ZAROORI)
```bash
# Ubuntu/Linux
sudo apt update && sudo apt install ffmpeg -y

# Windows → https://ffmpeg.org/download.html → PATH mein add karo

# Mac
brew install ffmpeg
```

### Step 3 — Config set karo
`config.py` mein apna token already set hai.
`summarizer.py` line 13 mein Grok API key daalo:
```python
GROK_API_KEY = "your_xai_grok_api_key_here"
```

### Step 4 — Run karo
```bash
python main.py
```

---

## 🚀 Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome + Disclaimer |
| `/help` | Help guide |
| `/about` | About VaultFetch |
| `/history` | Last 10 downloads |
| `/stats` | Your personal stats |
| `/botstats` | Global bot stats |
| `/settings` | Quality & preferences |
| `/summarize <URL>` | AI summarize any URL |

---

## 🎯 Features

### Phase 1 — Core Downloader
- ✅ YouTube, Instagram, TikTok, Twitter/X, Facebook, Reddit
- ✅ Vimeo, Twitch, Dailymotion, SoundCloud + 1000+ sites
- ✅ MP3 audio extraction (192kbps)
- ✅ Quality selector: Best / 720p / 480p / 360p
- ✅ Article scraper (BeautifulSoup)
- ✅ Disclaimer on /start

### Phase 2 — AI URL Intelligence
- ✅ 50+ platform rule-based classifier (98% confidence)
- ✅ Indian apps: Moj, Josh, ShareChat, Chingari, MX TakaTak
- ✅ ML keyword fallback for unknown sites
- ✅ AI confidence bar displayed to user
- ✅ Smart ⚡ auto-detect button

### Phase 3 — Database + AI Summarizer
- ✅ SQLite database (users, downloads, summaries, preferences)
- ✅ Download history per user
- ✅ Personal + global stats
- ✅ Grok AI summarizer (articles + YouTube transcripts)
- ✅ Summary caching — same URL = instant result
- ✅ User preferences (default quality, auto-download toggle)

---

## ⚠️ Disclaimer
This tool is for **personal use only**.
The developer is not responsible for any misuse or copyright violations.

---

*Built with ❤️ — VaultFetch @VaultFetch_bot*
