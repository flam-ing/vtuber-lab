"""치비(파워퍼프풍) 캐릭터 2장(closed/open) -> Anime2.5DRig용 레이어드 PSD.

플랫 컬러 + 굵은 외곽선이라 색 기반 분리가 정확하다. closed.png가 기준 프레임,
open.png에서는 벌린 입만 뽑아 닫힌 입 위치에 정렬한다.

레이어 (아래->위): topwear / face / eyewhite / irides / mouth_open / mouth_close /
handwear_1 / handwear_2
- eyewhite: 흰자 + 빨간 링 + 눈 테두리 검정 (시선 고정부)
- irides: 눈동자 검정 + 내부 하이라이트 (시선 추적으로 움직임)
- eye_close 없음 -> 툴이 범용 감은 눈을 자동 합성 (eyewhite 앵커 필요 -> 충족)
"""
import os
import numpy as np
import cv2
from PIL import Image
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer
from psd_tools.constants import Compression

BASE = os.path.dirname(os.path.abspath(__file__))
CLOSED = os.path.join(BASE, "closed.png")
OPEN = os.path.join(BASE, "open.png")
OUT_PSD = os.path.join(BASE, "chibi_anime25d.psd")
OUT_PREVIEW = os.path.join(BASE, "preview.png")
DEBUG_DIR = os.path.join(BASE, "parts")
os.makedirs(DEBUG_DIR, exist_ok=True)

def load(p):
    return np.array(Image.open(p).convert("RGB")).astype(int)

def comp_masks(mask):
    n, lab, stats, cent = cv2.connectedComponentsWithStats(mask.astype(np.uint8))
    return n, lab, stats, cent

def fill_holes(mask):
    h, w = mask.shape
    ff = np.zeros((h + 2, w + 2), np.uint8)
    inv = (~mask).astype(np.uint8)
    cv2.floodFill(inv, ff, (0, 0), 0)  # 바깥과 연결된 배경을 0으로
    return mask | (inv > 0)

