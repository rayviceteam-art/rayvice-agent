"""Image pipeline: provider adapter + Pillow branded-card fallback.

Rules (master prompt):
- Sirf verified/free image APIs; koi paid silent nahi.
- Fail ho to Pillow se clean branded educational card (text-based temporary identity,
  koi fake logo nahi).
- Publishing APIs ko PUBLIC URL chahiye — local path kabhi assume mat karo.
"""
import hashlib
import os
import textwrap
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone

import config
from social import db

MEDIA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "media")

BRAND_BG = (11, 17, 22)        # near-black (matches app icon)
BRAND_PANEL = (18, 28, 36)     # panel tint
BRAND_FG = (255, 255, 255)
BRAND_ACCENT = (224, 138, 60)  # brand orange (from app icon)
BRAND_BLUE = (75, 127, 166)    # brand steel blue
BRAND_MUTED = (150, 165, 178)

ICON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "assets", "brand", "app-icon.png")

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/system/fonts/Roboto-Bold.ttf",
]


def _font(size):
    from PIL import ImageFont
    for p in _FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def render_branded_card(title, subtitle="", footer="Rayvice", out_path=None, size=(1080, 1080)):
    """Brand card v2: real logo icon + brand colors + wrapped title."""
    from PIL import Image, ImageDraw
    os.makedirs((os.path.dirname(out_path) if out_path else "") or MEDIA_DIR, exist_ok=True)
    out_path = out_path or os.path.join(MEDIA_DIR, f"card_{uuid.uuid4().hex[:10]}.png")
    img = Image.new("RGB", size, BRAND_BG)
    d = ImageDraw.Draw(img)
    w, h = size

    # signature top bar: orange -> blue gradient strip
    bar = Image.new("RGB", (w, 14), BRAND_ACCENT)
    bd = ImageDraw.Draw(bar)
    for x in range(w):
        t = x / max(1, w - 1)
        col = tuple(int(BRAND_ACCENT[i] + (BRAND_BLUE[i] - BRAND_ACCENT[i]) * t) for i in range(3))
        bd.line([(x, 0), (x, 14)], fill=col)
    img.paste(bar, (0, 0))

    # logo icon (rounded) + wordmark
    did_icon = False
    if os.path.exists(ICON_PATH):
        try:
            icon = Image.open(ICON_PATH).convert("RGBA").resize((132, 132), Image.LANCZOS)
            mask = Image.new("L", (132, 132), 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, 131, 131], radius=28, fill=255)
            img.paste(icon, (70, 76), mask)
            did_icon = True
        except Exception:
            did_icon = False
    tx = 232 if did_icon else 70
    d.text((tx, 88), "Rayvice", font=_font(58), fill=BRAND_FG)
    d.text((tx + 3, 158), "NDIS admin, simplified", font=_font(28), fill=BRAND_MUTED)

    # hook text block
    f_title = _font(66)
    lines = textwrap.wrap(title or "", width=25)[:6]
    y = int(h * 0.30)
    for ln in lines:
        d.text((70, y), ln, font=f_title, fill=BRAND_FG)
        y += 86
    # accent underline after text
    d.rounded_rectangle([72, y + 14, 72 + 140, y + 22], radius=4, fill=BRAND_ACCENT)

    # subtitle panel
    if subtitle:
        f_sub = _font(34)
        sub_lines = textwrap.wrap(subtitle, width=44)[:3]
        py = h - 268
        d.rounded_rectangle([56, py - 34, w - 56, py + 34 + 48 * len(sub_lines)], radius=22, fill=BRAND_PANEL)
        y2 = py
        for ln in sub_lines:
            d.text((86, y2), ln, font=f_sub, fill=BRAND_MUTED)
            y2 += 48

    d.text((70, h - 80), footer, font=_font(30), fill=BRAND_ACCENT)
    d.text((w - 320, h - 80), "rayvice.com", font=_font(30), fill=BRAND_BLUE)
    img.save(out_path, "PNG", optimize=True)
    return out_path


SCREENSHOTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "assets", "screenshots")


def find_screenshot(feature_key):
    """assets/screenshots/<key>.{png,jpg,jpeg,webp} — optional product screenshot."""
    if not feature_key:
        return None
    for ext in ("png", "jpg", "jpeg", "webp"):
        p = os.path.join(SCREENSHOTS_DIR, f"{feature_key}.{ext}")
        if os.path.exists(p):
            return p
    return None


