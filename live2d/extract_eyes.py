"""Extract the ORIGINAL character's eye linework from the PNGTuber sprites.

The AI-generated front-facing eyes clash with the original sleepy profile eye,
so we lift the real eye (open, from 1_green_idle) and the closed-lash line
(from 3_green_blink) by masking dark linework + inner highlight against the
flat pink face, and save them as transparent parts for assemble_psd.py.
"""
import os
import numpy as np
import cv2
from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(BASE, "..", "assets")
PARTS = os.path.join(BASE, "parts_v2")

# eye bounding boxes in the 1024x1024 originals (x0, y0, x1, y1)
JOBS = [
    ("1_green_idle.png", (448, 305, 550, 392), "eye_open.png"),
    ("3_green_blink.png", (448, 305, 555, 380), "eye_closed.png"),
]

def extract(src_path, box, out_path):
    img = np.array(Image.open(src_path).convert("RGBA"))
    x0, y0, x1, y1 = box
    crop = img[y0:y1, x0:x1].copy()
    rgb = crop[:, :, :3].astype(float)
    lum = rgb[:, :, 0] * 0.3 + rgb[:, :, 1] * 0.59 + rgb[:, :, 2] * 0.11

    dark = (lum < 95).astype(np.uint8)                      # eye linework / iris
    white = (lum > 190).astype(np.uint8)                    # inner highlight
    near_dark = cv2.dilate(dark, np.ones((15, 15), np.uint8))
    keep = (dark | (white & near_dark)) * 255

    # close small holes inside the iris
    keep = cv2.morphologyEx(keep, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))

    # drop stray fragments: components touching the crop border (hair/beak
    # linework cut off by the box) or too small to be part of the eye
    n, labels = cv2.connectedComponents((keep > 128).astype(np.uint8))
    h, w = keep.shape
    for i in range(1, n):
        comp = labels == i
        ys, xs = np.where(comp)
        touches_border = ys.min() == 0 or xs.min() == 0 or ys.max() == h - 1 or xs.max() == w - 1
        if touches_border or comp.sum() < 80:
            keep[comp] = 0

    keep = cv2.dilate(keep, np.ones((3, 3), np.uint8))
    keep = cv2.GaussianBlur(keep, (5, 5), 0)

    crop[:, :, 3] = keep
    # save at original coordinates on a full transparent canvas (in-place mode)
    full = np.zeros_like(img)
    full[y0:y1, x0:x1] = crop
    Image.fromarray(full.astype(np.uint8)).save(out_path)
    print(f"{out_path}: box={box}, opaque px={int((keep > 128).sum())}")

for src, box, out in JOBS:
    extract(os.path.join(ASSETS, src), box, os.path.join(PARTS, out))
