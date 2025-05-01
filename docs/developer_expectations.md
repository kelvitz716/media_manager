# Jellyfin Media Downloader Bot: Developer Expectations

This document outlines the expected user interactions, message formats, and internal flows for the Python Telegram Media Downloader Bot. Share this with the development team to clarify UI/UX and processing requirements.

---

## 1. Commands & Outputs

### 1.1 `/start` & `/help`
**User:** `/start` or `/help`  
**Bot:** Welcome message with commands and supported formats.
```
👋 Welcome to the Jellyfin Media Downloader Bot!

Send me any media file and I will download it to your Jellyfin library.

📂 COMMANDS:
/start - Show this welcome message
/stats - 📊 Show download statistics
/queue - 📋 View current download queue
/test - 🔍 Run system test
/help - ❓ Show usage help

📱 SUPPORTED FORMATS:
🎬 Videos - MP4, MKV, AVI, etc.
🎵 Audio - MP3, FLAC, WAV, etc.
📄 Documents - PDF, ZIP, etc.
```

### 1.2 `/status`
**User:** `/status`  
**Bot:** Download statistics summary.
```
📊 DOWNLOAD STATISTICS

📆 Bot uptime: 7s
📥 Files handled: 5

DOWNLOADS:
✅ Successful: 4 (80.0%)
❌ Failed: 1 (20.0%)
💾 Total data: 5.2 GB

PERFORMANCE:
⚡ Average speed: 1.2 MB/s
⏱️ Avg time per file: 8m 15s
📊 Peak concurrent downloads: 2/3

⏳ Current status: 1 active, 2 queued
```

### 1.3 `/queue`
**User:** `/queue`  
**Bot:** Current queue and active downloads.
```
📋 DOWNLOAD QUEUE STATUS

⏳ Active downloads: 1/3
🔄 Queued files: 3

🔽 CURRENTLY DOWNLOADING:
1️⃣ Cleaner...mkv (9% complete)

⏭️ NEXT IN QUEUE:
1. Daredevil...05...(207.4 MB)
2. Daredevil...06...(224.0 MB)
3. Daredevil...07...(225.3 MB)

🛑 To cancel a download: press ❌ next to the file
```

### 1.4 `/test`
**User:** `/test`  
**Bot:** System diagnostics.
```
🔍 SYSTEM TEST RESULTS

📁 Directory Checks
✅ telegram_download_dir: OK (76.1 GB free)
✅ movies_dir: OK (76.1 GB free)
...

🔧 System Checks
✅ Internet connection: OK
✅ Telethon client: Connected
...

🌐 API Connections
✅ Telegram Bot API: Connected
✅ TMDb API: Connected
...

⚡ Performance
⚡ Network speed: 28.3 KB/s
⏱️ API response time: 615 ms
...

📊 Overall Status: All systems operational
```

---

## 2. File-Driven Events

### 2.1 New Media Message
- **Trigger:** User sends media file/document.
- **Bot Response:** File detected notice and storage path, then added to queue.
```
📂 File detected: <filename>.mkv
📄 Document
📁 Will be stored in: /home/kelvitz/Videos/.../Downloads/
⏳ Added to download queue (position N)
```

### 2.2 Download Progress Updates

#### Large Files (>500 MB)
- **Interval:** Every 30 minutes until done or fail.
- **Format:**
```
📣 STATUS UPDATE - Large download in progress
📂 File: Cleaner.2025...mkv
⏱️ Running for: 1h 33m
✅ Progress: 65.4% complete
💾 Downloaded: 485.2 MB / 740.7 MB
⚡ Current speed: 512 KiB/s
🕒 ETA: 4 h 07 m

Download continuing normally...
```

#### Small Files (<500 MB)
- **One-off** during the download.
- **Format:**
```
📣 STATUS UPDATE - Download in progress
📂 File: Example.mkv
⏱️ Running for: 12 m 05 s
✅ Progress: 77.3% complete
💾 Downloaded: 340.7 MB / 440.7 MB
⚡ Current speed: 1.2 MB/s
🕒 ETA: 2 m 30 s
```

---

## 3. Cancellation Flow
- **Trigger:** User presses ❌ inline button on status or queue.
- **Bot Actions:** Stop download, remove from queue, confirm cancellation.
```
⚠️ Cancellation requested for <filename>
❌ Download cancelled for <filename>
🗑️ Removed from queue
```

---

## 4. Download Completion
- **Automatic:** Upon finish.
- **Bot Message:**
```
✅ Download Complete!
📂 File: <filename>.mkv
📊 Size: 99.2 MB
⏱️ Time: 6 m 58 s
🚀 Avg Speed: 243.1 KB/s

Media categorizer will start shortly.
```

---

## 5. Media Categorizer Workflow
After download, the bot triggers the categorizer module:
```
ℹ️ 📝 Started processing: <filename>.mkv

🔄 Stage: Analyzing
🔄 Stage: Verifying with TMDb
🔄 Stage: Moving to library
✅ Processed <filename>.mkv in 6.2 s
Moved to: /home/.../Jellyfin/Movies/...
```

---

**Legend:**  
❌ Cancel action  ⚠️ Warning/Error  ✅ Success indicator  ⏳ Timer/Duration  📊 Stats

Ensure the dev team implements these flows, message formats, timers, and inline controls exactly as specified for consistency and user clarity.