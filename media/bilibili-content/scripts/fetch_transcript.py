#!/usr/bin/env python3
"""
Fetch Bilibili video transcripts — official and AI subtitles without login.

Uses the x/v2/dm/view endpoint which exposes subtitle URLs for both official
and AI-generated subtitles in the vast majority of cases, NO login required.

QR login is only attempted as a last resort for locked/premium content.

Usage:
    python fetch_transcript.py <url_or_bvid> [options]

Examples:
    python fetch_transcript.py BV1GJ411x7h7
    python fetch_transcript.py https://bilibili.com/video/BV1GJ411x7h7 --format json
    python fetch_transcript.py BV1GJ411x7h7 --format srt --output sub.srt
    python fetch_transcript.py BV1GJ411x7h7 --language ai-zh
"""

import argparse
import http.cookiejar
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from typing import List, Dict, Optional, Tuple

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.bilibili.com",
}

# ---------------------------------------------------------------------------
# BV ID extraction
# ---------------------------------------------------------------------------

def extract_bvid(url_or_id: str) -> str:
    """Extract BV ID from various Bilibili URL formats."""
    s = url_or_id.strip()
    if re.match(r'^BV[1-9A-HJ-NP-Za-km-z]{10}$', s):
        return s
    # b23.tv short links require expansion, but we'll try patterns first
    patterns = [
        r'/video/(BV[1-9A-HJ-NP-Za-km-z]{10})',
        r'b23\.tv/(BV[1-9A-HJ-NP-Za-km-z]{10})',
        r'(BV[1-9A-HJ-NP-Za-km-z]{10})',
    ]
    for pat in patterns:
        m = re.search(pat, s)
        if m:
            return m.group(1)
    # If nothing matched, maybe it's a raw b23.tv code without BV prefix
    if re.match(r'^[0-9a-zA-Z]{6,}$', s) and 'b23.tv' not in s:
        # Could be a short code — we can't resolve it here without HTTP request
        pass
    raise ValueError(f"Cannot extract BV ID from: {url_or_id}")


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def api_request(url: str, headers_extra: Optional[Dict] = None) -> dict:
    h = dict(HEADERS)
    if headers_extra:
        h.update(headers_extra)
    req = urllib.request.Request(url, headers=h)
    resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read())
    if data.get("code") != 0:
        msg = data.get("message", "Bilibili API error")
        raise RuntimeError(f"{msg} (code={data.get('code')})")
    return data.get("data", {})


def get_video_info(bvid: str) -> dict:
    """Fetch video metadata."""
    return api_request(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}")


def get_subtitles_via_dm_view(cid: int) -> List[Dict]:
    """
    Primary subtitle source: x/v2/dm/view.
    Works WITHOUT login for official and AI subtitles on almost all videos.
    """
    try:
        data = api_request(f"https://api.bilibili.com/x/v2/dm/view?oid={cid}&type=1")
    except RuntimeError as e:
        # Some very old videos return errors on this endpoint
        raise RuntimeError(f"dm/view endpoint failed: {e}")

    subtitle_data = data.get("subtitle") if isinstance(data.get("subtitle"), dict) else {}
    if subtitle_data is None:
        return []
    subs = subtitle_data.get("subtitles", [])
    return subs if isinstance(subs, list) else []


def get_player_info(bvid: str, cid: int) -> dict:
    """Secondary check: player/v2 (mostly for need_login_subtitle flag)."""
    try:
        data = api_request(
            f"https://api.bilibili.com/x/player/v2?cid={cid}&bvid={bvid}",
            headers_extra={"Referer": f"https://www.bilibili.com/video/{bvid}"},
        )
    except RuntimeError:
        return {}
    return data


def fetch_subtitle_json(sub_url: str) -> List[Dict]:
    """Download and parse a Bilibili subtitle JSON file."""
    if sub_url.startswith("//"):
        sub_url = "https:" + sub_url
    data = api_request(sub_url, headers_extra={"Referer": "https://www.bilibili.com"})
    body = data.get("body", [])
    if not isinstance(body, list):
        return []
    return [
        {
            "text": item.get("content", "").strip(),
            "start": float(item.get("from", 0)),
            "end": float(item.get("to", 0)),
        }
        for item in body
        if item.get("content", "").strip()
    ]


