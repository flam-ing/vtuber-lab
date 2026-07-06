"""Assemble AI-generated flamingo parts into a Live2D-ready layered PSD.

Each part: green-screen removed, trimmed, scaled and placed on a shared canvas
per PLACEMENT, then exported as one PSD layer (bottom to top) plus a flattened
preview.png for visual checking.
"""
import os
import numpy as np
import cv2
from PIL import Image
import pytoshop
from pytoshop.user import nested_layers
from pytoshop import enums

BASE = os.path.dirname(os.path.abspath(__file__))
PARTS_DIR = os.path.join(BASE, "parts")
OUT_PSD = os.path.join(BASE, "flamingo_live2d.psd")
OUT_PREVIEW = os.path.join(BASE, "preview.png")

# Working coordinate space: 1024 wide, 1400 tall (head frame + torso below).
# Final canvas is 2x for resolution.
WORK_W, WORK_H = 1024, 1400
SCALE = 2
CANVAS_W, CANVAS_H = WORK_W * SCALE, WORK_H * SCALE

# name: (cx, cy, target_w, keep_largest_component)
# cx/cy/target_w in working coords. Layer order = list order, bottom -> top.
PLACEMENT = [
    ("body_fill",    (585, 1085, 980, False)),   # oversized body copy to close silhouette gaps
    ("head_base",    (470, 470, 880, False)),
    ("mouth_inside", (405, 580, 135, False)),
    ("lower_beak",   (395, 615, 300, False)),
    ("upper_beak",   (400, 545, 270, False)),
    ("eye_white",    (543, 470, 80, True)),
    ("eye_pupil",    (540, 471, 78, True)),
    ("eyelid",       (540, 471, 88, True)),
    ("hair_front",   (478, 185, 630, False)),
    ("body_base",    (610, 1080, 900, False)),
    ("left_arm",     (420, 1320, 620, False)),
    ("right_arm",    (730, 1330, 560, False)),
]

PREVIEW_SKIP = {"eyelid"}  # closed-eye layer would cover the open eye in the flat preview
FILE_ALIAS = {"body_fill": "body_base"}

def remove_green(arr):
    """RGBA uint8 -> alpha out green screen, with edge despill."""
    r = arr[:, :, 0].astype(int)
    g = arr[:, :, 1].astype(int)
    b = arr[:, :, 2].astype(int)
    green = (g > 120) & (g > r + 25) & (g > b + 25)
    alpha = np.where(green, 0, 255).astype(np.uint8)
    # soften 1px edge to kill green fringe
    alpha = cv2.erode(alpha, np.ones((3, 3), np.uint8), iterations=1)
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
    out = arr.copy()
    out[:, :, 3] = alpha
    # despill: clamp green channel to max(r,b) where semi-transparent edge
    edge = (alpha > 0) & (alpha < 255)
    maxrb = np.maximum(arr[:, :, 0], arr[:, :, 2])
    out[:, :, 1] = np.where(edge, np.minimum(arr[:, :, 1], maxrb), arr[:, :, 1])
    return out

def largest_component(arr):
    """Keep only the largest opaque blob (for picking one eye out of a pair)."""
    mask = (arr[:, :, 3] > 10).astype(np.uint8)
    n, labels = cv2.connectedComponents(mask)
    if n <= 2:
        return arr
    sizes = [(labels == i).sum() for i in range(1, n)]
    keep = 1 + int(np.argmax(sizes))
    out = arr.copy()
    out[:, :, 3] = np.where(labels == keep, arr[:, :, 3], 0)
    return out

def trim(arr):
    ys, xs = np.where(arr[:, :, 3] > 10)
    return arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1]

def build():
    layers = []          # (name, canvas RGBA at full res)
    preview = np.zeros((CANVAS_H, CANVAS_W, 4), dtype=np.uint8)
    preview[:, :] = (235, 235, 235, 255)  # light gray backdrop for eyeballing

    for name, (cx, cy, tw, keep_one) in PLACEMENT:
        path = os.path.join(PARTS_DIR, f"{FILE_ALIAS.get(name, name)}.png")
        arr = np.array(Image.open(path).convert("RGBA"))
        arr = remove_green(arr)
        if keep_one:
            arr = largest_component(arr)
        arr = trim(arr)

        w = int(tw * SCALE)
        h = int(arr.shape[0] * w / arr.shape[1])
        part = cv2.resize(arr, (w, h), interpolation=cv2.INTER_AREA)

        x0 = int(cx * SCALE - w / 2)
        y0 = int(cy * SCALE - h / 2)

        canvas = np.zeros((CANVAS_H, CANVAS_W, 4), dtype=np.uint8)
        # clip to canvas
        sx0, sy0 = max(0, -x0), max(0, -y0)
        dx0, dy0 = max(0, x0), max(0, y0)
        dx1, dy1 = min(CANVAS_W, x0 + w), min(CANVAS_H, y0 + h)
        if dx1 > dx0 and dy1 > dy0:
            canvas[dy0:dy1, dx0:dx1] = part[sy0:sy0 + (dy1 - dy0), sx0:sx0 + (dx1 - dx0)]
        layers.append((name, canvas))

        # alpha-composite onto preview
        if name in PREVIEW_SKIP:
            continue
        a = canvas[:, :, 3:4].astype(float) / 255.0
        preview[:, :, :3] = (canvas[:, :, :3] * a + preview[:, :, :3] * (1 - a)).astype(np.uint8)

    Image.fromarray(preview).save(OUT_PREVIEW)
    print(f"preview -> {OUT_PREVIEW}")

    psd_layers = []
    for name, canvas in reversed(layers):  # pytoshop lists top-first
        psd_layers.append(nested_layers.Image(
            name=name,
            visible=True,
            opacity=255,
            top=0, left=0,
            channels={
                0: canvas[:, :, 0],
                1: canvas[:, :, 1],
                2: canvas[:, :, 2],
                -1: canvas[:, :, 3],
            },
        ))
    psd = nested_layers.nested_layers_to_psd(
        psd_layers, color_mode=enums.ColorMode.rgb,
        size=(CANVAS_H, CANVAS_W),
        compression=enums.Compression.raw)
    with open(OUT_PSD, "wb") as f:
        psd.write(f)
    print(f"psd -> {OUT_PSD} ({CANVAS_W}x{CANVAS_H}, {len(layers)} layers)")

if __name__ == "__main__":
    build()
