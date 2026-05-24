#!/usr/bin/env python3
"""Collab-YT — YouTube, TikTok & Instagram Downloader
Gradio UI | Cookies | Multi-Thread | Direct Drive Save
Usage: python main.py
"""

import os, sys, re, json, shutil, subprocess, urllib.request, time, threading, random
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import gradio as gr

IN_COLAB = 'google.colab' in sys.modules or os.path.exists('/content')
if IN_COLAB:
    DRIVE_BASE = Path('/content/drive/MyDrive')
    DRIVE_DIR = DRIVE_BASE / 'Collab-YT-Downloads'
    if not DRIVE_BASE.exists():
        print('⚠ Drive not mounted. Run: from google.colab import drive; drive.mount("/content/drive")')
        DRIVE_DIR = Path('/content/Collab-YT/downloads')
else:
    DRIVE_DIR = Path.home() / 'Collab-YT-Downloads'

BASE_DIR = Path('/content/Collab-YT') if IN_COLAB else Path.cwd()
os.makedirs(DRIVE_DIR, exist_ok=True)

# Ensure BASE_DIR is in PATH so yt-dlp can find ffmpeg and deno
if str(BASE_DIR) not in os.environ.get('PATH', ''):
    os.environ['PATH'] = f"{BASE_DIR}:{os.environ.get('PATH', '')}"

print('📦 Installing deps...')
try:
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--upgrade',
                    'gradio', 'yt-dlp[curl-cffi]', 'curl_cffi>=0.10,<0.15'],
                   capture_output=True, check=False)
except Exception:
    pass
if not IN_COLAB:
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--upgrade', '--break-system-packages',
                        'gradio', 'yt-dlp[curl-cffi]', 'curl_cffi>=0.10,<0.15'],
                       capture_output=True, check=False)
    except Exception:
        pass
if IN_COLAB:
    print('📦 Installing ffmpeg via apt...')
    os.system('apt-get install -q -y ffmpeg 2>/dev/null')

QUALITY_MAP = {
    'max':     {'fmt': 'bestvideo[height<=2160]+bestaudio/best[height<=2160]'},
    '4k':      {'fmt': 'bestvideo[height<=2160]+bestaudio/best[height<=2160]'},
    '1080p':   {'fmt': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]'},
    '720p':    {'fmt': 'bestvideo[height<=720]+bestaudio/best[height<=720]'},
    '480p':    {'fmt': 'bestvideo[height<=480]+bestaudio/best[height<=480]'},
    'audio':   {'fmt': 'bestaudio/best'},
}

YTDLP_PATH = None
_ytdlp_lock = threading.Lock()
downloaded_ids = set()

# Global semaphore: caps the number of truly concurrent yt-dlp processes to
# avoid YouTube 429 rate-limits regardless of how many UI threads are chosen.
_YTDLP_SEM = threading.Semaphore(4)

# Event used to signal a 429 cool-down: all worker threads will pause when set.
_RATE_LIMIT_EVENT = threading.Event()
_RATE_LIMIT_EVENT.set()  # start in "green" (not throttled) state

def get_cookies_path():
    for p in [Path(__file__).parent / 'cookies.txt', BASE_DIR / 'cookies.txt']:
        if p.exists(): return str(p)
    return None

def get_ytdlp():
    global YTDLP_PATH
    if YTDLP_PATH: return YTDLP_PATH
    with _ytdlp_lock:
        if YTDLP_PATH: return YTDLP_PATH

        # 1. Prefer pip-installed yt-dlp (has curl_cffi for TikTok impersonation)
        for p in ['/usr/local/bin/yt-dlp', '/usr/bin/yt-dlp', str(Path.home() / '.local/bin/yt-dlp')]:
            if os.path.isfile(p):
                YTDLP_PATH = p
                return YTDLP_PATH

        # 2. Check what 'which' finds (may be standalone in BASE_DIR)
        which = shutil.which('yt-dlp')
        if which:
            YTDLP_PATH = which
            return YTDLP_PATH

        # 3. Standalone binary in project dir (last resort, no impersonation)
        standalone = str(BASE_DIR / 'yt-dlp')
        if os.path.isfile(standalone):
            YTDLP_PATH = standalone
            return YTDLP_PATH
    return None

def install_ytdlp():
    url = 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp'
    path = BASE_DIR / 'yt-dlp'
    print('⬇ Downloading yt-dlp...')
    urllib.request.urlretrieve(url, str(path))
    os.chmod(path, 0o755)
    with _ytdlp_lock:
        global YTDLP_PATH
        YTDLP_PATH = str(path)

