#!/usr/bin/env python3
"""Generate a profile banner from Spotify playback, with a Sunflower fallback.

The SVG is self-contained: both the banner art and the current album cover are
embedded so GitHub's image proxy can render the same image reliably.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "banner.svg"
FALLBACK_COVER = ROOT / "assets" / "sunflower-cover.jpg"
DEFAULT_BAR_COLOR = "#971018"

FALLBACK = {
    "title": "Sunflower",
    "artist": "Post Malone, Swae Lee",
    "mode": "SUNFLOWER · FALLBACK",
}


def request_json(url: str, *, data: bytes | None = None, headers: dict[str, str] | None = None):
    request = urllib.request.Request(url, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read()
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as error:
        if error.code in (204, 401, 403, 404):
            return error.code, None
        raise


def dominant_accent(image: bytes) -> str:
    """Select a readable, saturated dominant color from an album cover."""
    with Image.open(BytesIO(image)) as source:
        # Quantization prevents JPEG compression noise from defeating color counts.
        palette_image = source.convert("RGB").resize((64, 64)).quantize(colors=16)
        palette = palette_image.getpalette()
        colors = palette_image.getcolors() or []
    best: tuple[float, tuple[int, int, int]] | None = None
    for count, index in colors:
        red, green, blue = palette[index * 3 : index * 3 + 3]
        maximum, minimum = max(red, green, blue), min(red, green, blue)
        saturation = (maximum - minimum) / maximum if maximum else 0
        brightness = (red * 0.299 + green * 0.587 + blue * 0.114) / 255
        if saturation < 0.18 or not 0.10 <= brightness <= 0.90:
            continue
        score = count * (0.7 + saturation)
        if best is None or score > best[0]:
            best = (score, (red, green, blue))
    if best is None:
        _, index = max(colors, key=lambda entry: entry[0])
        red, green, blue = palette[index * 3 : index * 3 + 3]
        # A grayscale/dark sleeve still gets its own readable visualizer shade.
        peak = max(red, green, blue)
        if peak < 96:
            scale = 96 / max(peak, 1)
            red, green, blue = (min(255, round(channel * scale)) for channel in (red, green, blue))
        return f"#{red:02x}{green:02x}{blue:02x}"
    red, green, blue = best[1]
    return f"#{red:02x}{green:02x}{blue:02x}"


def image_asset(image: bytes, content_type: str) -> tuple[str, str]:
    if not content_type.startswith("image/") or not image:
        raise ValueError("Spotify returned an invalid album image")
    uri = f"data:{content_type};base64," + base64.b64encode(image).decode("ascii")
    return uri, dominant_accent(image)


def request_image_asset(url: str) -> tuple[str, str]:
    """Fetch Spotify cover artwork and prepare it for a single SVG image."""
    with urllib.request.urlopen(url, timeout=30) as response:
        return image_asset(response.read(), response.headers.get_content_type())


def local_image_asset(path: Path) -> tuple[str, str]:
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return image_asset(path.read_bytes(), content_type)


def cover_asset(data: dict) -> tuple[str, str]:
    """Use live artwork and accent color when available; otherwise use Sunflower."""
    cover_url = data.get("cover_url")
    if cover_url:
        try:
            return request_image_asset(cover_url)
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            print(f"Album cover fetch failed; using Sunflower cover: {error}", file=sys.stderr)
    return local_image_asset(FALLBACK_COVER)


def now_playing() -> dict | None:
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    refresh_token = os.getenv("SPOTIFY_REFRESH_TOKEN")
    if not all((client_id, client_secret, refresh_token)):
        return None

    encoded = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    payload = urllib.parse.urlencode(
        {"grant_type": "refresh_token", "refresh_token": refresh_token}
    ).encode()
    status, auth = request_json(
        "https://accounts.spotify.com/api/token",
        data=payload,
        headers={
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    if status != 200 or not auth or not auth.get("access_token"):
        return None

    status, playback = request_json(
        "https://api.spotify.com/v1/me/player/currently-playing",
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    if status != 200 or not playback or not playback.get("is_playing"):
        return None

    item = playback.get("item") or {}
    title = item.get("name")
    artists = ", ".join(a.get("name", "") for a in item.get("artists", []))
    images = ((item.get("album") or {}).get("images") or [])
    cover_url = images[0].get("url") if images else None
    if not title or not artists:
        return None
    return {
        "title": title,
        "artist": artists,
        "mode": "NOW PLAYING · SPOTIFY",
        "cover_url": cover_url,
    }


def fit_text(value: str, limit: int) -> str:
    """Reserve a fixed visual region without letting long metadata spill out."""
    value = " ".join(value.split())
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def safe_color(value: str) -> str:
    return value if re.fullmatch(r"#[0-9a-fA-F]{6}", value) else DEFAULT_BAR_COLOR


def estimate_width(text: str, font_size: int, font_weight: str = "normal") -> float:
    """Rough heuristic for Arial text width since exact font metrics aren't easily available."""
    width = 0.0
    for char in text:
        if char in "ijlI1.,' ":
            width += 0.3 * font_size
        elif char in "WwMmO0Q@":
            width += 0.85 * font_size
        elif char.isupper():
            width += 0.7 * font_size
        else:
            width += 0.55 * font_size
    if font_weight == "bold":
        width *= 1.1
    return width


