"""FFmpeg yardımcıları (imageio-ffmpeg ile gelen ffmpeg kullanılır, ayrıca kurulum gerekmez)."""
import subprocess

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

W, H, FPS = 1080, 1920, 30


def run(args: list[str]) -> None:
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *map(str, args)]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg hatası:\n{res.stderr.strip()}")


def duration(path) -> float:
    _, secs = imageio_ffmpeg.count_frames_and_secs(str(path))
    return float(secs)
