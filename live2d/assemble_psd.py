"""Assemble in-place decomposed parts (v2) into a Live2D-ready layered PSD.

Every part in parts_v2/ is the ORIGINAL 1024x1024 composition with everything
except that part erased to green, so assembly is a straight stack at identical
coordinates — no placement guessing. Output canvas is 2x for rigging headroom.
"""
import os
import numpy as np
import cv2
from PIL import Image
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer
from psd_tools.constants import Compression

BASE = os.path.dirname(os.path.abspath(__file__))
PARTS_DIR = os.path.join(BASE, "parts_v2")
OUT_PSD = os.path.join(BASE, "flamingo_live2d.psd")
OUT_PSD_25D = os.path.join(BASE, "flamingo_anime25d.psd")  # Anime2.5DRig naming
OUT_PREVIEW = os.path.join(BASE, "preview.png")
OUT_COMPARE = os.path.join(BASE, "compare.png")
ORIGINAL = os.path.join(BASE, "..", "assets", "1_green_idle.png")
TALK = os.path.join(BASE, "..", "assets", "2_green_talk.png")

SCALE = 2
SRC = 1024
CANVAS = SRC * SCALE

# layer order, bottom -> top (occlusion identical to the original composition).
# AI-infilled pixels (originally hidden) are split off and pushed behind their
# occluders so the resting composite reproduces the original exactly.
LAYERS = [
    "body_fill",     # AI-filled collar/chest (was hidden behind neck & wings)
    "head_base",
    "eye_open",
    "eye_closed",
    "mouth_inside",  # clipped to beak silhouette (comes from the open-beak pose)
    "lower_beak",    # AI-extended part clipped to upper beak
    "upper_beak",
    "hair_front",
    "body_visible",  # jersey pixels exactly as seen in the original
    "left_arm",
    "right_arm",
]

DIFF_THRESH = 40  # per-pixel mean |rgb diff| below this counts as "same as original"

PREVIEW_SKIP = {"eye_closed"}  # closed-eye layer would cover the open eye in the flat preview

def remove_green(arr):
    """RGBA uint8 -> alpha out green screen, with edge despill."""
    r = arr[:, :, 0].astype(int)
    g = arr[:, :, 1].astype(int)
    b = arr[:, :, 2].astype(int)
    green = (g > 120) & (g > r + 25) & (g > b + 25)
    # respect pre-existing transparency (e.g. extracted eye parts)
    alpha = np.where(green, 0, arr[:, :, 3]).astype(np.uint8)
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

def load_part(name):
    arr = np.array(Image.open(os.path.join(PARTS_DIR, f"{name}.png")).convert("RGBA"))
    assert arr.shape[:2] == (SRC, SRC), f"{name}: expected {SRC}x{SRC}, got {arr.shape}"
    return remove_green(arr)

def visible_fill_split(part, orig):
    """Split a part into (visible-in-original, AI-infilled) by pixel diff."""
    diff = np.abs(part[:, :, :3].astype(int) - orig[:, :, :3].astype(int)).mean(axis=2)
    same = (diff < DIFF_THRESH) & (part[:, :, 3] > 0) & (orig[:, :, 3] > 0)
    # absorb thin anti-aliasing seams into the visible side
    same = cv2.morphologyEx(same.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)) > 0
    visible, fill = part.copy(), part.copy()
    visible[:, :, 3] = np.where(same, part[:, :, 3], 0)
    fill[:, :, 3] = np.where(same, 0, part[:, :, 3])
    return visible, fill

def synth_open_beak(upper, lower, pivot=(445, 425), angle=27.0):
    """Synthesize the OPEN beak from the idle parts: swing the lower beak down
    around its root and fill the swept gap with a mouth-interior color.
    Derived from the idle pose, so alignment with mouth_close is guaranteed."""
    h, w = lower.shape[:2]

    def rotated(a, deg):
        M = cv2.getRotationMatrix2D(pivot, -deg, 1.0)  # negative = swing downward
        return cv2.warpAffine(a, M, (w, h), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))

    lower_open = rotated(lower, angle)

    # mouth cavity = area swept by the lower beak while opening
    sweep = np.zeros((h, w), np.uint8)
    for a_deg in np.arange(0, angle + 1, 2.0):
        sweep |= (rotated(lower, a_deg)[:, :, 3] > 40).astype(np.uint8)
    sweep = cv2.morphologyEx(sweep, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))

    cavity = np.zeros((h, w, 4), np.uint8)
    cavity[:, :, :3] = (142, 48, 66)  # dark mouth red
    cavity[:, :, 3] = sweep * 255
    # slightly darker toward the throat (upper part of the cavity)
    ys, xs = np.where(sweep > 0)
    if len(ys):
        grad = ((ys - ys.min()) / max(1, ys.max() - ys.min()) * 40).astype(np.uint8)
        cavity[ys, xs, 0] = np.maximum(cavity[ys, xs, 0] - (40 - grad), 90)

    return merge(cavity, lower_open, upper)

def merge(*parts_list):
    """Alpha-composite parts (given bottom -> top) into one layer."""
    out = np.zeros_like(parts_list[0]).astype(float)
    for p in parts_list:
        a = p[:, :, 3:4].astype(float) / 255.0
        out[:, :, :3] = p[:, :, :3] * a + out[:, :, :3] * (1 - a)
        out[:, :, 3:4] = np.maximum(out[:, :, 3:4], p[:, :, 3:4])
    return out.astype(np.uint8)

