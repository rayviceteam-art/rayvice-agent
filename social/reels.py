"""Reels pipeline: AI script -> free TTS voiceover -> ffmpeg 9:16 render (burned captions).

- Free tools only: edge-tts (Microsoft Edge neural voices, no key) + ffmpeg/libass.
- Source clips: assets/videos/<key>.mp4 (owner-provided screen recordings, demo data only).
- Produces: video (media/reels/<id>.mp4) + draft row + media row -> publish_queue reuse.
- Publishing: InstagramAdapter / FacebookAdapter media.kind == "reel" pe Reels flow chalate hain.
"""
import asyncio
import json
import os
import re
import subprocess
import uuid
from datetime import datetime, timezone

import config
from social import db, validators

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO_DIR = os.path.join(ROOT, "assets", "videos")
REEL_DIR = os.path.join(ROOT, "media", "reels")
VOICE = "en-AU-NatashaNeural"
PROMPT_VERSION = "reel-v1"
FONT = "DejaVu Sans"


def _ffmpeg():
    env = os.environ.get("FFMPEG_BIN")
    if env:
        return env
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def find_video(key):
    for ext in ("mp4", "mov", "mkv", "webm"):
        p = os.path.join(VIDEO_DIR, f"{key}.{ext}")
        if os.path.exists(p):
            return p
    return None


def _duration(path):
    """Media duration (seconds) — ffmpeg -i stderr parse."""
    out = subprocess.run([_ffmpeg(), "-i", path], capture_output=True, text=True).stderr
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", out)
    if not m:
        return 0.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def _build_messages(feature_desc):
    system = (
        "You write short-form video scripts for Rayvice, software for independent Australian NDIS "
        "support workers (invoicing, shifts, dashboard). STRICT RULES: Australian English. Never invent "
        "statistics, testimonials, customer numbers or certifications. Never guarantee compliance or "
        "approval. No fear-based marketing, no fake urgency. Describe only generic capabilities shown in "
        "the screen recording. Voiceover: 70-95 words, natural spoken tone, 4-6 short sentences, no emojis, "
        "no stage directions. Reply with ONLY valid JSON: "
        '{"hook": "<=60 chars on-screen idea", "voiceover": "spoken script", '
        '"caption": "IG/FB caption 1-3 sentences", "hashtags": ["ndis", ...max 8]}'
    )
    user = (f"Feature shown in the recording: {feature_desc}. "
            "Start by naming the pain point, show the workflow step by step, end with the free trial "
            "(9 days, no card, rayvice.com).")
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _extract_json(text):
    if not text:
        return None
    t = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    m = re.search(r"\{.*\}", t, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


def make_script(feature_desc, allow_retry=True):
    """AI reel script. Returns {ok, hook, voiceover, caption, hashtags} or error."""
    import model_router
    res = model_router.run_task("draft", _build_messages(feature_desc))
    data = _extract_json(res.text) if getattr(res, "ok", False) else None
    if data is None and allow_retry:
        msgs = _build_messages(feature_desc) + [
            {"role": "assistant", "content": (getattr(res, "text", "") or "")[:500]},
            {"role": "user", "content": "That was not valid JSON. Reply again with ONLY the JSON object."}]
        res2 = model_router.run_task("draft", msgs)
        data = _extract_json(res2.text) if getattr(res2, "ok", False) else None
    if data is None:
        return {"ok": False, "error": f"AI script failed: {getattr(res, 'error', 'junk output')}"[:300]}
    voice = str(data.get("voiceover") or "").strip()
    words = len(voice.split())
    if not (50 <= words <= 130):
        return {"ok": False, "error": f"voiceover word count off ({words})"}
    check = validators.validate("instagram", hook=str(data.get("hook") or ""), body=voice + "\n" + str(data.get("caption") or ""),
                                hashtags=data.get("hashtags") or [])
    if check["errors"]:
        return {"ok": False, "error": "validation failed: " + "; ".join(check["errors"][:4])}
    n = check["normalised"]
    hs = n.get("hashtags") or []
    return {"ok": True, "hook": n["hook"][:60], "voiceover": voice,
            "caption": str(data.get("caption") or "").strip(), "hashtags": hs[:8],
            "model": getattr(res, "model", "")}


def tts(text, out_path):
    """edge-tts se mp3 voiceover. Returns (ok, error)."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    try:
        import edge_tts

        async def _run():
            comm = edge_tts.Communicate(text, VOICE, rate="+6%")
            await comm.save(out_path)
        asyncio.run(_run())
        if os.path.exists(out_path) and os.path.getsize(out_path) > 2000:
            return True, ""
        return False, "tts produced too-small file"
    except Exception as e:
        return False, f"tts failed: {e}"[:200]


def _ass_time(sec):
    cs = max(0, int(sec * 100))
    return f"{cs // 360000}:{(cs // 6000) % 60:02d}:{(cs // 100) % 60:02d}.{cs % 100:02d}"


def _caption_cues(voiceover, total_dur, max_chars=38):
    """Sentences -> 2-line cues, time proportional to char count."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", voiceover) if s.strip()]
    cues = []
    for s in sentences:
        words, line, lines = s.split(), "", []
        for w in words:
            cand = (line + " " + w).strip()
            if len(cand) > max_chars and line:
                lines.append(line)
                line = w
            else:
                line = cand
        if line:
            lines.append(line)
        for i in range(0, len(lines), 2):
            cues.append("\\N".join(lines[i:i + 2]))
    total_chars = sum(len(c.strip("\\N")) for c in cues) or 1
    out, t = [], 0.2
    for c in cues:
        d = max(1.0, (len(c.replace("\\N", " ")) / total_chars) * (total_dur - 0.4))
        out.append((t, t + d, c))
        t += d
    return out


