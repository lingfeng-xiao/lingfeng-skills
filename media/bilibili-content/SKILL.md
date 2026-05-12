---
name: bilibili-content
description: >
  Extract transcripts from Bilibili videos and convert them into structured content
  (chapters, summaries, threads, blog posts). Checks for official subtitles first,
  then falls back to audio download + Whisper transcription when subtitles are absent.
  Use when the user shares a Bilibili URL or asks to summarize/analyze a Bilibili video.
---

# Bilibili Content Tool

Extract transcripts from Bilibili (B站) videos and convert them into useful formats.

## Prerequisites

```bash
# For official subtitle extraction: no extra deps
# For audio fallback: you-get, ffmpeg, openai-whisper
nix-shell -p you-get ffmpeg
pip install openai-whisper
```

## Helper Scripts

`SKILL_DIR` is the directory containing this SKILL.md file.

```bash
# Check subtitle availability and download if present
python3 SKILL_DIR/scripts/fetch_transcript.py "BV1xx411c7mD"

# Force audio download + Whisper transcription (slow, CPU-intensive)
python3 SKILL_DIR/scripts/fetch_transcript.py "BV1xx411c7mD" --transcribe

# With timestamps
python3 SKILL_DIR/scripts/fetch_transcript.py "BV1xx411c7mD" --timestamps

# Bilibili QR login (when AI subtitles require authentication)
# Generates a terminal QR code, waits for scan, saves SESSDATA to /tmp/bili_cookies.txt
python3 SKILL_DIR/scripts/bilibili_login.py --bvid "BV1xx411c7mD"
```

## Workflow

1. **Extract BV ID** from any Bilibili URL format (`BV...`, `b23.tv`, `av...`).
2. **Check subtitles via two APIs**:
   - First: `/x/web-interface/view` (legacy subtitle list).
   - Second: `/x/player/v2?cid={cid}&bvid={bvid}` (modern player API, reveals AI-generated subtitles and `need_login_subtitle` flag).
3. **If subtitles exist** (either API returns a `subtitle_url`): fetch and parse the JSON subtitle file directly.
4. **If `need_login_subtitle` is true**:
   - The video has AI-generated subtitles but they are hidden from anonymous API calls.
   - **Preferred**: ask the user for their `SESSDATA` cookie and re-run with authentication.
   - **Fallback**: use `yt-dlp --cookies-from-browser` (if the user has a logged-in browser) or download audio + Whisper.
5. **If truly no subtitles**:
   - Search public skill repos for newer dedicated tools first.
   - Search the web for existing notes/summaries of the video (course notes, 课代表, etc.).
   - Only then consider downloading audio + Whisper transcription. Warn the user about time cost (~5-15 min for a 40-min video on CPU).
6. **Transform** into the requested output format.

## Output Formats

Same as youtube-content skill:

- **Chapters**: Group by topic shifts, output timestamped chapter list
- **Summary**: Concise 5-10 sentence overview
- **Chapter summaries**: Chapters with a short paragraph summary for each
- **Thread**: Twitter/X thread format — numbered posts, each under 280 chars
- **Blog post**: Full article with title, sections, and key takeaways
- **Quotes**: Notable quotes with timestamps

### Example — Chapters Output

```
00:00 Introduction — host opens with the problem statement
03:45 Background — prior work and why existing solutions fall short
12:20 Core method — walkthrough of the proposed approach
24:10 Results — benchmark comparisons and key takeaways
31:55 Q&A — audience questions on scalability and next steps
```

## Key Findings from Real Usage

- **Most Bilibili videos have NO official subtitles.** The API returns `"subtitle": {"list": []}` for the majority of uploads.
- **AI-generated subtitles are common on popular videos** (especially courses and long-form content), but they require login. The `/x/player/v2` API exposes a `"need_login_subtitle": true` flag. **Do NOT report "no subtitles" when this flag is set** — the subtitles exist but are gated behind authentication.
- **QR login for subtitle access**: when `need_login_subtitle` is true and the user is willing to scan a QR code, use `scripts/bilibili_login.py`. It handles the full flow: generate QR → terminal display → poll → cookie extraction → subtitle fetch.
  - **Critical**: `generate` and `poll` MUST share a `CookieJar`. Bilibili sets a `buvid3` session cookie during `generate` that must be present during `poll`, or the login response will not include `SESSDATA`.
  - **Critical**: Bilibili's QR poll status is in the *inner* `data.code`, NOT the outer HTTP `code`. Outer code is always `0` for a successful API call. Inner codes: `86101` = unscanned, `86090` = scanned unconfirmed, `0` = success, `86038` = expired.
  - **Critical**: SESSDATA appears in the `Set-Cookie` header of the *poll* response when login succeeds. urllib's `CookieJar` may fail to capture it, so parse `resp.headers.get("Set-Cookie")` manually as a fallback.
- **Terminal QR display pitfalls**: 
  - `qrcode.print_tty()` **fails** when stdout is not a real TTY (e.g. inside `execute_code` or piped output). It raises `OSError: Not a tty`.
  - **ANSI escape codes** (`\x1b[7m` inverse video) are **stripped** by `execute_code`'s output pipeline, producing blank lines.
  - **Reliable terminal method**: use pure Unicode block characters (`\u2588\u2588` for dark modules, `"  "` for light modules). This works in `execute_code`, TUI mode, and any Unicode-capable terminal without relying on ANSI or TTY detection.
  - **Most reliable display**: save PNG to `/tmp/bili_qr.png` and open with `setsid xdg-open /tmp/bili_qr.png`. Works on Hyprland/Wayland and any DE.
- **AI subtitle content mismatch**: Bilibili's AI subtitle system occasionally attaches the wrong subtitle file to a video (e.g. a career advice subtitle attached to an English grammar course). Always sanity-check the first few lines against the video title/description. If the content is clearly mismatched, fall back to Whisper transcription.
- **Public skill repos** (skills.sh, lobehub, clawhub) do NOT currently offer a one-step "download + transcribe" tool for Bilibili. The closest skill (`bilibili-agent`) only fetches comments/danmaku, not transcripts.
- **Audio fallback is reliable but slow.** `you-get` works on NixOS via `nix-shell`; Whisper `base` model on CPU transcribes ~1x real-time (40 min audio ≈ 40 min processing). Use `tiny` or `base` for Mandarin Chinese; `small` if accuracy is critical and time allows.
- **Paid/season videos** may return preview-only content or require SESSDATA cookie authentication.
- **NixOS browser limitation**: `yt-dlp --cookies-from-browser` only works if the browser profile is on the local filesystem. If the user watches Bilibili in a containerized or remote browser, cookie extraction will fail (0 cookies extracted).

## Error Handling

- **`need_login_subtitle` detected**: do not tell the user "no subtitles exist". Explain that AI subtitles are present but require Bilibili login. Offer three options in order: (1) user provides `SESSDATA` cookie for direct fetch, (2) `yt-dlp --cookies-from-browser` if a logged-in browser profile exists locally, (3) audio download + Whisper transcription.
- **No subtitles + user declines transcription**: summarize based on title, description, comments, and any existing user notes. Be explicit about the limitation.
- **you-get timeout / blocked**: try `yt-dlp` as fallback, or ask the user to provide their own notes/transcript.
- **Whisper not installed**: guide the user to `nix-shell -p ffmpeg` and `pip install openai-whisper`.
- **Region-locked / login-required video**: inform the user that authentication is needed beyond what the skill can provide.

## Related Skills

- `youtube-content` — same workflow for YouTube (has official transcript API, much more reliable).
- `whisper` — detailed guidance on model sizes, language selection, and GPU acceleration.