# ---------------------------------------------------------------------------
# Subtitle selection
# ---------------------------------------------------------------------------

def pick_subtitle(subs: List[Dict], preferred: Optional[str] = None) -> Optional[Dict]:
    """Pick best matching subtitle from list."""
    if not subs:
        return None

    if preferred:
        # Exact match
        for sub in subs:
            if sub.get("lan") == preferred:
                return sub
        # Partial match
        for sub in subs:
            if preferred in sub.get("lan", ""):
                return sub

    # Default priority: Chinese AI -> Chinese -> English AI -> English -> first available
    priorities = ["ai-zh", "zh-CN", "zh-Hans", "zh", "ai-en", "en-US", "en"]
    for p in priorities:
        for sub in subs:
            if sub.get("lan") == p:
                return sub

    return subs[0]


# ---------------------------------------------------------------------------
# QR login helpers (last-resort fallback)
# ---------------------------------------------------------------------------

def generate_qr(opener=None) -> Tuple[str, str]:
    """Generate Bilibili login QR. Returns (login_url, qrcode_key)."""
    url = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
    req = urllib.request.Request(url, headers=HEADERS)
    if opener is not None:
        resp = opener.open(req, timeout=15)
    else:
        resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read())
    if data.get("code") != 0:
        raise RuntimeError(f"QR generate failed: {data}")
    return data["data"]["url"], data["data"]["qrcode_key"]


def display_qr(login_url: str, no_xdg: bool = False) -> bool:
    """Save QR as PNG and open it; also print terminal-friendly version."""
    try:
        import qrcode
        img = qrcode.make(login_url)
        img.save("/tmp/bili_qr.png")
    except Exception as e:
        print(f"Failed to generate PNG: {e}", file=sys.stderr)
        return False

    opened = False
    if not no_xdg and os.environ.get("DISPLAY"):
        try:
            subprocess.run(
                ["setsid", "xdg-open", "/tmp/bili_qr.png"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            opened = True
        except Exception:
            pass

    # Terminal fallback: pure Unicode block chars (no ANSI, no TTY needed)
    print("\n" + "=" * 46)
    print("         Scan this QR code with Bilibili App")
    print("=" * 46)
    try:
        qr = qrcode.QRCode(border=2)
        qr.add_data(login_url)
        qr.make()
        matrix = qr.get_matrix()
        for row in matrix:
            line = ""
            for mod in row:
                line += "\u2588\u2588" if mod else "  "
            print(line)
        print("=" * 46)
    except Exception as e:
        print(f"Terminal QR failed: {e}", file=sys.stderr)

    if opened:
        print("\nPNG image viewer opened. If you cannot see the QR above, check your desktop.")
    print("Waiting for scan...\n")
    return True


def poll_login(qrcode_key: str, cookie_jar=None) -> Tuple[bool, Optional[str], dict]:
    """Poll QR login status. Returns (success, sessdata, raw_response)."""
    poll_url = (
        f"https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
        f"?qrcode_key={qrcode_key}"
    )
    if cookie_jar is not None:
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cookie_jar)
        )
    else:
        opener = urllib.request.build_opener()

    req = urllib.request.Request(poll_url, headers=HEADERS)
    resp = opener.open(req, timeout=15)
    data = json.loads(resp.read())

    inner_code = data.get("data", {}).get("code", data.get("code"))

    if inner_code != 0:
        return False, None, data

    # Login succeeded. Extract SESSDATA from response headers (most reliable).
    sessdata = None
    set_cookie = resp.headers.get("Set-Cookie", "")
    for part in set_cookie.split(","):
        part = part.strip()
        if part.startswith("SESSDATA="):
            sessdata = part.split(";")[0].split("=", 1)[1]
            break

    # Fallback: check cookie jar
    if not sessdata and cookie_jar is not None:
        for c in cookie_jar:
            if c.name == "SESSDATA":
                sessdata = c.value
                break

    return True, sessdata, data


