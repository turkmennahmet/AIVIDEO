"""ComfyUI-GGUF yaması: yeni ComfyUI sürümleri Linear katmanına input_act / residual
parametreleri gönderiyor, GGUF eklentisi bunları tanımıyor ve şu hatayı veriyor:
  TypeError: GGMLOps.Linear.forward_ggml_cast_weights() got an unexpected keyword argument 'input_act'
Bu yama o parametreleri ComfyUI'nin kendi yardımcılarıyla uygular.

Kullanım: python patch_gguf.py <ComfyUI-GGUF klasörü>
"""
import sys
from pathlib import Path

OLD = """        def forward_ggml_cast_weights(self, input):
            weight, bias = self.cast_bias_weight(input)
            return torch.nn.functional.linear(input, weight, bias)
"""
NEW = """        def forward_ggml_cast_weights(self, input, input_act=None, act_weight=None, act_eps=0.0,
                                      residual=None, residual_scale=None):
            # [aivideo yaması] yeni ComfyUI input_act/residual parametreleri
            if input_act is not None:
                input = comfy.ops._eager_input_act(input, input_act, act_weight, act_eps)
            weight, bias = self.cast_bias_weight(input)
            out = torch.nn.functional.linear(input, weight, bias)
            if residual is not None:
                out = torch.addcmul(residual, out, residual_scale)
            return out
"""


def patch(gguf_dir: str) -> str:
    ops = Path(gguf_dir) / "ops.py"
    src = ops.read_text(encoding="utf-8")
    if "[aivideo yaması]" in src:
        return "zaten yamalı"
    if OLD not in src:
        return "yama gerekmedi / uygulanamadı (eklenti değişmiş olabilir)"
    ops.write_text(src.replace(OLD, NEW, 1), encoding="utf-8")
    return "yama uygulandı"


if __name__ == "__main__":
    print("GGUF:", patch(sys.argv[1]))
