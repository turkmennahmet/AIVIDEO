"""Şablon (senaryo) dosyalarını okur."""
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT / "templates"
MUSIC_DIR = ROOT / "music"

VALID_PEOPLE = {"kisi1", "kisi2", "ikisi"}

# şablonda yazılan geçiş adı -> ffmpeg xfade türü
TRANSITIONS = {
    "yumusak": "fade",
    "beyaz": "fadewhite",   # flaş: geçmişe dönüş anı
    "siyah": "fadeblack",
}


@dataclass
class Scene:
    kisi: str            # kisi1 | kisi2 | ikisi
    gorsel: str          # ilk kareyi üretecek prompt
    hareket: str         # kareyi canlandıracak prompt
    sure: float = 3.0    # saniye
    yazi: str = ""       # ekranda gösterilecek yazı (isteğe bağlı)
    sonraki_gecis: str = "fade"  # bu sahneden sonrakine geçiş (xfade türü)


@dataclass
class Template:
    ad: str
    dosya: Path
    sahneler: list[Scene]
    muzik: Path | None = None
    gecis: float = 0.4   # sahneler arası geçiş süresi (sn)
    aciklama: str = ""

    @property
    def toplam_sure(self) -> float:
        return sum(s.sure for s in self.sahneler) - self.gecis * (len(self.sahneler) - 1)


def load_template(path: Path) -> Template:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    sahneler = []
    for i, s in enumerate(data.get("sahneler") or [], 1):
        kisi = s.get("kisi", "ikisi")
        if kisi not in VALID_PEOPLE:
            raise ValueError(f"{path.name}: {i}. sahnede 'kisi' {sorted(VALID_PEOPLE)} olmalı, '{kisi}' yazılmış")
        gecis = s.get("sonraki_gecis", "yumusak")
        if gecis not in TRANSITIONS:
            raise ValueError(f"{path.name}: {i}. sahnede 'sonraki_gecis' {sorted(TRANSITIONS)} olmalı, '{gecis}' yazılmış")
        sahneler.append(Scene(
            sonraki_gecis=TRANSITIONS[gecis],
            kisi=kisi,
            gorsel=s.get("gorsel", ""),
            hareket=s.get("hareket", ""),
            sure=float(s.get("sure", 3)),
            yazi=s.get("yazi", "") or "",
        ))
    if not sahneler:
        raise ValueError(f"{path.name}: hiç sahne yok")

    muzik = None
    if data.get("muzik"):
        muzik = MUSIC_DIR / data["muzik"]
        if not muzik.exists():
            muzik = None  # müzik yoksa sessiz devam et

    return Template(
        ad=data.get("ad", path.stem),
        dosya=path,
        sahneler=sahneler,
        muzik=muzik,
        gecis=float(data.get("gecis", 0.4)),
        aciklama=data.get("aciklama", ""),
    )


def list_templates() -> dict[str, Template]:
    """Şablon adı -> Template. Hatalı dosyalar atlanır."""
    out = {}
    for p in sorted(TEMPLATES_DIR.glob("*.yaml")):
        try:
            t = load_template(p)
            out[t.ad] = t
        except Exception as e:  # noqa: BLE001
            print(f"[uyarı] şablon okunamadı: {p.name}: {e}")
    return out
