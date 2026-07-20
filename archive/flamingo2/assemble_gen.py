"""FLUX 생성 플라밍고 치비 1장 -> Anime2.5DRig용 PSD.

gen_closed_try1.png(부리 닫힘)을 마스터로 색·연결성 분리하고,
벌린 입은 아트의 팔레트·선굵기에 맞춰 합성한다 (정면 부리 특성상
생성보다 합성이 정렬·품질 모두 우위 — 기존 파이프라인 검증 방식).

레이어: topwear / bottomwear(발) / face / eyewhite / mouth_open /
mouth_close(부리) / front hair / handwear_1 / handwear_2
"""
import os
import numpy as np
import cv2
from PIL import Image, ImageDraw
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer
from psd_tools.constants import Compression

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "gen_closed_try1.png")
os.makedirs(os.path.join(BASE, "parts_gen"), exist_ok=True)

FACE_PINK = (255, 156, 162)
INK = (26, 18, 22)
MOUTH = (146, 42, 58)
MOUTH_DK = (112, 30, 44)
TONGUE = (244, 126, 146)

def comp_masks(mask):
    return cv2.connectedComponentsWithStats(mask.astype(np.uint8))

def fill_holes(mask):
    h, w = mask.shape
    ff = np.zeros((h + 2, w + 2), np.uint8)
    inv = (~mask).astype(np.uint8)
    cv2.floodFill(inv, ff, (0, 0), 0)
    return mask | (inv > 0)

