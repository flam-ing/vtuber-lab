#!/usr/bin/env python3
"""Offline showcase GIFs for README — pure black bg, no face, clear motion."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
DISP = 480
BG = (8, 8, 10, 255)


def to_square(im: Image.Image, size: int = DISP, bg=BG) -> Image.Image:
    im = im.convert("RGBA")
    im.thumbnail((size, size), Image.Resampling.LANCZOS)
    sq = Image.new("RGBA", (size, size), bg)
    sq.alpha_composite(im, ((size - im.width) // 2, (size - im.height) // 2))
    return sq


def save_gif(frames: list[Image.Image], path: Path, duration: int = 70) -> None:
    rgb = [f.convert("RGB") for f in frames]
    rgb[0].save(
        path,
        save_all=True,
        append_images=rgb[1:],
        duration=duration,
        loop=0,
        optimize=True,
    )
    print(f"wrote {path} ({path.stat().st_size // 1024}KB, {len(frames)}f)")


# ---------- 01: 4cut PNGTuber ----------
def chroma_key(img: Image.Image) -> Image.Image:
    arr = np.array(img.convert("RGBA"))
    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
    # aggressive green screen removal
    green = (g > 120) & (g > r + 25) & (g > b + 25)
    # also near-solid green fringe
    green |= (g > 100) & (r < 90) & (b < 90)
    arr[green, 3] = 0
    return Image.fromarray(arr, "RGBA")


def render_01() -> None:
    assets = ROOT / "01-mingo-4cut" / "assets"
    keys = {
        "idle": "1_green_idle.png",
        "talk": "2_green_talk.png",
        "blink": "3_green_blink.png",
        "talk_blink": "4_green_talk_blink.png",
    }
    spr = {k: chroma_key(Image.open(assets / fn)) for k, fn in keys.items()}
    # crop to content bbox with padding
    def content(im: Image.Image) -> Image.Image:
        a = np.array(im)
        ys, xs = np.where(a[:, :, 3] > 12)
        if len(xs) == 0:
            return im
        pad = 24
        x0, x1 = max(0, xs.min() - pad), min(im.width, xs.max() + pad)
        y0, y1 = max(0, ys.min() - pad), min(im.height, ys.max() + pad)
        return im.crop((x0, y0, x1, y1))

    spr = {k: content(v) for k, v in spr.items()}
    frames: list[Image.Image] = []
    n = 72
    for i in range(n):
        t = i / 12.0
        mouth = (math.sin(t * 9.0) > 0.05) and ((int(t) % 5) < 3)
        blink = (t % 2.7) < 0.14
        if blink and mouth:
            key = "talk_blink"
        elif blink:
            key = "blink"
        elif mouth:
            key = "talk"
        else:
            key = "idle"
        im = spr[key].copy()
        # subtle sway via offset on black canvas
        dx = int(10 * math.sin(t * 1.2))
        dy = int(6 * math.sin(t * 1.8))
        base = to_square(im)
        # re-center with sway
        layer = to_square(im)
        canvas = Image.new("RGBA", (DISP, DISP), BG)
        # paste with sway (clip)
        canvas.alpha_composite(layer, (dx, dy))
        # fill edges still black
        frames.append(canvas)
    save_gif(frames, OUT / "01-pngtuber.gif", duration=70)
    frames[8].convert("RGB").save(OUT / "01-preview.jpg", quality=90)


# ---------- 02: chibi 2.5 with head tilt + hand swap ----------
def render_02() -> None:
    parts_dir = ROOT / "02-chibi-25d" / "parts"
    names = [
        "topwear",
        "face",
        "eyewhite",
        "irides",
        "eyelash",
        "eye_close",
        "mouth_open",
        "mouth_close",
        "handwear_1",
        "handwear_2",
    ]
    imgs = {
        n: Image.open(parts_dir / f"{n}.png").convert("RGBA")
        for n in names
        if (parts_dir / f"{n}.png").exists()
    }
    w = max(i.width for i in imgs.values())
    h = max(i.height for i in imgs.values())

    def paste(canvas: Image.Image, name: str, dx=0, dy=0, angle=0.0, show=True):
        if not show or name not in imgs:
            return
        im = imgs[name]
        if abs(angle) > 0.05:
            # rotate around canvas center
            im = im.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False)
        x = (w - im.width) // 2 + dx
        y = (h - im.height) // 2 + dy
        canvas.alpha_composite(im, (x, y))

    def compose(blink: bool, mouth_open: bool, head_deg: float, iris_dx: int, iris_dy: int, hand: int, bob: int):
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        # body (no head tilt)
        paste(canvas, "topwear", dy=bob)
        # head group tilts together
        paste(canvas, "face", angle=head_deg, dy=bob)
        if blink and "eye_close" in imgs:
            paste(canvas, "eye_close", angle=head_deg, dy=bob)
        else:
            paste(canvas, "eyewhite", angle=head_deg, dy=bob)
            paste(canvas, "irides", dx=iris_dx, dy=iris_dy + bob, angle=head_deg)
            paste(canvas, "eyelash", angle=head_deg, dy=bob)
        paste(canvas, "mouth_open", angle=head_deg, dy=bob, show=mouth_open)
        paste(canvas, "mouth_close", angle=head_deg, dy=bob, show=not mouth_open)
        # hands: alternate / offset for pose change
        if hand == 0:
            paste(canvas, "handwear_1", dy=bob)
            paste(canvas, "handwear_2", dy=bob)
        elif hand == 1:
            # only left-ish hand raised
            paste(canvas, "handwear_1", dx=-18, dy=bob - 22)
            paste(canvas, "handwear_2", dx=8, dy=bob + 6)
        else:
            paste(canvas, "handwear_1", dx=10, dy=bob + 8)
            paste(canvas, "handwear_2", dx=22, dy=bob - 18)
        return to_square(canvas)

    frames: list[Image.Image] = []
    n = 84
    for i in range(n):
        t = i / 12.0
        blink = (t % 2.8) < 0.14
        mouth = (math.sin(t * 9.5) > 0.1) and ((int(t * 0.45) % 2) == 0 or (t % 7) < 4)
        head = 8.0 * math.sin(t * 0.85)  # degrees
        iris_dx = int(14 * math.sin(t * 1.1) + head * 0.4)
        iris_dy = int(5 * math.sin(t * 1.4))
        # hand pose cycles every ~2s
        hand = int(t / 2.0) % 3
        bob = int(3 * math.sin(t * 2.1))
        frames.append(compose(blink, mouth, head, iris_dx, iris_dy, hand, bob))
    save_gif(frames, OUT / "02-chibi25d.gif", duration=70)
    frames[12].convert("RGB").save(OUT / "02-preview.jpg", quality=90)


if __name__ == "__main__":
    render_01()
    render_02()
    print("01/02 done — render 04 via electron demoMotion separately")
