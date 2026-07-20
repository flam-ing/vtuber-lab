"""Build parts_v3: pure crops from the ORIGINAL sprite.

The v2 AI parts are used ONLY as region maps (which pixel belongs to which
part). Each original pixel is assigned to exactly ONE part (front-most part
wins); occluded areas are reconstructed with OpenCV inpainting from the part's
own pixels — no AI-painted pixel survives.
"""
import os
import numpy as np
import cv2
from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
V2 = os.path.join(BASE, "parts_v2")
V3 = os.path.join(BASE, "parts_v3")
ORIGINAL = os.path.join(BASE, "..", "assets", "1_green_idle.png")
DIFF_THRESH = 40

os.makedirs(V3, exist_ok=True)

def degreen(arr):
    r, g, b = arr[:, :, 0].astype(int), arr[:, :, 1].astype(int), arr[:, :, 2].astype(int)
    out = arr.copy()
    out[:, :, 3] = np.where((g > 120) & (g > r + 25) & (g > b + 25), 0, arr[:, :, 3])
    return out

orig = degreen(np.array(Image.open(ORIGINAL).convert("RGBA")))
orig_rgb = orig[:, :, :3]
orig_alpha = orig[:, :, 3] > 0

PARTS = ["upper_beak", "lower_beak", "hair_front", "left_arm", "right_arm",
         "body_base", "head_base"]

regions, claims = {}, {}
for name in PARTS:
    v2 = degreen(np.array(Image.open(os.path.join(V2, f"{name}.png")).convert("RGBA")))
    region = cv2.morphologyEx((v2[:, :, 3] > 0).astype(np.uint8), cv2.MORPH_CLOSE,
                              np.ones((5, 5), np.uint8)) > 0
    diff = np.abs(v2[:, :, :3].astype(int) - orig_rgb.astype(int)).mean(axis=2)
    claim = region & orig_alpha & (diff < DIFF_THRESH)
    claim = cv2.morphologyEx(claim.astype(np.uint8), cv2.MORPH_CLOSE,
                             np.ones((5, 5), np.uint8)) > 0
    regions[name], claims[name] = region, claim

# --- exclusive pixel ownership ---
taken = np.zeros_like(orig_alpha)
owned = {name: np.zeros_like(orig_alpha) for name in PARTS}

# z-order forced claims: front parts own the pixels they show at rest.
# eye first (belongs to the eye layers; head inpaints feathers behind it),
# then lower jaw before upper_beak (whose v2 region covers the whole beak).
eye = np.array(Image.open(os.path.join(V3, "eye_open.png")).convert("RGBA"))
eye_region = cv2.dilate((eye[:, :, 3] > 40).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
taken |= eye_region
for name in ["lower_beak", "upper_beak", "hair_front", "left_arm", "right_arm"]:
    owned[name] = claims[name] & ~taken
    taken |= owned[name]

# head/body claims are unreliable (v2 copied stray original pixels into both),
# so only conservative seeds are trusted; every remaining original pixel is
# then assigned to whichever part's owned area is nearest (beak tip -> beak,
# claws -> arm, neck -> head, jersey -> body)
r, g, b = orig_rgb[:, :, 0].astype(int), orig_rgb[:, :, 1].astype(int), orig_rgb[:, :, 2].astype(int)
lum = r * 0.3 + g * 0.59 + b * 0.11
jersey_color = ((b > g + 20) & (b > r)) | (lum > 185)  # navy or white stripes
seed_head = claims["head_base"] & ~claims["body_base"] & ~taken
seed_body = claims["body_base"] & ~claims["head_base"] & ~taken & jersey_color
seed_head = cv2.erode(seed_head.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
seed_body = cv2.erode(seed_body.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
owned["head_base"], owned["body_base"] = seed_head, seed_body
taken |= seed_head | seed_body

leftover = orig_alpha & ~taken
dist_stack = np.stack([
    cv2.distanceTransform((~owned[n]).astype(np.uint8), cv2.DIST_L2, 3) for n in PARTS
])
winner = np.argmin(dist_stack, axis=0)
for i, n in enumerate(PARTS):
    owned[n] = owned[n] | (leftover & (winner == i))
taken |= leftover

near_bg = cv2.dilate((~orig_alpha).astype(np.uint8), np.ones((7, 7), np.uint8)) > 0

parts_out = {}
for name in PARTS:
    visible = owned[name]
    region = regions[name] | visible   # include pixels assigned beyond the v2 map
    hidden = region & ~visible

    # inpaint source: the part's own pixels, minus margins near other parts'
    # pixels and near the background so foreign colors don't bleed in
    others = taken & ~visible
    margin = cv2.dilate(others.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    src_ok = visible & ~margin & ~near_bg
    if not src_ok.any():
        src_ok = visible
    filled = cv2.inpaint(orig_rgb, (~src_ok).astype(np.uint8), 7, cv2.INPAINT_TELEA)

    part = np.zeros_like(orig)
    part[:, :, :3] = np.where(visible[:, :, None], orig_rgb, filled)
    alpha = ((region).astype(np.uint8) * 255)
    part[:, :, 3] = cv2.GaussianBlur(alpha, (3, 3), 0)

    parts_out[name] = part
    Image.fromarray(part).save(os.path.join(V3, f"{name}.png"))
    print(f"{name}: region={int(region.sum())}px, owned={int(visible.sum())}px, "
          f"inpainted={int(hidden.sum())}px")

# mouth interior: cavity swept by the lower beak opening (no AI source exists)
lower = parts_out["lower_beak"]
h, w = lower.shape[:2]
PIVOT, ANGLE = (445, 425), 27.0
sweep = np.zeros((h, w), np.uint8)
for a_deg in np.arange(0, ANGLE + 1, 2.0):
    M = cv2.getRotationMatrix2D(PIVOT, -a_deg, 1.0)
    rot = cv2.warpAffine(lower, M, (w, h), flags=cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    sweep |= (rot[:, :, 3] > 40).astype(np.uint8)
sweep = cv2.morphologyEx(sweep, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
cavity = np.zeros((h, w, 4), np.uint8)
cavity[:, :, :3] = (142, 48, 66)
cavity[:, :, 3] = sweep * 255
Image.fromarray(cavity).save(os.path.join(V3, "mouth_inside.png"))
print(f"mouth_inside: cavity={int(sweep.sum())}px (synthesized)")
