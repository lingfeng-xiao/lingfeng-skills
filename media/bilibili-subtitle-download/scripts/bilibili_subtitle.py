#!/usr/bin/env python3
"""
Fetch Bilibili video subtitles (including AI-generated subtitles).

Usage:
    python bilibili_subtitle.py <BV_ID_or_URL> [options]

Examples:
    python bilibili_subtitle.py BV1LU6KBLEZX
    python bilibili_subtitle.py BV1LU6KBLEZX --language ai-zh --format json
    python bilibili_subtitle.py https://bilibili.com/video/BV1LU6KBLEZX --output sub.txt

Install dependencies:
    pip install bilibili-api-python qrcode requests
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import requests

# Optional dependencies with helpful error messages
try:
    from bilibili_api import video, login_v2, Credential
    import qrcode
except ImportError as e:
    print(f"Error: Missing dependency: {e}", file=sys.stderr)
    print("Run: pip install bilibili-api-python qrcode requests", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CACHE_DIR = Path.home() / ".cache" / "bilibili-subtitle"
COOKIE_FILE = CACHE_DIR / "cookies.json"
QR_IMG_PATH = Path("/tmp/bilibili_qr.png")
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Referer": "https://www.bilibili.com",
}

# ---------------------------------------------------------------------------
# Credential management
# ---------------------------------------------------------------------------
def load_credential() -> Credential:
    if COOKIE_FILE.exists():
        try:
            cookies = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
            return Credential.from_cookies(cookies)
        except Exception:
            pass
    return None


def save_credential(cred: Credential) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    COOKIE_FILE.write_text(
        json.dumps(cred.get_cookies(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# BV parsing
# ---------------------------------------------------------------------------
def extract_bvid(url_or_bvid: str) -> str:
    url_or_bvid = url_or_bvid.strip()
    if url_or_bvid.startswith("BV") and len(url_or_bvid) == 12:
        return url_or_bvid
    patterns = [
        r'video/(BV[a-zA-Z0-9]{10})',
        r'(BV[a-zA-Z0-9]{10})',
    ]
    for pat in patterns:
        import re
        m = re.search(pat, url_or_bvid)
        if m:
            return m.group(1)
    raise ValueError(f"Cannot extract BV ID from: {url_or_bvid}")


# ---------------------------------------------------------------------------
# Login flow
# ---------------------------------------------------------------------------
async def login_with_qr() -> Credential:
    qr = login_v2.QrCodeLogin()
    await qr.generate_qrcode()

    # Save QR image using bilibili_api's Picture
    try:
        pic = qr.get_qrcode_picture()
        pic.to_file(str(QR_IMG_PATH))
        print(f"QR image saved to: {QR_IMG_PATH}")
    except Exception as e:
        print(f"Warning: could not save QR image: {e}", file=sys.stderr)

    # Try to generate a displayable QR using qrcode library
    # Access the actual login URL via name mangling (private attribute)
    qr_url = getattr(qr, '_QrCodeLogin__qr_link', None)
    if not qr_url:
        # Fallback: try to extract from picture (unlikely to work)
        try:
            qr_url = pic.url
        except Exception:
            qr_url = None

    if qr_url and qr_url.startswith("http"):
        qr_img = qrcode.make(qr_url)
        try:
            print(qr_img.terminal())
        except Exception:
            qr_obj = qrcode.QRCode(border=1)
            qr_obj.add_data(qr_url)
            qr_obj.make()
            qr_obj.print_ascii(invert=True)
    else:
        print(f"Warning: could not get login URL for QR display", file=sys.stderr)
        qr_url = None

    if qr_url:
        print(f"\nOr scan via URL: {qr_url}")
        encoded = requests.utils.quote(qr_url, safe="")
        print(f"Online QR: https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={encoded}")

    print("\n>>> Please scan the QR code with your Bilibili mobile app <<<")
    try:
        input("Press Enter after scanning...\n")
    except EOFError:
        print("Error: Cannot read input in non-interactive mode.", file=sys.stderr)
        print("Please run this script in an interactive terminal.", file=sys.stderr)
        sys.exit(1)

    # Check result
    state = await qr.check_state()
    if qr.has_done():
        cred = qr.get_credential()
        save_credential(cred)
        print("Login successful!")
        return cred
    elif state == login_v2.QrCodeLoginEvents.TIMEOUT:
        print("Error: QR code expired. Please run again.", file=sys.stderr)
        sys.exit(1)
    elif state == login_v2.QrCodeLoginEvents.SCAN:
        print("Error: QR scanned but not confirmed. Please confirm on your phone.", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"Error: Unexpected login status: {state}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Subtitle fetching
# ---------------------------------------------------------------------------
async def get_video_info(bvid: str) -> dict:
    """Get basic video info (no credential required)."""
    v = video.Video(bvid=bvid)
    return await v.get_info()


async def get_subtitle_list(bvid: str, cid: int, credential: Credential):
    """Return subtitle list. Requires valid credential for AI subtitles."""
    v = video.Video(bvid=bvid, credential=credential)
    result = await v.get_subtitle(cid=cid)
    subtitles = result.get("subtitles", []) if isinstance(result, dict) else result
    return subtitles


def download_subtitle_content(subtitle_url: str) -> list:
    """Download and parse subtitle JSON. Returns list of segment dicts."""
    # Bilibili sometimes returns protocol-relative URLs (//host/path)
    if subtitle_url.startswith("//"):
        subtitle_url = "https:" + subtitle_url
    resp = requests.get(subtitle_url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("body", [])


def pick_language(subtitles: list, preferred: str = None) -> dict:
    """Pick best matching subtitle from list."""
    if not subtitles:
        return None

    if preferred:
        for sub in subtitles:
            if sub.get("lan") == preferred:
                return sub
        for sub in subtitles:
            if preferred in sub.get("lan", ""):
                return sub

    priorities = ["ai-zh", "zh-CN", "zh-Hans", "zh", "ai-en", "en-US", "en"]
    for p in priorities:
        for sub in subtitles:
            if sub.get("lan") == p:
                return sub

    return subtitles[0]


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------
def format_time(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def to_text(segments: list, with_timestamps: bool = False) -> str:
    if with_timestamps:
        return "\n".join(
            f"[{format_time(seg['from'])}] {seg['content']}" for seg in segments
        )
    return " ".join(seg["content"] for seg in segments)


def to_srt(segments: list) -> str:
    lines = []
    for i, seg in enumerate(segments, 1):
        start = format_srt_time(seg["from"])
        end = format_srt_time(seg["to"])
        lines.append(f"{i}\n{start} --> {end}\n{seg['content']}\n")
    return "\n".join(lines)


def format_srt_time(seconds: float) -> str:
    total = int(seconds * 1000)
    h, rem = divmod(total, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_json(segments: list, bvid: str, title: str, lang: str) -> str:
    full_text = " ".join(seg["content"] for seg in segments)
    timestamped = "\n".join(
        f"[{format_time(seg['from'])}] {seg['content']}" for seg in segments
    )
    return json.dumps({
        "bvid": bvid,
        "title": title,
        "language": lang,
        "segment_count": len(segments),
        "full_text": full_text,
        "timestamped_text": timestamped,
        "segments": [
            {"text": seg["content"], "start": seg["from"], "end": seg["to"]}
            for seg in segments
        ],
    }, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Main async logic
# ---------------------------------------------------------------------------
async def async_main(args):
    bvid = extract_bvid(args.url)
    print(f"BV ID: {bvid}")

    # Step 1: Get video info (no credential needed)
    try:
        info = await get_video_info(bvid)
    except Exception as e:
        print(f"Error fetching video info: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Title: {info.get('title', 'N/A')}")
    cid = info["cid"]

    # Step 2: Load credential and try to get subtitles
    credential = None
    if not args.force_login:
        credential = load_credential()
        if credential:
            print("Using saved credentials.")

    subtitles = []
    if credential:
        try:
            subtitles = await get_subtitle_list(bvid, cid, credential)
        except Exception as e:
            print(f"Error fetching subtitles with saved credential: {e}", file=sys.stderr)
            print("Credential may be expired. Try --force-login", file=sys.stderr)
            sys.exit(1)

    print(f"Found {len(subtitles)} subtitle track(s).")

    # Step 3: No subtitles found, try login
    if not subtitles and not args.force_login:
        print("\nNo subtitles found without login. AI subtitles may require authentication.")
        print("Starting QR login...\n")
        credential = await login_with_qr()
        subtitles = await get_subtitle_list(bvid, cid, credential)
        print(f"Found {len(subtitles)} subtitle track(s) after login.")

    if not subtitles:
        print("Error: No subtitles available for this video.", file=sys.stderr)
        sys.exit(1)

    if args.list_languages:
        print("\nAvailable subtitle languages:")
        for sub in subtitles:
            print(f"  {sub.get('lan', 'unknown'):12}  {sub.get('lan_doc', 'Unknown')}")
        return

    selected = pick_language(subtitles, args.language)
    if selected is None:
        print("Error: Could not select a subtitle track.", file=sys.stderr)
        sys.exit(1)

    lang_code = selected.get("lan", "unknown")
    print(f"\nSelected language: {lang_code} ({selected.get('lan_doc', '')})")
    print(f"Downloading...")

    segments = download_subtitle_content(selected["subtitle_url"])
    print(f"Downloaded {len(segments)} segments.")

    if args.format == "json":
        output = to_json(segments, bvid, info.get("title", ""), lang_code)
    elif args.format == "srt":
        output = to_srt(segments)
    else:
        output = to_text(segments, with_timestamps=args.timestamps)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Saved to: {args.output}")
    else:
        print("\n" + "=" * 60)
        print(output)


def main():
    parser = argparse.ArgumentParser(description="Download Bilibili video subtitles")
    parser.add_argument("url", help="Bilibili URL or BV ID")
    parser.add_argument("--language", "-l", default=None, help="Preferred language code")
    parser.add_argument("--format", "-f", choices=["text", "json", "srt"], default="text")
    parser.add_argument("--timestamps", "-t", action="store_true")
    parser.add_argument("--output", "-o", default=None, help="Output file")
    parser.add_argument("--force-login", action="store_true")
    parser.add_argument("--list-languages", action="store_true")
    args = parser.parse_args()
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