def build():
    img = load(CLOSED)
    H, W, _ = img.shape
    r, g, b = img[:, :, 0], img[:, :, 1], img[:, :, 2]
    lum = (r + g + b) / 3

    # --- 기본 색 마스크 ---
    bg_color = img[5:40, 5:40].reshape(-1, 3).mean(axis=0)
    bg_like = (np.abs(img - bg_color).sum(axis=2) < 60)
    n, lab, _, _ = comp_masks(bg_like)
    border_ids = set(lab[0, :]) | set(lab[-1, :]) | set(lab[:, 0]) | set(lab[:, -1])
    background = np.isin(lab, [i for i in border_ids if i != 0]) & bg_like
    char = ~background

    skin = (np.abs(r - 251) < 30) & (np.abs(g - 196) < 35) & (np.abs(b - 157) < 40) & char
    navy = (b > r + 30) & (b > 80) & (b < 200) & (lum < 150) & char
    black = (lum < 70) & char
    white = (lum > 225) & (np.abs(r - b) < 30) & char
    darkred = (r > 120) & (r < 215) & (g < 70) & (b < 80) & char        # 눈 링
    hairred = (r > 200) & (g < 120) & (b < 70) & char                    # 주황 머리

    # --- 유니폼 (navy 최대 성분 + 구멍 채움: 줄무늬/로고/칼라 포함) ---
    n, lab, stats, _ = comp_masks(navy)
    jersey_core = lab == (1 + np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    jersey = fill_holes(cv2.dilate(jersey_core.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0)
    jersey &= char & ~skin  # 턱이 침범하지 않게 피부는 제외

    # --- 팔 (머리와 분리된 피부 성분) ---
    n, lab, stats, cent = comp_masks(skin & ~jersey)
    order = np.argsort(stats[1:, cv2.CC_STAT_AREA])[::-1] + 1
    head_skin = lab == order[0]
    arms = []
    for i in order[1:3]:
        if stats[i, cv2.CC_STAT_AREA] < 5000:
            continue
        m = lab == i
        # 팔의 검은 외곽선 포함
        m = fill_holes(cv2.dilate(m.astype(np.uint8), np.ones((13, 13), np.uint8)) > 0) & char & ~jersey
        arms.append((cent[i][0], m))
    arms.sort(key=lambda t: t[0])  # 왼쪽부터

    # --- 눈: 이 그림체는 눈 전체가 하나의 큰 검정 덩어리(안에 링·흰자·하이라이트).
    # 위쪽 절반에서 "크고 뭉툭한" 검정 성분 2개 = 눈알. 머리 윤곽선 네트워크는
    # 가로로 길게 퍼져 있어 bbox 폭으로 걸러진다. 눈알 통째 -> eyewhite 레이어
    # (앵커 확보용; 시선 추적은 이 그림체에선 분리 불가라 생략).
    # 눈·눈썹·머리 윤곽선이 한 성분으로 이어져 있으므로, 침식으로 얇은
    # 연결선(윤곽 스트로크)을 끊고 뚱뚱한 눈 코어 2개만 남긴다.
    blk_up = black.copy()
    blk_up[int(H * 0.62):, :] = False
    R = 14
    ero = cv2.erode(blk_up.astype(np.uint8),
                    cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * R + 1, 2 * R + 1))) > 0
    n, lab, stats, _ = comp_masks(ero)
    order = np.argsort(stats[1:, cv2.CC_STAT_AREA])[::-1] + 1
    eyes = []
    wr = white | darkred  # 흰자·빨간 링
    n_wr, lab_wr, _, _ = comp_masks(wr)
    for i in order[:2]:
        if stats[i, cv2.CC_STAT_AREA] < 3000:
            continue
        core = lab == i
        grown = cv2.dilate(core.astype(np.uint8),
                           cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                                     (2 * R + 7, 2 * R + 7))) > 0
        mass = grown & blk_up
        # 검정 덩어리에 접촉한 흰자·링 성분을 흡수한 뒤 채워서 눈알 완성
        near = cv2.dilate(mass.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
        ids = set(np.unique(lab_wr[near & wr])) - {0}
        full = mass | np.isin(lab_wr, list(ids))
        full = cv2.morphologyEx(full.astype(np.uint8), cv2.MORPH_CLOSE,
                                np.ones((9, 9), np.uint8)) > 0
        eyes.append(fill_holes(full))
    eye_mask = np.zeros((H, W), bool)
    for e in eyes:
        eye_mask |= e
    eyewhite = eye_mask

    # --- 입 (closed: 웃는 곡선 / open: open.png에서 색으로) ---
    # ROI: 눈 세로중심 ~ 눈 최하단+10%H, 두 눈 중심 사이 (팔/손목 배제)
    ecs = []
    for e in eyes:
        ys_e, xs_e = np.where(e)
        ecs.append((xs_e.mean(), ys_e.mean(), ys_e.max()))
    ey0 = int(min(c[1] for c in ecs)) if ecs else int(H * 0.45)
    ey1 = int(max(c[2] for c in ecs) + 0.10 * H) if ecs else int(H * 0.72)
    ex0 = int(min(c[0] for c in ecs) * 0.98) if ecs else int(W * 0.35)
    ex1 = int(max(c[0] for c in ecs) * 1.04) if ecs else int(W * 0.68)
    mouth_roi = np.zeros((H, W), bool)
    mouth_roi[ey0:ey1, ex0:ex1] = True

    oimg = load(OPEN)
    orr, org, orb = oimg[:, :, 0], oimg[:, :, 1], oimg[:, :, 2]
    # 입안 색: 진빨강/분홍 모두 b>40 — 머리 주황(b<25)과 구분된다
    o_red = (orr > 120) & (org < 110) & (orb > 40) & (orb < 170)
    o_pink = (orr > 190) & (org > 80) & (org < 170) & (orb > 100) & (orb < 200)
    seed = o_red | o_pink
    roi_o = np.zeros((H, W), bool)
    roi_o[int(H * 0.40):int(H * 0.80), int(W * 0.28):int(W * 0.74)] = True
    seed &= roi_o
    o_skin = (np.abs(orr - 251) < 30) & (np.abs(org - 196) < 35) & (np.abs(orb - 157) < 40)
    n, lab, stats, cent = comp_masks(cv2.morphologyEx(seed.astype(np.uint8),
                                     cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8)) > 0)
    # 입은 피부에 둘러싸이고 로고는 navy에 둘러싸인다: 피부 링 비율 최대 성분
    core, best_ring = None, 0.15
    for i in np.argsort(stats[1:, cv2.CC_STAT_AREA])[::-1] + 1:
        if stats[i, cv2.CC_STAT_AREA] < 1500:
            break
        m = lab == i
        ring = (cv2.dilate(m.astype(np.uint8), np.ones((31, 31), np.uint8)) > 0) & ~m
        sr = o_skin[ring].mean()
        if sr > best_ring:
            core, best_ring = m, sr
    if core is None:
        raise RuntimeError("open mouth not found")
    # 입 주위 검정 테두리 포함
    olum = (orr + org + orb) / 3
    rim = (cv2.dilate(core.astype(np.uint8), np.ones((25, 25), np.uint8)) > 0) & (olum < 70)
    o_mouth = fill_holes(core | rim)
    ob = cv2.boundingRect(o_mouth.astype(np.uint8))
    o_cx, o_cy = ob[0] + ob[2] / 2, ob[1] + ob[3] / 2

    # 닫힌 입(웃는 곡선) = ROI 내 검정 성분 중 "벌린 입 위치"에 가장 가까운 것.
    # (두 이미지는 거의 정렬돼 있어 입끼리는 수십 px 이내)
    n, lab, stats, cent = comp_masks((black & mouth_roi & ~eye_mask & ~jersey).astype(np.uint8) > 0)
    mouth_close_mask = np.zeros((H, W), bool)
    best = None
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        bw, bh = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        if not (300 < area < 16000 and bw < W * 0.25 and bh < H * 0.12):
            continue
        d = np.hypot(cent[i][0] - o_cx, cent[i][1] - o_cy)
        if best is None or d < best[0]:
            best = (d, i)
    if best:
        mouth_close_mask = lab == best[1]
        print(f"mouth_close pick: dist={best[0]:.0f}px")
    else:
        print("!! mouth_close not found in ROI")
    mc_bb = cv2.boundingRect(mouth_close_mask.astype(np.uint8))  # x,y,w,h

    # 벌린 입을 닫힌 입 위치로 이동: 윗변을 웃는 곡선 위치에 맞춤
    dx = (mc_bb[0] + mc_bb[2] / 2) - (ob[0] + ob[2] / 2)
    dy = mc_bb[1] - ob[1] - 6
    M = np.float32([[1, 0, dx], [0, 1, dy]])

    # --- 레이어 RGBA 생성 ---
    def to_rgba(mask, src=img, fillcolor=None):
        out = np.zeros((H, W, 4), np.uint8)
        out[:, :, :3] = np.clip(src, 0, 255).astype(np.uint8)
        if fillcolor is not None:
            out[:, :, :3] = np.where(mask[:, :, None], out[:, :, :3], fillcolor)
        a = (mask * 255).astype(np.uint8)
        a = cv2.GaussianBlur(a, (3, 3), 0)
        out[:, :, 3] = a
        return out

    # 얼굴: 머리 전체(피부+머리카락+윤곽선). 유니폼·팔은 살짝 팽창시켜 빼서
    # 외곽선 찌꺼기로 이어지는 걸 끊고, 최대 성분(머리)만 남긴다.
    cut = cv2.dilate(jersey.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
    for _, m in arms:
        cut |= cv2.dilate(m.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
    face_mask = char & ~cut
    n, lab, stats, _ = comp_masks(face_mask)
    face_mask = lab == (1 + np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    covered = cv2.dilate((eye_mask | mouth_close_mask).astype(np.uint8),
                         np.ones((3, 3), np.uint8)) > 0
    face_rgb = np.where(covered[:, :, None], [251, 196, 157], img)
    face = to_rgba(face_mask, src=face_rgb)

    open_rgba = to_rgba(o_mouth, src=oimg)
    open_rgba = cv2.warpAffine(open_rgba, M, (W, H), flags=cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))

    layers = [
        ("topwear",     to_rgba(jersey)),
        ("face",        face),
        ("eyewhite",    to_rgba(eyewhite)),
        ("mouth_open",  open_rgba),
        ("mouth_close", to_rgba(mouth_close_mask)),
    ]
    for idx, (_, m) in enumerate(arms):
        layers.append((f"handwear_{idx + 1}", to_rgba(m)))

    psd = PSDImage.new(mode="RGBA", size=(W, H))
    for name, canvas in layers:
        ys, xs = np.where(canvas[:, :, 3] > 0)
        if not len(ys):
            print(f"!! {name}: empty, skipped")
            continue
        tile = Image.fromarray(canvas[ys.min():ys.max() + 1, xs.min():xs.max() + 1])
        psd.append(PixelLayer.frompil(tile, psd, name, int(ys.min()), int(xs.min()), Compression.RLE))
        Image.fromarray(canvas).save(os.path.join(DEBUG_DIR, f"{name}.png"))
        print(f"{name}: {int((canvas[:, :, 3] > 0).sum())}px")
    psd.save(OUT_PSD)
    print(f"psd -> {OUT_PSD}")

    # 프리뷰 (mouth_open 제외 = 평상시)
    prev = np.full((H, W, 4), 235, np.uint8)
    for name, canvas in layers:
        if name == "mouth_open":
            continue
        a = canvas[:, :, 3:4].astype(float) / 255
        prev[:, :, :3] = (canvas[:, :, :3] * a + prev[:, :, :3] * (1 - a)).astype(np.uint8)
    Image.fromarray(prev).save(OUT_PREVIEW)
    print(f"preview -> {OUT_PREVIEW}")

if __name__ == "__main__":
    build()
