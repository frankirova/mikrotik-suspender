# Demo recording

Reproduces the README screencast: CSV → preview → ejecutar → address-list
`suspendido` seen in **Winbox**, over a **real** MikroTik CHR (RouterOS 7.24,
QEMU/KVM). Nothing touches a physical router, and every IP/name is fake.

Two ways to get a router for the demo:

| Path | What you see | Cost |
|------|--------------|------|
| **CHR (used for the published video)** | real RouterOS + real Winbox | needs `/dev/kvm`, ~1 GB image |
| `tools/routeros_sim.py` | RouterOS **API** simulator + HTML console | stdlib only, instant |

The simulator speaks the real API protocol but nothing else, so Winbox cannot
connect to it — use it for quick offline demos, not for Winbox footage.

## What runs where

| Piece | Port | Purpose |
|-------|------|---------|
| `mikrotik-suspender` (your instance) | 8001 | normal use |
| `mikrotik-demo` (throwaway copy) | 8002 | clean DB, demo CSV — used for the video |
| `chr` | 8291 (Winbox), 8728 (API) | real RouterOS CHR on KVM |
| `routeros-sim` | 8728 (API), 8729 (console) | API-only simulator (offline demos) |

The demo instance runs on a separate container so the recording never shows the
real `data/options.db` contents.

## 0. Real CHR + Winbox (the published path)

```bash
docker run -d --name chr --privileged --device /dev/kvm \
  --network mikrotik-suspender_default --ip 172.19.0.97 \
  -p 127.0.0.1:8291:8291 evilfreelancer/docker-routeros:latest

# CHR boots as admin with an empty password; set one the app can use
docker exec mikrotik-demo python -c "
import routeros_api
p = routeros_api.RouterOsApiPool('172.19.0.97', username='admin', password='', plaintext_login=True)
a = p.get_api(); a.get_resource('/user').set(id='admin', password='demo'); p.disconnect()"
```

The demo app then runs with `-e USER_MIKROTIK=admin -e PASS_MIKROTIK=demo`.

Winbox is a Qt app with no scripting interface, so the footage drives it on a
virtual display with synthetic input (`tools/gui-ctl/xdo.py`, XTest):

```bash
nohup Xvfb :99 -screen 0 1440x900x24 -nolisten tcp &
mkdir -p /tmp/wbhome            # clean HOME: no saved routers in the video
HOME=/tmp/wbhome DISPLAY=:99 nohup /path/to/WinBox > /tmp/winbox.log 2>&1 &

X="tools/gui-ctl/.venv/bin/python tools/gui-ctl/xdo.py"   # venv with python-xlib
$X click 420 392 && $X type "127.0.0.1"      # Connect to
$X click 344 443 && $X type "demo"           # Password
$X click 317 546                             # Connect
$X click 173 564                             # New Terminal (sidebar)
$X type "n" && $X key Return                # skip the license prompt
```

Capture each Winbox beat with `ffmpeg -f x11grab -video_size 1440x900 -i :99`.

## 1. Start the simulator (offline alternative)

The host firewall blocks container → host traffic, so the simulator runs as a
sidecar on the compose network:

```bash
docker run -d --name routeros-sim \
  --network mikrotik-suspender_default --ip 172.19.0.99 \
  -p 127.0.0.1:8729:8729 \
  -v "$PWD/tools:/tools:ro" -w /tools \
  python:3.12-alpine python routeros_sim.py --host 0.0.0.0
```

Console (read-only): <http://127.0.0.1:8729> · plain text: `/print`.

`tools/routeros_sim.py` speaks the real RouterOS binary API (v6.43+ plaintext
login) and implements only `/ip/firewall/address-list/print|add|set|remove`.
State is in memory: restart the container to get an empty router.

## 2. Start the demo app

```bash
docker run -d --name mikrotik-demo \
  --network mikrotik-suspender_default --ip 172.19.0.98 \
  -p 127.0.0.1:8002:8000 \
  -e USER_MIKROTIK=demo -e PASS_MIKROTIK=demo \
  -v mikrotik-demo-data:/app/data \
  mikrotik-suspender-mikrotik-suspender:latest
```

Then load the demo client list and a few fake saved options:

```bash
docker exec -i mikrotik-demo sh -c 'cat > /app/data/clientes.csv' < tools/demo/clientes.csv
docker exec mikrotik-demo python -c "
import sqlite3
c = sqlite3.connect('/app/data/options.db')
c.execute('delete from options')
c.executemany('insert into options(option) values (?)', [('10.50.0.11',), ('10.50.0.12',), ('10.50.0.13',)])
c.commit()"
```

## 3. Record

```bash
cd tools/recorder
npm install          # once: playwright
npx playwright install chromium
docker restart routeros-sim   # start from an empty address-list
APP_URL=http://127.0.0.1:8002/ CONSOLE_URL=http://127.0.0.1:8729/ \
ROUTER_IP=172.19.0.99 SUSPENSION_DATE=2025-11-10 node record.mjs
```

Output: `tools/demo/raw/*.webm` (1440×900, Playwright). The recorder paints its
own pointer because Playwright does not capture the cursor.

## 4. Encode

The system ffmpeg has no `drawtext` (no freetype), so the caption is a PNG
overlay built with ImageMagick:

```bash
WEBM=$(ls tools/demo/raw/*.webm)

convert -background "rgba(0,0,0,0.55)" -fill "rgba(255,255,255,0.92)" \
  -font /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf -pointsize 20 \
  -bordercolor "rgba(0,0,0,0.55)" -border 13 \
  label:"RouterOS simulado · IPs y nombres ficticios" \
  -define png:color-type=6 PNG32:/tmp/caption.png

ffmpeg -y -i "$WEBM" -i /tmp/caption.png \
  -filter_complex "[0:v][1:v]overlay=28:H-h-34,format=yuv420p" \
  -c:v libx264 -preset slow -crf 20 -movflags +faststart \
  docs/demo/mikrotik-suspender-demo.mp4

ffmpeg -y -i "$WEBM" -i /tmp/caption.png \
  -filter_complex "[0:v][1:v]overlay=28:H-h-34,fps=10,scale=900:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=160:stats_mode=diff[p];[s1][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
  docs/demo/mikrotik-suspender-demo.gif
```

## Notes

- Every IP and name in the video is fake (`10.50.0.0/24`, `Perez Ana`,
  `Gomez Luis`, …). Nothing touches a real router.
- The app instance on 8001 is untouched by the recording; the demo copy keeps its
  own Docker volume.
