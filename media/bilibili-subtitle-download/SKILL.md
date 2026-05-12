---
name: bilibili-subtitle-download
description: |
  Download subtitles from Bilibili videos, including AI-generated subtitles that require login.
  Supports QR-code login with persistent credential storage.
install: |
  pip install bilibili-api-python qrcode requests
usage: |
  # Basic: try without login first
  python3 ~/.hermes/skills/media/bilibili-subtitle-download/scripts/bilibili_subtitle.py BV1xx411c7mD

  # Specify language (e.g. Chinese AI subtitle)
  python3 ~/.hermes/skills/media/bilibili-subtitle-download/scripts/bilibili_subtitle.py BV1xx411c7mD --language ai-zh

  # Force re-login (if credentials expired)
  python3 ~/.hermes/skills/media/bilibili-subtitle-download/scripts/bilibili_subtitle.py BV1xx411c7mD --force-login

  # Output as JSON with timestamps
  python3 ~/.hermes/skills/media/bilibili-subtitle-download/scripts/bilibili_subtitle.py BV1xx411c7mD --format json --timestamps

  # Save to file instead of stdout
  python3 ~/.hermes/skills/media/bilibili-subtitle-download/scripts/bilibili_subtitle.py BV1xx411c7mD --output subtitle.txt
output_formats: |
  Default: plain text (paragraphs)
  --format json: structured JSON with segments, full_text, timestamped_text
  --format srt: SRT subtitle format
  --timestamps: prepend [MM:SS] to each line (text mode only)
author: lingfeng
---

# Bilibili Subtitle Download

This skill downloads subtitles from Bilibili videos. Many Bilibili videos only have AI-generated subtitles, which require a logged-in account to access.

## Features

1. **Auto-detect login requirement**: Tries without login first; prompts for QR login only when needed
2. **Persistent credentials**: Saves login state to `~/.cache/bilibili-subtitle/cookies.json`
3. **Multiple languages**: Supports official subtitles and AI-generated subtitles (`ai-zh`, `ai-en`, etc.)
4. **Flexible output**: Plain text, JSON, or SRT format; optional timestamps
5. **Terminal QR display**: Shows QR code in terminal (ASCII art) + saves image to `/tmp`

## When to use

- You need to analyze the content of a Bilibili video
- You want to create notes or summaries from a video
- You need subtitles for translation or accessibility

## Embedding Bilibili videos in Obsidian

If you want to watch Bilibili videos directly inside Obsidian without switching apps, use an iframe with Bilibili's official embed player.

### Embed URL format

```
https://player.bilibili.com/player.html?bvid={BV_ID}&page=1&high_quality=1&autoplay=0
```

Parameters:
- `bvid` — the BV ID (e.g. `BV1LU6KBLEZX`)
- `page` — episode/page number (default 1)
- `high_quality=1` — request high quality (actual quality depends on login state)
- `autoplay=0` — do not auto-play on load
- `t=332` — optional start time in seconds (e.g. `t=332` starts at 05:32)

### Markdown iframe snippet

```markdown
<iframe src="https://player.bilibili.com/player.html?bvid=BV1LU6KBLEZX&page=1&high_quality=1&autoplay=0" width="100%" height="400" frameborder="0" allowfullscreen></iframe>
```

### Limitations

- The iframe only renders in **Reading mode** or **Live Preview** mode. In Source mode you see raw HTML.
- **清晰度 (quality)**: The player has a quality selector (bottom-right gear icon). `high_quality=1` requests HD, but 1080P+ requires a logged-in Bilibili account or premium membership.
- **倍速 (playback speed)**: Built-in support via the player's own controls.
- **时间点跳转 (timepoint links)**: Clicking a timestamp link inside the note cannot control the already-loaded iframe due to Obsidian's security sandbox. Workarounds:
  - Record timestamps as plain text (e.g. `05:32 虚拟语气定义`) and manually seek the player.
  - Use an external Bilibili link with `?t=332` parameter — opens in browser and auto-seeks, but requires switching apps.

### Batch-generating embed codes

If you have many course files with `bvid` in frontmatter, generate iframe snippets via script:

```python
import re

bvid = re.search(r'^bvid:\s*(\S+)', content, re.MULTILINE).group(1)
iframe = f'<iframe src="https://player.bilibili.com/player.html?bvid={bvid}&page=1&high_quality=1&autoplay=0" width="100%" height="400" frameborder="0" allowfullscreen></iframe>'
```

## Common issues

- **"No subtitles found" even after login**: Some videos genuinely have no subtitles. Check if the video has "AI字幕" enabled on the Bilibili web player.
- **"Invalid URL" / "No scheme supplied" for subtitle download**: Bilibili sometimes returns protocol-relative URLs (`//aisubtitle.hdslb.com/...`). The script auto-fixes this by prepending `https:`, but if you see this error, ensure you're using the latest version of the script.
- **QR code expired**: Default timeout is ~3 minutes. If you take too long, run with `--force-login` again.
- **"Credential expired"**: Bilibili sessions expire after some time. Use `--force-login` to refresh.
- **QR not displaying in terminal**: The script tries multiple methods (terminal ANSI codes, ASCII art, image file). If all fail, use the "Online QR" link or open `/tmp/bilibili_qr.png` directly.
- **"Cannot read input in non-interactive mode"**: The QR login requires an interactive terminal. Run the script directly in a terminal, not via piping or background processes.
- **Cookie saved to `/tmp/bili_cookie.txt` but script can't find it**: The skill expects cookies at `~/.cache/bilibili-subtitle/cookies.json` (JSON format). If you have a raw cookie string from another source, parse it into JSON and save it there, or re-run `--force-login`.

## Implementation notes

This script was developed against `bilibili-api-python` with a newer async API. Key differences from older tutorials:

- `QrCodeLogin` uses `generate_qrcode()` / `check_state()` instead of old `get_url()` / `get_events()`
- `Video.get_subtitle()` now **requires** a valid credential (sessdata) — it will fail with `CredentialNoSessdataException` if omitted
- The login URL is stored in a private attribute (`_QrCodeLogin__qr_link`), accessed via Python name mangling
- The `Picture.url` from `get_qrcode_picture()` is a local file path, not the scan URL

## Script arguments

```
python3 bilibili_subtitle.py <BV_ID_or_URL> [options]

Options:
  --language LANG     Subtitle language code (default: ai-zh if available, else zh)
  --format {text,json,srt}  Output format (default: text)
  --timestamps        Include timestamps in text output
  --output FILE       Save to file instead of stdout
  --force-login       Ignore saved credentials and re-login
  --list-languages    Only list available subtitle languages, don't download
```