def check_ffmpeg():
    return bool(shutil.which('ffmpeg') or (BASE_DIR / 'ffmpeg').exists())

def install_ffmpeg():
    url = 'https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz'
    archive = BASE_DIR / 'ffmpeg.tar.xz'
    print('⬇ Downloading FFmpeg...')
    urllib.request.urlretrieve(url, str(archive))
    import tarfile
    with tarfile.open(archive) as tar:
        for m in tar.getmembers():
            if m.name.endswith('/ffmpeg') or m.name.endswith('/ffprobe'):
                m.name = os.path.basename(m.name)
                tar.extract(m, str(BASE_DIR))
    archive.unlink()
    os.chmod(BASE_DIR / 'ffmpeg', 0o755)
    os.chmod(BASE_DIR / 'ffprobe', 0o755)

def check_deno():
    return bool(shutil.which('deno') or (BASE_DIR / 'deno').exists())

def install_deno():
    url = 'https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip'
    archive = BASE_DIR / 'deno.zip'
    print('⬇ Downloading Deno...')
    urllib.request.urlretrieve(url, str(archive))
    import zipfile
    with zipfile.ZipFile(archive, 'r') as zip_ref:
        zip_ref.extract('deno', path=str(BASE_DIR))
    archive.unlink()
    os.chmod(BASE_DIR / 'deno', 0o755)

def sanitize(name):
    return re.sub(r'[\\/*?:"<>|]', '', name)[:100]

def extract_channel_from_url(url):
    m = re.search(r'(?:youtube\.com|youtu\.be)/@([^/?]+)', url)
    if m: return m.group(1)
    m = re.search(r'youtube\.com/channel/([^/?]+)', url)
    if m: return m.group(1)
    m = re.search(r'youtube\.com/c/([^/?]+)', url)
    if m: return m.group(1)
    m = re.search(r'tiktok\.com/@([^/?]+)', url)
    if m: return m.group(1)
    m = re.search(r'instagram\.com/([^/?]+)', url)
    if m and m.group(1) not in ('p', 'reel', 'tv', 'stories', 'explore', 'accounts'):
        return m.group(1)
    return ''

def format_size(b):
    if b > 1e9: return f'{b/1e9:.2f} GB'
    if b > 1e6: return f'{b/1e6:.2f} MB'
    if b > 1e3: return f'{b/1e3:.2f} KB'
    return f'{b} B'

def get_video_info(url):
    cmd = get_ytdlp()
    if not cmd: return None
    cookies = get_cookies_path()
    extra = ['--cookies', cookies] if cookies else []
    
    if 'tiktok.com' in url:
        extra.extend(['--extractor-args', 'tiktok:api_host=web', '--impersonate'])

    url_channel = extract_channel_from_url(url)
    try:
        r = subprocess.run(
            [cmd, '--flat-playlist', '--dump-json', '--no-download'] + extra + [url],
            capture_output=True, text=True, timeout=120
        )
        if r.returncode != 0:
            return None
        items = []
        for line in r.stdout.strip().split('\n'):
            line = line.strip()
            if not line: continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if not items:
            return None
        first = items[0]
        is_playlist = bool(first.get('playlist_title') or first.get('playlist_count'))

        if is_playlist:
            title = first.get('playlist_title', 'Unknown')
            count = int(first.get('playlist_count', 0))
            playlist_channel = first.get('playlist_uploader') or first.get('uploader', '') or url_channel or 'Mix'
            video_items = items[1:] if len(items) > 1 else []
        else:
            title = first.get('title', 'Unknown')
            count = 1
            try:
                r2 = subprocess.run(
                    [cmd, '--dump-json', '--no-download'] + extra + [url],
                    capture_output=True, text=True, timeout=120
                )
                if r2.returncode == 0:
                    full = json.loads(r2.stdout.strip())
                    items[0] = full
            except:
                pass
            url_channel = url_channel or 'Mix'
            video_items = items

        videos = []
        for item in video_items:
            vid_url = item.get('webpage_url') or item.get('url') or f"https://www.youtube.com/watch?v={item.get('id', '')}"
            ch = item.get('channel') or item.get('uploader') or item.get('channel_name', '') or url_channel
            if is_playlist:
                ch = ch or playlist_channel
            if not ch:
                ch = 'Mix'
            videos.append({
                'url': vid_url,
                'title': item.get('title', 'Unknown'),
                'id': item.get('id', ''),
                'duration': item.get('duration_string', 'N/A'),
                'views': item.get('view_count', 0),
                'thumbnail': item.get('thumbnail', ''),
                'channel': ch,
                'uploader': item.get('uploader', ''),
            })
        return {'title': title, 'count': str(count), 'videos': videos}
    except Exception as e:
        print(f'get_video_info error: {e}')
    return None

