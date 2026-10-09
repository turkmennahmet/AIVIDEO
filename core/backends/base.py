"""Video üretim motorlarının ortak arayüzü.

Her motor iki iş yapar:
  1. make_keyframe: fotoğraflar + sahne promptu -> sahnenin ilk karesi (PNG)
  2. animate:       ilk kare + hareket promptu  -> kısa klip (MP4)

Önizleme motoru bunları yapay zekâ olmadan yapar; Kaggle / fal.ai motorları
aynı arayüzü uygulayarak gerçek AI üretimi yapacak.
"""
from abc import ABC, abstractmethod
from pathlib import Path

from core.templates import Scene


class Backend(ABC):
    name: str = "base"

    def before_keyframes(self) -> None:
        """Tüm ilk kareler üretilmeden önce bir kez çağrılır (bağlantı kontrolü vb.)."""

    def before_animation(self) -> None:
        """Kareler bitip canlandırmaya geçmeden önce bir kez çağrılır (bellek boşaltma vb.)."""

    @abstractmethod
    def make_keyframe(self, photos: dict[str, Path], scene: Scene, out_path: Path) -> Path:
        """photos: {'kisi1': yol, 'kisi2': yol}"""

    @abstractmethod
    def animate(self, image: Path, scene: Scene, out_path: Path) -> Path:
        ...
