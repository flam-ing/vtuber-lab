"""플라밍고 치비 캐릭터를 코드로 직접 그려서 Anime2.5DRig용 PSD 생성.

AI 이미지 생성/분리 없이 레이어를 애초에 따로 그린다 (치비 스타일:
플랫 컬러 + 굵은 외곽선 + 파워퍼프 비율). 눈은 원본 플라밍고의
반쯤 감긴 시크한 눈, 부리는 검은 끝(플라밍고 시그니처).

레이어 (아래->위): topwear / face / eyewhite / mouth_open / mouth_close /
handwear_1 / handwear_2
"""
import os
import numpy as np
from PIL import Image, ImageDraw
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer
from psd_tools.constants import Compression

BASE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(BASE, "parts"), exist_ok=True)
W = H = 1024
SS = 4  # 슈퍼샘플링

# 팔레트
PINK = (242, 105, 145)        # 얼굴/깃털
PINK_DK = (229, 56, 118)      # 머리카락(진핑크)
PINK_WING = (238, 88, 132)
BEAK = (248, 224, 228)        # 부리 연분홍
NAVY = (36, 52, 128)
WHITE = (245, 246, 250)
INK = (24, 20, 26)            # 외곽선
MOUTH = (146, 42, 58)         # 입안
TONGUE = (240, 120, 140)

def catmull(pts, samples=24):
    """닫힌 catmull-rom 곡선 -> 조밀한 폴리곤."""
    n = len(pts)
    out = []
    for i in range(n):
        p0, p1, p2, p3 = (np.array(pts[(i - 1) % n], float), np.array(pts[i], float),
                          np.array(pts[(i + 1) % n], float), np.array(pts[(i + 2) % n], float))
        for t in np.linspace(0, 1, samples, endpoint=False):
            a = 2 * p1
            b = p2 - p0
            c = 2 * p0 - 5 * p1 + 4 * p2 - p3
            d = -p0 + 3 * p1 - 3 * p2 + p3
            q = 0.5 * (a + b * t + c * t * t + d * t ** 3)
            out.append(tuple(q))
    return out

def S(pts):  # 슈퍼샘플 좌표
    return [(x * SS, y * SS) for x, y in pts]

def new_layer():
    return Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))

