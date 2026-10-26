import os
import subprocess
import tempfile

import pytest

from app.media.video import FFMPEG, keyframes
from app.media.validate import MediaError


def _make_video(seconds: int) -> bytes:
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "v.mp4")
        subprocess.run([FFMPEG, "-loglevel", "error", "-f", "lavfi", "-i",
                        f"testsrc=duration={seconds}:size=320x240:rate=10", "-pix_fmt", "yuv420p", out],
                       check=True)
        return open(out, "rb").read()


async def test_keyframes_distinct_frames():
    frames = await keyframes(_make_video(4), max_frames=4)
    assert 1 <= len(frames) <= 4
    assert all(f["jpeg"][:3] == b"\xff\xd8\xff" for f in frames)


async def test_rejects_long_video(monkeypatch):
    from app.core import config
    monkeypatch.setattr(config.get_settings(), "max_video_seconds", 2)
    with pytest.raises(MediaError):
        await keyframes(_make_video(4))
