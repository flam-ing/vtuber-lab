"""v4: AI가 그린 독립 파츠 시트 1장 → 절단 → 배경 제거 → 원본 포즈 위치에 배치 → 레이어드 PSD.

원본과 픽셀 일치는 요구하지 않는다. 각 파츠를 원본 스프라이트에서 그 부위가 차지하던
bbox(parts_v3 알파에서 계산)에 비율 유지로 끼워 넣고, OVERRIDES로 미세조정한다.
"""
import os
import sys
import numpy as np
import cv2
from PIL import Image
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer
from psd_tools.constants import Compression

BASE = os.path.dirname(os.path.abspath(__file__))
SHEET = os.path.join(BASE, "parts_sheet.png")
V3 = os.path.join(BASE, "parts_v3")          # 목표 bbox 계산용 (픽셀은 안 씀)
ORIGINAL = os.path.join(BASE, "..", "assets", "1_green_idle.png")
PARTS_V4 = os.path.join(BASE, "parts_v4")    # 절단 결과 확인용

# 캔버스 크기를 인자로 조절 가능: `assemble_v4.py 1024` -> *_1024.psd
CANVAS = int(sys.argv[1]) if len(sys.argv) > 1 else 2048
SUF = "" if CANVAS == 2048 else f"_{CANVAS}"
OUT_PSD = os.path.join(BASE, f"flamingo_live2d{SUF}.psd")
OUT_PSD_25D = os.path.join(BASE, f"flamingo_anime25d{SUF}.psd")
OUT_PREVIEW = os.path.join(BASE, f"preview{SUF}.png")
OUT_COMPARE = os.path.join(BASE, f"compare{SUF}.png")
BBOX_SCALE = CANVAS / 1024  # v3 bbox(1024 공간) -> 캔버스 좌표

# 시트 그리드 (1536x1024 기준, 구분선 검출값): (x0, y0, x1, y1)
COLS = [(22, 326), (365, 703), (767, 1090), (1153, 1474)]
ROWS = [(23, 265), (281, 460), (482, 746)]
CELLS = {  # (row, col) -> 파츠명
    (0, 0): "right_arm",  (0, 1): "left_arm",    (0, 2): "body_visible", (0, 3): "hair_front",
    (1, 0): "upper_beak", (1, 1): "lower_beak",  (1, 2): "mouth_inside", (1, 3): "eye_closed",
    (2, 0): "eye_open",   (2, 1): "head_base",   (2, 2): "body_fill",    # (2,3)=원본 참고
}

# 배치 목표 bbox의 소스: v4 파츠명 -> v3 파일명
TARGET_SRC = {
    "body_visible": "body_base", "body_fill": "body_base",
}

# contain-fit 후 미세조정: 파츠명 -> (dx, dy, scale 배율) — 1024 공간 단위
OVERRIDES = {
    "body_fill": (0, -20, 1.15),   # 전체 유니폼: 살짝 크게, 목 뒤로 올림
    "mouth_inside": (0, 0, 0.9),
}

LAYERS = [  # 아래 -> 위
    "body_fill", "head_base", "eye_open", "eye_closed", "body_visible",
    "mouth_inside", "lower_beak", "upper_beak", "hair_front", "left_arm", "right_arm",
]
PREVIEW_SKIP = {"eye_closed", "mouth_inside"}  # 평상시 안 보이는 상태 레이어