def fetch_subtitles_with_cookie(bvid: str, sessdata: str) -> Tuple[List[Dict], str]:
    """Fetch AI subtitles for a video using SESSDATA cookie."""
    h = dict(HEADERS)
    h["Cookie"] = f"SESSDATA={sessdata}"

    # Get CID
    view_data = api_request(
        f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}",
        headers_extra=h,
    )
    cid = view_data["cid"]
    title = view_data.get("title", "")

    # Get subtitle list via player/v2 (authenticated)
    player_data = api_request(
        f"https://api.bilibili.com/x/player/v2?cid={cid}&bvid={bvid}",
        headers_extra=h,
    )
    subs = player_data.get("subtitle", {}).get("subtitles", [])
    if not subs:
        return [], title

    sub_url = subs[0].get("subtitle_url", "")
    if not sub_url:
        return [], title
    if sub_url.startswith("//"):
        sub_url = "https:" + sub_url

    segments = fetch_subtitle_json(sub_url)
    return segments, title


# ---------------------------------------------------------------------------
# Fallback: audio + Whisper
# ---------------------------------------------------------------------------

def download_audio(bvid: str, out_dir: str) -> str:
    """Download audio from Bilibili using you-get."""
    subprocess.run(
        ["you-get", f"https://www.bilibili.com/video/{bvid}"],
        cwd=out_dir,
        check=True,
        capture_output=True,
    )
    files = [f for f in os.listdir(out_dir) if f.endswith((".mp4", ".flv", ".mkv", "webm"))]
    if not files:
        raise RuntimeError("you-get did not produce a video file")
    video_path = os.path.join(out_dir, files[0])
    audio_path = os.path.join(out_dir, "audio.wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", audio_path],
        check=True,
        capture_output=True,
    )
    return audio_path


