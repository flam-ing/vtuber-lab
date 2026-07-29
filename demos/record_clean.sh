#!/bin/bash
# Clean avatar-only demos: black backdrop, no face, motion-driven, crop to window.
set -euo pipefail
OUT="$(cd "$(dirname "$0")" && pwd)"
LAB="$(cd "$OUT/.." && pwd)"
PY="$LAB/tuber-env/bin/python"
export PATH="/opt/homebrew/bin:$PATH"

kill_match() {
  python3 - <<'PY'
import os, signal, subprocess
keys = [
  "black_backdrop.py", "demo_01_clean.py", "demo_02_clean.py",
  "vroid-base-custom-girl", "vite --port 5183", "wait-and-electron",
  "run_pngtuber.py",
]
out = subprocess.check_output(["ps", "-axo", "pid=,command="], text=True)
for line in out.splitlines():
    if any(k in line for k in keys):
        if "record_clean" in line or ("python3" in line and "<<" in line):
            continue
        try:
            os.kill(int(line.split()[0]), signal.SIGKILL)
        except ProcessLookupError:
            pass
for line in out.splitlines():
    if "Electron" in line and ("mingo-mate" in line or "vroid-base" in line):
        try:
            os.kill(int(line.split()[0]), signal.SIGKILL)
        except ProcessLookupError:
            pass
print("cleaned")
PY
}

window_bounds() {
  # $1 = window name contains
  local name="$1"
  osascript -e "
tell application \"System Events\"
  set procs to every process whose background only is false
  repeat with p in procs
    try
      repeat with w in windows of p
        set t to name of w as text
        if t contains \"${name}\" then
          set p1 to position of w
          set s1 to size of w
          return ((item 1 of p1) as text) & \",\" & ((item 2 of p1) as text) & \",\" & ((item 1 of s1) as text) & \",\" & ((item 2 of s1) as text)
        end if
      end repeat
    end try
  end repeat
end tell
return \"\"
" 2>/dev/null || true
}

# Convert points to retina pixels (scale=2 on this Mac)
record_window() {
  local title_sub="$1"
  local out_mp4="$2"
  local secs="${3:-6}"
  sleep 1.2
  local b
  b=$(window_bounds "$title_sub")
  echo "bounds[$title_sub]=$b"
  local scale=2
  if [[ -z "$b" ]]; then
    echo "WARN: window not found, full-screen crop center"
    # center 520x520 at 2x
    ffmpeg -y -f avfoundation -framerate 15 -i "5:none" -t "$secs" \
      -vf "crop=1040:1040:(in_w-1040)/2:(in_h-1040)/2,scale=520:-2" \
      -pix_fmt yuv420p -c:v libx264 -preset ultrafast "$out_mp4" 2>"${out_mp4}.log"
  else
    IFS=',' read -r x y w h <<<"$b"
    # pad a little; clamp even sizes
    local px=$(( x * scale ))
    local py=$(( y * scale ))
    local pw=$(( w * scale ))
    local ph=$(( h * scale ))
    # ensure even
    pw=$(( pw - pw % 2 )); ph=$(( ph - ph % 2 ))
    px=$(( px - px % 2 )); py=$(( py - py % 2 ))
    # safety margins
    if (( px < 0 )); then px=0; fi
    if (( py < 0 )); then py=0; fi
    echo "crop=${pw}x${ph}+${px}+${py}"
    ffmpeg -y -f avfoundation -framerate 15 -i "5:none" -t "$secs" \
      -vf "crop=${pw}:${ph}:${px}:${py},scale=480:-2" \
      -pix_fmt yuv420p -c:v libx264 -preset ultrafast "$out_mp4" 2>"${out_mp4}.log"
  fi
}

to_gif() {
  local in="$1" out="$2"
  ffmpeg -y -i "$in" -vf "fps=12,scale=480:-2:flags=lanczos,palettegen=stats_mode=diff" "$OUT/_pal.png" 2>/dev/null
  ffmpeg -y -i "$in" -i "$OUT/_pal.png" \
    -lavfi "fps=12,scale=480:-2:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5" \
    "$out" 2>/dev/null
  ls -lh "$out"
}

kill_match
mkdir -p "$OUT/clean"

# ---- backdrop ----
"$PY" "$OUT/black_backdrop.py" >/dev/null 2>&1 &
echo $! > "$OUT/backdrop.pid"
sleep 1

# ---- 01 ----
echo "=== 01 clean motion ==="
"$PY" "$OUT/demo_01_clean.py" >/dev/null 2>&1 &
echo $! > "$OUT/d01.pid"
sleep 1.5
record_window "demo-01-pngtuber" "$OUT/clean/01.mp4" 6
kill "$(cat "$OUT/d01.pid")" 2>/dev/null || true
to_gif "$OUT/clean/01.mp4" "$OUT/clean/01-pngtuber.gif"

# ---- 02 ----
echo "=== 02 clean motion ==="
"$PY" "$OUT/demo_02_clean.py" >/dev/null 2>&1 &
echo $! > "$OUT/d02.pid"
sleep 1.5
record_window "demo-02-chibi25d" "$OUT/clean/02.mp4" 6
kill "$(cat "$OUT/d02.pid")" 2>/dev/null || true
to_gif "$OUT/clean/02.mp4" "$OUT/clean/02-chibi25d.gif"

# ---- 04 ----
echo "=== 04 clean motion (demoMotion, no cam UI) ==="
cd "$LAB/04-vroid-base-custom-girl"
MINGO_DEMO_MOTION=1 npm run dev >"$OUT/clean/04_run.log" 2>&1 &
echo $! > "$OUT/d04.pid"
for i in $(seq 1 25); do
  code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5183/ || true)
  if [[ "$code" == "200" ]]; then echo "vite ready $i"; break; fi
  sleep 1
done
# give model load time
sleep 8
# Electron window title is often empty for frameless; crop lower-right panel area
# WIN 520x780 at bottom-right of workArea
record_window "Electron" "$OUT/clean/04.mp4" 7 || true
# if electron title empty, try fixed crop from screen geometry
if [[ ! -s "$OUT/clean/04.mp4" ]] || [[ $(stat -f%z "$OUT/clean/04.mp4" 2>/dev/null || echo 0) -lt 10000 ]]; then
  echo "fallback fixed crop for 04"
  # workArea-ish: bottom-right 520x780 @2x
  ffmpeg -y -f avfoundation -framerate 15 -i "5:none" -t 7 \
    -vf "crop=1040:1560:in_w-1040-48:in_h-1560-40,scale=480:-2" \
    -pix_fmt yuv420p -c:v libx264 -preset ultrafast "$OUT/clean/04.mp4" 2>"$OUT/clean/04_ffmpeg.log"
fi
to_gif "$OUT/clean/04.mp4" "$OUT/clean/04-vroid.gif"

# cleanup
kill_match
kill "$(cat "$OUT/backdrop.pid")" 2>/dev/null || true

echo "DONE"
ls -lah "$OUT/clean"