def blob(img, pts, fill, outline=INK, ow=11, smooth=True, sharp=()):
    """부드러운 블롭. sharp에 든 인덱스 꼭짓점은 뾰족하게 유지."""
    d = ImageDraw.Draw(img)
    if smooth:
        poly = []
        n = len(pts)
        for i in range(n):
            if i in sharp:
                poly.append(pts[i])
            else:
                # 해당 꼭짓점 주변만 곡선화: catmull 전체 적용이 단순해서 전체 사용
                poly = catmull(pts)
                break
        else:
            poly = pts
        if poly is not pts and sharp:
            poly = pts  # sharp 혼합이면 직선 폴리곤 (아래 spiky용)
    else:
        poly = pts
    poly = catmull(pts) if smooth and not sharp else poly
    d.polygon(S(poly), fill=fill)
    if outline and ow:
        d.line(S(poly + [poly[0]]), fill=outline, width=ow * SS, joint="curve")
        for p in poly[::max(1, len(poly) // 40)]:
            x, y = p
            r = ow * SS / 2
            d.ellipse([x * SS - r, y * SS - r, x * SS + r, y * SS + r], fill=outline)

def spiky(img, pts, fill, outline=INK, ow=11):
    """뾰족한 폴리곤 (머리카락/스파이크)."""
    d = ImageDraw.Draw(img)
    d.polygon(S(pts), fill=fill)
    if outline and ow:
        d.line(S(pts + [pts[0]]), fill=outline, width=ow * SS, joint="curve")

def stroke(img, pts, color=INK, w=10):
    d = ImageDraw.Draw(img)
    d.line(S(pts), fill=color, width=w * SS, joint="curve")
    for p in (pts[0], pts[-1]):
        x, y = p
        r = w * SS / 2
        d.ellipse([x * SS - r, y * SS - r, x * SS + r, y * SS + r], fill=color)

def circle(img, c, r, fill, outline=None, ow=0):
    d = ImageDraw.Draw(img)
    x, y = c
    d.ellipse([(x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS],
              fill=fill, outline=outline, width=ow * SS if ow else 0)

def down(img):
    return img.resize((W, H), Image.LANCZOS)

# ============================== 레이어 ==============================

def draw_topwear():
    L = new_layer()
    torso = [(322, 705), (400, 662), (512, 648), (624, 662), (702, 705),
             (742, 775), (756, 900), (758, 1023), (266, 1023), (268, 900), (282, 775)]
    blob(L, torso, NAVY)
    # 어깨 줄무늬 3개씩
    for k in range(3):
        o = k * 24
        stroke(L, [(352 + o, 668 + k * 4), (306 + o, 760)], WHITE, 9)
        stroke(L, [(672 - o, 668 + k * 4), (718 - o, 760)], WHITE, 9)
    # V넥 칼라
    stroke(L, [(444, 664), (512, 738), (580, 664)], WHITE, 15)
    spiky(L, [(430, 660), (470, 655), (512, 700), (480, 712)], WHITE, ow=7)
    spiky(L, [(594, 660), (554, 655), (512, 700), (544, 712)], WHITE, ow=7)
    # 로고 "Ai" 느낌 (부리 끝·날개를 피해 왼쪽 가슴 아래)
    d = ImageDraw.Draw(L)
    spiky(L, [(398, 902), (448, 796), (470, 796), (518, 902), (486, 902),
              (460, 838), (432, 902)], (236, 62, 92), outline=None, ow=0)
    circle(L, (503, 804), 11, (222, 40, 70))
    for k, h in enumerate([30, 44, 34]):
        x = 532 + k * 21
        d.rectangle([x * SS, (896 - h) * SS, (x + 13) * SS, 896 * SS], fill=(70, 100, 210))
    return L

def draw_face():
    L = new_layer()
    # 머리 (넓은 타원)
    blob(L, [(512, 148), (700, 190), (812, 330), (818, 470), (752, 620),
             (620, 706), (512, 718), (404, 706), (272, 620), (206, 470),
             (212, 330), (324, 190)], PINK)
    # 목: 머리가 칼라에 얹힘 (치비 비율이라 별도 목 없음)
    # 앞머리: 오른쪽으로 쓸어넘긴 삐죽 프린지 (크기 불규칙)
    hair = [(216, 448), (208, 318), (246, 210), (318, 138),
            (346, 58), (398, 142), (452, 66), (488, 152),
            (558, 62), (592, 158), (668, 96), (688, 196),
            (778, 158), (772, 268), (836, 330), (824, 452),
            # 이마 지그재그 (오른쪽 -> 왼쪽, 스윕 느낌)
            (766, 440), (734, 320), (686, 452), (634, 330),
            (584, 470), (524, 344), (470, 466), (416, 356),
            (362, 462), (306, 392), (260, 468)]
    spiky(L, hair, PINK_DK)
    return L

def draw_eyes():
    L = new_layer()
    for cx, flip in [(392, 1), (632, -1)]:
        # 반쯤 감긴 시크한 눈: 위가 평평한 아몬드
        eye = [(cx - 78, 452), (cx, 434), (cx + 78, 452), (cx + 84, 492),
               (cx + 30, 528), (cx - 30, 528), (cx - 84, 492)]
        blob(L, eye, WHITE, ow=9)
        # 홍채(큰 다크) + 하이라이트
        circle(L, (cx + 8 * flip, 488), 40, (44, 38, 50))
        circle(L, (cx - 6 * flip, 474), 12, (250, 250, 252))
        # 두꺼운 윗꺼풀 + 속눈썹 플릭
        stroke(L, [(cx - 82, 452), (cx, 431), (cx + 82, 452)], INK, 16)
        stroke(L, [(cx - 82 * flip, 452), (cx - 112 * flip, 440)], INK, 13)
    return L

def draw_mouth_close():
    L = new_layer()
    # 닫힌 부리: 크게 아래로 처지는 플라밍고 부리, 끝 40%는 검정
    shield = [(446, 540), (582, 540), (612, 606), (596, 668), (556, 734),
              (498, 766), (448, 722), (418, 636)]
    blob(L, shield, BEAK, ow=10)
    tip = [(428, 652), (604, 648), (582, 700), (548, 742), (498, 766), (448, 722)]
    blob(L, tip, INK, outline=None, ow=0)
    stroke(L, [(430, 654), (602, 650)], INK, 6)
    # 콧구멍
    stroke(L, [(496, 580), (514, 592)], INK, 8)
    return L

def draw_mouth_open():
    L = new_layer()
    # 활짝 연 부리: 어두운 입안 + 혀 + 연분홍 윗부리 처마 + 검은 아래턱
    cav = [(440, 534), (586, 534), (622, 636), (576, 762), (506, 796),
           (444, 756), (392, 632)]
    blob(L, cav, MOUTH, ow=10)
    # 혀
    blob(L, [(462, 672), (552, 668), (576, 718), (508, 762), (450, 714)],
         TONGUE, outline=(120, 30, 45), ow=6)
    # 윗부리 조각 (연분홍 처마)
    blob(L, [(440, 534), (586, 534), (600, 566), (604, 588), (424, 590), (428, 562)],
         BEAK, ow=9)
    stroke(L, [(496, 562), (514, 574)], INK, 7)
    # 아래 검은 턱
    blob(L, [(426, 716), (450, 770), (506, 806), (572, 772), (600, 712),
             (576, 762), (506, 796), (444, 756)], INK, outline=None, ow=0)
    return L

def draw_wing(side=1):
    """side=1 왼쪽, -1 오른쪽 (좌우 대칭)."""
    L = new_layer()
    def M(pts):
        return [(512 - side * (512 - x), y) for x, y in pts]
    wing = [(58, 926), (150, 858), (268, 846), (368, 876), (430, 920),
            (438, 964), (404, 982), (398, 1016), (356, 992), (340, 1023),
            (296, 996), (272, 1023), (222, 1000), (60, 1022)]
    blob(L, M(wing), PINK_WING)
    # 깃털 라인 2개
    stroke(L, M([(300, 882), (330, 940)]), INK, 7)
    stroke(L, M([(236, 872), (252, 938)]), INK, 7)
    return L

def build():
    layers = [
        ("topwear", draw_topwear()),
        ("face", draw_face()),
        ("eyewhite", draw_eyes()),
        ("mouth_open", draw_mouth_open()),
        ("mouth_close", draw_mouth_close()),
        ("handwear_1", draw_wing(1)),
        ("handwear_2", draw_wing(-1)),
    ]
    psd = PSDImage.new(mode="RGBA", size=(W, H))
    closed = Image.new("RGBA", (W, H), (235, 235, 235, 255))
    opened = Image.new("RGBA", (W, H), (235, 235, 235, 255))
    for name, Lss in layers:
        img = down(Lss)
        img.save(os.path.join(BASE, "parts", f"{name}.png"))
        a = np.array(img)
        ys, xs = np.where(a[:, :, 3] > 0)
        tile = Image.fromarray(a[ys.min():ys.max() + 1, xs.min():xs.max() + 1])
        psd.append(PixelLayer.frompil(tile, psd, name, int(ys.min()), int(xs.min()), Compression.RLE))
        if name != "mouth_open":
            closed.alpha_composite(img)
        if name != "mouth_close":
            opened.alpha_composite(img)
        print(f"{name}: ok")
    psd.save(os.path.join(BASE, "flamingo_chibi.psd"))
    side = Image.new("RGB", (W * 2, H), (235, 235, 235))
    side.paste(closed.convert("RGB"), (0, 0))
    side.paste(opened.convert("RGB"), (W, 0))
    side.save(os.path.join(BASE, "preview.png"))
    print("psd -> flamingo_chibi.psd / preview.png (닫힘|벌림)")

if __name__ == "__main__":
    build()
