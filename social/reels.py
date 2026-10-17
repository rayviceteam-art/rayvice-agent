"""Reels pipeline v2: scene-synced script -> free TTS voiceover -> ffmpeg 9:16 render.

- Free tools only: edge-tts (Microsoft Edge neural voices) + ffmpeg/libass.
- Source clips: assets/videos/<key>.mp4 (owner screen recordings, demo data only).
- Edit plan: assets/videos/<key>.edit.json - privacy blur windows + optional jump cuts
  (cut se pehle emails ka scroll/transition wala hissa hata dete hain).
- Segments: [{"at": seconds(final timeline), "text": "..."}] -> per-segment TTS,
  exact timestamps pe placed = screen ke saath sync.
- Publishing: adapters media.kind == "reel" pe Reels flow chalate hain.
"""
import asyncio
import hashlib
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
VOICE = "en-AU-WilliamMultilingualNeural"
PROMPT_VERSION = "reel-v2"
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


def load_edit(key):
    p = os.path.join(VIDEO_DIR, f"{key}.edit.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_segments(key):
    p = os.path.join(VIDEO_DIR, f"{key}.segments.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None


def _duration(path):
    out = subprocess.run([_ffmpeg(), "-i", path], capture_output=True, text=True).stderr
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", out)
    if not m:
        return 0.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


# ---------------- AI script (generic, future features) ----------------

def _build_messages(feature_desc):
    system = (
        "You write short-form video scripts for Rayvice, software for independent Australian NDIS "
        "support workers (invoicing, shifts, dashboard). STRICT RULES: Australian English. Never invent "
        "statistics, testimonials, customer numbers or certifications. Never guarantee compliance or "
        "approval. No fear-based marketing, no fake urgency. Reply with ONLY valid JSON: "
        '{"hook": "<=60 chars", "voiceover": "70-95 word spoken script", '
        '"caption": "IG/FB caption 1-3 sentences", "hashtags": ["ndis", ...max 8]}'
    )
    user = (f"Feature shown in the recording: {feature_desc}. Start by naming the pain point, show the "
            "workflow step by step, end with the free trial (9 days, no card, rayvice.com).")
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
    if not (40 <= words <= 140):
        return {"ok": False, "error": f"voiceover word count off ({words})"}
    check = validators.validate("instagram", hook=str(data.get("hook") or ""),
                                body=voice + "\n" + str(data.get("caption") or ""),
                                hashtags=data.get("hashtags") or [])
    if check["errors"]:
        return {"ok": False, "error": "validation failed: " + "; ".join(check["errors"][:4])}
    n = check["normalised"]
    return {"ok": True, "hook": n["hook"][:60], "voiceover": voice,
            "caption": str(data.get("caption") or "").strip(), "hashtags": (n.get("hashtags") or [])[:8],
            "model": getattr(res, "model", "")}


# ---------------- TTS ----------------

def tts(text, out_path, voice=None, rate="+8%"):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    try:
        import edge_tts

        async def _run():
            comm = edge_tts.Communicate(text, voice or VOICE, rate=rate)
            await comm.save(out_path)
        asyncio.run(_run())
        if os.path.exists(out_path) and os.path.getsize(out_path) > 1500:
            return True, ""
        return False, "tts produced too-small file"
    except Exception as e:
        return False, f"tts failed: {e}"[:200]


# ---------------- captions (ASS) ----------------

def _ass_time(sec):
    cs = max(0, int(sec * 100))
    return f"{cs // 360000}:{(cs // 6000) % 60:02d}:{(cs // 100) % 60:02d}.{cs % 100:02d}"


def _caption_cues(segments, seg_durs, max_chars=40):
    """Segments -> cues: (start, end, text). Segment ke andar proportional timing."""
    cues = []
    for (seg, dur) in zip(segments, seg_durs):
        text = re.sub(r"\s+", " ", seg["text"]).strip()
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", text) if s]
        lines = []
        for s in sentences:
            line = ""
            for w in s.split():
                cand = (line + " " + w).strip()
                if len(cand) > max_chars and line:
                    lines.append(line)
                    line = w
                else:
                    line = cand
            if line:
                lines.append(line)
        chunks = ["\\N".join(lines[i:i + 2]) for i in range(0, len(lines), 2)]
        total_chars = sum(len(c) for c in chunks) or 1
        t = seg["at"]
        for c in chunks:
            d = max(0.9, (len(c) / total_chars) * max(1.0, dur - 0.15))
            cues.append((t, t + d, c))
            t += d
    return cues


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


# ---------------- render ----------------

def _blur_filters(blurs, base_t, src_label):
    """Returns (filter_segments, out_label). windows FINAL timeline -> branch local (base_t shift)."""
    segs = []
    lbl = src_label
    for i, b in enumerate(blurs):
        wins = []
        for a, z in b["windows"]:
            a2, z2 = max(a, base_t), z
            if z2 > a2:
                wins.append((a2 - base_t, z2 - base_t))
        if not wins:
            continue
        x, y, w, h = b["box"]
        en = "+".join(f"between(t,{a:.2f},{z:.2f})" for a, z in wins)
        cb = f"cb{i}_{lbl}"
        ov = f"ov{i}_{lbl}"
        segs.append(f"[{lbl}]split=2[{cb}s][{cb}t]")
        segs.append(f"[{cb}t]crop={w}:{h}:{x}:{y},boxblur=10:3[{cb}]")
        segs.append(f"[{cb}s][{cb}]overlay={x}:{y}:enable='{en}'[{ov}]")
        lbl = ov
    return segs, lbl


def render_reel(source, voice_files, segments, out_path, edit=None, size=(1080, 1920), freeze_pad=0.3):
    """voice_files: [(at, path, dur)]; segments: [{"at","text"}] (captions ke liye)."""
    edit = edit or {}
    cut = edit.get("cut")  # [start, end] original timeline
    blurs = edit.get("blur", [])
    w, h = size
    v_dur = _duration(source)
    a_end = cut[0] if cut else v_dur
    b_start = cut[1] if cut else v_dur
    cut_len = (b_start - a_end) if cut else 0.0
    f_vdur = v_dur - cut_len

    last_end = max((a + d for a, _, d in voice_files), default=0.0)
    total = max(f_vdur, last_end + freeze_pad)
    freeze = max(0.0, total - f_vdur)

    ass_path = out_path + ".ass"
    _write_ass(_caption_cues(segments, [d for _, _, d in voice_files]), ass_path, w, h)

    a_blurs = [b for b in blurs if min(a for a, _ in b["windows"]) < a_end]
    if b_start < v_dur - 0.01:
        graph = ["[0:v]split=2[vs0][vs1]",
                 f"[vs0]trim=0:{a_end:.3f},setpts=PTS-STARTPTS[va0]"]
        a_segs, a_out = _blur_filters(a_blurs, 0.0, "va0")
        graph += a_segs
        graph.append(f"[vs1]trim={b_start:.3f},setpts=PTS-STARTPTS[vb0]")
        b_blurs = [b for b in blurs if min(a for a, _ in b["windows"]) >= a_end]
        b_segs, b_out = _blur_filters(b_blurs, a_end, "vb0")
        graph += b_segs
        graph.append(f"[{a_out}][{b_out}]concat=n=2:v=1:a=0[vc]")
        vlast = "vc"
    else:
        graph = [f"[0:v]trim=0:{a_end:.3f},setpts=PTS-STARTPTS[va0]"]
        a_segs, a_out = _blur_filters(a_blurs, 0.0, "va0")
        graph += a_segs
        vlast = a_out
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
          f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=0x0B1116,setsar=1,fps=30")
    if freeze > 0.05:
        vf += f",tpad=stop_mode=clone:stop_duration={freeze:.2f}"
    vf += f",subtitles={ass_path}"
    graph.append(f"[{vlast}]{vf}[v]")

    ag = []
    amix_ins = []
    for i, (at, path, dur) in enumerate(voice_files):
        ms = int(at * 1000)
        ag.append(f"[{i + 1}:a]adelay={ms}:all=1[a{i}]")
        amix_ins.append(f"[a{i}]")
    ag.append("".join(amix_ins) + f"amix=inputs={len(voice_files)}:normalize=0:duration=longest,"
              f"loudnorm=I=-16:TP=-1.5:LRA=11,apad[a]")

    cmd = [_ffmpeg(), "-y", "-i", source]
    for _, p, _ in voice_files:
        cmd += ["-i", p]
    cmd += ["-filter_complex", ";".join(graph) + ";" + ";".join(ag),
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
            "-t", f"{total:.2f}", out_path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    os.path.exists(ass_path) and os.remove(ass_path)
    if r.returncode != 0 or not os.path.exists(out_path):
        raise ValueError(f"ffmpeg render failed: {r.stderr[-2500:]}")
    return out_path


def make_reel(feature_key, segments, caption="", hashtags=None, hook="",
              voice=None, register=True, edit=None, freeze_pad=0.3):
    """Full pipeline: per-segment TTS -> render (cut+blur) -> media row."""
    src = find_video(feature_key)
    if not src:
        return {"ok": False, "error": f"assets/videos/{feature_key}.mp4 not found"}
    if not segments:
        return {"ok": False, "error": "segments required"}
    edit = edit if edit is not None else load_edit(feature_key)

    body = " ".join(s["text"] for s in segments)
    check = validators.validate("instagram", hook=hook, body=body + "\n" + caption,
                                hashtags=hashtags or [])
    if check["errors"]:
        return {"ok": False, "error": "validation failed: " + "; ".join(check["errors"][:4])}

    mid = "m_" + uuid.uuid4().hex[:10]
    work = os.path.join(REEL_DIR, f".work_{mid}")
    os.makedirs(work, exist_ok=True)
    voice_files = []
    try:
        for i, seg in enumerate(segments):
            p = os.path.join(work, f"seg{i}.mp3")
            ok, err = tts(seg["text"], p, voice=voice)
            if not ok:
                return {"ok": False, "error": err}
            voice_files.append((float(seg["at"]), p, _duration(p)))
        out = os.path.join(REEL_DIR, f"{mid}.mp4")
        render_reel(src, voice_files, segments, out, edit=edit, freeze_pad=freeze_pad)
    finally:
        for _, p, _ in voice_files:
            os.path.exists(p) and os.remove(p)
        try:
            os.rmdir(work)
        except Exception:
            pass

    url_media = __import__("social.media", fromlist=["public_url"]).public_url(f"reels/{os.path.basename(out)}")
    rel = os.path.relpath(out, os.path.dirname(REEL_DIR)).replace("\\", "/")
    bytes_ = os.path.getsize(out)
    with open(out, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if register:
        c = db.connect()
        c.execute("INSERT INTO social_media VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (mid, ts, "reel", rel, url_media, "ffmpeg", (hook or body[:80])[:500],
                   1080, 1920, bytes_, sha, "READY", ""))
        c.commit()
        c.close()
    return {"ok": True, "media_id": mid, "path": out, "rel_path": rel, "url": url_media,
            "bytes": bytes_, "sha256": sha}
