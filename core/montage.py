"""Klipleri tek videoda birleştirir: boyut eşitleme, yazı, geçiş, müzik."""
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from core.ffmpeg import FPS, H, W, run
from core.templates import Template

FONT_CANDIDATES = [
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for f in FONT_CANDIDATES:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default(size)


def render_caption(text: str, out_path: Path) -> Path:
    """Şeffaf arka planlı, kenarlıklı beyaz yazı (ekranın alt-orta bölümünde)."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _font(72)
    lines = textwrap.wrap(text, width=22)
    line_h = 90
    y = int(H * 0.68) - line_h * len(lines) // 2
    for line in lines:
        draw.text((W // 2, y), line, font=font, fill="white", anchor="mt",
                  stroke_width=6, stroke_fill="black")
        y += line_h
    img.save(out_path)
    return out_path


def normalize_clip(src: Path, seconds: float, out_path: Path, caption: Path | None) -> Path:
    """Her klibi 1080x1920, 30fps ve tam istenen süreye getirir (AI klipleri farklı boyutta gelebilir)."""
    vf = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
          f"fps={FPS},setsar=1,tpad=stop_mode=clone:stop_duration={seconds},"
          f"trim=duration={seconds},setpts=PTS-STARTPTS")
    args = ["-i", src]
    if caption:
        args += ["-loop", "1", "-i", caption]
        vf += "[base];[base][1:v]overlay=0:0:shortest=1"
    vf += "[v]"
    run([*args, "-filter_complex", vf, "-map", "[v]", "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
         "-t", seconds, out_path])
    return out_path


def assemble(template: Template, clips: list[Path], work_dir: Path, out_path: Path) -> Path:
    scenes = template.sahneler
    norm = []
    for i, (scene, clip) in enumerate(zip(scenes, clips), 1):
        cap = render_caption(scene.yazi, work_dir / f"yazi_{i}.png") if scene.yazi else None
        norm.append(normalize_clip(clip, scene.sure, work_dir / f"norm_{i}.mp4", cap))

    T = template.gecis
    total = template.toplam_sure
    inputs: list = []
    for p in norm:
        inputs += ["-i", p]

    # xfade zinciri
    if len(norm) == 1:
        fc = "[0:v]null[vout]"
    else:
        parts, prev, elapsed = [], "0:v", 0.0
        for k in range(1, len(norm)):
            elapsed += scenes[k - 1].sure
            offset = elapsed - k * T
            label = "vout" if k == len(norm) - 1 else f"x{k}"
            parts.append(f"[{prev}][{k}:v]xfade=transition={scenes[k - 1].sonraki_gecis}:duration={T}:offset={offset:.3f}[{label}]")
            prev = label
        fc = ";".join(parts)

    # ses: müzik varsa döngüle + sonda kıs, yoksa sessiz iz
    a_idx = len(norm)
    if template.muzik:
        inputs += ["-stream_loop", "-1", "-i", template.muzik]
        fade_start = max(0.0, total - 1.5)
        fc += f";[{a_idx}:a]atrim=duration={total:.3f},afade=t=out:st={fade_start:.3f}:d=1.5[aout]"
    else:
        inputs += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        fc += f";[{a_idx}:a]atrim=duration={total:.3f}[aout]"

    run([*inputs, "-filter_complex", fc, "-map", "[vout]", "-map", "[aout]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
         "-t", f"{total:.3f}", out_path])
    return out_path
