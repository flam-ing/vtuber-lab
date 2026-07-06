"""v5: 원본 스프라이트 "제자리 절단" → 가림 영역 인페인트 → 레이어드 PSD.

v4(독립 AI 파츠 끼워맞춤)와 달리 모든 보이는 픽셀은 원본 1_green_idle.png 그대로다.
파츠 마스크로 원본을 분할하고, 파츠가 가리던 뒤쪽(두피·부리 뒤 볼·칼라 뒤 목·팔 뒤 셔츠)만
원본 실루엣 안쪽에서 인페인트로 메꾼다 → 정지 상태 합성이 원본과 픽셀 일치.

눈 감음은 3_green_blink(눈 외 영역 정합 확인됨), 입안은 2_green_talk의 구강에서 가져온다.

실행:  ./tuber-env/bin/python live2d/make_psd_v5.py
산출:  flamingo_live2d.psd(Cubism), flamingo_anime25d.psd(Anime2.5DRig),
       preview.png, compare.png(원본|정지|눈감음|입벌림), parts_v5/*.png, masks_debug.png
"""
import os
import numpy as np
import cv2
from PIL import Image
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer
from psd_tools.constants import Compression

BASE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(BASE, "..", "assets")
OUT_PSD = os.path.join(BASE, "flamingo_live2d.psd")
OUT_PSD_25D = os.path.join(BASE, "flamingo_anime25d.psd")
OUT_PREVIEW = os.path.join(BASE, "preview.png")
OUT_COMPARE = os.path.join(BASE, "compare.png")
OUT_MASKS = os.path.join(BASE, "masks_debug.png")
PARTS_V5 = os.path.join(BASE, "parts_v5")

W = 1024                 # 작업 해상도(원본과 동일)
EXPORT_SCALE = 2         # PSD 저장 시 업스케일 배율 (2048x2048)

# ---- 경계 정의 (1024 좌표, zoom crop으로 눈 측정한 값 — 조정은 여기서) ----
EYE_OPEN_BOX = (430, 285, 580, 398)      # idle의 눈 (선화+흰자 추출용 탐색 범위)
EYE_CLOSED_BOX = (425, 265, 600, 375)    # blink의 감은 눈
BEAK_CLIP = [(268, 332), (545, 330), (608, 398), (600, 420), (555, 455),
             (505, 490), (455, 520), (430, 545), (422, 592), (400, 606),
             (330, 610), (300, 604), (255, 450)]        # 부리 한계 (칼라/턱선 제외 — 게이프 아래로 빠르게 좁힘)
BEAK_SEAM = [(600, 412), (540, 427), (492, 439), (452, 452), (415, 466),
             (330, 483), (250, 497)]                    # 입 이음선: 아래 = 아랫부리
HAIR_CUT = [(180, 470), (250, 430), (300, 385), (340, 360), (380, 340),
            (420, 348), (445, 335), (452, 306), (475, 298), (520, 288),
            (560, 290), (600, 300), (632, 314), (662, 340), (682, 374),
            (696, 420), (706, 470), (718, 530), (735, 600)]  # 위 = hair_front
ARM_Y_MIN = 690          # 이 아래의 핑크 = 팔(날개)
ARM_SPLIT_X = 425        # 좌우 팔 분리 실패 시 강제 분할선
GAPE = (588, 414)        # 입꼬리(아랫부리 회전 피벗)
MOUTH_ANGLE = 24         # 입 벌림 시 아랫부리 회전각(도, OpenCV 기준 CCW=화면상 아래로 벌어짐)
# 2_green_talk의 "벌린 부리" 작화를 통째로 잘라 idle에 정렬 (절차 생성보다 훨씬 자연스러움)
TALK_CLIP = [(255, 345), (330, 358), (390, 342), (430, 322), (462, 300), (472, 330),
             (500, 382), (542, 396), (542, 428), (495, 505), (445, 548), (395, 575),
             (330, 572), (282, 538), (248, 455)]   # talk 좌표계 부리 한계(두 눈 제외)
