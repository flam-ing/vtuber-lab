#!/usr/bin/env python3
"""
Clean 01 PNGTuber demo window:
- real 4-cut sprites from 01-mingo-4cut
- scripted mouth/blink/sway (no camera preview, no face on screen)
- solid dark canvas for recording
"""
from __future__ import annotations

import math
import os
import time

import numpy as np
from PIL import Image, ImageTk
import tkinter as tk

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "01-mingo-4cut", "assets"))
W = H = 520
SPRITE = 400

def load_sprite(path: str) -> np.ndarray:
    img = Image.open(path).convert("RGBA")
    arr = np.array(img)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    green = (g > 140) & (r < 110) & (b < 110)
    arr[green] = [0, 0, 0, 0]
    out = Image.fromarray(arr).resize((SPRITE, SPRITE), Image.Resampling.LANCZOS)
    return np.array(out, dtype=np.float32)

class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("demo-01-pngtuber")
        self.root.geometry(f"{W}x{H}+200+120")
        self.root.configure(bg="#0a0a0c")
        self.root.overrideredirect(True)  # no title bar in recordings
        self.root.attributes("-topmost", True)
        self.canvas = tk.Label(self.root, bg="#0a0a0c", bd=0)
        self.canvas.pack(fill="both", expand=True)

        self.idle = load_sprite(os.path.join(BASE, "1_green_idle.png"))
        self.talk = load_sprite(os.path.join(BASE, "2_green_talk.png"))
        self.blink = load_sprite(os.path.join(BASE, "3_green_blink.png"))
        self.talk_blink = load_sprite(os.path.join(BASE, "4_green_talk_blink.png"))
        self.t0 = time.time()
        self._photo = None
        self.tick()

    def tick(self):
        t = time.time() - self.t0
        # scripted performance: talk bursts + blinks + sway
        mouth = 0.5 + 0.5 * math.sin(t * 9.0) * (0.55 + 0.45 * math.sin(t * 0.7))
        mouth = max(0.0, min(1.0, mouth if (int(t) % 5) < 3 else mouth * 0.15))
        blink = 1.0 if (t % 3.2) < 0.14 or (t % 3.2) > 3.05 else 0.0
        dx = int(28 * math.sin(t * 1.1))
        dy = int(16 * math.sin(t * 1.7) + 3 * math.sin(t * 2.0))

        if blink > 0.5 and mouth > 0.45:
            spr = self.talk_blink
        elif blink > 0.5:
            spr = self.blink
        elif mouth > 0.45:
            spr = self.talk
        else:
            # soft crossfade idle↔talk via alpha mix
            a = mouth
            spr = self.idle * (1 - a) + self.talk * a

        canvas = np.zeros((H, W, 4), dtype=np.float32)
        canvas[:, :, 3] = 0
        # dark opaque bg so recording is clean
        canvas[:, :, 0:3] = 10
        canvas[:, :, 3] = 255
        x0 = (W - SPRITE) // 2 + dx
        y0 = (H - SPRITE) // 2 + dy
        # clip blit
        x1, y1 = max(0, x0), max(0, y0)
        x2, y2 = min(W, x0 + SPRITE), min(H, y0 + SPRITE)
        sx1, sy1 = x1 - x0, y1 - y0
        sx2, sy2 = sx1 + (x2 - x1), sy1 + (y2 - y1)
        patch = spr[sy1:sy2, sx1:sx2]
        # alpha composite
        src = patch
        dst = canvas[y1:y2, x1:x2]
        sa = src[:, :, 3:4] / 255.0
        dst[:, :, :3] = src[:, :, :3] * sa + dst[:, :, :3] * (1 - sa)
        dst[:, :, 3] = 255

        im = Image.fromarray(np.clip(dst, 0, 255).astype(np.uint8), "RGBA").convert("RGB")
        self._photo = ImageTk.PhotoImage(im)
        self.canvas.configure(image=self._photo)
        self.root.after(33, self.tick)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    App().run()
