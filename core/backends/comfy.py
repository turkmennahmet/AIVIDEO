"""ComfyUI motoru: Kaggle'da (veya herhangi bir sunucuda) çalışan ComfyUI'ye bağlanır.

- İlk kare: Qwen-Image-Edit-2509 (+4 adım Lightning LoRA) — yüklenen yüzleri koruyarak sahneyi çizer.
- Canlandırma: Wan 2.2 I2V 14B (+4 adım lightx2v LoRA) — kareyi kısa videoya çevirir.

Model dosya adları kaggle/build_notebook.py'deki indirme listesiyle aynı olmalı.
"""
import math
import random
import time
import uuid
from pathlib import Path

import httpx
from PIL import Image, ImageOps

from core.backends.base import Backend
from core.templates import Scene

QUANT = "Q4_K_M"

QWEN = {
    "unet": f"Qwen-Image-Edit-2509-{QUANT}.gguf",
    "lora": "Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors",
    "clip": "qwen_2.5_vl_7b_fp8_scaled.safetensors",
    "vae": "qwen_image_vae.safetensors",
    "width": 720, "height": 1280,
}
WAN = {
    "high": f"Wan2.2-I2V-A14B-HighNoise-{QUANT}.gguf",
    "low": f"Wan2.2-I2V-A14B-LowNoise-{QUANT}.gguf",
    "lora_high": "wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors",
    "lora_low": "wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors",
    "clip": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
    "vae": "wan_2.1_vae.safetensors",
    "width": 480, "height": 848, "fps": 16,
}

IDENTITY_ONE = ("Keep the exact face, identity, age features and hairstyle of the person in image 1. "
                "The face is clearly visible and well lit, never in silhouette or shadow. "
                "Photorealistic, vertical 9:16 frame. ")
IDENTITY_TWO = ("The person from image 1 and the person from image 2 together in one scene; keep both "
                "exact faces and identities. Both faces are clearly visible and well lit. "
                "Photorealistic, vertical 9:16 frame. ")
WAN_NEGATIVE = ("static, frozen, blurry, low quality, distorted face, deformed hands, extra limbs, "
                "watermark, text, subtitles, morphing identity")


class ComfyError(RuntimeError):
    pass


class ComfyBackend(Backend):
    name = "Kaggle (AI)"

    def __init__(self, url: str, timeout_per_job: float = 1800):
        if not url:
            raise ComfyError("Kaggle adresi boş. Notebook'un verdiği https://...trycloudflare.com adresini gir.")
        self.url = url.strip().rstrip("/")
        self.timeout_per_job = timeout_per_job
        self.client = httpx.Client(base_url=self.url, timeout=120, follow_redirects=True)
        self.client_id = uuid.uuid4().hex
        self._uploaded: dict[Path, str] = {}

    # ---- ComfyUI API ----------------------------------------------------
    def check(self) -> None:
        try:
            self.client.get("/system_stats").raise_for_status()
        except Exception as e:  # noqa: BLE001
            raise ComfyError(f"Kaggle motoruna bağlanılamadı ({self.url}). Notebook açık mı, adres doğru mu?\n{e}")

    def free_memory(self) -> None:
        self.client.post("/free", json={"unload_models": True, "free_memory": True})

    def _upload(self, path: Path) -> str:
        if path in self._uploaded:
            return self._uploaded[path]
        # büyük telefon fotoğraflarını küçült (hem hızlı yükleme hem de model zaten ~1MP kullanıyor)
        img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        img.thumbnail((1536, 1536), Image.LANCZOS)
        small = path.with_name(path.stem + "_yukle.jpg")
        img.save(small, quality=95)
        with small.open("rb") as f:
            r = self.client.post("/upload/image", files={"image": (f"{uuid.uuid4().hex}.jpg", f, "image/jpeg")},
                                 data={"overwrite": "true"})
        r.raise_for_status()
        d = r.json()
        name = f"{d['subfolder']}/{d['name']}" if d.get("subfolder") else d["name"]
        self._uploaded[path] = name
        return name

    def _run(self, workflow: dict) -> list[dict]:
        r = self.client.post("/prompt", json={"prompt": workflow, "client_id": self.client_id})
        if r.status_code != 200:
            raise ComfyError(f"ComfyUI iş kabul etmedi:\n{r.text[:2000]}")
        prompt_id = r.json()["prompt_id"]

        start = time.time()
        while time.time() - start < self.timeout_per_job:
            time.sleep(3)
            try:
                h = self.client.get(f"/history/{prompt_id}").json()
            except httpx.HTTPError:
                continue  # tünelde anlık kopma olabilir
            if prompt_id not in h:
                continue
            entry = h[prompt_id]
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                msgs = [m[1] for m in status.get("messages", []) if m[0] == "execution_error"]
                detail = msgs[0].get("exception_message", "") if msgs else str(status)
                raise ComfyError(f"ComfyUI hatası: {detail}")
            if status.get("completed"):
                files = []
                for out in entry.get("outputs", {}).values():
                    for items in out.values():
                        if isinstance(items, list):
                            files += [i for i in items if isinstance(i, dict) and "filename" in i]
                if not files:
                    raise ComfyError("ComfyUI iş bitti ama çıktı dosyası yok.")
                return files
        raise ComfyError("ComfyUI işi zaman aşımına uğradı.")

    def _download(self, info: dict, out_path: Path) -> Path:
        r = self.client.get("/view", params={"filename": info["filename"], "subfolder": info.get("subfolder", ""),
                                             "type": info.get("type", "output")}, timeout=600)
        r.raise_for_status()
        out_path.write_bytes(r.content)
        return out_path

    # ---- Backend arayüzü ------------------------------------------------
    def before_keyframes(self) -> None:
        self.check()

    def before_animation(self) -> None:
        self.free_memory()  # Qwen modellerini boşalt, Wan'a yer aç

    def make_keyframe(self, photos: dict[str, Path], scene: Scene, out_path: Path) -> Path:
        if scene.kisi == "ikisi":
            images = [self._upload(photos["kisi1"]), self._upload(photos["kisi2"])]
            prompt = IDENTITY_TWO + scene.gorsel
        else:
            images = [self._upload(photos[scene.kisi])]
            prompt = IDENTITY_ONE + scene.gorsel
        files = self._run(qwen_edit_workflow(images, prompt, random.randint(0, 2**31)))
        return self._download(files[0], out_path)

    def animate(self, image: Path, scene: Scene, out_path: Path) -> Path:
        name = self._upload(image)
        # Wan kare sayısı 4n+1 olmalı
        frames = 4 * math.ceil(scene.sure * WAN["fps"] / 4) + 1
        files = self._run(wan_i2v_workflow(name, scene.hareket, frames, random.randint(0, 2**31)))
        video = next((f for f in files if f["filename"].lower().endswith((".mp4", ".webm", ".mov"))), files[0])
        return self._download(video, out_path)