def _write_ass(cues, path, width=1080, height=1920):
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{FONT},54,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,3,0,2,60,60,240,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for st, en, text in cues:
        lines.append(f"Dialogue: 0,{_ass_time(st)},{_ass_time(en)},Cap,,0,0,0,,{text}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def render_reel(source_video, voice_path, voiceover, out_path, size=(1080, 1920)):
    """ffmpeg: brand bg pad + burned captions + voiceover (video height match)."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    v_dur, a_dur = _duration(source_video), _duration(voice_path)
    if v_dur <= 0 or a_dur <= 0:
        raise ValueError(f"bad durations video={v_dur} audio={a_dur}")
    extra = max(0.0, a_dur + 0.6 - v_dur)
    total = min(v_dur + extra, 90.0)
    ass_path = out_path + ".ass"
    _write_ass(_caption_cues(voiceover, min(a_dur, total)), ass_path, size[0], size[1])
    w, h = size
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
          f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=0x0B1116,setsar=1,fps=30")
    if extra > 0.05:
        vf += f",tpad=stop_mode=clone:stop_duration={extra:.2f}"
    vf += f",subtitles={ass_path}"
    cmd = [_ffmpeg(), "-y", "-i", source_video, "-i", voice_path,
           "-filter_complex", f"[0:v]{vf}[v];[1:a]apad[a]",
           "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
           "-t", f"{total:.2f}", out_path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    os.path.exists(ass_path) and os.remove(ass_path)
    if r.returncode != 0 or not os.path.exists(out_path):
        raise ValueError(f"ffmpeg render failed: {r.stderr[-400:]}")
    return out_path


def make_reel(feature_key, feature_desc, feature_benefit="", register=True):
    """Full pipeline: script -> tts -> render -> media row. Publish alag (draft enqueue)."""
    src = find_video(feature_key)
    if not src:
        return {"ok": False, "error": f"assets/videos/{feature_key}.mp4 not found"}
    sc = make_script(f"{feature_desc}. {feature_benefit}".strip())
    if not sc.get("ok"):
        return sc
    mid = "m_" + uuid.uuid4().hex[:10]
    os.makedirs(REEL_DIR, exist_ok=True)
    voice = os.path.join(REEL_DIR, f"{mid}.mp3")
    ok, err = tts(sc["voiceover"], voice)
    if not ok:
        return {"ok": False, "error": err}
    out = os.path.join(REEL_DIR, f"{mid}.mp4")
    try:
        render_reel(src, voice, sc["voiceover"], out)
    finally:
        os.path.exists(voice) and os.remove(voice)
    from social import media as media_mod  # noqa: F401
    rel = os.path.relpath(out, os.path.dirname(REEL_DIR)).replace("\\", "/")
    from social.media import public_url
    url = public_url(f"reels/{os.path.basename(out)}")
    bytes_ = os.path.getsize(out)
    import hashlib
    with open(out, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if register:
        c = db.connect()
        c.execute("INSERT INTO social_media VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (mid, ts, "reel", rel, url, "ffmpeg", sc["hook"][:500],
                   1080, 1920, bytes_, sha, "READY", ""))
        c.commit()
        c.close()
    return {"ok": True, "media_id": mid, "path": out, "rel_path": rel, "url": url,
            "hook": sc["hook"], "voiceover": sc["voiceover"], "caption": sc["caption"],
            "hashtags": sc["hashtags"], "bytes": bytes_, "sha256": sha}