TALK_GAPE = (528, 396)   # talk 입꼬리 → idle GAPE로 평행이동
OPEN_ROT = 0             # 정렬 회전(도)
OPEN_DXY = (10, -18)     # 추가 오프셋: 위-오른쪽으로 당겨 닫힌 부리 베이스와 겹침(볼 노출 최소화)
SKULL = ((515, 320), (225, 205), -8)     # 머리 뒤 두피 타원 (center, axes, angle)
CHEEK = [(352, 342), (390, 394), (430, 428), (480, 452), (530, 460), (570, 444),
         (592, 412), (600, 360), (500, 328), (400, 328)]  # 부리 뒤 볼: 자연스러운 얼굴 윤곽 커브

LAYERS = [  # 아래 -> 위 (눈 3분할: 흰자 → 홍채 → 속눈썹 순으로 겹침)
    "body_fill", "head_base", "eye_white", "eye_iris", "eye_lash", "eye_closed",
    "body_visible", "mouth_inside", "lower_beak", "upper_beak", "hair_front",
    "left_arm", "right_arm",
]
IDLE_HIDE = {"eye_closed", "mouth_inside"}


def load_rgba(name):
    """초록 배경 → 알파. 가장자리 그린 스필 제거."""
    img = np.array(Image.open(os.path.join(ASSETS, name)).convert("RGB")).astype(np.int32)
    r, g, b = img[:, :, 0], img[:, :, 1], img[:, :, 2]
    greenness = g - np.maximum(r, b)                     # 초록 우세도
    alpha = np.clip((60 - greenness) * 255 // 50, 0, 255).astype(np.uint8)
    # 반투명 가장자리 despill: 언믹스. observed = art*a + bg*(1-a) → art 복원
    # (G 클램프 방식은 어두운 올리브빛 테두리를 남긴다 — 다크 배경 송출에서 티가 남)
    alpha[alpha < 48] = 0        # 초저알파는 제거 — 언믹스가 색을 발산시켜 마젠타 프린지가 됨
    bg = np.median(img[alpha == 0].reshape(-1, 3), axis=0) if (alpha == 0).any() else np.zeros(3)
    a = alpha.astype(np.float64)[:, :, None] / 255.0
    edge = (alpha > 0) & (alpha < 255)
    unmixed = np.clip((img - bg[None, None, :] * (1 - a)) / np.maximum(a, 1e-3), 0, 255)
    img = np.where(edge[:, :, None], unmixed.astype(np.int32), img)
    out = np.dstack([np.clip(img, 0, 255).astype(np.uint8), alpha])
    out[alpha == 0] = 0
    return out


def poly_mask(points, shape=(W, W)):
    m = np.zeros(shape, np.uint8)
    cv2.fillPoly(m, [np.array(points, np.int32)], 1)
    return m > 0


def below_polyline(pts, shape=(W, W)):
    """폴리라인 아래쪽 half-plane 마스크 (x 선형보간)."""
    xs = np.arange(shape[1])
    px = np.array([p[0] for p in pts], float)
    py = np.array([p[1] for p in pts], float)
    line_y = np.interp(xs, px, py)
    yy = np.arange(shape[0])[:, None]
    return yy > line_y[None, :]


def largest_cc(mask):
    n, labels = cv2.connectedComponents(mask.astype(np.uint8))
    if n <= 1:
        return mask
    sizes = [(labels == i).sum() for i in range(1, n)]
    return labels == (1 + int(np.argmax(sizes)))


def close_mask(mask, k):
    return cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))) > 0


