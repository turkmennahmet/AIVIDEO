"""Uçtan uca akış: fotoğraflar + şablon -> sahne kareleri -> klipler -> montaj."""
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable

from core.backends.base import Backend
from core.montage import assemble
from core.templates import ROOT, Template

OUTPUT_DIR = ROOT / "output"

ProgressFn = Callable[[float, str], None]


def generate(photos: dict[str, Path], template: Template, backend: Backend,
             progress: ProgressFn = lambda p, m: print(f"[{p:4.0%}] {m}"),
             on_keyframes: Callable[[list[Path]], None] = lambda ks: None) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = OUTPUT_DIR / f"{stamp}_is"
    work.mkdir(parents=True, exist_ok=True)

    # yüklenen fotoğrafları iş klasörüne kopyala (Gradio geçici dosyaları silebilir)
    local = {}
    for key, p in photos.items():
        dst = work / f"{key}{Path(p).suffix.lower() or '.jpg'}"
        shutil.copy(p, dst)
        local[key] = dst

    # Önce tüm kareler, sonra tüm klipler: AI motorunda her model yalnızca bir kez yüklenir.
    n = len(template.sahneler)
    steps = n * 2 + 1
    backend.before_keyframes()
    keyframes = []
    for i, scene in enumerate(template.sahneler, 1):
        progress((i - 1) / steps, f"Sahne {i}/{n}: ilk kare hazırlanıyor")
        keyframes.append(backend.make_keyframe(local, scene, work / f"kare_{i}.png"))
        on_keyframes(keyframes)

    backend.before_animation()
    clips = []
    for i, (scene, key) in enumerate(zip(template.sahneler, keyframes), 1):
        progress((n + i - 1) / steps, f"Sahne {i}/{n}: canlandırılıyor")
        clips.append(backend.animate(key, scene, work / f"klip_{i}.mp4"))

    progress((steps - 1) / steps, "Montaj: geçişler, yazılar, müzik")
    out = OUTPUT_DIR / f"{stamp}_{template.dosya.stem}.mp4"
    assemble(template, clips, work, out)
    progress(1.0, "Bitti")
    return out
