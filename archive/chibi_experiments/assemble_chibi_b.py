"""치비 캐릭터 2장(closed/open) -> Anime2.5DRig용 레이어드 PSD. (B 트랙)

assemble_chibi.py(다른 세션이 작업 중)와 독립적으로 작업하는 복제본.
출력도 *_b로 분리: chibi_anime25d_b.psd / preview_b.png / parts_b/

v4(B) 변경점 — 사용자 피드백 반영:
- irides = 빨간 링 + 검은 동공 + 하이라이트 (홍채 유닛 전체가 시선을 따라감).
  흰 초승달만 흰자. 홍채 뒤 eyewhite는 흰색 메디안으로 채움.
  ※ 툴이 irides를 eyewhite 알파로 스텐실 클리핑하므로 eyewhite 마스크는
    눈 내부 전체(홍채 자리 포함)여야 한다.
- 눈 바깥 검정 테두리는 face에 귀속 — 깜빡임 때 eyewhite가 페이드아웃해도
  눈매 윤곽이 남아 깨져 보이지 않는다.
- 내부 파츠 경계는 하드 알파(페더 금지), 실루엣만 AA. 인접 파츠는 2~3px 겹침.
- 벌린 입: 균일 스케일로 폭을 닫은 입×1.15에 맞추고, 가로 중심·윗입술 라인 정렬.

레이어 (아래->위): topwear / face / eyewhite / irides / mouth_open /
mouth_close / handwear_1 / handwear_2  (전부 visible — 툴이 페이드 제어)
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
OUT_PSD = os.path.join(BASE, "chibi_anime25d_b.psd")
OUT_PREVIEW = os.path.join(BASE, "preview_b.png")
DEBUG_DIR = os.path.join(BASE, "parts_b")
os.makedirs(DEBUG_DIR, exist_ok=True)

K3 = np.ones((3, 3), np.uint8)
OVERLAP = 3  # 인접 파츠 하드 겹침(px)


def load(p):
    return np.array(Image.open(p).convert("RGB")).astype(int)


def comp_masks(mask):
    return cv2.connectedComponentsWithStats(mask.astype(np.uint8))


def ellipse(r):
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def dil(mask, r):
    if r <= 0:
        return mask.astype(bool)
    return cv2.dilate(mask.astype(np.uint8), ellipse(r)) > 0


def fill_holes(mask):
    h, w = mask.shape
    ff = np.zeros((h + 2, w + 2), np.uint8)
    inv = (~mask).astype(np.uint8)
    cv2.floodFill(inv, ff, (0, 0), 0)
    return mask | (inv > 0)


def solid_fill(img_rgb, fill_mask, sample_mask):
    """fill_mask를 sample_mask 메디안 색으로 단색 채움 — 줄무늬/오염 없음."""
    out = img_rgb.copy()
    if not fill_mask.any():
        return out
    if sample_mask.any():
        col = np.median(img_rgb[sample_mask], axis=0)
    else:
        col = np.array([251, 196, 157], dtype=img_rgb.dtype)
    out[fill_mask] = col.astype(out.dtype)
    return out


def grow_labels(labels, char, priority):
    """모든 시드에서 1px/스텝 동시 성장. 겹칠 땐 priority 순서가 이긴다."""
    for _ in range(800):
        unclaimed = char & (labels == 0)
        if not unclaimed.any():
            break
        grew = False
        for lid in priority:
            g = (cv2.dilate((labels == lid).astype(np.uint8), K3) > 0) & unclaimed
            if g.any():
                labels[g] = lid
                unclaimed &= ~g
                grew = True
        if not grew:
            labels[unclaimed] = priority[-1]
            break
    return labels


def build():
    img = load(CLOSED)
    H, W, _ = img.shape
    r, g, b = img[:, :, 0], img[:, :, 1], img[:, :, 2]
    lum = (r + g + b) / 3.0

    # --- 배경/캐릭터 ---
    bg_color = img[5:40, 5:40].reshape(-1, 3).mean(axis=0)
    bg_dist = np.abs(img.astype(np.float32) - bg_color).sum(axis=2)
    bg_like = bg_dist < 60
    n, lab, _, _ = comp_masks(bg_like)
    border_ids = set(lab[0, :]) | set(lab[-1, :]) | set(lab[:, 0]) | set(lab[:, -1])
    background = np.isin(lab, [i for i in border_ids if i != 0]) & bg_like
    char = ~background

    # 실루엣 AA: 배경 접면 밴드만 알파, RGB는 un-premultiply
    band = char & (cv2.dilate(background.astype(np.uint8), K3, iterations=2) > 0)
    sil_alpha = np.ones((H, W), np.float32)
    sil_alpha[band] = np.clip(bg_dist[band] / 250.0, 0.0, 1.0)
    sil_alpha[background] = 0.0
    src = img.astype(np.float32)
    a = sil_alpha[band][:, None]
    src[band] = np.clip((src[band] - (1 - a) * bg_color) / np.maximum(a, 0.25), 0, 255)
    src = src.astype(np.uint8)

    # --- 색 마스크 ---
    skin = (np.abs(r - 251) < 30) & (np.abs(g - 196) < 35) & (np.abs(b - 157) < 40) & char
    navy = (b > r + 30) & (b > 80) & (b < 200) & (lum < 150) & char
    black = (lum < 70) & char
    white = (lum > 225) & (np.abs(r - b) < 30) & char
    darkred = (r > 120) & (r < 215) & (g < 70) & (b < 80) & char
    hairred = (r > 200) & (g < 120) & (b < 70) & char
    # 눈 링의 밝은 빨강이 hairred에 걸리지 않게, 눈 몸통 확정 후 제외한다 (아래 참조)

    # --- 눈 몸통 (두 개) ---
    blk_up = black.copy()
    blk_up[int(H * 0.62):, :] = False
    R = 14
    erode_core = cv2.erode(blk_up.astype(np.uint8), ellipse(R)) > 0
    n, lab, stats, _ = comp_masks(erode_core)
    order = np.argsort(stats[1:, cv2.CC_STAT_AREA])[::-1] + 1
    eye_bodies = []
    wr = white | darkred
    n_wr, lab_wr, _, _ = comp_masks(wr)
    for i in order[:2]:
        if stats[i, cv2.CC_STAT_AREA] < 3000:
            continue
        mass = dil(lab == i, R + 3) & blk_up
        near = dil(mass, 4)
        ids = set(np.unique(lab_wr[near & wr])) - {0}
        full = mass | np.isin(lab_wr, list(ids))
        full = cv2.morphologyEx(full.astype(np.uint8), cv2.MORPH_CLOSE,
                                np.ones((11, 11), np.uint8)) > 0
        eye_bodies.append(fill_holes(full))
    if len(eye_bodies) != 2:
        raise RuntimeError(f"expected 2 eyes, got {len(eye_bodies)}")
    eye_bodies.sort(key=lambda m: np.where(m)[1].mean())

    # --- open.png 입 ---
    oimg = load(OPEN)
    orr, org, orb = oimg[:, :, 0], oimg[:, :, 1], oimg[:, :, 2]
    o_red = (orr > 120) & (org < 110) & (orb > 40) & (orb < 170)
    o_pink = (orr > 190) & (org > 80) & (org < 170) & (orb > 100) & (orb < 200)
    seed = o_red | o_pink
    roi_o = np.zeros((H, W), bool)
    roi_o[int(H * 0.40):int(H * 0.80), int(W * 0.28):int(W * 0.74)] = True
    seed &= roi_o
    o_skin = (np.abs(orr - 251) < 30) & (np.abs(org - 196) < 35) & (np.abs(orb - 157) < 40)
    n, lab, stats, _ = comp_masks(
        cv2.morphologyEx(seed.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8)) > 0)
    core, best_ring = None, 0.15
    for i in np.argsort(stats[1:, cv2.CC_STAT_AREA])[::-1] + 1:
        if stats[i, cv2.CC_STAT_AREA] < 1500:
            break
        m = lab == i
        ring = dil(m, 15) & ~m
        sr = o_skin[ring].mean() if ring.any() else 0
        if sr > best_ring:
            core, best_ring = m, sr
    if core is None:
        raise RuntimeError("open mouth not found")
    olum = (orr + org + orb) / 3.0
    rim = dil(core, 12) & (olum < 70)
    o_mouth = fill_holes(core | rim)
    ob = cv2.boundingRect(o_mouth.astype(np.uint8))
    o_cx, o_cy = ob[0] + ob[2] / 2, ob[1] + ob[3] / 2

    # --- 닫힌 입 ---
    eye_mask0 = eye_bodies[0] | eye_bodies[1]
    n, lab, stats, cent = comp_masks(black & ~dil(eye_mask0, 3))
    best = None
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        bw, bh = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        if not (300 < area < 16000 and bw < W * 0.25 and bh < H * 0.12):
            continue
        d = np.hypot(cent[i][0] - o_cx, cent[i][1] - o_cy)
        if best is None or d < best[0]:
            best = (d, i)
    if best is None:
        raise RuntimeError("mouth_close not found")
    mouth_close_mask = lab == best[1]
    print(f"mouth_close pick: dist={best[0]:.0f}px")

    # --- 피부/팔/머리/유니폼 시드 ---
    n, lab, stats, cent = comp_masks(skin)
    order = np.argsort(stats[1:, cv2.CC_STAT_AREA])[::-1] + 1
    headskin = lab == order[0]
    arm_seeds = []
    for i in order[1:3]:
        if stats[i, cv2.CC_STAT_AREA] >= 5000:
            arm_seeds.append((cent[i][0], lab == i))
    arm_seeds.sort(key=lambda t: t[0])
    if len(arm_seeds) != 2:
        raise RuntimeError(f"expected 2 arms, got {len(arm_seeds)}")

    # 머리색: 눈 영역(밝은 빨간 링 오염) 제외
    n, lab, stats, cent = comp_masks(hairred & ~dil(eye_mask0, 3))
    hair = np.zeros((H, W), bool)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] > 1000 and cent[i][1] < H * 0.65:
            hair |= lab == i

    jersey_seed = navy.copy()
    n, lab, stats, _ = comp_masks(white & ~eye_mask0)
    navy_d = dil(navy, 2)
    for i in range(1, n):
        m = lab == i
        if stats[i, cv2.CC_STAT_AREA] > 50 and (m & navy_d).any():
            jersey_seed |= m

    n, lab, stats, _ = comp_masks(black)
    face_black = np.zeros((H, W), bool)
    for i in range(1, n):
        m = lab == i
        if (stats[i, cv2.CC_STAT_AREA] < 1500
                and not (m & mouth_close_mask).any()
                and not (m & dil(eye_mask0, 2)).any()
                and (dil(m, 3) & skin).sum() > m.sum()):
            face_black |= m

    # --- 멀티시드 BFS ---
    EYE_L, EYE_R, MOUTH, ARM1, ARM2, JERSEY, HAIR, HEADSKIN = range(1, 9)
    labels = np.zeros((H, W), np.uint8)
    eye_starts = [eb | (dil(eb, 9) & black & blk_up) for eb in eye_bodies]
    seeds = [
        (EYE_L, eye_starts[0]),
        (EYE_R, eye_starts[1]),
        (MOUTH, mouth_close_mask),
        (ARM1, arm_seeds[0][1]),
        (ARM2, arm_seeds[1][1]),
        (JERSEY, jersey_seed),
        (HAIR, hair),
        (HEADSKIN, headskin | face_black),
    ]
    for lid, m in seeds:
        labels[m & char & (labels == 0)] = lid
    priority = [EYE_L, EYE_R, MOUTH, ARM1, ARM2, JERSEY, HAIR, HEADSKIN]
    labels = grow_labels(labels, char, priority)
    assert not (char & (labels == 0)).any(), "uncovered pixels remain"

    eyes_full = [fill_holes(labels == EYE_L), fill_holes(labels == EYE_R)]
    eye_mask = eyes_full[0] | eyes_full[1]
    mouth_close_mask = labels == MOUTH
    arms = [fill_holes(labels == ARM1), fill_holes(labels == ARM2)]
    jersey = fill_holes(labels == JERSEY)
    face0 = (labels == HAIR) | (labels == HEADSKIN)

    # --- 눈 분해: 홍채(링+동공+하이라이트) / 내부(흰자 영역) / 바깥 테두리 ---
    irides = np.zeros((H, W), bool)
    eye_interior = np.zeros((H, W), bool)  # 눈 내부 전체 (홍채 자리 포함) = eyewhite 마스크
    for ef in eyes_full:
        blk_e = black & ef
        # 동공: opening으로 얇은 스트로크 제거 후 최대 성분
        pupil = cv2.morphologyEx(blk_e.astype(np.uint8), cv2.MORPH_OPEN, ellipse(11)) > 0
        n, lab, stats, _ = comp_masks(pupil)
        big = np.zeros((H, W), bool)
        if n >= 2:
            big_i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
            if stats[big_i, cv2.CC_STAT_AREA] >= 2000:
                big = lab == big_i
        red_e = darkred & ef
        iris_core = big | red_e
        # 하이라이트: 홍채에 접하고 대부분 홍채 12px 안에 있는 흰 성분
        hl = np.zeros((H, W), bool)
        if iris_core.any():
            nw, lw, sw, _ = comp_masks(white & ef)
            core_d = dil(iris_core, 3)
            for i in range(1, nw):
                m = lw == i
                if (m & core_d).any() and (m & ~dil(iris_core, 12)).sum() < m.sum() * 0.3:
                    hl |= m
        iris = fill_holes(iris_core | hl)
        # 링 가장자리 AA 흡수 (바깥 테두리 검정·초승달 흰자는 제외)
        contour = blk_e & ~big
        crescent = (white & ef) & ~hl
        iris |= dil(iris, 2) & ef & ~contour & ~crescent
        irides |= iris
        # 내부 = 흰자·링·홍채를 채운 영역 (바깥 검정 스트로크 제외)
        interior = fill_holes((white & ef) | red_e | iris)
        eye_interior |= interior & ef
    have_irides = irides.any()
    print(f"irides(링+동공+하이라이트): {'ok' if have_irides else 'FAILED'} "
          f"({int(irides.sum())}px), interior={int(eye_interior.sum())}px")

    # 바깥 테두리(face 귀속) = 눈 영역에서 내부를 뺀 나머지
    eye_outline = eye_mask & ~eye_interior

    # --- 벌린 입: 균일 스케일로 폭 맞춤 + 윗입술 라인 정렬 ---
    mc_bb = cv2.boundingRect(mouth_close_mask.astype(np.uint8))  # x,y,w,h
    s = float(np.clip((mc_bb[2] * 1.15) / max(ob[2], 1), 0.7, 1.3))
    mo_rgba_full = np.zeros((H, W, 4), np.uint8)
    mo_rgba_full[:, :, :3] = np.clip(oimg, 0, 255).astype(np.uint8)
    mo_rgba_full[:, :, 3] = o_mouth.astype(np.uint8) * 255
    ox, oy, ow, oh = ob
    tile = mo_rgba_full[oy:oy + oh, ox:ox + ow]
    new_w, new_h = max(1, int(round(ow * s))), max(1, int(round(oh * s)))
    tile_r = cv2.resize(tile, (new_w, new_h), interpolation=cv2.INTER_AREA)
    paste_x = int(round(mc_bb[0] + mc_bb[2] / 2 - new_w / 2))  # 가로 중심 일치
    paste_y = int(round(mc_bb[1] - 2))                          # 윗변 = 웃는 곡선 윗변
    open_rgba = np.zeros((H, W, 4), np.uint8)
    x0, y0 = max(0, paste_x), max(0, paste_y)
    x1, y1 = min(W, paste_x + new_w), min(H, paste_y + new_h)
    open_rgba[y0:y1, x0:x1] = tile_r[y0 - paste_y:y1 - paste_y, x0 - paste_x:x1 - paste_x]
    oa = open_rgba[:, :, 3]
    open_rgba[:, :, 3] = np.where(oa > 40, 255, 0).astype(np.uint8)  # 하드 알파
    open_rgba[:, :, :3][open_rgba[:, :, 3] == 0] = 0
    o_mouth_t = open_rgba[:, :, 3] > 0
    print(f"mouth_open align: scale={s:.3f} smile={mc_bb[2]}x{mc_bb[3]} "
          f"open {ow}x{oh} -> {new_w}x{new_h}")

    # --- face: 머리+테두리 소유, 눈 내부/입 자리는 단색 채움 ---
    covered = (dil(eye_interior, OVERLAP) | dil(mouth_close_mask, OVERLAP)
               | dil(o_mouth_t, OVERLAP)) & char & ~eye_outline
    face_mask = face0 | eye_mask | covered  # eye_mask 포함: 테두리 원본 유지 + 내부 채움
    fill_zone = (eye_interior | (covered & ~eye_outline)) & ~mouth_close_mask
    fill_zone = fill_zone | mouth_close_mask | (o_mouth_t & char)
    face_sample_skin = skin & face0 & ~covered
    face_sample_hair = hairred & face0 & ~covered
    face_rgb = solid_fill(src, fill_zone,
                          face_sample_skin if face_sample_skin.any() else skin)
    hair_zone = fill_zone & dil(hair, 6)
    if hair_zone.any() and face_sample_hair.any():
        face_rgb = solid_fill(face_rgb, hair_zone, face_sample_hair)
    # 테두리는 원본 스트로크 유지 (깜빡여도 눈매 윤곽이 남는다)
    face_rgb[eye_outline] = src[eye_outline]

    # --- topwear: 턱/팔 뒤 언더익스텐션 (네이비 단색) ---
    ext = dil(jersey, 14) & (face_mask | arms[0] | arms[1]) & char
    jersey_full = fill_holes(jersey | ext)
    jersey_rgb = solid_fill(src, ext, navy & jersey)

    # --- eyewhite: 내부 전체(스텐실용), 홍채 자리는 흰자 메디안으로 ---
    ew_mask = eye_interior | (dil(eye_interior, 2) & eye_mask)  # 테두리 밑 2px 겹침
    white_sample = white & eye_interior & ~dil(irides, 1)
    behind_iris = dil(irides, 2) & ew_mask
    ew_rgb = solid_fill(src, behind_iris,
                        white_sample if white_sample.any() else (white & eye_mask))

    # --- RGBA: 내부 하드 알파, 실루엣 밴드만 AA ---
    def to_rgba(mask, rgb=None):
        out = np.zeros((H, W, 4), np.uint8)
        out[:, :, :3] = src if rgb is None else rgb
        m = mask.astype(bool)
        a = np.zeros((H, W), np.float32)
        a[m] = 255.0
        edge = m & band
        a[edge] = sil_alpha[edge] * 255.0
        a[background] = 0
        out[:, :, 3] = np.clip(a, 0, 255).astype(np.uint8)
        out[:, :, :3][out[:, :, 3] == 0] = 0
        return out

    layers = [
        ("topwear", to_rgba(jersey_full, rgb=jersey_rgb)),
        ("face", to_rgba(face_mask, rgb=face_rgb)),
        ("eyewhite", to_rgba(ew_mask, rgb=ew_rgb)),
    ]
    if have_irides:
        layers.append(("irides", to_rgba(irides)))
    layers += [
        ("mouth_open", open_rgba),
        ("mouth_close", to_rgba(mouth_close_mask)),
        ("handwear_1", to_rgba(arms[0])),
        ("handwear_2", to_rgba(arms[1])),
    ]

    # --- PSD ---
    psd = PSDImage.new(mode="RGBA", size=(W, H))
    for name, canvas in layers:
        ys, xs = np.where(canvas[:, :, 3] > 0)
        if not len(ys):
            print(f"!! {name}: empty, skipped")
            continue
        tile2 = Image.fromarray(canvas[ys.min():ys.max() + 1, xs.min():xs.max() + 1])
        psd.append(PixelLayer.frompil(
            tile2, psd, name, int(ys.min()), int(xs.min()), Compression.RLE))
        Image.fromarray(canvas).save(os.path.join(DEBUG_DIR, f"{name}.png"))
        print(f"{name}: {int((canvas[:, :, 3] > 0).sum())}px")
    psd.save(OUT_PSD)
    print(f"psd -> {OUT_PSD}")

    # --- 프리뷰 + QA ---
    def composite(names):
        prev = np.zeros((H, W, 3), np.float32)
        prev[:] = bg_color
        for name, canvas in layers:
            if name not in names:
                continue
            a2 = canvas[:, :, 3:4].astype(np.float32) / 255.0
            prev = canvas[:, :, :3] * a2 + prev * (1 - a2)
        return prev.astype(np.uint8)

    closed_names = {"topwear", "face", "eyewhite", "irides", "mouth_close",
                    "handwear_1", "handwear_2"}
    prev = composite(closed_names)
    Image.fromarray(prev).save(OUT_PREVIEW)
    diff = np.abs(prev.astype(int) - img).max(axis=2)
    bad = diff > 40
    print(f"preview -> {OUT_PREVIEW}")
    print(f"QA diff vs closed.png: mean={diff.mean():.2f} px>40: {int(bad.sum())} "
          f"({100 * bad.sum() / (H * W):.3f}%)")
    heat = img.copy()
    heat[bad] = [255, 0, 255]
    Image.fromarray(heat.astype(np.uint8)).save(os.path.join(DEBUG_DIR, "qa_diff.png"))
    Image.fromarray(composite(closed_names - {"mouth_close"} | {"mouth_open"})) \
        .save(os.path.join(DEBUG_DIR, "qa_open.png"))
    # 깜빡임 시뮬레이션: eyewhite/irides 없는 상태 (face 채움+테두리만)
    Image.fromarray(composite(closed_names - {"eyewhite", "irides"})) \
        .save(os.path.join(DEBUG_DIR, "qa_blink.png"))
    # 홍채 이동 시뮬레이션: irides를 +12px 오른쪽으로
    shifted = layers.copy()
    for i2, (nm, cv_) in enumerate(shifted):
        if nm == "irides":
            M2 = np.float32([[1, 0, 12], [0, 1, 4]])
            cv_2 = cv2.warpAffine(cv_, M2, (W, H))
            # 스텐실 클리핑 에뮬레이션: eyewhite 마스크 밖은 잘림
            cv_2[:, :, 3] = np.where(ew_mask, cv_2[:, :, 3], 0)
            shifted[i2] = (nm, cv_2)
    layers_bak = layers[:]
    layers[:] = shifted
    Image.fromarray(composite(closed_names)).save(os.path.join(DEBUG_DIR, "qa_gaze.png"))
    layers[:] = layers_bak


if __name__ == "__main__":
    build()