def extract_eye(img, box):
    """어두운 선화 + 선화 주변의 흰자만 추출 (extract_eyes.py 방식, 제자리)."""
    x0, y0, x1, y1 = box
    rgb = img[y0:y1, x0:x1, :3].astype(float)
    lum = rgb[:, :, 0] * .3 + rgb[:, :, 1] * .59 + rgb[:, :, 2] * .11
    dark = (lum < 95).astype(np.uint8)
    white = (lum > 185).astype(np.uint8)
    near = cv2.dilate(dark, np.ones((17, 17), np.uint8))
    keep = ((dark | (white & near)) * 255).astype(np.uint8)
    keep = cv2.morphologyEx(keep, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, labels = cv2.connectedComponents((keep > 128).astype(np.uint8))
    h, w = keep.shape
    for i in range(1, n):
        comp = labels == i
        ys, xs = np.where(comp)
        if (ys.min() == 0 or xs.min() == 0 or ys.max() == h - 1 or xs.max() == w - 1
                or comp.sum() < 60):
            keep[comp] = 0
    keep = cv2.dilate(keep, np.ones((3, 3), np.uint8))
    keep = cv2.GaussianBlur(keep, (5, 5), 0)
    full = np.zeros((W, W), np.uint8)
    full[y0:y1, x0:x1] = keep
    return full


def split_eye_parts(img, eye_m):
    """뜬 눈을 흰자/홍채(+하이라이트)/속눈썹으로 3분할.
    홍채 = 어두운 덩어리를 침식해 가는 속눈썹 획을 제거하고 남는 코어."""
    rgb = img[:, :, :3].astype(float)
    lum = rgb[:, :, 0] * .3 + rgb[:, :, 1] * .59 + rgb[:, :, 2] * .11
    white = eye_m & (lum > 185)
    dark = eye_m & ~white
    core = cv2.erode(dark.astype(np.uint8),
                     cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))) > 0
    if core.any():
        core = largest_cc(core)
    iris = dark & (cv2.dilate(core.astype(np.uint8),
                              cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))) > 0)
    # 홍채 안에 갇힌 흰 하이라이트는 홍채와 함께 움직여야 한다
    n, wl = cv2.connectedComponents(white.astype(np.uint8))
    iris_grow = cv2.dilate(iris.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
    for i in range(1, n):
        cc = wl == i
        if not (cc & ~iris_grow).any():
            iris = iris | cc
    sclera = white & ~iris
    lash = dark & ~iris
    return sclera, iris, lash


def cut(img, mask):
    """마스크 영역을 제자리 RGBA로 절단. 내부 경계는 하드 엣지 —
    페더링하면 인접 파츠 사이에 반투명 실선 틈이 생긴다(겹침으로 이음새 해결).
    실루엣 가장자리는 원본 크로마 알파(min)가 그대로 살아 부드럽다."""
    out = img.copy()
    out[:, :, 3] = np.minimum(out[:, :, 3], (mask * 255).astype(np.uint8))
    return out


def inpaint_into(img, region, sample_from):
    """region을 sample_from 영역의 색"만" 보고 인페인트한 RGB 반환.
    무관한 픽셀은 색을 지우는 게 아니라(검정이 새어들어 어두운 링 생김)
    인페인트 마스크에 포함시켜 '미지 영역'으로 함께 채운다."""
    ys, xs = np.where(region)
    pad = 48
    y0, y1 = max(0, ys.min() - pad), min(img.shape[0], ys.max() + pad)
    x0, x1 = max(0, xs.min() - pad), min(img.shape[1], xs.max() + pad)
    work = img[y0:y1, x0:x1, :3].copy()
    unknown = ~sample_from[y0:y1, x0:x1]
    filled = cv2.inpaint(work, unknown.astype(np.uint8), 7, cv2.INPAINT_TELEA)
    out = img[:, :, :3].copy()
    out[y0:y1, x0:x1] = np.where(region[y0:y1, x0:x1, None], filled, out[y0:y1, x0:x1])
    return out


def merge_rgba(*parts):
    out = np.zeros((W, W, 4), float)
    for p in parts:
        a = p[:, :, 3:4].astype(float) / 255
        out[:, :, :3] = p[:, :, :3] * a + out[:, :, :3] * (1 - a)
        out[:, :, 3:4] = a * 255 + out[:, :, 3:4] * (1 - a)
    return out.astype(np.uint8)


def build():
    os.makedirs(PARTS_V5, exist_ok=True)
    idle = load_rgba("1_green_idle.png")
    blink = load_rgba("3_green_blink.png")
    talk = load_rgba("2_green_talk.png")
    char = idle[:, :, 3] > 40                      # 캐릭터 실루엣
    rgb = idle[:, :, :3].astype(int)
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    lum = rgb.mean(axis=2)
    sat = rgb.max(axis=2) - rgb.min(axis=2)

    # ---- 기본 색 분류 ----
    pink = char & (r > 150) & (r - b > 35) & (r - g > 40)          # 살/머리/날개
    blue = char & (b > 80) & (b - r > 25)                          # 유니폼
    pale = char & (sat < 70) & (lum > 140) & (r >= b - 10)         # 부리 옅은색/흰자/줄무늬
    black = char & (lum < 75)                                      # 검정(부리끝/선화)

    # ---- 눈 ----
    eye_open_m = extract_eye(idle, EYE_OPEN_BOX) > 40
    eye_closed_m = extract_eye(blink, EYE_CLOSED_BOX) > 40

    # ---- 부리: clip 폴리곤 안의 pale+black을 시드로 닫아 붙임, 눈/유니폼 제외 ----
    clip = poly_mask(BEAK_CLIP)
    blue_loose = char & (b > 55) & (b - r > 15)          # 네이비 칼라 포함 유니폼 계열
    beak = (pale | black) & clip & ~blue_loose & ~cv2.dilate(
        eye_open_m.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    beak = largest_cc(close_mask(beak, 9)) & char
    seam_up = [(x, y - 5) for x, y in BEAK_SEAM]         # 아랫부리를 5px 위로 겹쳐
    lower_beak_m = beak & below_polyline(seam_up)        # 이음선 틈 방지 (윗부리가 위에서 덮음)
    upper_beak_m = beak & ~below_polyline(BEAK_SEAM)

    # ---- 머리카락: 컷라인 위쪽의 캐릭터 전부 (부리/눈 제외) ----
    hair_m = char & ~below_polyline(HAIR_CUT) & ~beak & ~eye_open_m
    hair_m = largest_cc(hair_m)

    # ---- 팔: 하단의 핑크, 좌우 분리 ----
    arm_zone = pink & (np.arange(W)[:, None] > ARM_Y_MIN)
    arm_zone = close_mask(arm_zone, 7)
    n, labels, stats, cents = cv2.connectedComponentsWithStats(arm_zone.astype(np.uint8))
    comps = [(stats[i, cv2.CC_STAT_AREA], cents[i][0], i) for i in range(1, n)
             if stats[i, cv2.CC_STAT_AREA] > 3000]
    comps.sort(reverse=True)
    if len(comps) >= 2 and abs(comps[0][1] - comps[1][1]) > 150:
        big2 = sorted(comps[:2], key=lambda t: t[1])   # centroid x 순
        left_arm_m = labels == big2[0][2]
        right_arm_m = labels == big2[1][2]
    else:  # 날개끼리 붙어버림 → x로 강제 분할
        left_arm_m = arm_zone & (np.arange(W)[None, :] < ARM_SPLIT_X)
        right_arm_m = arm_zone & ~left_arm_m
    # 팔에 걸친 선화(어두운 외곽선)도 팔에 포함
    for m in ("l", "r"):
        am = left_arm_m if m == "l" else right_arm_m
        grown = cv2.dilate(am.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
        am |= grown & char & (lum < 110) & (np.arange(W)[:, None] > ARM_Y_MIN)
        if m == "l":
            left_arm_m = largest_cc(close_mask(am, 5))
        else:
            right_arm_m = largest_cc(close_mask(am, 5))
    arms = left_arm_m | right_arm_m

    # ---- 몸(셔츠) vs 머리(목) 분할 ----
    # 목 = y<560 위까지 이어진 핑크 CC(얼굴/머리와 한 덩어리). 그 주변 11px(턱/목 윤곽선 포함)은
    # head 소속, 나머지 y>500 전부가 몸 — 어깨 줄무늬·칼라 선화가 head로 새지 않는다.
    # 로고의 빨강/핑크 CC는 상단에 안 닿으므로 셔츠에 남는다.
    top_parts = hair_m | beak | eye_open_m | arms
    n, plabels = cv2.connectedComponents((pink & ~arms).astype(np.uint8))
    upper_labels = [l for l in np.unique(plabels[:560]) if l != 0]
    neck_mask = np.isin(plabels, upper_labels)
    neck_zone = cv2.dilate(neck_mask.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
    neck_zone &= ~blue_loose                         # 칼라 파랑은 링에서 제외(몸 소속)
    body_m = char & ~top_parts & ~neck_zone & (np.arange(W)[:, None] > 500)
    body_m = close_mask(body_m, 5) & char & ~arms & ~beak & ~neck_mask
    body_m = largest_cc(body_m)

    # ---- 머리(얼굴+목): 나머지 중 상단부/목 주변만. 하단의 고아 픽셀(셔츠 밑단 선화 등)은
    #      머리에 붙으면 리깅 시 떠다니므로 몸으로 돌린다 ----
    rest = char & ~hair_m & ~beak & ~eye_open_m & ~body_m & ~arms
    head_m = rest & ((np.arange(W)[:, None] < 640) | neck_zone | neck_mask)
    body_m |= rest & ~head_m

    # ---- head_base 뒤쪽 메꿈 ----
    head_base = cut(idle, head_m)
    face_skin = head_m & pink
    # (1) 두피: 머리카락 영역 중 두개골 타원 안쪽만 피부로
    skull = np.zeros((W, W), np.uint8)
    cv2.ellipse(skull, SKULL[0], SKULL[1], SKULL[2], 0, 360, 1, -1)
    # 부리 발자국은 제외 — 앞머리 가닥 틈 뒤는 닫힌 상태에선 부리, 벌린 상태에선 배경이 정답
    scalp = hair_m & (skull > 0) & ~beak
    # (2) 부리 뒤 볼: 자연스러운 얼굴 윤곽 커브(CHEEK) 안쪽만 — 입 벌려 부리가 치워졌을 때
    #     노출되는 경계가 매끈한 볼 라인이 되도록 (dilate 블롭은 아메바처럼 보임)
    cheek = beak & poly_mask(CHEEK)
    # (3) 눈 뒤 피부
    eye_fill = cv2.dilate(eye_open_m.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
    fill_region = (scalp | cheek | eye_fill) & char
    filled_rgb = inpaint_into(idle, fill_region, face_skin)
    head_base[:, :, :3] = np.where(fill_region[:, :, None], filled_rgb, head_base[:, :, :3])
    head_base[:, :, 3] = np.where(fill_region, 255, head_base[:, :, 3])
    # (4) 칼라 뒤 목 연장: 목 기둥을 아래로 60px 압출 —
    #     body_visible이 위에서 덮는 곳(body_m)에만 써서 원본 픽셀을 침범하지 않는다
    neck_cols = np.where((face_skin & (np.arange(W)[:, None] > 540)).any(axis=0))[0]
    if len(neck_cols):
        for x in neck_cols:
            col = np.where(face_skin[:, x])[0]
            y_last = col.max()
            if y_last > 540:
                ext_to = min(W - 1, y_last + 60)
                seg = body_m[y_last:ext_to, x]
                head_base[y_last:ext_to, x, :3] = np.where(
                    seg[:, None], head_base[y_last - 3, x, :3], head_base[y_last:ext_to, x, :3])
                head_base[y_last:ext_to, x, 3] = np.where(
                    seg, 255, head_base[y_last:ext_to, x, 3])

    # ---- body_fill: 팔이 가린 셔츠 (팔 영역 ∩ 셔츠 근방만, 실루엣 밖 금지) ----
    near_body = cv2.dilate(body_m.astype(np.uint8),
                           cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (161, 161))) > 0
    # 팔 실루엣보다 2px 안쪽까지만 (블러/삐져나옴 금지 — 팔이 흔들려 밖이 드러나면
    # 원본에서도 배경이었던 곳이므로 투명이 정답)
    behind_arms = arms & near_body & cv2.erode(char.astype(np.uint8),
                                               np.ones((5, 5), np.uint8)).astype(bool)
    fill_rgb = inpaint_into(idle, behind_arms, body_m).astype(np.int32)
    # 크로마 에지 잔여 그린 억제
    fill_rgb[:, :, 1] = np.minimum(fill_rgb[:, :, 1],
                                   np.maximum(fill_rgb[:, :, 0], fill_rgb[:, :, 2]))
    body_fill = np.zeros((W, W, 4), np.uint8)
    body_fill[:, :, :3] = np.where(behind_arms[:, :, None], fill_rgb.astype(np.uint8), 0)
    body_fill[:, :, 3] = np.where(behind_arms, 255, 0)

    # ---- 입안(절차 생성): 벌릴 때 드러나는 건 원래 아랫부리 자리(부리 실루엣 내부)뿐이므로
    #      그 영역을 구강색으로 채우고 혀 타원을 얹는다. 색은 talk 스프라이트에서 샘플링.
    trgb = talk[:, :, :3].astype(int)
    tr, tg, tb = trgb[:, :, 0], trgb[:, :, 1], trgb[:, :, 2]
    tlum = trgb.mean(axis=2)
    cavity = (talk[:, :, 3] > 40) & (tr > tb) & (tr - tg > 25) & (tlum < 185) & (tr < 230)
    cavity &= poly_mask([(280, 380), (520, 380), (540, 560), (400, 620), (280, 560)])
    dark_px = trgb[cavity & (tlum < 130)]
    tongue_px = trgb[cavity & (tr > 170)]
    cav_col = np.median(dark_px, axis=0) if len(dark_px) else np.array([88, 42, 48])
    tongue_col = np.median(tongue_px, axis=0) if len(tongue_px) else np.array([233, 150, 155])

    # 입안 = 아랫부리가 0°→MOUTH_ANGLE로 쓸고 지나가는 영역(sweep union).
    # 부리 끝 호(arc)가 자연 경계가 되어 실루엣 밖으로 안 나가고,
    # 벌린 상태에서 아랫부리/윗부리가 위에 덮이면 남는 부분이 정확히 "벌어진 틈"이다.
    lb_u8 = lower_beak_m.astype(np.uint8)
    mouth_m = np.zeros((W, W), bool)
    final_jaw = None
    for th in range(0, MOUTH_ANGLE + 1, 3):
        Msw = cv2.getRotationMatrix2D((float(GAPE[0]), float(GAPE[1])), th, 1.0)
        stamp = cv2.warpAffine(lb_u8, Msw, (W, W), flags=cv2.INTER_NEAREST) > 0
        mouth_m |= stamp
        final_jaw = stamp
    mouth_m = close_mask(mouth_m, 9)                     # 스윕 스텝 톱니 제거
    # 벌린 턱 아래쪽은 입안이 아님 — 최종 턱(+3px)을 통째로 빼서 턱의 반투명
    # 가장자리 밑으로 적갈색이 비치지 않게 한다 (턱의 검은 외곽선이 접합부를 가림)
    mouth_m &= ~(cv2.dilate(final_jaw.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0)
    mouth_inside = np.zeros((W, W, 4), np.uint8)
    mouth_inside[:, :, :3] = cav_col.astype(np.uint8)
    ys, xs = np.where(mouth_m)
    tongue = np.zeros((W, W), np.uint8)
    cv2.ellipse(tongue, (int(xs.mean() - 25), int(ys.mean() + 12)), (55, 22),
                -35, 0, 360, 1, -1)                      # 부리 방향(좌하향)으로 기울인 혀
    tongue = (tongue > 0) & cv2.erode(mouth_m.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
    mouth_inside[:, :, :3] = np.where(tongue[:, :, None],
                                      tongue_col.astype(np.uint8), mouth_inside[:, :, :3])
    a = (mouth_m * 255).astype(np.uint8)
    mouth_inside[:, :, 3] = cv2.GaussianBlur(a, (3, 3), 0)

    # ---- 벌린 부리(talk 작화) 추출·정렬: 25D mouth_open + Cubism 리깅 참고용 ----
    treddish = (talk[:, :, 3] > 40) & (tr > tb) & (tr - tg > 25) & (tlum < 200)
    tsat = trgb.max(axis=2) - trgb.min(axis=2)
    tpale = (talk[:, :, 3] > 40) & (tsat < 70) & (tlum > 140) & (tr >= tb - 10)
    tblack = (talk[:, :, 3] > 40) & (tlum < 75)
    tpink = (talk[:, :, 3] > 40) & (tr > 150) & (tr - tb > 35) & (tr - tg > 40)
    ob = (tpale | tblack | treddish) & poly_mask(TALK_CLIP)
    ob = largest_cc(close_mask(ob, 11)) & (talk[:, :, 3] > 40)
    inv = (~ob).astype(np.uint8)                     # 갇힌 구멍(혀 등) 포함
    nh, hl = cv2.connectedComponents(inv)
    border = set(hl[0, :]) | set(hl[-1, :]) | set(hl[:, 0]) | set(hl[:, -1])
    ob |= ~np.isin(hl, list(border)) & ~ob
    # 클로징이 끌어들인 "경계의" 얼굴 핑크만 제거 — 부리 내부의 분홍 음영/혀는 보존
    ring = ob & ~(cv2.erode(ob.astype(np.uint8), np.ones((13, 13), np.uint8)) > 0)
    ob &= ~(tpink & ring)
    open_beak = talk.copy()
    open_beak[:, :, 3] = np.where(ob, open_beak[:, :, 3], 0)
    Mo = cv2.getRotationMatrix2D((float(TALK_GAPE[0]), float(TALK_GAPE[1])), OPEN_ROT, 1.0)
    Mo[0, 2] += GAPE[0] - TALK_GAPE[0] + OPEN_DXY[0]
    Mo[1, 2] += GAPE[1] - TALK_GAPE[1] + OPEN_DXY[1]
    open_beak = cv2.warpAffine(open_beak, Mo, (W, W), flags=cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))

    # ---- 레이어 절단 ----
    sclera_m, iris_m, lash_m = split_eye_parts(idle, eye_open_m)
    parts = {
        "body_fill": body_fill,
        "head_base": head_base,
        "eye_white": cut(idle, sclera_m),
        "eye_iris": cut(idle, iris_m),
        "eye_lash": cut(idle, lash_m),
        "eye_closed": cut(blink, eye_closed_m),
        "body_visible": cut(idle, body_m),
        "mouth_inside": mouth_inside,
        "lower_beak": cut(idle, lower_beak_m),
        "upper_beak": cut(idle, upper_beak_m),
        "hair_front": cut(idle, hair_m),
        "left_arm": cut(idle, left_arm_m),
        "right_arm": cut(idle, right_arm_m),
    }
    for name, p in parts.items():
        Image.fromarray(p).save(os.path.join(PARTS_V5, f"{name}.png"))

    # ---- 마스크 디버그 (색코딩 오버레이) ----
    dbg = idle[:, :, :3].copy()
    colors = {"hair_front": (255, 0, 255), "upper_beak": (0, 200, 255),
              "lower_beak": (0, 90, 255), "eye_white": (255, 255, 255),
              "eye_iris": (255, 255, 0), "eye_lash": (0, 255, 255),
              "body_visible": (0, 255, 128), "left_arm": (255, 128, 0),
              "right_arm": (128, 0, 255), "head_base": (255, 64, 64)}
    masks = {"hair_front": hair_m, "upper_beak": upper_beak_m, "lower_beak": lower_beak_m,
             "eye_white": sclera_m, "eye_iris": iris_m, "eye_lash": lash_m,
             "body_visible": body_m, "left_arm": left_arm_m,
             "right_arm": right_arm_m, "head_base": head_m}
    for name, m in masks.items():
        dbg[m] = (np.array(colors[name]) * .55 + dbg[m] * .45).astype(np.uint8)
    Image.fromarray(dbg).save(OUT_MASKS)

    # ---- 상태 합성 ----
    def compose(hide=(), swap_eye=False, open_mouth=False):
        canvas = np.zeros((W, W, 4), np.uint8)
        for name in LAYERS:
            if name in hide:
                continue
            p = parts[name]
            if open_mouth and name == "lower_beak":
                M2 = cv2.getRotationMatrix2D((float(GAPE[0]), float(GAPE[1])), MOUTH_ANGLE, 1.0)
                p = cv2.warpAffine(p, M2, (W, W), flags=cv2.INTER_LINEAR,
                                   borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
            canvas = merge_rgba(canvas, p)
        if swap_eye:
            pass
        return canvas

    idle_c = compose(hide=IDLE_HIDE)
    blink_c = compose(hide={"eye_white", "eye_iris", "eye_lash", "mouth_inside"})
    # 벌림 상태 = 닫힌 부리 제거 + talk 작화 부리 (25D와 동일한 표현)
    open_c = merge_rgba(compose(hide={"eye_closed", "mouth_inside",
                                      "lower_beak", "upper_beak"}), open_beak)

    # ---- 검증: 정지 합성 vs 원본 ----
    d = np.abs(idle_c[:, :, :3].astype(int) - idle[:, :, :3].astype(int)).sum(axis=2)
    d[~char] = 0
    bad = (d > 40).sum()
    print(f"[verify] idle 합성 vs 원본: diff>40 픽셀 = {bad} ({bad / char.sum() * 100:.2f}% of char)")

    def on_bg(c, bg=(235, 235, 235)):
        a = c[:, :, 3:4].astype(float) / 255
        return (c[:, :, :3] * a + np.array(bg) * (1 - a)).astype(np.uint8)

    Image.fromarray(on_bg(idle_c)).save(OUT_PREVIEW)
    strip = np.concatenate([on_bg(idle), on_bg(idle_c), on_bg(blink_c), on_bg(open_c)], axis=1)
    Image.fromarray(strip).save(OUT_COMPARE)
    print(f"preview -> {OUT_PREVIEW}\ncompare(원본|정지|눈감음|입벌림) -> {OUT_COMPARE}")

    # ---- PSD 저장 (EXPORT_SCALE 배 업스케일) ----
    S = W * EXPORT_SCALE

    def write_psd(path, layer_list, hidden=()):
        psd = PSDImage.new(mode="RGBA", size=(S, S))
        for name, p in layer_list:
            up = cv2.resize(p, (S, S), interpolation=cv2.INTER_LANCZOS4)
            ys, xs = np.where(up[:, :, 3] > 0)
            if len(ys) == 0:
                continue
            tile = Image.fromarray(up[ys.min():ys.max() + 1, xs.min():xs.max() + 1])
            layer = PixelLayer.frompil(tile, psd, name, int(ys.min()), int(xs.min()),
                                       Compression.RLE)
            layer.visible = name not in hidden       # 상태 레이어는 기본 숨김(뷰어에서 idle로 보임)
            psd.append(layer)
        psd.save(path)
        print(f"psd -> {path} ({len(layer_list)} layers, {S}x{S})")

    write_psd(OUT_PSD, [(n, parts[n]) for n in LAYERS] + [("open_beak_ref", open_beak)],
              hidden=IDLE_HIDE | {"open_beak_ref"})

    # Anime2.5DRig 명명 규칙 변형 (mouth_open = 입안 쐐기+아랫부리 회전+윗부리 병합)
    M2 = cv2.getRotationMatrix2D((float(GAPE[0]), float(GAPE[1])), MOUTH_ANGLE, 1.0)
    lb_open = cv2.warpAffine(parts["lower_beak"], M2, (W, W), flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    # 명명 규약(852wa README 기준) + 실기 피드백 반영:
    # - mouth_open = talk 작화의 벌린 부리 통째로, mouth_close = 닫힌 부리 통째로.
    #   (절차 생성 쐐기는 뻣뻣해 보임 — 사용자 피드백)
    # - 눈은 한 장으로 병합. 외눈 프로필이라 eyewhite/irides 분리 시 좌우눈 로직이 헛돌며
    #   분홍 제네릭 눈꺼풀 얼룩이 생겼다 (병합 상태에선 깜빡임 자연스러움 확인됨).
    # - 앞머리는 face에 병합(房 물리 과함), 팔은 handwear 병합(미지명은 head로 붙음),
    #   목은 face에 통합(권장 一体型).
    write_psd(OUT_PSD_25D, [
        ("face", merge_rgba(parts["body_fill"], parts["head_base"], parts["hair_front"])),
        ("eyelash", merge_rgba(parts["eye_white"], parts["eye_iris"], parts["eye_lash"])),
        ("eye_close", parts["eye_closed"]),
        ("topwear", parts["body_visible"]),
        ("mouth_open", open_beak),
        ("mouth_close", merge_rgba(parts["lower_beak"], parts["upper_beak"])),
        ("handwear", merge_rgba(parts["left_arm"], parts["right_arm"])),
    ])


if __name__ == "__main__":
    build()