def transcribe_with_whisper(audio_path: str, language: str = "zh") -> List[Dict]:
    """Transcribe audio using OpenAI Whisper."""
    import whisper
    model = whisper.load_model("base")
    result = model.transcribe(audio_path, language=language, verbose=False)
    segments = []
    for seg in result.get("segments", []):
        segments.append({
            "text": seg["text"].strip(),
            "start": float(seg["start"]),
            "end": float(seg["end"]),
        })
    return segments


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_timestamp(seconds: float) -> str:
    total = int(seconds)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def format_srt_time(seconds: float) -> str:
    total = int(seconds * 1000)
    h, rem = divmod(total, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_text(segments: List[Dict], with_timestamps: bool = False) -> str:
    if with_timestamps:
        return "\n".join(
            f"[{format_timestamp(seg['start'])}] {seg['text']}" for seg in segments
        )
    return " ".join(seg["text"] for seg in segments)


def to_srt(segments: List[Dict]) -> str:
    lines = []
    for i, seg in enumerate(segments, 1):
        start = format_srt_time(seg["start"])
        end = format_srt_time(seg["end"])
        lines.append(f"{i}\n{start} --> {end}\n{seg['text']}\n")
    return "\n".join(lines)


def to_json(segments: List[Dict], bvid: str, title: str, lang: str, duration: int) -> str:
    full_text = " ".join(seg["text"] for seg in segments)
    timestamped = "\n".join(
        f"[{format_timestamp(seg['start'])}] {seg['text']}" for seg in segments
    )
    return json.dumps({
        "bvid": bvid,
        "title": title,
        "language": lang,
        "segment_count": len(segments),
        "duration": format_timestamp(duration) if isinstance(duration, int) else str(duration),
        "full_text": full_text,
        "timestamped_text": timestamped,
        "segments": [
            {"text": seg["text"], "start": seg["start"], "end": seg["end"]}
            for seg in segments
        ],
    }, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Fetch Bilibili transcript")
    parser.add_argument("url", help="Bilibili URL or BV ID")
    parser.add_argument("--language", "-l", default=None, help="Preferred subtitle language (e.g. ai-zh, zh-CN, en)")
    parser.add_argument("--format", "-f", choices=["text", "json", "srt"], default="text",
                        help="Output format (default: text)")
    parser.add_argument("--timestamps", "-t", action="store_true",
                        help="Include timestamps in text output")
    parser.add_argument("--output", "-o", default=None, help="Save to file instead of stdout")
    parser.add_argument("--transcribe", action="store_true",
                        help="Fall back to audio download + Whisper if no subtitles")
    parser.add_argument("--no-xdg-open", action="store_true",
                        help="Do not open QR code PNG with image viewer")
    parser.add_argument("--qr-timeout", type=int, default=120,
                        help="QR login polling timeout in seconds")
    args = parser.parse_args()

    bvid = extract_bvid(args.url)
    info = get_video_info(bvid)
    title = info.get("title", "")
    duration = info.get("duration", 0)
    cid = info.get("cid", 0)

    segments: List[Dict] = []
    selected_lang = "unknown"

    # ------------------------------------------------------------------
    # Step 1: PRIMARY — x/v2/dm/view (no login required for 99% videos)
    # ------------------------------------------------------------------
    if cid:
        try:
            subs = get_subtitles_via_dm_view(cid)
            if subs:
                selected = pick_subtitle(subs, args.language)
                if selected:
                    selected_lang = selected.get("lan", "unknown")
                    sub_url = selected.get("subtitle_url", "")
                    if sub_url:
                        segments = fetch_subtitle_json(sub_url)
        except RuntimeError as e:
            print(f"Subtitle lookup warning: {e}", file=sys.stderr)

    # ------------------------------------------------------------------
    # Step 2: If dm/view empty, check if login-gated AI subtitles exist
    # ------------------------------------------------------------------
    if not segments and cid:
        player_info = get_player_info(bvid, cid)
        needs_login = player_info.get("need_login_subtitle", False)
        if needs_login:
            print("AI subtitles may require Bilibili login. Generating QR code...", file=sys.stderr)

            # Fixed: single generate call with shared cookie jar
            cookie_jar = http.cookiejar.CookieJar()
            gen_opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(cookie_jar)
            )
            login_url, qrcode_key = generate_qr(opener=gen_opener)
            display_qr(login_url, no_xdg=args.no_xdg_open)

            print("Polling for login confirmation...", file=sys.stderr)
            sessdata = None
            for i in range(args.qr_timeout // 2):
                success, sd, data = poll_login(qrcode_key, cookie_jar=cookie_jar)
                if success:
                    sessdata = sd
                    break

                inner_code = data.get("data", {}).get("code", data.get("code"))
                if inner_code == 86090:
                    print(f"[{i*2}/{args.qr_timeout}s] Scanned, waiting for confirm...", file=sys.stderr)
                elif inner_code == 86101:
                    if i % 5 == 0:
                        print(f"[{i*2}/{args.qr_timeout}s] Waiting for scan...", file=sys.stderr)
                elif inner_code == 86038:
                    print("QR code expired.", file=sys.stderr)
                    break
                else:
                    print(f"Unknown status {inner_code}: {data.get('message', '')}", file=sys.stderr)

                time.sleep(2)
            else:
                print("Timeout waiting for scan.", file=sys.stderr)

            if sessdata:
                segments, _ = fetch_subtitles_with_cookie(bvid, sessdata)
                if segments:
                    selected_lang = "ai-zh"  # best guess after login
            else:
                print("Login failed or timed out.", file=sys.stderr)
                if not args.transcribe:
                    print(json.dumps({
                        "error": "Login failed or timed out",
                        "title": title,
                        "duration": duration,
                        "bvid": bvid,
                        "suggestion": "Re-run with --transcribe to use Whisper",
                    }, ensure_ascii=False, indent=2))
                    sys.exit(1)

    # ------------------------------------------------------------------
    # Step 3: Fallback — Audio download + Whisper transcription
    # ------------------------------------------------------------------
    if not segments and args.transcribe:
        print("No subtitles found. Falling back to Whisper transcription...", file=sys.stderr)
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = download_audio(bvid, tmpdir)
            segments = transcribe_with_whisper(audio_path)

    if not segments:
        print(json.dumps({
            "error": "No subtitles found.",
            "title": title,
            "duration": duration,
            "bvid": bvid,
            "suggestion": "Re-run with --transcribe to download audio and use Whisper",
        }, ensure_ascii=False, indent=2))
        sys.exit(1)

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------
    if args.format == "json":
        output = to_json(segments, bvid, title, selected_lang, duration)
    elif args.format == "srt":
        output = to_srt(segments)
    else:
        output = to_text(segments, with_timestamps=args.timestamps)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Saved to: {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
