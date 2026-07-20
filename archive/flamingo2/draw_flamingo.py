"""플라밍고 치비 캐릭터를 코드로 직접 그려서 Anime2.5DRig용 PSD 생성. (v2 퀄리티 패스)

레이어 (아래->위): topwear / face / eyewhite / mouth_open / mouth_close /
front hair / handwear_1 / handwear_2
- 'front hair'는 별도 레이어라 툴의 머리카락 물리(흔들림)를 받는다.
- 셀 셰이딩(그림자·하이라이트)은 각 레이어 안에 굽는다.
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageChops
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer
from psd_tools.constants import Compression

BASE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(BASE, "parts"), exist_ok=True)
W = H = 1024
SS = 4

# 팔레트
PINK = (242, 105, 145)          # 얼굴 기본
PINK_SH = (222, 82, 126)        # 얼굴 그림자
BLUSH = (232, 118, 150)
HAIR = (229, 56, 118)           # 머리
HAIR_SH = (204, 38, 100)
HAIR_HI = (244, 96, 150)
WING = (238, 88, 132)
WING_LT = (245, 116, 152)
WING_SH = (214, 62, 110)
BEAK = (248, 224, 228)
BEAK_SH = (232, 196, 204)
NAVY = (36, 52, 128)
NAVY_SH = (24, 36, 96)
WHITE = (245, 246, 250)
INK = (24, 20, 26)
MOUTH = (140, 40, 56)
MOUTH_DK = (108, 28, 42)
TONGUE = (240, 120, 140)
TONGUE_HI = (250, 160, 176)

# ---------------------------- 벡터 헬퍼 ----------------------------

def _catmull_seg(p0, p1, p2, p3, samples):
    out = []
    p0, p1, p2, p3 = map(lambda p: np.array(p, float), (p0, p1, p2, p3))
    for t in np.linspace(0, 1, samples, endpoint=False):
        a = 2 * p1
        b = p2 - p0
        c = 2 * p0 - 5 * p1 + 4 * p2 - p3
        d = -p0 + 3 * p1 - 3 * p2 + p3
        q = 0.5 * (a + b * t + c * t * t + d * t ** 3)
        out.append(tuple(q))
    return out

def smooth_path(pts, sharp=(), samples=18):
    """닫힌 경로. sharp 인덱스 꼭짓점은 뾰족하게, 나머지는 catmull 곡선."""
    n = len(pts)
    sharp = set(i % n for i in sharp)
    out = []
    for i in range(n):
        p0 = pts[(i - 1) % n]
        p1, p2 = pts[i], pts[(i + 1) % n]
        p3 = pts[(i + 2) % n]
        # 꼭짓점이 sharp면 클램프(중복점)해서 모서리 유지
        if i in sharp:
            p0 = p1
        if (i + 1) % n in sharp:
            p3 = p2
        out.extend(_catmull_seg(p0, p1, p2, p3, samples))
    return out

def S(pts):
    return [(x * SS, y * SS) for x, y in pts]

def new_layer():
    return Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))

def _outline(d, poly, color, ow):
    d.line(S(poly + [poly[0]]), fill=color, width=int(ow * SS), joint="curve")
    step = max(1, len(poly) // 60)
    for x, y in poly[::step]:
        r = ow * SS / 2
        d.ellipse([x * SS - r, y * SS - r, x * SS + r, y * SS + r], fill=color)

def blob(img, pts, fill, outline=INK, ow=11, sharp=(), samples=18):
    poly = smooth_path(pts, sharp, samples)
    d = ImageDraw.Draw(img)
    d.polygon(S(poly), fill=fill)
    if outline and ow:
        _outline(d, poly, outline, ow)

def stroke(img, pts, color=INK, w=10, smooth=False):
    d = ImageDraw.Draw(img)
    if smooth and len(pts) > 2:
        dense = []
        ext = [pts[0]] + list(pts) + [pts[-1]]
        for i in range(1, len(ext) - 2):
            dense.extend(_catmull_seg(ext[i - 1], ext[i], ext[i + 1], ext[i + 2], 14))
        dense.append(pts[-1])
        pts = dense
    d.line(S(pts), fill=color, width=int(w * SS), joint="curve")
    for p in (pts[0], pts[-1]):
        r = w * SS / 2
        d.ellipse([p[0] * SS - r, p[1] * SS - r, p[0] * SS + r, p[1] * SS + r], fill=color)

def circle(img, c, r, fill, outline=None, ow=0):
    d = ImageDraw.Draw(img)
    x, y = c
    d.ellipse([(x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS],
              fill=fill, outline=outline, width=int(ow * SS) if ow else 0)

def clipped(img, draw_fn):
    """img의 현재 알파에 클리핑해서 draw_fn(tmp) 결과를 얹는다 (셰이딩용)."""
    tmp = new_layer()
    draw_fn(tmp)
    mask = img.split()[3]
    tmp.putalpha(ImageChops.multiply(tmp.split()[3], mask))
    img.alpha_composite(tmp)

def down(img):
    return img.resize((W, H), Image.LANCZOS)

# ---------------------------- 레이어 ----------------------------

def draw_topwear():
    L = new_layer()
    torso = [(322, 705), (400, 662), (512, 648), (624, 662), (702, 705),
             (742, 775), (756, 900), (758, 1023), (266, 1023), (268, 900), (282, 775)]
    blob(L, torso, NAVY, ow=12)
    def sh(t):
        # 턱 밑 그림자 + 아랫단 어둡게 + 옆구리 주름 톤
        blob(t, [(420, 668), (512, 652), (604, 668), (596, 742), (512, 768), (428, 742)],
             NAVY_SH, outline=None, ow=0)
        blob(t, [(268, 960), (756, 960), (758, 1023), (266, 1023)],
             NAVY_SH, outline=None, ow=0)
    clipped(L, sh)
    # 어깨 줄무늬 (곡선)
    for k in range(3):
        o = k * 24
        stroke(L, [(348 + o, 670 + k * 5), (322 + o, 716), (306 + o, 762)], WHITE, 9, smooth=True)
        stroke(L, [(676 - o, 670 + k * 5), (702 - o, 716), (718 - o, 762)], WHITE, 9, smooth=True)
    # 옆구리 주름 선
    stroke(L, [(300, 850), (316, 900)], NAVY_SH, 7, smooth=True)
    stroke(L, [(724, 850), (708, 900)], NAVY_SH, 7, smooth=True)
    # 폴로 칼라: V 밴드 + 양쪽 깃
    stroke(L, [(446, 664), (512, 740), (578, 664)], WHITE, 16)
    blob(L, [(432, 660), (478, 654), (516, 706), (474, 718)], WHITE, ow=8, sharp=(2,))
    blob(L, [(592, 660), (546, 654), (508, 706), (550, 718)], WHITE, ow=8, sharp=(2,))
    # 소매 커프스
    stroke(L, [(288, 946), (306, 1002)], WHITE, 12, smooth=True)
    stroke(L, [(736, 946), (718, 1002)], WHITE, 12, smooth=True)
    # 로고 "Λi + 바" (원본 로고 오마주)
    d = ImageDraw.Draw(L)
    blob(L, [(398, 898), (450, 792), (472, 792), (522, 898), (488, 898),
             (461, 834), (432, 898)], (238, 64, 94), outline=None, ow=0,
         sharp=range(7), samples=4)
    circle(L, (506, 800), 11, (224, 42, 72))
    for k, h in enumerate([30, 46, 34]):
        x = 534 + k * 21
        d.rectangle([x * SS, (892 - h) * SS, (x + 13) * SS, 892 * SS], fill=(72, 102, 212))
    return L

def draw_face():
    L = new_layer()
    blob(L, [(512, 148), (700, 190), (812, 330), (818, 470), (752, 620),
             (620, 706), (512, 718), (404, 706), (272, 620), (206, 470),
             (212, 330), (324, 190)], PINK, ow=13)
    def sh(t):
        # 오른쪽 아래 림 셰이드
        blob(t, [(752, 620), (620, 706), (512, 718), (560, 668), (676, 596),
                 (742, 486), (790, 470)], PINK_SH, outline=None, ow=0)
        # 앞머리 밑 그림자 밴드
        blob(t, [(238, 470), (300, 428), (368, 486), (430, 420), (494, 500),
                 (556, 418), (616, 496), (668, 414), (724, 480), (772, 452),
                 (790, 492), (700, 540), (540, 556), (360, 544), (250, 508)],
             PINK_SH, outline=None, ow=0)
    clipped(L, sh)
    # 볼터치
    circle(L, (330, 574), 30, BLUSH)
    circle(L, (694, 574), 30, BLUSH)
    return L

def draw_front_hair():
    """스파이크를 절차 생성: 두피 호를 따라 골(smooth)-끝(sharp) 교대.
    끝은 오른쪽으로 살짝 기울여 스윕 느낌."""
    L = new_layer()
    HC = (512, 452)             # 두피 타원 중심
    RX, RY = 312, 300
    def on_arc(deg, k=1.0):
        r = np.radians(deg)
        return (HC[0] + RX * k * np.cos(r), HC[1] - RY * k * np.sin(r))

    pts, sharp = [], []
    # 바깥 스파이크: 왼쪽(165도) -> 오른쪽(15도), 길이 불규칙 + 오른쪽 기울임
    spikes = [(165, 0.42), (146, 0.34), (127, 0.52), (108, 0.40), (89, 0.56),
              (70, 0.38), (51, 0.50), (32, 0.36), (14, 0.46)]
    for i, (deg, ln) in enumerate(spikes):
        pts.append(on_arc(deg + 8, 0.99))            # 골 (스무스)
        sharp_tip = on_arc(deg - 4, 1.0 + ln)        # 끝 (샤프, 오른쪽 기움)
        pts.append(sharp_tip)
        sharp.append(len(pts) - 1)
    pts.append(on_arc(4, 0.99))
    # 오른쪽 스우시 꼬리 (볼 옆으로 흘러내림)
    pts.append((866, 560)); sharp.append(len(pts) - 1)
    pts.append((798, 512))
    # 이마 프린지: 오른쪽 -> 왼쪽, 끝이 아래로 (눈썹 위 ~470)
    teeth = [(742, 404, 700, 474), (652, 396, 598, 480), (546, 392, 494, 478),
             (440, 396, 386, 472), (334, 404, 282, 462)]
    for vx, vy, tx, ty in teeth:
        pts.append((vx, vy))                          # 골 (스무스)
        pts.append((tx, ty)); sharp.append(len(pts) - 1)  # 끝 (샤프)
    pts.append((236, 428))
    blob(L, pts, HAIR, ow=12, sharp=sharp)
    def sh(t):
        # 프린지 아랫단 그림자 톤
        band = [(236, 428)] + [(x, y - 6) for _, _, x, y in reversed(teeth)] + \
               [(798, 512), (700, 500), (520, 512), (330, 496)]
        blob(t, band, HAIR_SH, outline=None, ow=0)
        # 하이라이트 스트릭 1개 (왼쪽 위 결)
        stroke(t, [(300, 260), (400, 196), (520, 176)], HAIR_HI, 15, smooth=True)
    clipped(L, sh)
    return L

def draw_eyes():
    L = new_layer()
    for cx, flip in [(392, 1), (632, -1)]:
        eye = [(cx - 80, 452), (cx, 432), (cx + 80, 452), (cx + 86, 492),
               (cx + 32, 530), (cx - 32, 530), (cx - 86, 492)]
        blob(L, eye, WHITE, ow=9)
        # 홍채: 다크 플럼 + 검은 동공 + 이중 하이라이트
        circle(L, (cx + 6 * flip, 486), 42, (74, 40, 60))
        circle(L, (cx + 8 * flip, 492), 27, (30, 24, 34))
        circle(L, (cx - 10 * flip, 470), 13, (252, 252, 254))
        circle(L, (cx + 20 * flip, 506), 6, (252, 252, 254))
        # 두꺼운 윗꺼풀 + 속눈썹 플릭 2개
        stroke(L, [(cx - 84, 452), (cx, 429), (cx + 84, 452)], INK, 16, smooth=True)
        stroke(L, [(cx - 84 * flip, 452), (cx - 116 * flip, 438)], INK, 13)
        stroke(L, [(cx - 70 * flip, 442), (cx - 94 * flip, 424)], INK, 10)
        # 아래 눈꺼풀 라인
        stroke(L, [(cx - 40, 526), (cx, 532), (cx + 40, 526)], (150, 60, 95), 6, smooth=True)
    return L

def draw_mouth_close():
    L = new_layer()
    shield = [(446, 540), (582, 540), (612, 606), (596, 668), (556, 734),
              (498, 766), (448, 722), (418, 636)]
    blob(L, shield, BEAK, ow=10)
    def sh(t):
        # 오른쪽 면 그림자 + 왼쪽 위 하이라이트
        blob(t, [(560, 545), (596, 610), (588, 668), (548, 730), (566, 640)],
             BEAK_SH, outline=None, ow=0)
        stroke(t, [(452, 566), (438, 606), (440, 644)], (253, 242, 246), 9, smooth=True)
    clipped(L, sh)
    tip = [(428, 652), (604, 648), (582, 700), (548, 742), (498, 766), (448, 722)]
    blob(L, tip, INK, outline=None, ow=0)
    stroke(L, [(430, 654), (602, 650)], INK, 6)
    # 검은 끝 글린트
    stroke(L, [(472, 700), (496, 716)], (90, 84, 96), 7, smooth=True)
    # 콧구멍 (콤마형)
    stroke(L, [(494, 578), (512, 590)], INK, 8)
    return L

def draw_mouth_open():
    L = new_layer()
    cav = [(440, 534), (586, 534), (622, 636), (576, 762), (506, 796),
           (444, 756), (392, 632)]
    blob(L, cav, MOUTH, ow=10)
    def sh(t):
        blob(t, [(444, 538), (582, 538), (600, 590), (508, 612), (416, 588)],
             MOUTH_DK, outline=None, ow=0)
    clipped(L, sh)
    # 혀 + 하이라이트
    blob(L, [(462, 672), (552, 668), (576, 718), (508, 762), (450, 714)],
         TONGUE, outline=(120, 30, 45), ow=6)
    stroke(L, [(478, 692), (512, 686), (544, 692)], TONGUE_HI, 8, smooth=True)
    # 윗부리 처마
    blob(L, [(440, 534), (586, 534), (600, 566), (604, 588), (424, 590), (428, 562)],
         BEAK, ow=9)
    stroke(L, [(496, 562), (514, 574)], INK, 7)
    # 아래 검은 턱
    blob(L, [(426, 716), (450, 770), (506, 806), (572, 772), (600, 712),
             (576, 762), (506, 796), (444, 756)], INK, outline=None, ow=0)
    return L

def draw_wing(side=1):
    """앞단에 둥근 깃 3개(끝 smooth, 골 sharp)를 절차 생성한 날개 발."""
    L = new_layer()
    def M(pts):
        return [(512 - side * (512 - x), y) for x, y in pts]
    pts, sharp = [], []
    pts += [(58, 930), (140, 860), (262, 846), (368, 874), (432, 918)]  # 위 등선
    # 앞단 깃 3개: (골은 sharp, 끝은 smooth 라운드)
    fingers = [(428, 918), (352, 942), (278, 958)]
    for i, (fx, fy) in enumerate(fingers):
        if i > 0:
            pts.append((fx + 36, fy - 4)); sharp.append(len(pts) - 1)  # 깊은 골
        pts.append((fx + 10, fy + 68))        # 깃 끝(둥글게 2점)
        pts.append((fx - 28, fy + 62))
    pts += [(204, 1010), (60, 1018)]
    blob(L, M(pts), WING, ow=12, sharp=sharp)
    def sh(t):
        blob(t, M([(60, 980), (250, 968), (430, 950), (432, 1000), (60, 1018)]),
             WING_SH, outline=None, ow=0)
        stroke(t, M([(150, 884), (250, 864)]), WING_LT, 10, smooth=True)
        # 깃 사이 골 라인 (실루엣 안쪽에만)
        stroke(t, M([(388, 938), (382, 972)]), INK, 7, smooth=True)
        stroke(t, M([(314, 956), (310, 988)]), INK, 7, smooth=True)
        stroke(t, M([(180, 890), (196, 946)]), INK, 6, smooth=True)
    clipped(L, sh)
    return L

def build():
    layers = [
        ("topwear", draw_topwear()),
        ("face", draw_face()),
        ("eyewhite", draw_eyes()),
        ("mouth_open", draw_mouth_open()),
        ("mouth_close", draw_mouth_close()),
        ("front hair", draw_front_hair()),
        ("handwear_1", draw_wing(1)),
        ("handwear_2", draw_wing(-1)),
    ]
    psd = PSDImage.new(mode="RGBA", size=(W, H))
    closed = Image.new("RGBA", (W, H), (235, 235, 235, 255))
    opened = Image.new("RGBA", (W, H), (235, 235, 235, 255))
    for name, Lss in layers:
        img = down(Lss)
        img.save(os.path.join(BASE, "parts", f"{name.replace(' ', '_')}.png"))
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
