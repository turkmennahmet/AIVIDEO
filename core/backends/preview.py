"""Önizleme motoru: yapay zekâ kullanmaz, tamamen ücretsiz ve yereldir.

- İlk kare: fotoğraf(lar) dikey 1080x1920 kadraja yerleştirilir (arka plan bulanık).
- Canlandırma: yavaş yakınlaşma / kaydırma (Ken Burns efekti).

Şablonları ve montajı GPU'suz test etmek için kullanılır.
"""
import hashlib
import subprocess
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from core.backends.base import Backend
from core.ffmpeg import FFMPEG, FPS, H, W
from core.templates import Scene


def _open(path: Path) -> Image.Image:
    return ImageOps.exif_transpose(Image.open(path)).convert("RGB")


def _cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(img, size, Image.LANCZOS, centering=(0.5, 0.4))


def _framed(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Fotoğrafı kırpmadan sığdırır, boşlukları bulanık kopyasıyla doldurur."""
    bg = _cover(img, size).filter(ImageFilter.GaussianBlur(40))
    bg = ImageEnhance.Brightness(bg).enhance(0.55)
    fg = ImageOps.contain(img, size, Image.LANCZOS)
    bg.paste(fg, ((size[0] - fg.width) // 2, (size[1] - fg.height) // 2))
    return bg


class PreviewBackend(Backend):
    name = "Önizleme (ücretsiz, AI yok)"

    def make_keyframe(self, photos: dict[str, Path], scene: Scene, out_path: Path) -> Path:
        if scene.kisi == "ikisi":
            half = (W, H // 2)
            canvas = Image.new("RGB", (W, H))
            canvas.paste(_cover(_open(photos["kisi1"]), half), (0, 0))
            canvas.paste(_cover(_open(photos["kisi2"]), half), (0, H // 2))
        else:
            canvas = _framed(_open(photos[scene.kisi]), (W, H))
        canvas.save(out_path)
        return out_path

    def animate(self, image: Path, scene: Scene, out_path: Path) -> Path:
        img = _open(image)
        if img.size != (W, H):
            img = _cover(img, (W, H))

        # Her sahneye promptuna göre sabit ama farklı bir hareket ver
        h = int(hashlib.md5(scene.hareket.encode("utf-8")).hexdigest(), 16)
        zoom_in = h % 2 == 0
        pan_x = ((h >> 1) % 3 - 1) * 0.04   # -0.04, 0, +0.04
        pan_y = ((h >> 3) % 3 - 1) * 0.03
        max_zoom = 1.15

        n = max(1, round(scene.sure * FPS))
        proc = subprocess.Popen(
            [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
             str(out_path)],
            stdin=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        try:
            for i in range(n):
                t = i / max(1, n - 1)
                t = t * t * (3 - 2 * t)  # yumuşak başla / bitir
                p = t if zoom_in else 1 - t
                z = 1 + (max_zoom - 1) * p
                cw, ch = W / z, H / z
                cx = W / 2 + pan_x * W * p
                cy = H / 2 + pan_y * H * p
                x0 = min(max(cx - cw / 2, 0), W - cw)
                y0 = min(max(cy - ch / 2, 0), H - ch)
                frame = img.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))
                proc.stdin.write(frame.tobytes())
            proc.stdin.close()
            err = proc.stderr.read().decode("utf-8", "replace")
        finally:
            proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg hatası:\n{err}")
        return out_path
