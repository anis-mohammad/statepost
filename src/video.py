"""Turn a still photocard (PNG) into a short MP4 suitable for Facebook Reels.

Output spec (Reels-friendly):
  - H.264 / yuv420p video, 720x900, 30 fps
  - silent AAC audio track (Reels require an audio stream)
  - subtle slow zoom (Ken Burns) so the clip isn't a frozen frame

Requires `ffmpeg` on PATH.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

from PIL import Image

FPS = 30


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg not found on PATH. Install it (e.g. `brew install ffmpeg`).")
    return exe


def make_video(
    image_path: str,
    out_path: str,
    duration: float = 3.0,
    zoom: bool = False,
) -> str:
    """Render `image_path` into an MP4 at `out_path`."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(image_path)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    # Match the card's own dimensions (H.264 needs even width/height).
    with Image.open(image_path) as im:
        w, h = im.size
    w -= w % 2
    h -= h % 2

    total_frames = max(1, int(round(duration * FPS)))

    if zoom:
        # Slow zoom from 1.0 -> ~1.08 over the clip. Upscale first so the
        # zoompan source has enough pixels to avoid jitter/blur.
        end_zoom = 1.08
        vf = (
            f"scale={w*2}:{h*2},"
            f"zoompan=z='min(1+(on/{total_frames})*{end_zoom-1.0},{end_zoom})'"
            f":d={total_frames}:s={w}x{h}:fps={FPS},"
            f"format=yuv420p"
        )
    else:
        vf = f"scale={w}:{h},format=yuv420p"

    cmd = [
        _ffmpeg(), "-y",
        # video from the still image
        "-loop", "1", "-i", image_path,
        # silent stereo audio so the file has an audio track
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-t", f"{duration}",
        "-vf", vf,
        "-r", str(FPS),
        "-c:v", "libx264",
        "-preset", "medium",
        "-profile:v", "high",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        "-movflags", "+faststart",
        out_path,
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{proc.stderr[-2000:]}")
    return out_path


def encode_frames(frames, out_path: str, fps: int = FPS, duration: float | None = None) -> str:
    """Encode a list of PIL frames into a Reels-ready MP4 (+ silent AAC track)."""
    if not frames:
        raise ValueError("no frames to encode")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    dur = duration if duration is not None else len(frames) / fps

    with tempfile.TemporaryDirectory() as td:
        for i, fr in enumerate(frames):
            fr.save(os.path.join(td, f"{i:05d}.png"))
        cmd = [
            _ffmpeg(), "-y",
            "-framerate", str(fps),
            "-i", os.path.join(td, "%05d.png"),
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", f"{dur}",
            "-vf", "format=yuv420p",
            "-r", str(fps),
            "-c:v", "libx264",
            "-preset", "medium",
            "-profile:v", "high",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            "-movflags", "+faststart",
            out_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{proc.stderr[-2000:]}")
    return out_path


if __name__ == "__main__":
    import sys

    src = sys.argv[1] if len(sys.argv) > 1 else "output/demo_real.png"
    dst = sys.argv[2] if len(sys.argv) > 2 else "output/demo_real.mp4"
    print(make_video(src, dst))