def download_single(video_url, title, quality_key, output_dir, platform='youtube', index=0, watermark='', channel=''):
    cmd = get_ytdlp()
    if not cmd: return False, 'yt-dlp not found'
    clean = sanitize(title)
    wm = sanitize(watermark).strip()
    ch = sanitize(channel).strip() if channel else 'Mix'
    out_dir = output_dir / ch
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{index:03d}-{clean}" + (f" By @{wm}" if wm else "")
    out_path = out_dir / f'{fname}.mp4'
    if out_path.exists():
        return True, f'Exists: {clean}'
    qf = QUALITY_MAP.get(quality_key, QUALITY_MAP['max'])['fmt']
    out = str(out_dir / f'{fname}.%(ext)s')
    cookies = get_cookies_path()
    cookie_args = ['--cookies', cookies] if cookies else []
    archive_path = Path(__file__).parent / 'download_archive.txt'

    # Rate-limit friendly yt-dlp flags:
    #   --sleep-requests   → pause between each internal HTTP request
    #   --min/max-sleep-interval → random jitter between playlist items
    #   --concurrent-fragments 3 → fewer parallel fragment downloads (was 8)
    sleep_args = [
        '--sleep-requests', '1',
        '--min-sleep-interval', '2',
        '--max-sleep-interval', '5',
    ]
    if quality_key == 'audio':
        args = [cmd, '-f', qf, '-o', out, '--no-playlist', '--ignore-errors',
                '--extract-audio', '--audio-format', 'mp3', '--audio-quality', '0',
                '--retries', '10', '--fragment-retries', '10',
                '--download-archive', str(archive_path)] + sleep_args + cookie_args
    else:
        args = [cmd, '-f', qf, '-o', out, '--no-playlist', '--ignore-errors',
                '--merge-output-format', 'mp4', '--concurrent-fragments', '3',
                '--retries', '10', '--fragment-retries', '10',
                '--download-archive', str(archive_path)] + sleep_args + cookie_args
    if platform == 'tiktok':
        args.extend(['--extractor-args', 'tiktok:api_host=web', '--impersonate'])
    args.append(video_url)

    max_retries = 4
    for attempt in range(max_retries):
        # Wait if a global rate-limit cool-down is in progress
        _RATE_LIMIT_EVENT.wait(timeout=300)

        # Semaphore: only 4 yt-dlp processes run truly concurrently
        with _YTDLP_SEM:
            try:
                proc = subprocess.run(args, capture_output=True, text=True, timeout=3600)
            except subprocess.TimeoutExpired:
                return False, f'Timeout: {clean}'
            except Exception as e:
                return False, f'Error: {e}'

        if proc.returncode == 0:
            return True, f'Done: {clean}'

        combined = (proc.stderr or '') + (proc.stdout or '')
        is_429 = '429' in combined or 'Too Many Requests' in combined

        if is_429:
            # Pause ALL threads for an escalating back-off period
            _RATE_LIMIT_EVENT.clear()  # signal other threads to wait
            # Exponential back-off: 60s, 120s, 240s, 480s (+random jitter)
            wait = min(60 * (2 ** attempt), 480) + random.uniform(10, 40)
            print(f'⏳ 429 detected for "{clean}" — cooling down {wait:.0f}s (attempt {attempt+1}/{max_retries})')
            time.sleep(wait)
            _RATE_LIMIT_EVENT.set()  # release other threads
            if attempt < max_retries - 1:
                continue  # retry this video

        err = combined[:400].strip()
        return False, f'Failed: {err}'

    return False, f'Failed after {max_retries} retries (429 rate-limit): {clean}'