def banner(data: dict) -> str:
    is_playing = data["mode"].startswith("NOW PLAYING")
    title = escape(fit_text(data["title"], 27))
    artist = escape(fit_text(data["artist"], 30))
    mode = escape(data["mode"])
    cover = escape(data["cover"])
    bar_color = safe_color(data.get("bar_color", DEFAULT_BAR_COLOR))
    hero_data = "data:image/png;base64," + base64.b64encode(
        (ROOT / "assets" / "miles-hero.png").read_bytes()
    ).decode("ascii")

    bar_heights = (20, 45, 28, 61, 37, 54, 24, 49, 32, 58, 23)
    bars = "".join(
        f'''<rect x="{490 + i * 38}" y="{515 - height}" width="11" height="{height}" rx="5" class="bar">
    <animate attributeName="height" values="{height};{min(70, height + 14)};{max(12, height // 2)};{height}" dur="0.82s" begin="{i * 0.09}s" repeatCount="indefinite"/>
    <animate attributeName="y" values="{515 - height};{515 - min(70, height + 14)};{515 - max(12, height // 2)};{515 - height}" dur="0.82s" begin="{i * 0.09}s" repeatCount="indefinite"/>
  </rect>'''
        for i, height in enumerate(bar_heights)
    )
    title_fill = "#f4ff00" if not is_playing else "#f8f8f8"
    
    # Selectively squish title if it's too long
    title_width = estimate_width(data["title"], 61, "bold")
    title_attrs = ' class="track"'
    if title_width > 850:
        title_attrs += ' textLength="850" lengthAdjust="spacingAndGlyphs"'

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1983" height="793" viewBox="0 0 1983 793" role="img" aria-labelledby="title desc">
  <title id="title">What's Up Danger — {title}</title>
  <desc id="desc">Miles Morales profile banner. {mode}: {title} by {artist}.</desc>
  <defs>
    <clipPath id="coverClip"><rect x="122" y="215" width="328" height="328" rx="18"/></clipPath>
    <clipPath id="artistClip"><rect x="490" y="390" width="860" height="62"/></clipPath>
    <linearGradient id="card" x1="0" y1="0" x2="1" y2="1">
      <stop stop-color="#070b10" stop-opacity="0.97"/>
      <stop offset="1" stop-color="#0c1114" stop-opacity="0.93"/>
    </linearGradient>
    <style>
      .label {{ font: 500 28px Arial, sans-serif; fill: #727277; }}
      .track {{ font: 700 61px Arial, sans-serif; fill: {title_fill}; }}
      .artist {{ font: 400 34px Arial, sans-serif; fill: #c9f6f6; }}
      .bar {{ fill: {bar_color}; }}
    </style>
  </defs>
  <image href="{hero_data}" x="0" y="0" width="1983" height="793" preserveAspectRatio="xMidYMid slice"/>
  <rect x="64" y="164" width="1410" height="465" rx="35" fill="url(#card)" stroke="#202b34" stroke-width="2"/>
  <image href="{cover}" x="122" y="215" width="328" height="328" preserveAspectRatio="xMidYMid slice" clip-path="url(#coverClip)"/>
  <text x="490" y="304" class="label">Now Playing</text>
  <text x="490" y="381"{title_attrs}>{title}</text>
  <text x="490" y="432" class="artist" clip-path="url(#artistClip)">by {artist}</text>
  {bars}
</svg>\n'''


def main() -> None:
    try:
        data = now_playing() or FALLBACK.copy()
        data["cover"], data["bar_color"] = cover_asset(data)
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        print(f"Spotify request failed; using fallback: {error}", file=sys.stderr)
        data = FALLBACK.copy()
        data["cover"], data["bar_color"] = local_image_asset(FALLBACK_COVER)
    OUTPUT.write_text(banner(data), encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)} — {data['mode']}")


if __name__ == "__main__":
    main()