def cut_cell(sheet, row, col, punch_pale=False, enclosed_fill="inpaint"):
    """셀 크롭 -> 체커보드/여백/라벨 제거 -> 파츠 RGBA (tight crop)."""
    x0, x1 = COLS[col]
    y0, y1 = ROWS[row]
    cell = sheet[y0:y1, x0:x1]
    rgb = cell[:, :, :3].astype(int)
    lum = rgb.mean(axis=2)
    sat = rgb.max(axis=2) - rgb.min(axis=2)
    bg_like = (sat < 14) & (lum > 183)  # 체커보드 회색 2색 + 흰 여백/라벨 배경

    # 체커보드 두 톤 추정 (bg_like 픽셀 밝기의 상/하위 절반 중앙값)
    vals = lum[bg_like]
    mid = (vals.min() + vals.max()) / 2
    tone_lo, tone_hi = np.median(vals[vals <= mid]), np.median(vals[vals > mid])

    def is_checker(mask):
        """체커보드 판별: 반주기 P 이동 시 반전, 2P 이동 시 일치 (자기상관).
        균일한 흰 아트나 1방향 줄무늬는 통과하지 못한다."""
        P = 8  # 체커 반주기(px). 시트 렌더 해상도 기준
        ys, xs = np.where(mask)
        if len(ys) < (2 * P) ** 2:
            return False
        y0c, y1c, x0c, x1c = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        v = lum[y0c:y1c, x0c:x1c]
        m = mask[y0c:y1c, x0c:x1c]
        b = v > np.median(v[m])

        def agree(dy, dx):
            mm = m & np.roll(m, (dy, dx), (0, 1))
            if mm.sum() < 30:
                return 0.5
            return (b == np.roll(b, (dy, dx), (0, 1)))[mm].mean()

        sx = agree(0, 2 * P) - agree(0, P)
        sy = agree(2 * P, 0) - agree(P, 0)
        return min(sx, sy) > 0.15

    # 배경 = 테두리와 연결된 bg_like 성분만. 파츠 안에 갇힌 밝은 영역(눈 흰자,
    # 반투명으로 비친 체커)은 여기서 지우지 않고 아래에서 따로 처리한다.
    n, labels = cv2.connectedComponents(bg_like.astype(np.uint8))
    border_ids = set(labels[0, :]) | set(labels[-1, :]) | set(labels[:, 0]) | set(labels[:, -1])
    background = np.isin(labels, [b for b in border_ids if b != 0])
    fg = ~background

    # 파츠 본체 = 가장 큰 성분. 라벨 텍스트/번호 배지는 셀 상단 밴드에 있으므로 제거
    fg = cv2.morphologyEx(fg.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(fg)
    if n <= 1:
        raise RuntimeError(f"cell ({row},{col}): no foreground")
    main = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    keep = np.zeros(fg.shape, bool)
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        label_band = y + h < 52 and h < 46          # 상단 라벨 칩 영역
        if i == main or (area > 120 and not label_band):
            keep |= labels == i

    # 창백한 파츠 가장자리가 배경으로 오분류돼 생기는 "물린 자국" 메꿈
    keep = cv2.morphologyEx(keep.astype(np.uint8), cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))) > 0

    out = cell.copy()

    # 파츠 안에 갇힌 밝은 영역 처리:
    #  - 균일(std<5) = 진짜 흰 아트(눈 흰자, 유니폼 줄무늬) → 그대로
    #  - 불균일 = 반투명 렌더로 비친 체커보드 → 재도색
    #    (enclosed_fill='white'면 흰색으로, 아니면 주변색 inpaint)
    enclosed = bg_like & keep
    n2, lab2 = cv2.connectedComponents(enclosed.astype(np.uint8))
    repaint = np.zeros(enclosed.shape, bool)
    for i in range(1, n2):
        comp = lab2 == i
        if is_checker(comp):
            repaint |= comp
    if punch_pale:
        # head_base 전용: 얼굴 안의 큰 창백 영역 = 눈 구멍 → 뚫는다 (재도색 X)
        pale = (lum > 200) & keep
        n3, lab3, st3, _ = cv2.connectedComponentsWithStats(pale.astype(np.uint8))
        for i in range(1, n3):
            if st3[i, cv2.CC_STAT_AREA] > 250:
                hole = lab3 == i
                keep &= ~hole
                repaint &= ~hole
    if repaint.any():
        if enclosed_fill == "white":
            out[:, :, :3] = np.where(repaint[:, :, None], 250, out[:, :, :3])
        else:
            fixed = cv2.inpaint(out[:, :, :3], repaint.astype(np.uint8), 5, cv2.INPAINT_TELEA)
            out[:, :, :3] = np.where(repaint[:, :, None], fixed, out[:, :, :3])

    alpha = (keep * 255).astype(np.uint8)
    alpha = cv2.erode(alpha, np.ones((2, 2), np.uint8))
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
    out[:, :, 3] = alpha
    ys, xs = np.where(alpha > 10)
    return out[ys.min():ys.max() + 1, xs.min():xs.max() + 1]

