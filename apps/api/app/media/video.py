"""Keyframe extraction from short product videos (reels/TikToks)."""
import asyncio
import io
import os
import tempfile

import imageio_ffmpeg
import numpy as np
from PIL import Image

from app.core.config import get_settings
from app.media.validate import MediaError, clean_image, sniff

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


async def _run(args: list[str], timeout: float) -> bytes:
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise MediaError("Video processing timed out")
    if proc.returncode != 0:
        raise MediaError("Could not read video")
    return out + err


async def _duration(path: str) -> float:
    # ffmpeg prints Duration on stderr when given no output; parse defensively.
    proc = await asyncio.create_subprocess_exec(
        FFMPEG, "-hide_banner", "-i", path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, err = await asyncio.wait_for(proc.communicate(), 20)
    text = err.decode(errors="ignore")
    if "Duration:" not in text:
        raise MediaError("Could not read video")
    hms = text.split("Duration:")[1].split(",")[0].strip()
    try:
        h, m, sec = hms.split(":")
        return int(h) * 3600 + int(m) * 60 + float(sec)
    except ValueError as e:
        raise MediaError("Could not read video") from e


def _sharpness(img: Image.Image) -> float:
    g = np.asarray(img.convert("L").resize((256, 256)), dtype=np.float32)
    lap = g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:] - 4 * g[1:-1, 1:-1]
    return float(lap.var())


def _diff(a: Image.Image, b: Image.Image) -> float:
    x = np.asarray(a.convert("L").resize((32, 32)), dtype=np.float32)
    y = np.asarray(b.convert("L").resize((32, 32)), dtype=np.float32)
    return float(np.abs(x - y).mean())


async def keyframes(data: bytes, max_frames: int = 6) -> list[dict]:
    """Return distinct, sharp frames as [{t: seconds, jpeg: bytes}]."""
    s = get_settings()
    if len(data) > s.max_video_bytes:
        raise MediaError("Video too large")
    if sniff(data) not in {"mp4", "webm"}:
        raise MediaError("Unsupported video type (use MP4 or WEBM)")
    with tempfile.TemporaryDirectory(prefix="saasta-") as tmp:
        src = os.path.join(tmp, "in.bin")
        with open(src, "wb") as f:
            f.write(data)
        dur = await _duration(src)
        if dur <= 0 or dur > s.max_video_seconds:
            raise MediaError(f"Video must be under {s.max_video_seconds} seconds")
        fps = min(2.0, 24 / max(dur, 1))  # at most ~24 candidate frames
        await _run(
            [FFMPEG, "-hide_banner", "-loglevel", "error", "-nostdin", "-i", src, "-an", "-sn", "-dn",
             "-vf", f"fps={fps:.3f},scale='min(960,iw)':-2", "-frames:v", "30",
             os.path.join(tmp, "f_%03d.jpg")],
            timeout=60,
        )
        frames = sorted(p for p in os.listdir(tmp) if p.startswith("f_"))
        candidates = []
        for i, name in enumerate(frames):
            img = Image.open(os.path.join(tmp, name)).convert("RGB")
            candidates.append({"t": round(i / fps, 1), "img": img, "score": _sharpness(img)})
    # Greedy: sharpest first, skip near-duplicates of already chosen frames.
    chosen: list[dict] = []
    for c in sorted(candidates, key=lambda c: -c["score"]):
        if all(_diff(c["img"], k["img"]) > 12 for k in chosen):
            chosen.append(c)
        if len(chosen) >= max_frames:
            break
    chosen.sort(key=lambda c: c["t"])
    out = []
    for c in chosen:
        buf = io.BytesIO()
        c["img"].save(buf, "JPEG", quality=90)
        jpeg, _ = clean_image(buf.getvalue())
        out.append({"t": c["t"], "jpeg": jpeg})
    if not out:
        raise MediaError("No usable frames found in video")
    return out

