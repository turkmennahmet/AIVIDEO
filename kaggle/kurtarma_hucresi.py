import os, re, time, subprocess, urllib.request
from IPython.display import clear_output

subprocess.run("pkill -f 'main.py --listen' ; pkill -f cloudflared", shell=True)
time.sleep(3)

log = open(f"{BASE}/comfy.log", "w")
comfy = subprocess.Popen(
    ["python", "main.py", "--listen", "127.0.0.1", "--port", "8188", "--preview-method", "none"],
    cwd=COMFY, stdout=log, stderr=subprocess.STDOUT, env={**os.environ, "CUDA_VISIBLE_DEVICES": "0"},
    start_new_session=True)
for _ in range(180):
    try:
        urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=2); break
    except Exception:
        if comfy.poll() is not None:
            raise RuntimeError(open(f"{BASE}/comfy.log").read()[-3000:])
        time.sleep(2)
print("ComfyUI çalışıyor")

CF = f"{BASE}/cloudflared"
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
        m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", open(cf_log).read())
        if m:
            return m.group(0)
        time.sleep(1)

def tunnel_ok(url):
    try:
        return urllib.request.urlopen(f"{url}/system_stats", timeout=15).status == 200
    except Exception:
        return False

URL = start_tunnel()
time.sleep(10)  # tünelin dünyaya yayılması birkaç saniye sürer

fails = 0
while True:
    if comfy.poll() is not None:
        print("ComfyUI kapandı! Log:"); print(open(f"{BASE}/comfy.log").read()[-3000:]); break
    fails = 0 if tunnel_ok(URL) else fails + 1
    if fails >= 2:
        URL, fails = start_tunnel(), 0
        time.sleep(10)
    clear_output(wait=True)
    print("=" * 60)
    print("PROGRAMA YAPIŞTIRILACAK ADRES:", URL)
    print("=" * 60)
    print(time.strftime("%H:%M:%S"), "— motor çalışıyor. Son log satırları:")
    print("".join(open(f"{BASE}/comfy.log").readlines()[-15:]))
    time.sleep(30)