def process_single_url(url, quality_key, out_dir, platform, watermark, workers, add, track_progress, progress):
    yield add(f"\n{'═'*50}")
    yield add(f"🔍 Processing: {url}")
    yield add(f"{'═'*50}")
    info = get_video_info(url)
    if not info:
        yield add("❌ Could not fetch video info. Check URL.")
        return 0, 0
    videos = info['videos']
    total = len(videos)
    yield add(f"📺 {info['title']} — {total} video(s)")
    if track_progress: progress(0.1, desc=f'⬇ {info["title"][:30]}')
    yield add(f"⬇ Downloading | Threads: {int(workers)}")
    yield add("─" * 45)
    success_count = 0
    fail_count = 0
    new_videos = []
    for i, v in enumerate(videos):
        vid_id = v.get('id', '')
        if vid_id and vid_id in downloaded_ids:
            yield add(f"  ⏭ Skipped (already done): {v['title']}")
            continue
        new_videos.append((i + 1, v))
    total_new = len(new_videos)
    if total_new == 0:
        yield add("  ✅ All already downloaded!")
        return success_count, fail_count
    with ThreadPoolExecutor(max_workers=int(workers)) as ex:
        futures = {}
        for i, (idx, v) in enumerate(new_videos):
            # Stagger thread submission: small random delay prevents burst spike
            # at the very start when all threads fire simultaneously.
            if i > 0:
                time.sleep(random.uniform(0.5, 2.0))
            fut = ex.submit(
                download_single,
                v['url'], v['title'], quality_key, out_dir,
                platform.lower(), idx, watermark, v.get('channel', '')
            )
            futures[fut] = (idx, v)
        done_count = 0
        for fut in as_completed(futures):
            ok, msg = fut.result()
            done_count += 1
            if ok:
                success_count += 1
                idx, v = futures[fut]
                vid = v.get('id', '')
                if vid:
                    downloaded_ids.add(vid)
            else:
                fail_count += 1
            yield add(f"  {'✅' if ok else '❌'} [{done_count}/{total_new}] {msg}")
    return success_count, fail_count

def download_task(urls, quality, workers, platform, folder_name, watermark, progress=gr.Progress()):
    if not urls or not urls.strip():
        yield "❌ Please enter at least one URL!"
        return
    raw = urls.strip().split('\n')
    url_list = [u.strip() for u in raw if u.strip()]
    if not url_list:
        yield "❌ No valid URLs found!"
        return
    log = ""
    track_progress = True
    try:
        progress(0.01, desc='🔧 Checking tools...')
    except Exception:
        track_progress = False
    def add(msg):
        nonlocal log
        log += msg + "\n"
        return log
    yield add("🔧 Checking yt-dlp...")
    if not get_ytdlp():
        yield add("⬇ Installing yt-dlp...")
        try:
            install_ytdlp()
            yield add("✅ yt-dlp installed!")
        except Exception as e:
            yield add(f"❌ Failed: {e}")
            return
    if track_progress: progress(0.03, desc='🔧 Checking ffmpeg...')
    yield add("🔧 Checking ffmpeg...")
    if not check_ffmpeg():
        yield add("⬇ Installing ffmpeg...")
        try:
            install_ffmpeg()
            yield add("✅ ffmpeg installed!")
        except Exception as e:
            yield add(f"❌ Failed: {e}")
            return

    if track_progress: progress(0.04, desc='🔧 Checking deno...')
    yield add("🔧 Checking deno runtime...")
    if not check_deno():
        yield add("⬇ Installing deno...")
        try:
            install_deno()
            yield add("✅ deno installed!")
        except Exception as e:
            yield add(f"❌ Failed: {e}")
            return

    yield add("✅ Tools ready!")
    sub_dir = platform.lower()
    if IN_COLAB:
        folder_path = DRIVE_BASE / folder_name if folder_name else DRIVE_DIR
    else:
        folder_path = Path.home() / (folder_name or 'Collab-YT-Downloads')
    out_dir = folder_path / sub_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    yield add(f"📂 Output: {out_dir}")
    q_key = quality.lower().split(' ')[0]
    total_ok = 0
    total_fail = 0
    for i, url in enumerate(url_list):
        if track_progress:
            pct = 0.05 + (i / len(url_list)) * 0.90
            progress(pct, desc=f'📦 [{i+1}/{len(url_list)}] {url[:40]}')
        for msg in process_single_url(url, q_key, out_dir, platform, watermark, workers, add, track_progress, progress):
            yield msg
            if '✅' in msg and 'COMPLETE' not in msg: total_ok += 1
            elif '❌' in msg: total_fail += 1
    yield add("\n" + "═" * 50)
    if track_progress: progress(1.0, desc='🎉 All Done!')
    yield add("🎉 ALL QUEUES COMPLETE!")
    yield add(f"   ✅ Total Success: {total_ok}")
    yield add(f"   ❌ Total Failed:  {total_fail}")
    yield add(f"   📂 Saved in:     {out_dir}")
    # Create ZIP
    zip_path = folder_path / f"{platform.lower()}_downloads.zip"
    if list(out_dir.rglob('*.mp4')) or list(out_dir.rglob('*.mp3')) or list(out_dir.rglob('*.webm')):
        try:
            shutil.make_archive(str(zip_path.with_suffix('')), 'zip', out_dir)
            size = format_size(os.path.getsize(zip_path))
            yield add(f"📦 ZIP: {zip_path.name} ({size})")
        except Exception:
            pass

