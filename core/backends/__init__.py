from typing import Callable

from core.backends.base import Backend
from core.backends.comfy import ComfyBackend
from core.backends.preview import PreviewBackend

# Arayüzde görünen ad -> motoru oluşturan fonksiyon (Kaggle adresini alır)
BACKENDS: dict[str, Callable[[str], Backend]] = {
    ComfyBackend.name: lambda url: ComfyBackend(url),
    PreviewBackend.name: lambda url: PreviewBackend(),
}