def render_screenshot_card(screenshot_path, title="", subtitle="", footer="Rayvice",
                           out_path=None, size=(1080, 1080)):
    """Branded frame + real product screenshot (feature spotlight posts)."""
    from PIL import Image, ImageDraw
    os.makedirs((os.path.dirname(out_path) if out_path else "") or MEDIA_DIR, exist_ok=True)
    out_path = out_path or os.path.join(MEDIA_DIR, f"shot_{uuid.uuid4().hex[:10]}.png")
    img = Image.new("RGB", size, BRAND_BG)
    d = ImageDraw.Draw(img)
    w, h = size

    bar = Image.new("RGB", (w, 14), BRAND_ACCENT)
    bd = ImageDraw.Draw(bar)
    for x in range(w):
        t = x / max(1, w - 1)
        col = tuple(int(BRAND_ACCENT[i] + (BRAND_BLUE[i] - BRAND_ACCENT[i]) * t) for i in range(3))
        bd.line([(x, 0), (x, 14)], fill=col)
    img.paste(bar, (0, 0))

    did_icon = False
    if os.path.exists(ICON_PATH):
        try:
            icon = Image.open(ICON_PATH).convert("RGBA").resize((90, 90), Image.LANCZOS)
            mask = Image.new("L", (90, 90), 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, 89, 89], radius=20, fill=255)
            img.paste(icon, (70, 56), mask)
            did_icon = True
        except Exception:
            did_icon = False
    tx = 186 if did_icon else 70
    d.text((tx, 62), "Rayvice", font=_font(44), fill=BRAND_FG)
    d.text((tx + 2, 118), "NDIS admin, simplified", font=_font(24), fill=BRAND_MUTED)

    f_title = _font(52)
    lines = textwrap.wrap(title or "", width=34)[:2]
    y = 190
    for ln in lines:
        d.text((70, y), ln, font=f_title, fill=BRAND_FG)
        y += 66

    area_top = y + 16
    area_bottom = h - (170 if subtitle else 116)
    area_h = max(120, area_bottom - area_top)
    shot = Image.open(screenshot_path).convert("RGBA")
    sw, sh = shot.size
    scale = min((w - 140) / sw, area_h / sh)
    nw, nh = max(1, int(sw * scale)), max(1, int(sh * scale))
    shot = shot.resize((nw, nh), Image.LANCZOS)
    x0, y0 = (w - nw) // 2, area_top + (area_h - nh) // 2
    mask = Image.new("L", (nw, nh), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, nw - 1, nh - 1], radius=18, fill=255)
    img.paste(shot, (x0, y0), mask)
    d.rounded_rectangle([x0 - 1, y0 - 1, x0 + nw, y0 + nh], radius=18, outline=BRAND_BLUE, width=3)

    if subtitle:
        f_sub = _font(30)
        sub_lines = textwrap.wrap(subtitle, width=48)[:2]
        py = h - 158
        d.rounded_rectangle([56, py - 22, w - 56, py + 24 + 42 * len(sub_lines)], radius=18, fill=BRAND_PANEL)
        y2 = py
        for ln in sub_lines:
            d.text((86, y2), ln, font=f_sub, fill=BRAND_MUTED)
            y2 += 42

    d.text((70, h - 80), footer, font=_font(30), fill=BRAND_ACCENT)
    d.text((w - 320, h - 80), "rayvice.com", font=_font(30), fill=BRAND_BLUE)
    img.save(out_path, "PNG", optimize=True)
    return out_path


