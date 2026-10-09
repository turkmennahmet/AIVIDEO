# AI Video Stüdyosu

İki fotoğraftan, hazır bir senaryoya göre ~15 saniyelik dikey (1080x1920) yapay zekâ hikâye videosu üreten, **tamamen ücretsiz** bir araç.

Arayüz kendi bilgisayarında çalışır. Ağır AI işini ise Kaggle'ın ücretsiz T4 GPU'sunda çalışan ComfyUI yapar. Ücretli API kullanılmaz.

## Nasıl çalışır?

```
Fotoğraflar + şablon (YAML)
        │
        ▼
1. Sahne kareleri   → Qwen-Image-Edit-2509 (GGUF Q4)
2. Canlandırma      → Wan 2.2 I2V 14B (GGUF Q4) + lightx2v 4 adım
3. Montaj           → FFmpeg: geçişler, yazılar, müzik
        │
        ▼
output/<tarih>_<şablon>.mp4
```

Yerel uygulama (Gradio) ile Kaggle'daki ComfyUI arasındaki bağlantıyı bir Cloudflare tüneli (`trycloudflare.com`) sağlar.

## Kurulum

Gereken: Windows ve Python 3.10 veya üstü. FFmpeg `imageio-ffmpeg` paketiyle birlikte gelir, ayrıca kurman gerekmez.

```powershell
git clone https://github.com/KULLANICI/aivideo.git
cd aivideo
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## Kullanım

### 1. Kaggle motorunu başlat
1. [kaggle/ai_video_motor.ipynb](kaggle/ai_video_motor.ipynb) dosyasını Kaggle'a yükle.
2. **Settings → Accelerator: GPU T4** seç ve **Internet: On** yap.
3. Tüm hücreleri çalıştır. En sonda bir `https://....trycloudflare.com` adresi çıkar.
4. *(İsteğe bağlı)* İndirmelerin daha hızlı olması için **Add-ons → Secrets** bölümüne `HF_TOKEN` ekle.

> ComfyUI veya tünel çökerse notebook'u baştan çalıştırmak yerine [kaggle/kurtarma_hucresi.py](kaggle/kurtarma_hucresi.py) içeriğini yeni bir hücrede çalıştır.

### 2. Uygulamayı aç
`calistir.bat` dosyasına çift tıkla. Tarayıcıda arayüz açılır:

1. **Kişi 1** ve **Kişi 2** fotoğraflarını yükle. Yüzün net göründüğü, büyük ve orijinal boyutlu fotoğraflar daha iyi sonuç verir.
2. Bir **şablon** seç.
3. **Motor** olarak `Kaggle (AI)` seç ve Kaggle'ın verdiği adresi yapıştır.
4. **Video Üret**'e bas. Kareler hazırlandıkça arayüzde görünür.

> **Önizleme** motoru yapay zekâ kullanmaz. Fotoğraflara yakınlaşma/kaydırma efekti uygular. GPU olmadan şablonları ve montajı denemek için kullanılır.

## Kendi şablonunu yaz

`templates/` klasörüne yeni bir `.yaml` dosyası ekle:

```yaml
ad: Benim Hikayem
aciklama: "Kısa açıklama"
muzik: romantik.mp3        # music/ klasörüne koy; yoksa video sessiz olur
gecis: 0.4                 # sahneler arası geçiş süresi (sn)

sahneler:
  - kisi: kisi1            # kisi1 | kisi2 | ikisi
    gorsel: "the person standing on a beach at sunset, cinematic"   # ilk kare tarifi (İngilizce)
    hareket: "she turns and smiles at the camera"                    # hareket tarifi
    sure: 3
    yazi: "Ekranda çıkacak yazı"     # isteğe bağlı
    sonraki_gecis: beyaz             # yumusak | beyaz | siyah
```

Hazır örnekler: [templates/zombi.yaml](templates/zombi.yaml), [templates/ask_hikayesi.yaml](templates/ask_hikayesi.yaml)

## Klasör yapısı

| Yol | İçerik |
|---|---|
| `app.py` | Gradio arayüzü |
| `core/pipeline.py` | Uçtan uca akış: kare → klip → montaj |
| `core/backends/` | Motorlar: `comfy.py` (Kaggle AI), `preview.py` (önizleme) |
| `core/montage.py` | FFmpeg montajı: boyut, yazı, geçiş, müzik |
| `kaggle/build_notebook.py` | Kaggle notebook'unu üretir |
| `kaggle/patch_gguf.py` | ComfyUI-GGUF eklentisini yeni ComfyUI ile uyumlu hale getiren yama |
| `templates/` | Senaryo şablonları |
| `music/` | Arka plan müzikleri |
| `output/` | Üretilen videolar (git'e eklenmez) |

## Notlar
- Kaggle'ın haftalık ücretsiz GPU kotası sınırlıdır. İlk çalıştırmada modellerin inmesi zaman alır.
- Tünel adresi her oturumda değişir. Uygulama son girilen adresi `ayarlar.json` dosyasına kaydeder.