def get_library():
    items = []
    if not DRIVE_DIR.exists(): return items
    for cat_dir in sorted(DRIVE_DIR.iterdir()):
        if cat_dir.is_dir():
            videos = sorted(cat_dir.rglob('*.mp4')) + sorted(cat_dir.rglob('*.webm')) + sorted(cat_dir.rglob('*.mkv')) + sorted(cat_dir.rglob('*.mp3'))
            if videos:
                items.append({'category': cat_dir.name, 'count': len(videos),
                    'videos': [{'name': v.relative_to(cat_dir).as_posix(), 'size': v.stat().st_size, 'path': str(v)} for v in videos[:20]]})
    return items

def list_downloads():
    items = get_library()
    if not items: return '📂 No downloads yet'
    text = ''
    for cat in items:
        text += f"\n {'='*40}\n  📁 {cat['category']} ({cat['count']} files)\n {'='*40}\n"
        for v in cat['videos']:
            text += f"  {v['name']}  ({format_size(v['size'])})\n"
    return text or '📂 No downloads yet'

def delete_all():
    for f in DRIVE_DIR.iterdir():
        if f.is_dir(): shutil.rmtree(f)
        elif f.is_file(): f.unlink()
    return '🗑️ All downloads deleted'

HEADER_HTML = (
    "<style>"
    ".cyt-header{text-align:center;padding:44px 20px 16px}"
    ".cyt-logo{font-size:3rem;font-weight:900;letter-spacing:-.05em;"
    "background:linear-gradient(135deg,#8b5cf6,#ec4899,#06b6d4);"
    "-webkit-background-clip:text;-webkit-text-fill-color:transparent;"
    "background-clip:text;filter:drop-shadow(0 0 30px rgba(139,92,246,.4));margin-bottom:12px}"
    ".cyt-badges{display:flex;align-items:center;justify-content:center;gap:8px;flex-wrap:wrap;margin-bottom:4px}"
    ".cyt-badge{display:inline-flex;align-items:center;gap:5px;padding:5px 14px;border-radius:100px;"
    "font-size:12px;font-weight:600;font-family:Inter,sans-serif;"
    "border:1px solid rgba(139,92,246,.25);background:rgba(139,92,246,.1);color:rgba(180,180,230,.9)}"
    ".cyt-badge.yt{border-color:rgba(239,68,68,.3);background:rgba(239,68,68,.08);color:#fca5a5}"
    ".cyt-badge.tt{border-color:rgba(6,182,212,.3);background:rgba(6,182,212,.08);color:#67e8f9}"
    ".cyt-badge.ig{border-color:rgba(236,72,153,.3);background:rgba(236,72,153,.08);color:#f9a8d4}"
    ".cyt-badge.th{border-color:rgba(250,204,21,.3);background:rgba(250,204,21,.08);color:#fde68a}"
    ".cyt-badge.dr{border-color:rgba(52,211,153,.3);background:rgba(52,211,153,.08);color:#6ee7b7}"
    ".cyt-divider{height:1px;background:linear-gradient(90deg,transparent,rgba(139,92,246,.3),rgba(236,72,153,.3),transparent);margin:16px 0}"
    "</style>"
    '<div class="cyt-header">'
      '<div class="cyt-logo">▶ Collab-YT</div>'
      '<div class="cyt-badges">'
        '<span class="cyt-badge yt">📺 YouTube</span>'
        '<span class="cyt-badge tt">🎵 TikTok</span>'
        '<span class="cyt-badge ig">📸 Instagram</span>'
        '<span class="cyt-badge th">⚡ Multi-Thread</span>'
        '<span class="cyt-badge dr">💾 Drive Save</span>'
        '<span class="cyt-badge">🍪 Cookies</span>'
      "</div>"
      '<div class="cyt-divider"></div>'
    "</div>"
)

CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
:root {
  --bg0: #06060f; --bg1: #0c0c1e;
  --glass: rgba(255,255,255,0.035); --glass-hov: rgba(255,255,255,0.06);
  --border: rgba(255,255,255,0.07); --border-hov: rgba(139,92,246,0.4);
  --text: #f0f0ff; --text2: rgba(180,180,220,0.75); --text3: rgba(140,140,190,0.5);
  --acc: #8b5cf6; --acc2: #ec4899; --acc3: #06b6d4;
  --grad: linear-gradient(135deg,#8b5cf6,#ec4899);
  --grad2: linear-gradient(135deg,#8b5cf6,#06b6d4);
  --r: 16px; --r-sm: 10px;
  --shadow: 0 20px 60px rgba(0,0,0,.6), 0 4px 20px rgba(139,92,246,.15);
}
body.cyt-light {
  --bg0: #f0f0ff; --bg1: #ffffff;
  --glass: rgba(255,255,255,0.7); --glass-hov: rgba(255,255,255,0.9);
  --border: rgba(139,92,246,0.15);
  --text: #1a1a3e; --text2: rgba(60,60,120,0.75); --text3: rgba(100,100,160,0.5);
  --shadow: 0 20px 60px rgba(139,92,246,.12);
}
*,*::before,*::after{box-sizing:border-box;margin:0}
.gradio-container{font-family:'Inter',sans-serif!important;max-width:1000px!important;margin:auto!important;background:var(--bg0)!important;min-height:100vh!important;position:relative!important}
.gradio-container::before{content:'';position:fixed;inset:0;z-index:0;pointer-events:none;
  background:radial-gradient(ellipse 60% 50% at 15% 20%,rgba(139,92,246,.20) 0%,transparent 100%),
             radial-gradient(ellipse 50% 40% at 85% 15%,rgba(236,72,153,.14) 0%,transparent 100%),
             radial-gradient(ellipse 40% 60% at 70% 85%,rgba(6,182,212,.12) 0%,transparent 100%),
             radial-gradient(ellipse 30% 40% at 20% 80%,rgba(139,92,246,.10) 0%,transparent 100%);
  animation:orbFloat 12s ease-in-out infinite alternate}
@keyframes orbFloat{0%{opacity:.7;transform:scale(1)}100%{opacity:1;transform:scale(1.05)}}
.gradio-container>.wrap,.gradio-container .contain,.gradio-container section.main,.gradio-container .app{background:transparent!important}
.gradio-container .panel,.gradio-container .gr-group,.gradio-container .gr-box,.gradio-container .block,.gradio-container form{background:var(--glass)!important;backdrop-filter:blur(24px) saturate(1.6)!important;border:1px solid var(--border)!important;border-radius:var(--r)!important;box-shadow:var(--shadow)!important;transition:border-color .25s,box-shadow .25s!important}
.gradio-container .tabs{background:rgba(255,255,255,.02)!important;border:1px solid var(--border)!important;border-radius:14px!important;padding:5px!important;gap:4px!important}
.gradio-container .tab-nav button{font-family:'Inter',sans-serif!important;font-weight:600!important;font-size:13px!important;color:var(--text3)!important;border-radius:10px!important;padding:9px 22px!important;border:none!important;background:transparent!important;transition:all .2s!important}
.gradio-container .tab-nav button:hover{color:var(--text2)!important;background:rgba(255,255,255,.04)!important}
.gradio-container .tab-nav button.selected{color:#fff!important;background:var(--grad)!important;box-shadow:0 4px 18px rgba(139,92,246,.4)!important}
.gradio-container input[type=text],.gradio-container input[type=number],.gradio-container textarea,.gradio-container select{font-family:'Inter',sans-serif!important;font-size:14px!important;background:rgba(0,0,0,.25)!important;border:1px solid var(--border)!important;border-radius:var(--r-sm)!important;color:var(--text)!important;padding:11px 14px!important;transition:border-color .2s,box-shadow .2s!important;outline:none!important}
.gradio-container input:focus,.gradio-container textarea:focus,.gradio-container select:focus{border-color:var(--acc)!important;box-shadow:0 0 0 3px rgba(139,92,246,.18),0 0 20px rgba(139,92,246,.12)!important}
.gradio-container label span,.gradio-container .label-wrap span{font-family:'Inter',sans-serif!important;font-size:11px!important;font-weight:700!important;letter-spacing:.08em!important;text-transform:uppercase!important;color:var(--text3)!important}
.gradio-container button.primary{font-family:'Inter',sans-serif!important;font-weight:700!important;font-size:14px!important;background:var(--grad)!important;border:none!important;border-radius:var(--r-sm)!important;color:#fff!important;box-shadow:0 4px 24px rgba(139,92,246,.45)!important;transition:all .2s!important;padding:11px 28px!important}
.gradio-container button.primary:hover{transform:translateY(-2px) scale(1.02)!important;box-shadow:0 8px 36px rgba(139,92,246,.60)!important}
.gradio-container button.secondary{font-family:'Inter',sans-serif!important;font-weight:600!important;font-size:13px!important;background:rgba(255,255,255,.05)!important;border:1px solid var(--border)!important;border-radius:var(--r-sm)!important;color:var(--text2)!important;transition:all .2s!important;padding:11px 20px!important}
.gradio-container button.secondary:hover{background:rgba(255,255,255,.09)!important;border-color:rgba(139,92,246,.35)!important;transform:translateY(-1px)!important}
.gradio-container button.stop{font-family:'Inter',sans-serif!important;background:rgba(239,68,68,.1)!important;border:1px solid rgba(239,68,68,.3)!important;border-radius:var(--r-sm)!important;color:#f87171!important;transition:all .2s!important}
.gradio-container button.stop:hover{background:rgba(239,68,68,.18)!important}
.gradio-container input[type=range]{accent-color:var(--acc)!important}
.gradio-container .markdown,.gradio-container .prose{color:var(--text2)!important;font-family:'Inter',sans-serif!important;line-height:1.7!important}
.gradio-container .markdown h2,.gradio-container .markdown h3{color:var(--text)!important;font-weight:700!important}
.gradio-container textarea[readonly]{background:rgba(0,0,0,.3)!important;color:rgba(180,240,180,.85)!important;font-family:'JetBrains Mono','Cascadia Code',monospace!important;font-size:12.5px!important;line-height:1.6!important;border-radius:12px!important}
::-webkit-scrollbar{width:5px;height:5px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:rgba(139,92,246,.35);border-radius:10px}
footer{display:none!important}
@media(max-width:640px){.gradio-container{padding:8px!important}.gradio-container h1{font-size:1.9rem!important}}
"""

def handle_cookie_upload(file):
    if file is None:
        return "🍪 No cookie file uploaded"
    src = Path(file.name)
    dst = BASE_DIR / 'cookies.txt'
    shutil.copy2(src, dst)
    return f"✅ Cookies saved: {dst}"

def fetch_info(url):
    if not url or not url.strip():
        return '❌ Please enter a URL first!'
    urls = [u.strip() for u in url.strip().split('\n') if u.strip()]
    if not urls:
        return '❌ No valid URLs found'
    url = urls[0]
    if len(urls) > 1:
        preview = f"📦 **{len(urls)} URLs in queue** — showing preview for first URL:\n\n"
    else:
        preview = ""
    if not get_ytdlp():
        try:
            install_ytdlp()
        except:
            return '❌ Could not install yt-dlp'
    info = get_video_info(url)
    if info:
        lines = info['videos'][:20]
        first_ch = lines[0].get('channel', '') if lines else ''
        text = f"{'─'*50}\n📺 {info['title']}\n📊 Videos: {info['count']}"
        if first_ch:
            text += f"\n📢 Channel: {first_ch}"
        text += f"\n{'─'*50}\n\n"
        for i, v in enumerate(lines, 1):
            ch_tag = f" [{v.get('channel','')[:15]}]" if v.get('channel') else ""
            text += f"  {i:2}. {v['title'][:45]}{ch_tag}  ⏱ {v['duration']}\n"
        if len(info['videos']) > 20:
            text += f"\n  ... and {len(info['videos'])-20} more"
        return preview + text
    return preview + '❌ Failed to fetch info. Check URL and try again.'

def fetch_info_format(url):
    return fetch_info(url)

def list_downloads_format():
    items = get_library()
    if not items: return '📂 No downloads yet'
    text = ''
    for cat in items:
        text += f"\n {'='*40}\n  📁 {cat['category']} ({cat['count']} files)\n {'='*40}\n"
        for v in cat['videos']:
            text += f"  {v['name']}  ({format_size(v['size'])})\n"
    return text or '📂 No downloads yet'

with gr.Blocks(title='Collab-YT') as demo:
    gr.HTML(HEADER_HTML)
    with gr.Tabs():
        with gr.TabItem('⬇  Download'):
            with gr.Group():
                url_input = gr.Textbox(
                    label='🔗 Video / Playlist URL(s)',
                    placeholder='One URL per line for batch queue...',
                    lines=3
                )
                with gr.Row():
                    quality_dd = gr.Dropdown(
                        ['Max (Best)', '4K', '1080p', '720p', '480p', 'Audio Only'],
                        value='Max (Best)', label='📺 Quality', scale=2
                    )
                    workers_slider = gr.Slider(1, 16, value=3, step=1, label='⚡ Threads (≤4 rec. for YT)', scale=1)
                with gr.Row():
                    platform_dd = gr.Radio(
                        ['YouTube', 'TikTok', 'Instagram'], value='YouTube', label='🌐 Platform'
                    )
                    folder_input = gr.Textbox(
                        label='📁 Output Folder Name',
                        value='Collab-YT-Downloads',
                        placeholder='Folder name in Drive/Home',
                        lines=1
                    )
                with gr.Row():
                    watermark_input = gr.Textbox(
                        label='🏷️ Watermark (filename tag)',
                        value='TurabCoder',
                        placeholder='e.g. TurabCoder → 001-Title By @TurabCoder.mp4',
                        lines=1
                    )
                    cookie_upload = gr.File(
                        label='🍪 Upload cookies.txt',
                        file_types=['.txt'],
                        file_count='single'
                    )
                with gr.Row():
                    fetch_btn = gr.Button('🔍 Preview Info', variant='secondary', size='sm')
                    dl_btn    = gr.Button('⬇  Start Download', variant='primary', size='lg')
            info_out = gr.Textbox(
                label='📋 Video Info', lines=10, interactive=False,
                placeholder='Click Preview to see video/playlist details...'
            )
            log_out = gr.Textbox(
                label='📊 Download Log', lines=12, interactive=False,
                placeholder='Download progress will appear here...'
            )
        with gr.TabItem('📂  Library'):
            lib_out = gr.Textbox(label='📁 Downloaded Files', lines=15, interactive=False)
            with gr.Row():
                refresh_btn = gr.Button('🔄 Refresh', variant='secondary')
                delete_btn  = gr.Button('🗑️ Delete All', variant='stop')
            gr.Markdown(f'**💾 Save Path:** `{DRIVE_DIR}`')
            gr.Markdown('> 📦 ZIP archives also generated after download for easy transfer.')
        with gr.TabItem('❓  How to Use'):
            gr.Markdown('''
## 🚀 Quick Setup (Google Colab)

### Step 1 — Mount Drive
```python
from google.colab import drive
drive.mount('/content/drive')
```

### Step 2 — Clone & Run
```python
%cd /content
!git clone https://github.com/AsimGraphicx/Collab-YT.git
%cd Collab-YT
!python main.py
```

### Step 3 — Use the UI
- **URL(s):** One URL per line for batch queue
- **Quality:** Choose resolution or Audio Only
- **Platform:** YouTube / TikTok / Instagram
- **Watermark:** Auto-tag filenames (e.g. `By @TurabCoder`)
- **Cookies:** Upload `cookies.txt` for age-restricted content
- Click **⬇ Start Download**

### 🗂️ Output Structure
```
Collab-YT-Downloads/
├── youtube/
│   ├── ChannelName1/
│   │   ├── 001-Title By @Tag.mp4
│   │   └── 002-Title By @Tag.mp4
│   ├── ChannelName2/
│   └── youtube_downloads.zip   ← ZIP archive
├── tiktok/
└── instagram/
```

### ✨ Features
- 📺 **Up to 4K** quality · ⚡ **Multi-Threaded** (1–16 workers)
- 🎵 **Audio Extract** (MP3) · 📋 **Full Playlist** support
- 💾 **Direct Drive Save** · 🍪 **Cookie Auth**
- 🏷️ **Watermark Tag** in filenames
- 📂 **Channel-wise folders** (`youtube/ChannelName/`)
- 📦 **Multi-URL Queue** (one per line)
- 📥 **ZIP Archive** generated after download
- 🌙 **Dark/Light Mode** · 📱 **Mobile Friendly**
''')
    cookie_upload.upload(fn=handle_cookie_upload, inputs=cookie_upload, outputs=log_out)
    fetch_btn.click(fn=fetch_info_format, inputs=url_input, outputs=info_out)
    dl_btn.click(fn=download_task, inputs=[url_input, quality_dd, workers_slider, platform_dd, folder_input, watermark_input], outputs=log_out)
    refresh_btn.click(fn=list_downloads_format, outputs=lib_out)
    delete_btn.click(fn=delete_all, outputs=lib_out)

print("🚀 Launching Collab-YT (Gradio)...")
demo.queue()
if IN_COLAB:
    from google.colab import output as colab_out
    colab_out.serve_kernel_port_as_window(7860)
try:
    demo.launch(share=True, debug=False, theme=gr.themes.Base(), css=CUSTOM_CSS)
except TypeError:
    import sys
    print("ℹ️  Gradio version is older — launching without custom theme...")
    sys.stdout.flush()
    demo.launch(share=True, debug=False)
