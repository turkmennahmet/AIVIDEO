"""kaggle/ai_video_motor.ipynb dosyasını üretir.  Çalıştır: python kaggle/build_notebook.py"""
import json
from pathlib import Path

# patch_gguf.py'nin fonksiyonları (docstring ve __main__ hariç) notebook'a gömülür
_patch_src = Path(__file__).with_name("patch_gguf.py").read_text(encoding="utf-8")
PATCH_CODE = "# ComfyUI-GGUF uyumluluk yaması (bkz. kaggle/patch_gguf.py)\n" + \
    _patch_src.split('"""', 2)[2].split('if __name__')[0].strip() + "\n"

CELLS = [
("md", """# AI Video Motoru (Kaggle)
Bu notebook ComfyUI + Qwen-Image-Edit + Wan 2.2 modellerini kurar ve bilgisayarındaki
**AI Video Stüdyosu** programının bağlanacağı bir adres verir.

**Başlamadan önce (sağ panel → Settings):**
1. **Accelerator:** `GPU T4 x2`
2. **Internet:** açık (telefon doğrulaması gerekir)

Sonra üstten **Run All**. İlk kurulum ~10-15 dk sürer. En sonda çıkan
`https://....trycloudflare.com` adresini programdaki **Kaggle adresi** kutusuna yapıştır.
**Bu sekmeyi kapatma** — kapanırsa motor da kapanır."""),

("code", """# 1) Ayarlar ve kontrol
import os, shutil, subprocess
QUANT = "Q4_K_M"   # disk/RAM yetmezse "Q3_K_M" yap (biraz daha düşük kalite)
BASE = "/kaggle/tmp" if os.path.isdir("/kaggle/tmp") else "/tmp"
COMFY = f"{BASE}/ComfyUI"
MODELS = f"{BASE}/models"
os.makedirs(MODELS, exist_ok=True)

print(subprocess.run("nvidia-smi --query-gpu=name,memory.total --format=csv", shell=True, capture_output=True, text=True).stdout)
free_gb = shutil.disk_usage(BASE).free / 1e9
print(f"Boş disk ({BASE}): {free_gb:.0f} GB")
if free_gb < 58 and QUANT == "Q4_K_M":
    print("UYARI: disk az olabilir. Kurulum hata verirse QUANT = 'Q3_K_M' yapıp tekrar çalıştır.")"""),

("code", """# 2) ComfyUI kurulumu (torch Kaggle'da hazır, yeniden kurulmaz)
if not os.path.isdir(COMFY):
    subprocess.run(f"git clone -q --depth 1 https://github.com/comfyanonymous/ComfyUI {COMFY}", shell=True, check=True)
    subprocess.run(f"git clone -q --depth 1 https://github.com/city96/ComfyUI-GGUF {COMFY}/custom_nodes/ComfyUI-GGUF", shell=True, check=True)
import re as _re
reqs = [l for l in open(f"{COMFY}/requirements.txt").read().splitlines()
        if l.strip() and not l.startswith("#")
        and _re.split(r"[<>=!~\\[ ;]", l.strip())[0] not in ("torch", "torchvision", "torchaudio")]
open("/tmp/reqs.txt", "w").write("\\n".join(reqs + ["gguf>=0.13", "huggingface_hub[hf_xet]>=0.34"]))
r = subprocess.run("pip install -q -r /tmp/reqs.txt", shell=True, capture_output=True, text=True)
print(r.stdout[-2000:], r.stderr[-2000:])
""" + PATCH_CODE + """
print("GGUF:", patch(f"{COMFY}/custom_nodes/ComfyUI-GGUF"))
print("ComfyUI hazır")"""),

("code", """# 3) Modelleri indir (~52 GB, birkaç dakika)
from concurrent.futures import ThreadPoolExecutor
from huggingface_hub import hf_hub_download

# İsteğe bağlı: Kaggle Secrets'a HF_TOKEN eklersen indirme daha hızlı olur (Add-ons → Secrets)
try:
    from kaggle_secrets import UserSecretsClient
    os.environ["HF_TOKEN"] = UserSecretsClient().get_secret("HF_TOKEN")
    print("HF_TOKEN kullanılıyor")
except Exception:
    print("HF_TOKEN yok, hesapsız indiriliyor (daha yavaş olabilir)")

FILES = [  # (repo, dosya, ComfyUI klasörü)
    ("QuantStack/Wan2.2-I2V-A14B-GGUF", f"HighNoise/Wan2.2-I2V-A14B-HighNoise-{QUANT}.gguf", "unet"),
    ("QuantStack/Wan2.2-I2V-A14B-GGUF", f"LowNoise/Wan2.2-I2V-A14B-LowNoise-{QUANT}.gguf", "unet"),
    ("QuantStack/Qwen-Image-Edit-2509-GGUF", f"Qwen-Image-Edit-2509-{QUANT}.gguf", "unet"),
    ("Comfy-Org/Wan_2.1_ComfyUI_repackaged", "split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors", "text_encoders"),
    ("Comfy-Org/Wan_2.1_ComfyUI_repackaged", "split_files/vae/wan_2.1_vae.safetensors", "vae"),
    ("Comfy-Org/Wan_2.2_ComfyUI_Repackaged", "split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors", "loras"),
    ("Comfy-Org/Wan_2.2_ComfyUI_Repackaged", "split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors", "loras"),
    ("Comfy-Org/Qwen-Image_ComfyUI", "split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors", "text_encoders"),
    ("Comfy-Org/Qwen-Image_ComfyUI", "split_files/vae/qwen_image_vae.safetensors", "vae"),
    ("lightx2v/Qwen-Image-Lightning", "Qwen-Image-Edit-2509/Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors", "loras"),
]

def get(item):
    repo, fname, folder = item
    path = hf_hub_download(repo, fname, local_dir=MODELS)
    dst_dir = f"{COMFY}/models/{folder}"
    os.makedirs(dst_dir, exist_ok=True)
    dst = f"{dst_dir}/{os.path.basename(fname)}"
    if not os.path.exists(dst):
        os.symlink(path, dst)
    return os.path.basename(fname)

with ThreadPoolExecutor(4) as ex:
    for name in ex.map(get, FILES):
        print("✓", name)
print(f"Kalan disk: {shutil.disk_usage(BASE).free/1e9:.0f} GB")"""),

("code", """# 4) ComfyUI'yi başlat
import time, urllib.request
log = open(f"{BASE}/comfy.log", "w")
comfy = subprocess.Popen(
    ["python", "main.py", "--listen", "127.0.0.1", "--port", "8188", "--preview-method", "none"],
    cwd=COMFY, stdout=log, stderr=subprocess.STDOUT, env={**os.environ, "CUDA_VISIBLE_DEVICES": "0"},
    start_new_session=True)  # hücre durdurulunca ComfyUI kapanmasın
for _ in range(180):
    try:
        urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=2); break
    except Exception:
        if comfy.poll() is not None:
            raise RuntimeError(open(f"{BASE}/comfy.log").read()[-3000:])
        time.sleep(2)
print("ComfyUI çalışıyor")"""),

("code", """# 5) Dışarıya adres aç (Cloudflare tüneli, hesap gerekmez)
import re
CF = f"{BASE}/cloudflared"
if not os.path.exists(CF):
    subprocess.run(f"wget -q -O {CF} https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 && chmod +x {CF}", shell=True, check=True)
cf_log = f"{BASE}/cf.log"

def start_tunnel():
    global tunnel
    try:
        tunnel.kill()
    except NameError:
        pass
    tunnel = subprocess.Popen([CF, "tunnel", "--no-autoupdate", "--url", "http://127.0.0.1:8188"],
                              stdout=open(cf_log, "w"), stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(60):
        m = re.search(r"https://[a-z0-9-]+\\.trycloudflare\\.com", open(cf_log).read())
        if m:
            return m.group(0)
        time.sleep(1)

def tunnel_ok(url):
    try:
        return urllib.request.urlopen(f"{url}/system_stats", timeout=15).status == 200
    except Exception:
        return False

URL = start_tunnel()
print("=" * 60)
print("PROGRAMA YAPIŞTIRILACAK ADRES:")
print(URL)
print("=" * 60)"""),

("code", """# 6) Motoru açık tut — bu hücre çalışmaya devam etmeli. Sekmeyi kapatma.
#    (Bu hücreyi durdurmak motoru kapatmaz; tekrar çalıştırarak izlemeye devam edebilirsin.)
from IPython.display import clear_output
fails = 0
while True:
    if comfy.poll() is not None:
        print("ComfyUI kapandı! Log:"); print(open(f"{BASE}/comfy.log").read()[-3000:]); break
    # tünel koptuysa (2 kontrol üst üste başarısız) yeniden aç
    fails = 0 if tunnel_ok(URL) else fails + 1
    if fails >= 2:
        URL, fails = start_tunnel(), 0
        print("!!! Tünel koptu, yeniden açıldı. YENİ ADRESİ programa yapıştır:", URL)
        time.sleep(20)
    clear_output(wait=True)
    print("ADRES:", URL, "  <- bu adres değişirse programa yeniden yapıştır")
    print(time.strftime("%H:%M:%S"), "— motor çalışıyor. Son log satırları:")
    print("".join(open(f"{BASE}/comfy.log").readlines()[-15:]))
    time.sleep(30)"""),
]


def cell(kind, src):
    lines = src.splitlines(keepends=True)
    if kind == "md":
        return {"cell_type": "markdown", "metadata": {}, "source": lines}
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": lines}


nb = {
    "nbformat": 4, "nbformat_minor": 5,
    "metadata": {
        "kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
        "language_info": {"name": "python"},
        "kaggle": {"accelerator": "nvidiaTeslaT4", "isInternetEnabled": True, "isGpuEnabled": True},
    },
    "cells": [cell(k, s) for k, s in CELLS],
}
out = Path(__file__).with_name("ai_video_motor.ipynb")
out.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print("yazıldı:", out)