# ---- Workflow'lar (ComfyUI API formatı) -----------------------------------

def qwen_edit_workflow(images: list[str], prompt: str, seed: int) -> dict:
    wf = {
        "unet": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": QWEN["unet"]}},
        "lora": {"class_type": "LoraLoaderModelOnly",
                 "inputs": {"model": ["unet", 0], "lora_name": QWEN["lora"], "strength_model": 1.0}},
        "shift": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["lora", 0], "shift": 3.0}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": QWEN["clip"], "type": "qwen_image"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": QWEN["vae"]}},
        "pos": {"class_type": "TextEncodeQwenImageEditPlus",
                "inputs": {"clip": ["clip", 0], "vae": ["vae", 0], "prompt": prompt}},
        "neg": {"class_type": "TextEncodeQwenImageEditPlus",
                "inputs": {"clip": ["clip", 0], "vae": ["vae", 0], "prompt": ""}},
        "latent": {"class_type": "EmptySD3LatentImage",
                   "inputs": {"width": QWEN["width"], "height": QWEN["height"], "batch_size": 1}},
        "sample": {"class_type": "KSampler", "inputs": {
            "model": ["shift", 0], "positive": ["pos", 0], "negative": ["neg", 0], "latent_image": ["latent", 0],
            "seed": seed, "steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["sample", 0], "vae": ["vae", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["decode", 0], "filename_prefix": "aivideo/kare"}},
    }
    for i, name in enumerate(images, 1):
        wf[f"img{i}"] = {"class_type": "LoadImage", "inputs": {"image": name}}
        wf["pos"]["inputs"][f"image{i}"] = [f"img{i}", 0]
    return wf


def wan_i2v_workflow(image: str, prompt: str, frames: int, seed: int) -> dict:
    steps, switch = 4, 2
    return {
        "high": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": WAN["high"]}},
        "low": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": WAN["low"]}},
        "lora_h": {"class_type": "LoraLoaderModelOnly",
                   "inputs": {"model": ["high", 0], "lora_name": WAN["lora_high"], "strength_model": 1.0}},
        "lora_l": {"class_type": "LoraLoaderModelOnly",
                   "inputs": {"model": ["low", 0], "lora_name": WAN["lora_low"], "strength_model": 1.0}},
        "shift_h": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["lora_h", 0], "shift": 5.0}},
        "shift_l": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["lora_l", 0], "shift": 5.0}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": WAN["clip"], "type": "wan"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": WAN["vae"]}},
        "pos": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["clip", 0], "text": prompt}},
        "neg": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["clip", 0], "text": WAN_NEGATIVE}},
        "img": {"class_type": "LoadImage", "inputs": {"image": image}},
        "i2v": {"class_type": "WanImageToVideo", "inputs": {
            "positive": ["pos", 0], "negative": ["neg", 0], "vae": ["vae", 0], "start_image": ["img", 0],
            "width": WAN["width"], "height": WAN["height"], "length": frames, "batch_size": 1}},
        "s_high": {"class_type": "KSamplerAdvanced", "inputs": {
            "model": ["shift_h", 0], "positive": ["i2v", 0], "negative": ["i2v", 1], "latent_image": ["i2v", 2],
            "add_noise": "enable", "noise_seed": seed, "steps": steps, "cfg": 1.0,
            "sampler_name": "euler", "scheduler": "simple",
            "start_at_step": 0, "end_at_step": switch, "return_with_leftover_noise": "enable"}},
        "s_low": {"class_type": "KSamplerAdvanced", "inputs": {
            "model": ["shift_l", 0], "positive": ["i2v", 0], "negative": ["i2v", 1], "latent_image": ["s_high", 0],
            "add_noise": "disable", "noise_seed": seed, "steps": steps, "cfg": 1.0,
            "sampler_name": "euler", "scheduler": "simple",
            "start_at_step": switch, "end_at_step": 10000, "return_with_leftover_noise": "disable"}},
        "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["s_low", 0], "vae": ["vae", 0]}},
        "video": {"class_type": "CreateVideo", "inputs": {"images": ["decode", 0], "fps": float(WAN["fps"])}},
        "save": {"class_type": "SaveVideo", "inputs": {
            "video": ["video", 0], "filename_prefix": "aivideo/klip", "format": "mp4", "codec": "h264"}},
    }