def build():
    img = np.array(Image.open(SRC).convert("RGB")).astype(int)
    H, W, _ = img.shape
    r, g, b = img[:, :, 0], img[:, :, 1], img[:, :, 2]
    lum = (r + g + b) / 3

    white_bg = (lum > 242) & (np.abs(r - g) < 10) & (np.abs(g - b) < 10)
    n, lab, _, _ = comp_masks(white_bg)
    border_ids = set(lab[0, :]) | set(lab[-1, :]) | set(lab[:, 0]) | set(lab[:, -1])
    background = np.isin(lab, [i for i in border_ids if i != 0]) & white_bg
    char = ~background

    dark = (lum < 80) & char
    navy = (b > r + 40) & (b > 70) & char
    hair = (r > 235) & (g > 55) & (g < 135) & (b > 70) & (b < 160) & char
    beak_pale = (r > 240) & (g > 175) & (g < 225) & (b > 190) & char

    # --- 눈: 큰 검정 덩어리 2개 (침식 분리) ---
    blk_up = dark.copy()
    blk_up[int(H * 0.62):, :] = False
    R = 10
    ero = cv2.erode(blk_up.astype(np.uint8),
                    cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * R + 1, 2 * R + 1))) > 0
    n, lab, stats, _ = comp_masks(ero)
    order = np.argsort(stats[1:, cv2.CC_STAT_AREA])[::-1] + 1
    eyes = []
    for i in order[:2]:
        if stats[i, cv2.CC_STAT_AREA] < 2000:
            continue
        grown = cv2.dilate((lab == i).astype(np.uint8),
                           cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * R + 9, 2 * R + 9))) > 0
        eyes.append(fill_holes(grown & blk_up))
    eye_mask = np.zeros((H, W), bool)
    for e in eyes:
        eye_mask |= e

    # --- 부리(mouth_close): 연분홍 몸통 먼저 -> 바로 아래 "두꺼운" 검정만 끝으로 ---
    n, lab, stats, cent = comp_masks(beak_pale)
    body = None
    for i in np.argsort(stats[1:, cv2.CC_STAT_AREA])[::-1] + 1:
        if stats[i, cv2.CC_STAT_AREA] < 3000:
            break
        cx_, cy_ = cent[i]
        if W * 0.40 < cx_ < W * 0.60 and H * 0.40 < cy_ < H * 0.64:
            body = lab == i
            break
    if body is None:
        raise RuntimeError("beak body not found")
    pys, pxs = np.where(body)
    pb_x0, pb_x1, pb_y1 = pxs.min(), pxs.max(), pys.max()

    dark_bk = dark & (b < 60)   # 진짜 검정만 (네이비 유니폼 제외)

    # 부리 영역 한계 박스 (칼라로 새지 않게)
    limit = np.zeros((H, W), bool)
    limit[max(0, pys.min() - 30):min(H, pb_y1 + 190),
          max(0, pb_x0 - 35):min(W, pb_x1 + 35)] = True

    # 두꺼운 검정 코어(얇은 칼라 외곽선은 침식으로 소멸)
    dark_core = cv2.erode(dark_bk.astype(np.uint8),
                          cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))) > 0
    strip = np.zeros((H, W), bool)
    strip[pb_y1 - 15:min(H, pb_y1 + 150), max(0, pb_x0 - 15):min(W, pb_x1 + 15)] = True
    n2, lab2, st2, _ = comp_masks(dark_core & strip & ~eye_mask)
    tip_core = np.zeros((H, W), bool)
    for i in range(1, n2):
        if st2[i, cv2.CC_STAT_AREA] > 300:
            tip_core |= lab2 == i
    tip = (cv2.dilate(tip_core.astype(np.uint8),
                      cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (19, 19))) > 0) \
        & dark_bk & limit & ~eye_mask

    core = body | tip
    ring = (cv2.dilate(core.astype(np.uint8), np.ones((21, 21), np.uint8)) > 0) \
        & dark_bk & limit & ~eye_mask
    beak = fill_holes(cv2.morphologyEx((core | ring).astype(np.uint8), cv2.MORPH_CLOSE,
                                       np.ones((9, 9), np.uint8)) > 0)

    # --- 유니폼 / 날개 / 발 ---
    n, lab, stats, _ = comp_masks(navy)
    jersey_core = lab == (1 + np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    jersey = fill_holes(cv2.dilate(jersey_core.astype(np.uint8), np.ones((11, 11), np.uint8)) > 0)
    jersey &= char & ~beak

    pinkish = char & ~jersey & ~eye_mask & ~beak & ~hair & (r > 200) & (g > 90)
    n, lab, stats, cent = comp_masks(pinkish)
    order = np.argsort(stats[1:, cv2.CC_STAT_AREA])[::-1] + 1
    head_skin = lab == order[0]
    wings, feet = [], np.zeros((H, W), bool)
    for i in order[1:6]:
        if stats[i, cv2.CC_STAT_AREA] < 3000:
            continue
        m = fill_holes(cv2.dilate((lab == i).astype(np.uint8), np.ones((13, 13), np.uint8)) > 0) \
            & char & ~jersey
        cx, cy = cent[i]
        if cy > H * 0.85:
            feet |= m
        else:
            wings.append((cx, m))
    wings.sort(key=lambda t: t[0])

    # --- face: 머리 전체(헤어 제외·헤어라인 안쪽은 살구색 채움) ---
    cut = cv2.dilate((jersey | feet).astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
    for _, m in wings:
        cut |= cv2.dilate(m.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
    head_all = char & ~cut
    n, lab, stats, _ = comp_masks(head_all)
    head_all = lab == (1 + np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    hair_full = fill_holes(cv2.morphologyEx((hair & head_all).astype(np.uint8),
                                            cv2.MORPH_CLOSE, np.ones((13, 13), np.uint8)) > 0)
    hair_full |= (cv2.dilate(hair_full.astype(np.uint8), np.ones((15, 15), np.uint8)) > 0) & dark
    hairless = head_all & ~hair_full
    fill_zone = hair_full & (cv2.dilate(hairless.astype(np.uint8), np.ones((81, 81), np.uint8)) > 0)
    face_mask = hairless | fill_zone
    face_rgb = img.copy()
    covered = cv2.dilate((eye_mask | beak).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    face_rgb = np.where((covered | fill_zone)[:, :, None], FACE_PINK, face_rgb)

    # --- mouth_open 합성: 같은 부리가 "살짝 벌어진" 모양 ---
    # 윗부리(연분홍 몸통)는 위로, 아랫부리(검은 끝)는 아래로, 사이에 작은 틈만.
    bys, bxs = np.where(beak)
    bx0, bx1, by0, by1 = bxs.min(), bxs.max(), bys.min(), bys.max()
    bw_, bh_ = bx1 - bx0, by1 - by0
    cx = (bx0 + bx1) / 2

    tip_full = tip | ((cv2.dilate(tip.astype(np.uint8), np.ones((13, 13), np.uint8)) > 0)
                      & dark_bk & beak)
    upper_full = beak & ~tip_full
    ty0 = np.where(tip_full)[0].min()
    UP_SHIFT, DOWN_SHIFT = 14, int(bh_ * 0.24)

    def shifted(mask, dy):
        out = np.zeros((H, W, 4), np.uint8)
        out[:, :, :3] = img
        out[:, :, 3] = np.where(mask, 255, 0)
        M = np.float32([[1, 0, 0], [0, 1, dy]])
        return cv2.warpAffine(out, M, (W, H), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))

    upper_img = shifted(upper_full, -UP_SHIFT)
    lower_img = shifted(tip_full, DOWN_SHIFT)

    # 틈: 부리 폭보다 좁은 작은 둥근 렌즈 (부리 실루엣에서 크게 안 벗어남)
    mo_final = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(mo_final)
    gw = bw_ * 0.44
    gy0, gy1 = ty0 - UP_SHIFT - 6, ty0 + DOWN_SHIFT + 26
    d.ellipse([cx - gw, gy0, cx + gw, gy1], fill=MOUTH, outline=INK, width=10)
    d.ellipse([cx - gw + 10, gy0 + 8, cx + gw - 10, gy0 + (gy1 - gy0) * 0.42], fill=MOUTH_DK)
    tw = gw * 0.9
    d.ellipse([cx - tw / 2, gy1 - (gy1 - gy0) * 0.42, cx + tw / 2, gy1 - 8],
              fill=TONGUE, outline=(150, 50, 70), width=6)
    mo_final.alpha_composite(Image.fromarray(lower_img))
    mo_final.alpha_composite(Image.fromarray(upper_img))

    # --- 레이어 구성 ---
    def to_rgba(mask, src=img):
        out = np.zeros((H, W, 4), np.uint8)
        out[:, :, :3] = np.clip(src, 0, 255).astype(np.uint8)
        a = (mask * 255).astype(np.uint8)
        out[:, :, 3] = cv2.GaussianBlur(a, (3, 3), 0)
        return out

    layers = [
        ("topwear", to_rgba(jersey)),
        ("bottomwear", to_rgba(feet)),
        ("face", to_rgba(face_mask, src=face_rgb)),
        ("eyewhite", to_rgba(eye_mask)),
        ("mouth_open", np.array(mo_final)),
        ("mouth_close", to_rgba(beak)),
        ("front hair", to_rgba(hair_full)),
    ]
    for idx, (_, m) in enumerate(wings[:2]):
        layers.append((f"handwear_{idx + 1}", to_rgba(m)))

    psd = PSDImage.new(mode="RGBA", size=(W, H))
    closed = Image.new("RGBA", (W, H), (235, 235, 235, 255))
    opened = Image.new("RGBA", (W, H), (235, 235, 235, 255))
    for name, canvas in layers:
        a = canvas[:, :, 3]
        if not (a > 0).any():
            print(f"!! {name}: empty")
            continue
        ys, xs = np.where(a > 0)
        tile = Image.fromarray(canvas[ys.min():ys.max() + 1, xs.min():xs.max() + 1])
        psd.append(PixelLayer.frompil(tile, psd, name, int(ys.min()), int(xs.min()), Compression.RLE))
        Image.fromarray(canvas).save(os.path.join(BASE, "parts_gen", f"{name.replace(' ', '_')}.png"))
        if name != "mouth_open":
            closed.alpha_composite(Image.fromarray(canvas))
        if name != "mouth_close":
            opened.alpha_composite(Image.fromarray(canvas))
        print(f"{name}: {int((a > 0).sum())}px")
    psd.save(os.path.join(BASE, "flamingo_gen.psd"))
    side = Image.new("RGB", (W * 2, H), (235, 235, 235))
    side.paste(closed.convert("RGB"), (0, 0))
    side.paste(opened.convert("RGB"), (W, 0))
    side.save(os.path.join(BASE, "preview_gen.png"))
    print("psd -> flamingo_gen.psd / preview_gen.png")

if __name__ == "__main__":
    build()