def _pollinations(prompt, width=1080, height=1080, timeout=90):
    prompt = (prompt or "").strip()
    if prompt and "photo" not in prompt.lower():
        prompt += ", professional corporate photography, natural light, realistic, Australian small business, no text, no watermark, no logos"
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt[:900]) +
           f"?width={width}&height={height}&nologo=true&safe=true&model=flux")
    req = urllib.request.Request(url, headers={"User-Agent": config.REDDIT_USER_AGENT or "rayvice-agent"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    if len(data) < 5000:
        raise ValueError("pollinations returned too-small file")
    return data


def validate_image(path):
    """Returns (ok, info_or_error)."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            fmt, (w, h) = im.format, im.size
        size = os.path.getsize(path)
        if fmt not in ("PNG", "JPEG"):
            return False, f"format {fmt} not supported (PNG/JPEG only)"
        if w < 320 or h < 320:
            return False, f"too small {w}x{h} (min 320)"
        ratio = w / float(h)
        if ratio < 0.8 or ratio > 1.91:
            return False, f"aspect {ratio:.2f} outside 0.8-1.91 range"
        if size > 8 * 1024 * 1024:
            return False, f"file {size} bytes exceeds 8MB"
        return True, {"format": fmt, "width": w, "height": h, "bytes": size}
    except Exception as e:
        return False, f"unreadable image: {e}"


def public_url(filename):
    """Publishing APIs ke liye public URL. MEDIA_PUBLIC_BASE set ho to wahi."""
    if config.MEDIA_PUBLIC_BASE:
        return f"{config.MEDIA_PUBLIC_BASE}/{filename}"
    if config.GITHUB_REPO:
        return f"https://raw.githubusercontent.com/{config.GITHUB_REPO}/main/media/{filename}"
    return ""


def verify_public_url(url, timeout=30):
    """Publishing se pehle URL actually reachable hai ya nahi (anon GET)."""
    if not url:
        return False, "no public URL configured"
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "rayvice-agent"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            code = r.getcode()
            r.read(2048)
        return (200 <= code < 300), f"HTTP {code}"
    except Exception as e:
        return False, str(e)[:200]


def generate_image(prompt, title="", kind="image", register=True, subtitle=""):
    """Provider chain -> local file -> DB record. Returns dict."""
    os.makedirs(MEDIA_DIR, exist_ok=True)
    mid = "m_" + uuid.uuid4().hex[:10]
    provider = config.IMAGE_PROVIDER or "card"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path, used = None, ""

    if provider == "pollinations":
        fname = f"{mid}.png"
        cand = os.path.join(MEDIA_DIR, fname)
        try:
            data = _pollinations(prompt or title or "NDIS admin tips")
            with open(cand, "wb") as f:
                f.write(data)
            ok, info = validate_image(cand)
            if ok:
                path, used = cand, "pollinations"
            else:
                os.remove(cand)
        except Exception:
            path = None

    if not path:
        cand = os.path.join(MEDIA_DIR, f"{mid}.png")
        path = render_branded_card(title or prompt or "Rayvice", subtitle=subtitle, out_path=cand)
        used = "card"

    ok, info = validate_image(path)
    if not ok:
        return {"ok": False, "error": str(info)}

    with open(path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    rel = os.path.relpath(path, os.path.dirname(MEDIA_DIR)).replace("\\", "/")
    url = public_url(os.path.basename(path))

    if register:
        c = db.connect()
        c.execute("INSERT INTO social_media VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (mid, ts, kind, rel, url, used, (prompt or "")[:500],
                   info["width"], info["height"], info["bytes"], sha, "READY", ""))
        c.commit()
        c.close()
    return {"ok": True, "media_id": mid, "path": path, "rel_path": rel, "url": url,
            "provider": used, "sha256": sha, "width": info["width"], "height": info["height"],
            "bytes": info["bytes"]}


def generate_feature_image(feature_key, title="", subtitle="", register=True, kind="feature"):
    """Feature spotlight image: real screenshot (assets/screenshots/<key>.*) ho to
    branded frame me, warna same info ka branded card. Returns dict (generate_image jaisa)."""
    shot = find_screenshot(feature_key)
    if not shot:
        return generate_image(title, title=title, kind=kind, register=register, subtitle=subtitle)

    os.makedirs(MEDIA_DIR, exist_ok=True)
    mid = "m_" + uuid.uuid4().hex[:10]
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cand = os.path.join(MEDIA_DIR, f"{mid}.png")
    try:
        path = render_screenshot_card(shot, title=title or feature_key, subtitle=subtitle, out_path=cand)
        used = "screenshot"
    except Exception:
        return generate_image(title, title=title, kind=kind, register=register, subtitle=subtitle)

    ok, info = validate_image(path)
    if not ok:
        return generate_image(title, title=title, kind=kind, register=register, subtitle=subtitle)

    with open(path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    rel = os.path.relpath(path, os.path.dirname(MEDIA_DIR)).replace("\\", "/")
    url = public_url(os.path.basename(path))
    if register:
        c = db.connect()
        c.execute("INSERT INTO social_media VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (mid, ts, kind, rel, url, used, f"feature:{feature_key}"[:500],
                   info["width"], info["height"], info["bytes"], sha, "READY", ""))
        c.commit()
        c.close()
    return {"ok": True, "media_id": mid, "path": path, "rel_path": rel, "url": url,
            "provider": used, "sha256": sha, "width": info["width"], "height": info["height"],
            "bytes": info["bytes"]}