def build():
    orig_src = remove_green(np.array(Image.open(ORIGINAL).convert("RGBA")))
    orig_alpha = orig_src[:, :, 3] > 0

    parts = {}
    body = load_part("body_base")
    parts["body_visible"], parts["body_fill"] = visible_fill_split(body, orig_src)

    for name in ["head_base", "eye_open", "eye_closed", "mouth_inside",
                 "lower_beak", "upper_beak", "hair_front", "left_arm", "right_arm"]:
        parts[name] = load_part(name)

    # mouth interior comes from the open-beak pose: at rest it must hide
    # entirely behind the closed beaks
    beak_union = (parts["upper_beak"][:, :, 3] > 0) | (parts["lower_beak"][:, :, 3] > 0)
    beak_union = cv2.erode(beak_union.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    parts["mouth_inside"][:, :, 3] = np.where(beak_union, parts["mouth_inside"][:, :, 3], 0)

    # lower beak's AI-extended root must not spill outside the upper beak
    lower_full = parts["lower_beak"].copy()  # unclipped, for open-beak synthesis
    lower_vis, lower_fill = visible_fill_split(parts["lower_beak"], orig_src)
    spill = (lower_fill[:, :, 3] > 0) & (parts["upper_beak"][:, :, 3] == 0)
    parts["lower_beak"][:, :, 3] = np.where(spill, 0, parts["lower_beak"][:, :, 3])

    # --- guarantee the resting composite reproduces the original exactly ---
    # 1) each surface part's "visible" pixels take the original RGB verbatim
    # 2) original pixels no part claimed (repainted neck, wing sweep, ...) are
    #    assigned to the part whose visible region is nearest
    surface = ["right_arm", "left_arm", "body_visible", "hair_front",
               "upper_beak", "lower_beak", "eye_open", "head_base"]
    vis_masks = {}
    for name in surface:
        p = parts[name]
        if name == "eye_open":
            vis = p[:, :, 3] > 0  # extracted straight from the original
        else:
            diff = np.abs(p[:, :, :3].astype(int) - orig_src[:, :, :3].astype(int)).mean(axis=2)
            vis = (diff < DIFF_THRESH) & (p[:, :, 3] > 0) & orig_alpha
        vis_masks[name] = vis

    covered = np.zeros_like(orig_alpha)
    for v in vis_masks.values():
        covered |= v
    residual = orig_alpha & ~covered

    # nearest-visible-part assignment via distance transforms
    dists = []
    for name in surface:
        inv = (~vis_masks[name]).astype(np.uint8)
        dists.append(cv2.distanceTransform(inv, cv2.DIST_L2, 3))
    owner = np.argmin(np.stack(dists), axis=0)

    for i, name in enumerate(surface):
        take = vis_masks[name] | (residual & (owner == i))
        p = parts[name]
        p[:, :, :3] = np.where(take[:, :, None], orig_src[:, :, :3], p[:, :, :3])
        p[:, :, 3] = np.where(take, orig_src[:, :, 3], p[:, :, 3])
    print(f"residual px reassigned: {int(residual.sum())}")

    layers = []
    preview = np.zeros((CANVAS, CANVAS, 4), dtype=np.uint8)
    preview[:, :] = (235, 235, 235, 255)

    for name in LAYERS:
        arr = parts[name]
        canvas = cv2.resize(arr, (CANVAS, CANVAS), interpolation=cv2.INTER_CUBIC)
        layers.append((name, canvas))

        if name in PREVIEW_SKIP:
            continue
        a = canvas[:, :, 3:4].astype(float) / 255.0
        preview[:, :, :3] = (canvas[:, :, :3] * a + preview[:, :, :3] * (1 - a)).astype(np.uint8)

    Image.fromarray(preview).save(OUT_PREVIEW)
    print(f"preview -> {OUT_PREVIEW}")

    # side-by-side: original sprite vs assembled stack
    orig = np.array(Image.open(ORIGINAL).convert("RGBA"))
    orig = cv2.resize(orig, (CANVAS, CANVAS), interpolation=cv2.INTER_CUBIC)
    compare = np.concatenate([orig[:, :, :3], preview[:, :, :3]], axis=1)
    Image.fromarray(compare).save(OUT_COMPARE)
    print(f"compare -> {OUT_COMPARE}")

    def write_psd(path, layer_list):
        psd = PSDImage.new(mode="RGBA", size=(CANVAS, CANVAS))
        for name, canvas in layer_list:  # append order: bottom -> top
            ys, xs = np.where(canvas[:, :, 3] > 0)
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            tile = Image.fromarray(canvas[y0:y1, x0:x1])
            psd.append(PixelLayer.frompil(tile, psd, name, int(y0), int(x0), Compression.RLE))
        psd.save(path)
        print(f"psd -> {path} ({CANVAS}x{CANVAS}, {len(layer_list)} layers)")

    write_psd(OUT_PSD, layers)

    # --- Anime2.5DRig variant: merged layers under its naming convention ---
    mouth_open = synth_open_beak(parts["upper_beak"], lower_full)
    Image.fromarray(mouth_open).save(os.path.join(BASE, "mouth_open_debug.png"))

    variant_src = [
        ("face",        parts["head_base"]),
        ("eyelash",     parts["eye_open"]),
        ("eye_close",   parts["eye_closed"]),
        ("mouth_open",  mouth_open),
        ("mouth_close", merge(parts["lower_beak"], parts["upper_beak"])),
        ("front hair",  parts["hair_front"]),
        ("topwear",     merge(parts["body_fill"], parts["body_visible"])),
        ("left_arm",    parts["left_arm"]),
        ("right_arm",   parts["right_arm"]),
    ]
    variant = [(n, cv2.resize(p, (CANVAS, CANVAS), interpolation=cv2.INTER_CUBIC))
               for n, p in variant_src]
    write_psd(OUT_PSD_25D, variant)

if __name__ == "__main__":
    build()