def cut_eye(sheet, row, col):
    """눈 전용 절단: 외곽선 틈으로 흰자가 배경과 이어지고 홍채가 반투명이라
    일반 절단이 망가진다. 어두운 선화+채색만 뽑고 구멍을 메꿔 형태를 복원한 뒤
    흰자/홍채를 평탄화한다."""
    x0, x1 = COLS[col]
    y0, y1 = ROWS[row]
    cell = sheet[y0:y1, x0:x1]
    rgb = cell[:, :, :3].astype(int)
    lum = rgb.mean(axis=2)
    sat = rgb.max(axis=2) - rgb.min(axis=2)

    art = (lum < 165) | (sat > 25)      # 선화·홍채·핑크 액센트
    art[:60] = False                     # 라벨 칩 제거
    art = cv2.morphologyEx(art.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)) > 0

    # 형태 = 아트 + 그 안에 갇힌 영역(흰자)
    n, labels = cv2.connectedComponents((~art).astype(np.uint8))
    border_ids = set(labels[0, :]) | set(labels[-1, :]) | set(labels[:, 0]) | set(labels[:, -1])
    outside = np.isin(labels, [b for b in border_ids if b != 0])
    shape = art | ~outside

    out = cell.copy()
    sclera = shape & (lum >= 183) & (sat < 25)
    iris = shape & (lum >= 90) & (lum < 183) & (sat < 25)
    out[:, :, :3] = np.where(sclera[:, :, None], 250, out[:, :, :3])
    out[:, :, :3][iris] = (48, 48, 58)

    alpha = (shape * 255).astype(np.uint8)
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
    out[:, :, 3] = alpha
    ys, xs = np.where(alpha > 10)
    return out[ys.min():ys.max() + 1, xs.min():xs.max() + 1]

def v3_bbox(name):
    a = np.array(Image.open(os.path.join(V3, f"{name}.png")).convert("RGBA"))[:, :, 3]
    ys, xs = np.where(a > 128)
    return xs.min(), ys.min(), xs.max(), ys.max()  # 1024 공간

def place_at(part, cx, cy, tw, th, fit="contain"):
    """파츠를 캔버스 좌표 (cx,cy) 중심의 tw×th 박스에 비율 유지로 배치."""
    h, w = part.shape[:2]
    s = (min if fit == "contain" else max)(tw / w, th / h)
    nw, nh = max(1, round(w * s)), max(1, round(h * s))
    scaled = cv2.resize(part, (nw, nh), interpolation=cv2.INTER_LANCZOS4 if s > 1 else cv2.INTER_AREA)

    canvas = np.zeros((CANVAS, CANVAS, 4), np.uint8)
    px, py = round(cx - nw / 2), round(cy - nh / 2)
    sx0, sy0 = max(0, -px), max(0, -py)
    px, py = max(0, px), max(0, py)
    canvas[py:py + nh - sy0, px:px + nw - sx0] = scaled[sy0:, sx0:][:CANVAS - py, :CANVAS - px]
    return canvas

def place(part, name):
    """v3 알파 bbox(원본 포즈의 그 부위 자리)에 contain-fit + OVERRIDES."""
    x0, y0, x1, y1 = v3_bbox(TARGET_SRC.get(name, name))
    dx, dy, mul = OVERRIDES.get(name, (0, 0, 1.0))
    cx, cy = ((x0 + x1) / 2 + dx) * BBOX_SCALE, ((y0 + y1) / 2 + dy) * BBOX_SCALE
    tw, th = (x1 - x0) * mul * BBOX_SCALE, (y1 - y0) * mul * BBOX_SCALE
    return place_at(part, cx, cy, tw, th)

def merge(*layers):
    out = np.zeros_like(layers[0]).astype(float)
    for p in layers:
        a = p[:, :, 3:4].astype(float) / 255.0
        out[:, :, :3] = p[:, :, :3] * a + out[:, :, :3] * (1 - a)
        out[:, :, 3:4] = np.maximum(out[:, :, 3:4], p[:, :, 3:4])
    return out.astype(np.uint8)

def write_psd(path, layer_list):
    psd = PSDImage.new(mode="RGBA", size=(CANVAS, CANVAS))
    for name, canvas in layer_list:
        ys, xs = np.where(canvas[:, :, 3] > 0)
        tile = Image.fromarray(canvas[ys.min():ys.max() + 1, xs.min():xs.max() + 1])
        psd.append(PixelLayer.frompil(tile, psd, name, int(ys.min()), int(xs.min()), Compression.RLE))
    psd.save(path)
    print(f"psd -> {path} ({len(layer_list)} layers)")

