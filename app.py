"""AI Video Stüdyosu — yerel arayüz.

Çalıştırma: calistir.bat  (veya: .venv\\Scripts\\python app.py)
"""
import json
import queue
import threading
import time
from pathlib import Path

import gradio as gr

from core.backends import BACKENDS
from core.pipeline import OUTPUT_DIR, generate
from core.templates import ROOT, list_templates

SETTINGS = ROOT / "ayarlar.json"


def _load_settings() -> dict:
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _save_settings(**kw) -> None:
    SETTINGS.write_text(json.dumps({**_load_settings(), **kw}, ensure_ascii=False, indent=2), encoding="utf-8")


def _template_info(name: str) -> str:
    t = list_templates().get(name)
    if not t:
        return ""
    muzik = t.muzik.name if t.muzik else "yok (sessiz)"
    rows = "\n".join(
        f"{i}. **{s.kisi}** · {s.sure:g} sn{' · “' + s.yazi + '”' if s.yazi else ''}"
        for i, s in enumerate(t.sahneler, 1)
    )
    return f"{t.aciklama}\n\n**Süre:** ~{t.toplam_sure:.1f} sn · **Müzik:** {muzik}\n\n{rows}"


def run(photo1, photo2, template_name, backend_name, url):
    if not photo1 or not photo2:
        raise gr.Error("İki fotoğrafı da yükle.")
    templates = list_templates()
    if template_name not in templates:
        raise gr.Error("Şablon bulunamadı.")
    if url:
        _save_settings(kaggle_url=url.strip())
    try:
        backend = BACKENDS[backend_name](url)
    except Exception as e:  # noqa: BLE001
        raise gr.Error(str(e))

    # Üretimi ayrı thread'de çalıştır, ilerlemeyi ve kareleri canlı göster
    events: queue.Queue = queue.Queue()
    result: dict = {}
    t0 = time.time()

    def work():
        try:
            result["out"] = generate(
                {"kisi1": Path(photo1), "kisi2": Path(photo2)},
                templates[template_name], backend,
                progress=lambda p, msg: events.put(("progress", (p, msg))),
                on_keyframes=lambda ks: events.put(("keyframes", [str(k) for k in ks])),
            )
        except Exception as e:  # noqa: BLE001
            result["error"] = e
        finally:
            events.put(("done", None))

    threading.Thread(target=work, daemon=True).start()
    gallery: list[str] = []
    while True:
        kind, data = events.get()
        if kind == "keyframes":
            gallery = data
            yield gr.skip(), gallery, gr.skip()
        elif kind == "progress":
            p, msg = data
            mins = (time.time() - t0) / 60
            yield gr.skip(), gr.skip(), f"**%{p * 100:.0f}** — {msg}  \n_geçen süre: {mins:.1f} dk_"
        else:
            break

    if "error" in result:
        raise gr.Error(f"Hata: {result['error']}")
    out = result["out"]
    yield str(out), gallery, f"Bitti ({(time.time() - t0) / 60:.1f} dk). Kaydedildi: `{out}`"


def build_ui() -> gr.Blocks:
    templates = list(list_templates())
    backends = list(BACKENDS)
    saved_url = _load_settings().get("kaggle_url", "")

    with gr.Blocks(title="AI Video Stüdyosu") as ui:
        gr.Markdown("# AI Video Stüdyosu\nİki fotoğraf yükle, bir şablon seç, videonu üret.")
        with gr.Row():
            with gr.Column():
                with gr.Row():
                    p1 = gr.Image(label="Kişi 1", type="filepath", height=300)
                    p2 = gr.Image(label="Kişi 2", type="filepath", height=300)
                tpl = gr.Dropdown(templates, value=templates[0] if templates else None, label="Şablon")
                info = gr.Markdown(_template_info(templates[0]) if templates else "templates/ klasöründe şablon yok.")
                be = gr.Dropdown(backends, value=backends[0], label="Motor")
                url = gr.Textbox(saved_url, label="Kaggle adresi",
                                 placeholder="https://....trycloudflare.com  (Kaggle notebook'unun verdiği adres)")
                btn = gr.Button("Video Üret", variant="primary")
            with gr.Column():
                status = gr.Markdown()
                video = gr.Video(label="Sonuç", height=640)
                frames = gr.Gallery(label="Sahne kareleri", columns=4, height=260)

        tpl.change(_template_info, tpl, info)
        be.change(lambda b: gr.update(visible=b == "Kaggle (AI)"), be, url)
        btn.click(run, [p1, p2, tpl, be, url], [video, frames, status])
    return ui


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(exist_ok=True)
    build_ui().launch(inbrowser=True, allowed_paths=[str(OUTPUT_DIR)])
