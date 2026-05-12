#!/usr/bin/env python3
"""
Bilibili QR login + subtitle fetcher.

Handles the full flow:
  1. Generate login QR code (single API call with shared cookie jar)
  2. Display QR (PNG via xdg-open + terminal Unicode blocks)
  3. Poll for scan confirmation
  4. Extract SESSDATA from response headers
  5. Fetch AI subtitles for a given BV ID

CRITICAL FIX: generate() and poll() MUST share the same CookieJar.
Bilibili sets a buvid3 session cookie during generate that must be
present during poll, or the login response will not include SESSDATA.

Usage:
    python3 bilibili_login.py --bvid BV1LU6KBLEZX
    python3 bilibili_login.py --bvid BV1LU6KBLEZX --no-xdg-open
"""

import argparse
import http.cookiejar
import json
import os
import subprocess
import sys
import time
import urllib.request
from typing import Tuple, Optional

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.bilibili.com",
}


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


def display_qr(login_url, no_xdg=False):
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


def poll_login(qrcode_key, cookie_jar=None):
    """Poll QR login status. Returns (success: bool, sessdata: str, raw_response)."""
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
    # urllib's CookieJar may NOT capture it due to cookie policy quirks,
    # so we parse Set-Cookie manually as a fallback.
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


def fetch_subtitles_with_cookie(bvid, sessdata):
    """Fetch AI subtitles for a video using SESSDATA cookie."""
    h = dict(HEADERS)
    h["Cookie"] = f"SESSDATA={sessdata}"

    # Get CID
    view_req = urllib.request.Request(
        f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}",
        headers=h,
    )
    view_resp = urllib.request.urlopen(view_req, timeout=15)
    view_data = json.loads(view_resp.read())
    cid = view_data["data"]["cid"]
    title = view_data["data"]["title"]

    # Get subtitle list
    sub_req = urllib.request.Request(
        f"https://api.bilibili.com/x/player/v2?cid={cid}&bvid={bvid}",
        headers=h,
    )
    sub_resp = urllib.request.urlopen(sub_req, timeout=15)
    sub_data = json.loads(sub_resp.read())

    subs = sub_data.get("data", {}).get("subtitle", {}).get("subtitles", [])
    if not subs:
        return None, title

    sub_url = subs[0].get("subtitle_url", "") if subs else ""
    if not sub_url:
        return None, title
    if sub_url.startswith("//"):
        sub_url = "https:" + sub_url

    sub_req2 = urllib.request.Request(sub_url, headers=h)
    sub_resp2 = urllib.request.urlopen(sub_req2, timeout=15)
    sub_json = json.loads(sub_resp2.read())

    body = sub_json.get("body", [])
    lines = [item["content"].strip() for item in body if item.get("content", "").strip()]
    return lines, title


def main():
    parser = argparse.ArgumentParser(description="Bilibili QR login + subtitle fetch")
    parser.add_argument("--bvid", required=True, help="Bilibili BV ID")
    parser.add_argument("--no-xdg-open", action="store_true", help="Do not open PNG viewer")
    parser.add_argument("--cookies", default="/tmp/bili_cookies.txt", help="Where to save SESSDATA")
    parser.add_argument("--timeout", type=int, default=120, help="Polling timeout in seconds")
    args = parser.parse_args()

    # FIXED: single generate call with shared cookie jar.
    # The CookieJar captures buvid3 during generate, which is required for poll
    # to return SESSDATA.
    cookie_jar = http.cookiejar.CookieJar()
    gen_opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cookie_jar)
    )
    login_url, qrcode_key = generate_qr(opener=gen_opener)
    display_qr(login_url, no_xdg=args.no_xdg_open)

    print("Polling for login confirmation...")
    for i in range(args.timeout // 2):
        success, sessdata, data = poll_login(qrcode_key, cookie_jar=cookie_jar)
        if success:
            print("\nLogin successful!")
            if sessdata:
                with open(args.cookies, "w") as f:
                    f.write(f"SESSDATA={sessdata}\n")
                print(f"SESSDATA saved to {args.cookies}")
            else:
                print("WARNING: No SESSDATA found in response.")
                print(f"Response: {json.dumps(data, ensure_ascii=False, indent=2)}")
                sys.exit(1)

            print(f"\nFetching subtitles for {args.bvid}...")
            lines, title = fetch_subtitles_with_cookie(args.bvid, sessdata)
            if lines is None:
                print("No subtitles found for this video.")
                sys.exit(1)

            out_txt = f"/tmp/bili_subtitle_{args.bvid}.txt"
            with open(out_txt, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            print(f"\nTitle: {title}")
            print(f"Subtitles: {len(lines)} lines")
            print(f"Saved to: {out_txt}")
            sys.exit(0)

        inner_code = data.get("data", {}).get("code", data.get("code"))
        if inner_code == 86090:
            print(f"[{i*2}/{args.timeout}s] Scanned, waiting for confirm...")
        elif inner_code == 86101:
            if i % 5 == 0:
                print(f"[{i*2}/{args.timeout}s] Waiting for scan...")
        elif inner_code == 86038:
            print("QR code expired. Please re-run.")
            sys.exit(1)
        else:
            print(f"Unknown status {inner_code}: {data.get('message', '')}")

        time.sleep(2)

    print("Timeout waiting for scan.")
    sys.exit(1)


if __name__ == "__main__":
    main()