def build():
    os.makedirs(PARTS_V4, exist_ok=True)
    sheet = np.array(Image.open(SHEET).convert("RGBA"))

    cuts, placed = {}, {}
    for (r, c), name in CELLS.items():
        if name.startswith("eye"):
            part = cut_eye(sheet, r, c)
        else:
            part = cut_cell(sheet, r, c, punch_pale=(name == "head_base"))
        Image.fromarray(part).save(os.path.join(PARTS_V4, f"{name}.png"))
        cuts[name] = part
        placed[name] = place(part, name)
        print(f"{name}: cut {part.shape[1]}x{part.shape[0]}")

    # 눈은 v3 좌표가 아니라 "새 머리의 눈 구멍" 위치·크기에 맞춘다
    head = placed["head_base"]
    head_a = head[:, :, 3] < 10
    n, labels = cv2.connectedComponents(head_a.astype(np.uint8))
    outside = {labels[0, 0], labels[0, -1], labels[-1, 0], labels[-1, -1]}
    holes = [(int((labels == i).sum()), i) for i in range(1, n) if i not in outside]
    if holes:
        _, hole_id = max(holes)
        hole = labels == hole_id
        ys, xs = np.where(hole)
        hcx, hcy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
        hw, hh = xs.max() - xs.min(), ys.max() - ys.min()
        print(f"eye hole in head: center=({hcx:.0f},{hcy:.0f}) {hw}x{hh}")
        # 구멍은 살색으로 메꿔 두고 (가장자리 투명 누출 방지) 눈을 그 위에 올린다
        grow = cv2.dilate(hole.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
        head[:, :, :3] = cv2.inpaint(head[:, :, :3], grow.astype(np.uint8), 9, cv2.INPAINT_TELEA)
        head[:, :, 3] = np.where(hole, 255, head[:, :, 3])
        for e in ["eye_open", "eye_closed"]:
            placed[e] = place_at(cuts[e], hcx, hcy, hw * 1.25, hh * 1.25, fit="contain")

    # body_fill이 셔츠 밑단 아래로 삐져나오지 않게 클리핑
    ys, _ = np.where(placed["body_visible"][:, :, 3] > 0)
    placed["body_fill"][ys.max() - 6:, :, 3] = 0

    layers = [(n, placed[n]) for n in LAYERS]
    write_psd(OUT_PSD, layers)

    preview = np.zeros((CANVAS, CANVAS, 4), np.uint8)
    preview[:, :] = (235, 235, 235, 255)
    for name, canvas in layers:
        if name in PREVIEW_SKIP:
            continue
        a = canvas[:, :, 3:4].astype(float) / 255.0
        preview[:, :, :3] = (canvas[:, :, :3] * a + preview[:, :, :3] * (1 - a)).astype(np.uint8)
    Image.fromarray(preview).save(OUT_PREVIEW)

    orig = cv2.resize(np.array(Image.open(ORIGINAL).convert("RGBA")), (CANVAS, CANVAS))
    Image.fromarray(np.concatenate([orig[:, :, :3], preview[:, :, :3]], axis=1)).save(OUT_COMPARE)
    print(f"preview/compare -> {OUT_PREVIEW}")

    # Anime2.5DRig 변형: mouth_open = 입안 + 아랫부리 27도 회전 + 윗부리
    lb = placed["lower_beak"]
    ys, xs = np.where(lb[:, :, 3] > 40)
    pivot = (float(xs.max()), float(ys.min()))  # 부리 뿌리(오른쪽 위)
    M = cv2.getRotationMatrix2D(pivot, -27, 1.0)
    lb_open = cv2.warpAffine(lb, M, (CANVAS, CANVAS), flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    mouth_open = merge(placed["mouth_inside"], lb_open, placed["upper_beak"])

    write_psd(OUT_PSD_25D, [
        ("face", placed["head_base"]),
        ("eyelash", placed["eye_open"]),
        ("eye_close", placed["eye_closed"]),
        ("topwear", merge(placed["body_fill"], placed["body_visible"])),
        ("mouth_open", mouth_open),
        ("mouth_close", merge(placed["lower_beak"], placed["upper_beak"])),
        ("front hair", placed["hair_front"]),
        ("left_arm", placed["left_arm"]),
        ("right_arm", placed["right_arm"]),
    ])

if __name__ == "__main__":
    build()
