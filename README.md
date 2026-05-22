<p align="center">
  <img src="https://img.shields.io/badge/YouTube-Downloader-red?style=for-the-badge&logo=youtube" alt="YouTube">
  <img src="https://img.shields.io/badge/TikTok-Downloader-black?style=for-the-badge&logo=tiktok" alt="TikTok">
  <img src="https://img.shields.io/badge/Instagram-Downloader-E4405F?style=for-the-badge&logo=instagram" alt="Instagram">
</p>

<h1 align="center">▶️ Collab-YT</h1>
<p align="center">
  <b>YouTube · TikTok · Instagram Downloader</b><br>
  <i>Gradio UI · Multi-Thread · Drive Save · Watermark Tag · Channel Categorization</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-blue?style=flat-square&logo=python">
  <img src="https://img.shields.io/badge/Gradio-UI-8B5CF6?style=flat-square">
  <img src="https://img.shields.io/badge/yt--dlp-powered-00AA00?style=flat-square">
  <img src="https://img.shields.io/badge/Google_Colab-ready-F9AB00?style=flat-square&logo=googlecolab">
  <img src="https://img.shields.io/badge/Local-Linux/Mac/WSL-success?style=flat-square">
  <img src="https://img.shields.io/github/license/AsimGraphicx/Collab-YT?style=flat-square">
</p>

---

## 📸 Preview

> A **premium glassmorphism Gradio UI** with animated orbs, dark/light mode, and real-time download progress.

---

## ✨ Features

| # | Feature | Detail |
|---|---------|--------|
| 📺 | **Max Quality** | Up to **4K (2160p)** |
| ⚡ | **Multi-Threading** | 1–16 **parallel** download workers |
| 🎵 | **Audio Extract** | **MP3** output with best quality |
| 💾 | **Drive Save** | Direct to **Google Drive** (Colab) or local folder |
| 🏷️ | **Watermark Tag** | Auto-numbered: `001-Title By @You.mp4` |
| 📂 | **Channel Folders** | Auto-categorized: `youtube/MKBHD/file.mp4` |
| 📦 | **Batch Queue** | Process **multiple URLs** in sequence |
| 📥 | **ZIP Archive** | Auto-generates downloadable ZIP |
| 🍪 | **Cookie Auth** | Age-restricted / login-required videos |
| 🌙 | **Dark/Light** | Premium glassmorphism theme |

### Supported Platforms

| Platform | Type | Auto-Categorization |
|----------|------|-------------------|
| [YouTube](https://youtube.com) | Videos, Playlists, Channels, Shorts | ✅ `youtube/ChannelName/` |
| [TikTok](https://tiktok.com) | Single Videos | ✅ `tiktok/@username/` |
| [Instagram](https://instagram.com) | Posts, Reels | ✅ `instagram/@username/` |

---

## 🚀 Quick Start

### Google Colab (Recommended)

```python
from google.colab import drive
drive.mount('/content/drive')

%cd /content
!git clone https://github.com/AsimGraphicx/Collab-YT.git
%cd Collab-YT
!python main.py
```

> A **public Gradio URL** will appear — open on **any device**.

### Local / Desktop

```bash
git clone https://github.com/AsimGraphicx/Collab-YT.git
cd Collab-YT
python3 main.py
```

> Dependencies (`gradio`, `yt-dlp`, `ffmpeg`) install **automatically**.

---

## 🎯 How to Use

### 1️⃣ Enter URL(s)
- **Single video:** Paste one URL
- **Batch queue:** One URL **per line**
- Supports YouTube, TikTok, Instagram

### 2️⃣ Configure
| Setting | Description |
|---------|-------------|
| **Quality** | Max (Best) · 4K · 1080p · 720p · 480p · Audio Only |
| **Threads** | 1–16 parallel downloads per URL |
| **Platform** | YouTube · TikTok · Instagram |
| **Folder Name** | Custom output folder in Drive/Home |
| **Watermark** | Filename tag (e.g. `TurabCoder`) |

### 3️⃣ Upload Cookies (Optional)
1. Install [Cookie-Editor](https://chrome.google.com/webstore/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm) (Chrome)
2. Go to [YouTube](https://youtube.com) while logged in
3. Export → **Netscape format** → save as `cookies.txt`
4. Upload via the **🍪 Upload cookies.txt** button in UI

> ⚠️ **Never share your cookies.txt** — contains your login session!

### 4️⃣ Click Download
- Real-time log shows progress
- Files save to categorized folders
- **ZIP archive** generated automatically

---

## 📁 Output Structure

```
Collab-YT-Downloads/                    ← Configurable folder name
├── youtube/
│   ├── MKBHD/
│   │   ├── 001-This is a video By @Tag.mp4
│   │   └── 002-Another video By @Tag.mp4
│   ├── LinusTechTips/
│   │   └── 001-Some video By @Tag.mp4
│   └── youtube_downloads.zip           ← Auto-generated ZIP
├── tiktok/
│   └── @therock/
│       └── 001-Video By @Tag.mp4
└── instagram/
    └── @natgeo/
        └── 001-Photo By @Tag.mp4
```

**Colab:** `MyDrive/<FolderName>/`  
**Local:** `~/<FolderName>/`

---

## 🏷️ Watermark / Filename Format

Files are saved as:

```
001-Me at the zoo By @TurabCoder.mp4
002-Another video By @TurabCoder.mp4
```

Set your tag in the **Watermark** input. Leave empty for plain filenames.

---

## 🛠️ Technical Stack

- **[Gradio](https://gradio.app)** — Web UI framework
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** — Video extraction engine
- **[FFmpeg](https://ffmpeg.org)** — Audio/video merging
- **ThreadPoolExecutor** — Parallel downloads
- **Google Colab** — Free cloud runtime

---

## 🤝 Contributing

PRs welcome! [Open an issue](https://github.com/AsimGraphicx/Collab-YT/issues) for bugs/features.

<p align="center">
  Created with ❤️ by <b>@AsimGraphicx</b> · Maintained by <b>@TurabCoder</b>
</p>
