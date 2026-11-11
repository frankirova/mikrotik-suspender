# Demo recording

Reproduces the README screencast: CSV → **plan** (read-only) → **apply** →
address-list visible in **Winbox**, over a real MikroTik CHR (RouterOS 7.24 on
QEMU/KVM). Nothing touches a physical router and every IP/name is fictional.

Two ways to get a router:

| Path | What you see | Cost |
|------|--------------|------|
| **CHR (used for the published video)** | real RouterOS + real Winbox | needs `/dev/kvm`, ~1 GB image |
| `tools/routeros_sim.py` | RouterOS **API** simulator + HTML console | stdlib only, instant |

The simulator speaks the real API protocol but nothing else, so Winbox cannot
connect to it — use it for quick offline checks, not for Winbox footage.

## What runs where

| Piece | Port | Purpose |
|-------|------|---------|
| `chr` | 8291 (Winbox), 8728 (API) | real RouterOS CHR on KVM |
| `mikrotik-demo` (throwaway copy) | 8002 | clean DB, demo CSV, `lab` alias → CHR |
| `routeros-sim` | 8728 (API), 8729 (console) | API-only simulator (offline demos) |

## 1. Real CHR

```bash
docker run -d --name chr --privileged --device /dev/kvm \
  --network mikrotik-suspender_default --ip 172.19.0.97 \
  -p 127.0.0.1:8291:8291 evilfreelancer/docker-routeros:latest

# CHR boots as admin with an empty password; set the one the app will use
docker exec mikrotik-demo python -c "
import routeros_api
p = routeros_api.RouterOsApiPool('172.19.0.97', username='admin', password='', plaintext_login=True)
a = p.get_api(); a.get_resource('/user').set(id='admin', password='demo'); p.disconnect()"
```

## 2. Demo app

Routers and their address-lists are aliases from `ROUTERS_JSON`; a non-loopback
bind requires `API_KEY` (that is why the demo looks like a real deployment).

```bash
docker build -t mikrotik-demo:release .

docker run -d --name mikrotik-demo \
  --network mikrotik-suspender_default --ip 172.19.0.98 \
  -p 127.0.0.1:8002:8000 \
  -e USER_MIKROTIK=admin -e PASS_MIKROTIK=demo \
  -e HOST=0.0.0.0 -e API_KEY=demo-token-123 -e ROUTER_TLS=false \
  -e 'ROUTERS_JSON={"lab":{"host":"172.19.0.97","port":8728,"address_list":"lab-suspensions"}}' \
  -v mikrotik-demo-data:/app/data \
  mikrotik-demo:release

docker exec -i mikrotik-demo sh -c 'cat > /app/data/clientes.csv' < tools/demo/clientes.csv
```

The UI then needs alias `lab`, a date, and the token `demo-token-123`.

## 3. Winbox on a virtual display

Winbox is a Qt app with no scripting interface, so the footage drives it with
synthetic input (`tools/gui-ctl/xdo.py`, XTest) on Xvfb:

```bash
nohup Xvfb :99 -screen 0 1440x900x24 -nolisten tcp &
mkdir -p /tmp/wbhome            # clean HOME: no saved routers in the video
HOME=/tmp/wbhome DISPLAY=:99 nohup /path/to/WinBox > /tmp/winbox.log 2>&1 &

X="tools/gui-ctl/.venv/bin/python tools/gui-ctl/xdo.py"   # venv with python-xlib
$X click 420 392 && $X type "127.0.0.1"      # Connect to
$X click 344 443 && $X type "demo"           # Password
$X click 317 546                             # Connect
$X click 190 558                             # New Terminal (sidebar)
$X type "n" && $X key Return                 # skip the license prompt
```

Capture each beat with `ffmpeg -f x11grab -video_size 1440x900 -i :99`.

The two beats are `/ip/firewall/address-list/print where list=lab-suspensions`
(empty before `apply`) and the same command after it (8 entries).

## 4. Record the app

```bash
cd tools/recorder
npm install && npx playwright install chromium

# take A: title card + plan (read-only)
APP_URL=http://127.0.0.1:8002/ ROUTER_ALIAS=lab node record.mjs

# take C: plan + confirmed apply (the UI asks for a plan in this session first)
APP_URL=http://127.0.0.1:8002/ ROUTER_ALIAS=lab node record-exec.mjs
```

Output: `tools/demo/raw/*.webm` (1440×900). Playwright does not capture the
cursor, so both scripts paint their own pointer.

## 5. Encode

The system ffmpeg has no `drawtext` (no freetype), so the caption is a PNG
overlay built with ImageMagick; segments are encoded with identical parameters
and concatenated:

```bash
convert -background "rgba(0,0,0,0.55)" -fill "rgba(255,255,255,0.92)" \
  -font /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf -pointsize 20 \
  -bordercolor "rgba(0,0,0,0.55)" -border 13 \
  label:"MikroTik CHR real · IPs y nombres ficticios" \
  -define png:color-type=6 PNG32:/tmp/caption.png

ENC="-c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -r 25 -movflags +faststart"
ffmpeg -y -i "$TAKE_A"  -i /tmp/caption.png -filter_complex "[0:v]scale=1440:900,setsar=1[v];[v][1:v]overlay=28:H-h-34" $ENC /tmp/segs/1.mp4
ffmpeg -y -ss 1.6 -i /tmp/wb_b.mp4 -i /tmp/caption.png -filter_complex "[0:v]scale=1440:900,setsar=1[v];[v][1:v]overlay=28:H-h-34" $ENC /tmp/segs/2.mp4
ffmpeg -y -i "$TAKE_C"  -i /tmp/caption.png -filter_complex "[0:v]scale=1440:900,setsar=1[v];[v][1:v]overlay=28:H-h-34" $ENC /tmp/segs/3.mp4
ffmpeg -y -ss 1.6 -i /tmp/wb_d.mp4 -i /tmp/caption.png -filter_complex "[0:v]scale=1440:900,setsar=1[v];[v][1:v]overlay=28:H-h-34" $ENC /tmp/segs/4.mp4

ffmpeg -y -f concat -safe 0 -i /tmp/segs/list.txt -c copy docs/demo/mikrotik-suspender-demo.mp4
ffmpeg -y -i docs/demo/mikrotik-suspender-demo.mp4 \
  -vf "fps=10,scale=900:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=160:stats_mode=diff[p];[s1][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
  docs/demo/mikrotik-suspender-demo.gif
```
