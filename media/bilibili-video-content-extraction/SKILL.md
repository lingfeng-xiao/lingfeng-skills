---
name: bilibili-video-content-extraction
description: >
  Extract subtitles, transcripts, or structured content from Bilibili videos (BV/EP/SS IDs).
  Covers API-based subtitle discovery, login-required subtitle access via QR code,
  fallback to audio download + Whisper transcription, and common NixOS/environment pitfalls.
  Use when the user shares a Bilibili URL or asks to summarize/analyze a Bilibili video.
---

# Bilibili Video Content Extraction

Extract and summarize Bilibili video content through multiple pathways.

## When to use

- User shares a `bilibili.com/video/BV...` link and asks for summary, transcript, or analysis
- User wants to evaluate notes taken from a Bilibili course/lecture
- Need to convert Bilibili video content into structured text for LLM processing

## Workflow

### Step 1: Check subtitle availability without login

Use these API endpoints to check if the video has subtitles (manual or AI-generated):

```python
import requests, json

bvid = 'BV1LU6KBLEZX'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': f'https://www.bilibili.com/video/{bvid}',
}

# Get video info + basic subtitle list
resp = requests.get(f'https://api.bilibili.com/x/web-interface/view?bvid={bvid}', headers=headers)
data = resp.json()['data']
cid = data['cid']  # First page CID
subtitle_list = data.get('subtitle', {}).get('list', [])

# Get detailed player subtitle info
resp2 = requests.get(f'https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}', headers=headers)
player_subs = resp2.json()['data'].get('subtitle', {}).get('subtitles', [])
```

If either list is non-empty, fetch the subtitle JSON from the `subtitle_url` field.

**Common pitfall:** Empty lists do NOT mean "no subtitles exist" — they may require login to access AI-generated subtitles.

### Step 2: Search public skill registries

```bash
hermes skills search bilibili
hermes skills search transcript
hermes skills search whisper
```

Known useful skills:
- `lobehub/bilibili-agent` — Prompt-only skill for comments/danmaku, NOT subtitles
- `DavinciEvans/bilibili-subtitle-download-skill` — Requires login, downloads subtitles + chunks text
- `official/mlops/models/whisper` — For audio transcription fallback

### Step 3: Login-required subtitle extraction

If Step 1 returns empty but user insists subtitles exist, use `bilibili-api-python` with login:

```bash
pip install bilibili-api-python qrcode
```

```python
import asyncio
from bilibili_api import login_v2, video
import qrcode

async def login_and_get_subtitles(bvid):
    qr = login_v2.QrCodeLogin(platform=login_v2.QrCodeLoginChannel.WEB)
    await qr.generate_qrcode()
    
    # Display QR code in terminal
    url = qr._QrCodeLogin__qr_link
    qr_obj = qrcode.QRCode(border=1, box_size=1)
    qr_obj.add_data(url)
    qr_obj.make(fit=True)
    qr_obj.print_ascii(invert=True)
    print(f"\nOr visit: {url}")
    
    # Wait for user to scan
    while not qr.has_done():
        state = await qr.check_state()
        if state == login_v2.QrCodeLoginEvents.DONE:
            break
        await asyncio.sleep(2)
    
    credential = qr.get_credential()
    
    # Now fetch video with credentials
    v = video.Video(bvid=bvid, credential=credential)
    player_info = await v.get_player_info(cid=(await v.get_info())['cid'])
    subtitles = player_info.get('subtitle', {}).get('subtitles', [])
    
    for sub in subtitles:
        sub_url = sub['subtitle_url']
        if sub_url.startswith('//'):
            sub_url = 'https:' + sub_url
        content = requests.get(sub_url).json().get('body', [])
        text = '\n'.join([b.get('content', '') for b in content])
        return text
```

**Pitfall:** `bilibili_api`'s `get_player_info()` requires `sessdata` credential — will raise `CredentialNoSessdataException` without login.

**Pitfall on NixOS:** Terminal/browser tools may fail due to dynamic linking. Use Python API libraries instead of CLI browsers.

### Step 4: Fallback — Audio download + Whisper transcription

If no subtitles exist after login:

```bash
# NixOS
nix-shell -p yt-dlp ffmpeg

# Download audio only
yt-dlp -x --audio-format mp3 -o audio.mp3 'https://www.bilibili.com/video/BVxxxxx'

# Install and run Whisper
pip install openai-whisper
whisper audio.mp3 --model base --language zh
```

**Model recommendation:** `base` or `small` for Chinese educational content. `base` is ~150MB, ~6x real-time on CPU.

## Environment Pitfalls (NixOS)

| Issue | Solution |
|-------|----------|
| Browser tool fails with "cannot run dynamically linked executable" | Use Python `requests`/`httpx` instead of browser automation |
| `pyzbar` missing `libzbar` | Use `nix-shell -p zbar` or avoid — use `qrcode` + `bilibili_api` reflection instead |
| `cv2` not installed | Use `qrcode` library's `print_ascii()` for terminal QR codes |
| ffmpeg missing | `nix-shell -p ffmpeg` |
| yt-dlp connection timeout to BiliBili | May need cookie; try `you-get` as alternative (`nix-shell -p you-get`) |

## Chunking for LLM processing

After obtaining subtitle text:
- Split into ~40K character chunks with 2K overlap
- Feed each chunk to subagent or process sequentially
- Merge summaries focusing on: core concepts, logical flow, key examples

## Resources

- `bilibili-api-python`: https://github.com/Nemo2011/bilibili-api
- B站字幕提取skill参考: `DavinciEvans/bilibili-subtitle-download-skill`
