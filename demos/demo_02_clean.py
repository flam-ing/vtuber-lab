#!/usr/bin/env python3
"""
Clean 02 chibi 2.5 demo:
- real cut parts from 02-chibi-25d/parts
- animated iris / mouth / blink / slight bob (no camera, no face)
"""
from __future__ import annotations

import math
import os
import time
from pathlib import Path

from PIL import Image, ImageTk
import tkinter as tk

PARTS = Path(__file__).resolve().parent.parent / "02-chibi-25d" / "parts"
ORDER = [
    "topwear", "face", "eyewhite", "irides", "eyelash",
    "eye_close", "mouth_open", "mouth_close", "handwear_1", "handwear_2",
]

class App:
    def __init__(self):
        self.imgs = {
            n: Image.open(PARTS / f"{n}.png").convert("RGBA")
            for n in ORDER if (PARTS / f"{n}.png").exists()
        }
        self.w = max(i.width for i in self.imgs.values())
        self.h = max(i.height for i in self.imgs.values())
        # fixed square window for reliable crop (same as 01)
        self.disp = 520
        self.scale = min(1.0, self.disp / max(self.w, self.h))

        self.root = tk.Tk()
        self.root.title("demo-02-chibi25d")
        self.root.geometry(f"{self.disp}x{self.disp}+200+120")
        self.root.configure(bg="#0a0a0c")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.label = tk.Label(self.root, bg="#0a0a0c", bd=0, width=self.disp, height=self.disp)
        self.label.pack(fill="both", expand=True)
        self.t0 = time.time()
        self._photo = None
        self.tick()

    def compose(self, blink: bool, mouth_open: bool, iris_dx: int, iris_dy: int, bob: int):
        canvas = Image.new("RGBA", (self.w, self.h), (10, 10, 12, 255))
        def paste(name, dx=0, dy=0, show=True):
            if not show or name not in self.imgs:
                return
            im = self.imgs[name]
            x = (self.w - im.width) // 2 + dx
            y = (self.h - im.height) // 2 + dy + bob
            canvas.alpha_composite(im, (x, y))
        paste("topwear")
        paste("face")
        # Blink must hide ALL open-eye layers (including eyewhite).
        # Old bug: left eyewhite on → looked half-open / neither open nor closed.
        if blink and "eye_close" in self.imgs:
            paste("eye_close")
        else:
            paste("eyewhite")
            paste("irides", iris_dx, iris_dy)
            paste("eyelash")
        paste("mouth_open", show=mouth_open)
        paste("mouth_close", show=not mouth_open)
        paste("handwear_1")
        paste("handwear_2")
        # fit into square black canvas
        fitted_w = max(1, int(self.w * self.scale))
        fitted_h = max(1, int(self.h * self.scale))
        if self.scale != 1.0:
            canvas = canvas.resize((fitted_w, fitted_h), Image.Resampling.LANCZOS)
        square = Image.new("RGBA", (self.disp, self.disp), (10, 10, 12, 255))
        ox = (self.disp - canvas.width) // 2
        oy = (self.disp - canvas.height) // 2
        square.alpha_composite(canvas, (ox, oy))
        return square

    def tick(self):
        t = time.time() - self.t0
        blink = (t % 2.8) < 0.12
        mouth = (math.sin(t * 10) > 0.15) and ((int(t * 0.5) % 2) == 0 or (t % 6) < 3.5)
        iris_dx = int(18 * math.sin(t * 0.9))
        iris_dy = int(6 * math.sin(t * 1.3))
        bob = int(4 * math.sin(t * 2.2))
        frame = self.compose(blink, mouth, iris_dx, iris_dy, bob).convert("RGB")
        self._photo = ImageTk.PhotoImage(frame)
        self.label.configure(image=self._photo)
        self.root.after(33, self.tick)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    App().run()
