"""치비(파워퍼프풍) 캐릭터 2장(closed/open) -> Anime2.5DRig용 레이어드 PSD.

v3 경계 수정:
- 내부 파츠 경계: 하드 알파 (페더 금지 — 반투명 실선 틈 방지, HANDOFF 교훈)
- 실루엣 가장자리만 안티앨리어싱 알파
- 가림 영역 채움: 보로노이(줄무늬) 대신 cv2.inpaint + 플랫 색 폴백
- 눈: 동공 구멍을 흰자/링 메디안 색으로 채우고, 검정 테두리를 eyewhite에 확실히 귀속
- 레이어 겹침 3px로 파츠 이동 시 틈 방지

레이어 (아래->위): topwear / face / eyewhite / irides / mouth_open /
mouth_close / handwear_1 / handwear_2
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


def ero(mask, r):
    if r <= 0:
        return mask.astype(bool)
    return cv2.erode(mask.astype(np.uint8), ellipse(r)) > 0


def fill_holes(mask):
    h, w = mask.shape
    ff = np.zeros((h + 2, w + 2), np.uint8)
    inv = (~mask).astype(np.uint8)
    cv2.floodFill(inv, ff, (0, 0), 0)
    return mask | (inv > 0)


def solid_fill(img_rgb, fill_mask, sample_mask):
    """fill_mask를 sample_mask 메디안 색(또는 평균)으로 단색 채움 — 줄무늬 없음."""
    out = img_rgb.copy()
    if not fill_mask.any():
        return out
    if sample_mask.any():
        col = np.median(img_rgb[sample_mask], axis=0)
    else:
        col = np.array([251, 196, 157], dtype=img_rgb.dtype)  # skin fallback
    out[fill_mask] = col.astype(out.dtype)
    return out


def inpaint_fill(img_rgb, fill_mask, sample_mask):
    """sample 영역만 색 소스로 쓰고 fill은 TELEA. 그 외 픽셀은 미지로 막아 오염 방지.

    (v2 버그: 전체 이미지를 known으로 두면 눈 빨간 링이 얼굴 언더필로 번짐)
    """
    if not fill_mask.any():
        return img_rgb.copy()
    if not sample_mask.any():
        return solid_fill(img_rgb, fill_mask, sample_mask)
    work = img_rgb.astype(np.uint8).copy()
    # sample만 남기고 나머지는 임시로 sample 메디안 → 인페인트 소스가 오염되지 않게
    med = np.median(work[sample_mask], axis=0).astype(np.uint8)
    base = np.zeros_like(work)
    base[:] = med
    base[sample_mask] = work[sample_mask]
    # 미지 = fill ∪ (¬sample ∧ ¬fill의 버퍼 밖) → fill만 채우면 됨
    unknown = fill_mask.astype(np.uint8)
    # sample과 fill이 안 닿으면 통로 확보: fill을 약간 키워 sample에 접하게
    grow = dil(fill_mask, 6) & ~sample_mask
    unknown = (fill_mask | grow).astype(np.uint8)
    filled = cv2.inpaint(base, unknown, 9, cv2.INPAINT_TELEA)
    out = work.copy()
    out[fill_mask] = filled[fill_mask]
    # 이탈 색은 메디안으로
    pix = out[fill_mask].astype(np.float32)
    dist = np.abs(pix - med.astype(np.float32)).sum(axis=1)
    bad = dist > 80
    if bad.any():
        idx = np.where(fill_mask)
        bi = np.where(bad)[0]
        out[idx[0][bi], idx[1][bi]] = med
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

    # 실루엣 AA: 배경 접면만 알파, RGB는 un-premultiply
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
        # 눈 외곽 검정 스트로크를 두껍게 포함
        full = fill_holes(full | (dil(full, 5) & black & blk_up))
        eye_bodies.append(full)
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
    rim = dil(core, 14) & (olum < 75)
    o_mouth = fill_holes(core | rim)
    # 윗입술 검정 아치가 빠지지 않게: 코어 위쪽 밴드의 검정 포함
    ys, xs = np.where(core)
    if len(ys):
        top_band = np.zeros_like(core)
        y_top = int(ys.min())
        top_band[max(0, y_top - 18):y_top + 8, int(xs.min()) - 8:int(xs.max()) + 8] = True
        o_mouth |= top_band & (olum < 75) & roi_o
        o_mouth = fill_holes(o_mouth)
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

    n, lab, stats, cent = comp_masks(hairred)
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
    # 눈: 테두리 검정 선점 강화 (9px)
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

    # --- irides (동공 + 하이라이트) ---
    irides = np.zeros((H, W), bool)
    for ef in eyes_full:
        blk_e = black & ef
        pupil = cv2.morphologyEx(blk_e.astype(np.uint8), cv2.MORPH_OPEN, ellipse(11)) > 0
        n, lab, stats, _ = comp_masks(pupil)
        if n < 2:
            continue
        big_i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        if stats[big_i, cv2.CC_STAT_AREA] < 2000:
            continue
        big = lab == big_i
        nw, lw, sw, _ = comp_masks(white & ef)
        pup_d = dil(big, 3)
        hl = np.zeros((H, W), bool)
        for i in range(1, nw):
            m = lw == i
            if (m & pup_d).any() and (m & ~dil(big, 12)).sum() < m.sum() * 0.3:
                hl |= m
        irides |= fill_holes(big | hl)
    have_irides = irides.any()
    print(f"irides: {'ok' if have_irides else 'NOT separated'} ({int(irides.sum())}px)")

    # --- 눈 레이어 분리 (깜빡임 검은 가로줄 방지) ---
    # eyewhite = 흰자+빨간링만 (두꺼운 검정 테두리 제외)
    # 검정 테두리 = face에 고정 (툴이 eyewhite를 세로로 찌부러뜨릴 때 테두리가 막대로 안 남음)
    # eye_close = 각 눈 위치에 감은 눈 선 (명시 레이어 → 자동 합성 대신 사용)
    eye_interior = np.zeros((H, W), bool)
    for ef in eyes_full:
        interior = fill_holes((white | darkred | (irides & ef)) & ef)
        # 테두리 안쪽만: 검정 스트로크를 바깥으로 밀어냄
        interior = ero(interior | dil(interior, 2), 1)
        interior = fill_holes(interior & ef)
        eye_interior |= interior
    if not eye_interior.any():
        eye_interior = (white | darkred) & eye_mask
    eye_interior = fill_holes(eye_interior)
    # irides는 interior 안으로
    if have_irides:
        irides = irides & dil(eye_interior, 2)

    eyewhite_sample = (white | darkred) & eye_interior & ~dil(irides, 1)
    if not eyewhite_sample.any():
        eyewhite_sample = (white | darkred) & eye_mask

    # eyewhite = 흰자+링만 (검정 테두리 제외 → 깜빡임 가로 막대 방지)
    # eyelash = 뜬 눈 검정 테두리 (Anime2.5D 규약)
    eye_outline = black & eye_mask & ~eye_interior & ~irides
    eye_outline = fill_holes(dil(eye_outline, 1) & black & dil(eye_mask, 2))
    # 내부와 테두리 사이 1px 겹침만
    thin_rim = dil(eye_interior, 2) & black & eye_mask
    eyewhite_mask = eye_interior | thin_rim
    eyelash_mask = (black & eye_mask & ~eye_interior) | (dil(eye_interior, 2) & black)
    eyelash_mask = dil(eyelash_mask, 1) & black & dil(eye_mask, 2)

    # eye_close: 화난 감은 눈 — 곡선 + 테이퍼 + 쌍꺼풀 라인 (ㅡㅡ 막대 지양)
    eye_close_rgb = np.zeros((H, W, 3), np.uint8)
    eye_close_a = np.zeros((H, W), np.uint8)
    skin_col = np.median(src[skin], axis=0).astype(np.uint8) if skin.any() \
        else np.array([251, 196, 157], np.uint8)
    ink = (22, 18, 18)

    def _lid_curve(cx, cy, half_w, half_h, side, n=40):
        r"""side=-1 left, +1 right. Angry closed-eye curve."""
        pts = []
        for i in range(n):
            t = i / (n - 1)  # 0..1 outer-left → outer-right
            u = t * 2 - 1    # -1..1
            x = cx + u * half_w
            # 기본 기울기 (바깥 끝이 위)
            y = cy + side * u * half_h * 0.85
            # 중앙 살짝 처짐(감은 눈 두께감)
            y += (1 - u * u) * half_h * 0.35
            # 바깥 끝 살짝 치켜올림
            outer = t if side > 0 else (1 - t)
            y -= outer ** 1.5 * half_h * 0.25
            pts.append([x, y])
        return np.array(pts, np.float32)

    def _draw_tapered_poly(canvas, pts, max_thick, color):
        """끝으로 갈수록 가늘어지는 폴리라인."""
        pts_i = pts.astype(np.int32)
        n = len(pts_i)
        for i in range(n - 1):
            # 끝 0.15 구간 테이퍼
            edge = min(i, n - 2 - i) / max(1, 0.18 * n)
            thr = max(2, int(max_thick * min(1.0, edge + 0.25)))
            cv2.line(canvas, tuple(pts_i[i]), tuple(pts_i[i + 1]),
                     color, thickness=thr, lineType=cv2.LINE_AA)
        # 끝점 둥글게
        for endp in (pts_i[0], pts_i[-1]):
            cv2.circle(canvas, tuple(endp), max(2, max_thick // 3), color, -1, cv2.LINE_AA)

    for ei, ef in enumerate(eyes_full):
        base = ef & eye_interior if (ef & eye_interior).any() else ef
        ys, xs = np.where(base)
        if not len(ys):
            continue
        x0, x1 = int(xs.min()), int(xs.max())
        y0, y1 = int(ys.min()), int(ys.max())
        cx = (x0 + x1) / 2.0
        cy = (y0 + y1) / 2.0 + (y1 - y0) * 0.02
        half_w = (x1 - x0) * 0.44
        half_h = max(6.0, (y1 - y0) * 0.18)
        side = -1 if ei == 0 else 1
        pts = _lid_curve(cx, cy, half_w, half_h, side)
        # 살색 패드: 곡선 따라 얇게 (눈알 잔상 가림)
        pad_m = np.zeros((H, W), np.uint8)
        max_thick = max(6, int((y1 - y0) * 0.13))
        _draw_tapered_poly(pad_m, pts, max_thick + 4, 255)
        pad = dil(pad_m > 0, 2)
        eye_close_rgb[pad] = skin_col
        eye_close_a[pad] = 255
        # 메인 잉크 라인
        main = np.zeros((H, W), np.uint8)
        _draw_tapered_poly(main, pts, max_thick, 255)
        eye_close_rgb[main > 0] = ink
        eye_close_a[main > 0] = 255
        # 윗 쌍꺼풀/주름: 메인보다 위·얇게
        pts_up = pts.copy()
        pts_up[:, 1] -= max(2.5, half_h * 0.22)
        pts_up[:, 0] += side * half_w * 0.02
        crease = np.zeros((H, W), np.uint8)
        _draw_tapered_poly(crease, pts_up, max(3, max_thick // 3), 255)
        # 주름은 살짝만
        crease = crease > 0
        eye_close_rgb[crease] = (35, 28, 28)
        eye_close_a[crease] = 255
        # 바깥 끝 작은 뾰족 강조 (화난 눈매)
        tip = pts[-1] if side > 0 else pts[0]
        tip2 = tip + np.array([side * half_w * 0.12, -half_h * 0.2])
        cv2.line(eye_close_rgb, (int(tip[0]), int(tip[1])),
                 (int(tip2[0]), int(tip2[1])), ink,
                 thickness=max(2, max_thick // 4), lineType=cv2.LINE_AA)
        # alpha for tip line
        tip_m = np.zeros((H, W), np.uint8)
        cv2.line(tip_m, (int(tip[0]), int(tip[1])),
                 (int(tip2[0]), int(tip2[1])), 255,
                 thickness=max(2, max_thick // 4), lineType=cv2.LINE_AA)
        eye_close_a[tip_m > 0] = 255
    eye_close = np.dstack([eye_close_rgb, eye_close_a])

    # --- 벌린 입: 원본 종횡비 유지 + 웃는 입 위치에 자연스럽게 ---
    mc_bb = cv2.boundingRect(mouth_close_mask.astype(np.uint8))  # x,y,w,h
    mo_bb = list(ob)
    # 너비: 닫힌 미소보다 조금 넓게(말풍선 느낌), 세로는 원본 비율
    # 균등 스케일(종횡비 유지). 닫힌 미소 대비 적당히 큰 벌림
    target_w = mc_bb[2] * 1.42
    sx = target_w / max(mo_bb[2], 1)
    sy = sx
    if mo_bb[3] * sy > mc_bb[3] * 3.5:
        sy = (mc_bb[3] * 3.5) / max(mo_bb[3], 1)
        sx = sy
    # 윤곽 보존: 마스크 약간 팽창 후 RGB는 원본
    mo_alpha = dil(o_mouth, 2)
    mo_rgba = np.zeros((H, W, 4), np.uint8)
    mo_rgba[:, :, :3] = np.clip(oimg, 0, 255).astype(np.uint8)
    mo_rgba[:, :, 3] = (mo_alpha.astype(np.uint8) * 255)
    # 검정 윤곽이 반투명이면 불투명화
    olum = mo_rgba[:, :, :3].mean(axis=2)
    dark = (mo_rgba[:, :, 3] > 0) & (olum < 90)
    mo_rgba[dark, 3] = 255
    ox, oy, ow, oh = cv2.boundingRect(mo_alpha.astype(np.uint8))
    pad = 3
    ox2, oy2 = max(0, ox - pad), max(0, oy - pad)
    ow2 = min(W - ox2, ow + 2 * pad)
    oh2 = min(H - oy2, oh + 2 * pad)
    tile = mo_rgba[oy2:oy2 + oh2, ox2:ox2 + ow2]
    new_w = max(1, int(round(ow2 * sx)))
    new_h = max(1, int(round(oh2 * sy)))
    # 색/알파는 LINEAR, 너무 흐려지지 않게
    tile_r = cv2.resize(tile, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    mc_cx = mc_bb[0] + mc_bb[2] / 2
    paste_x = int(round(mc_cx - new_w / 2))
    # 윗입술을 미소 선 바로 아래에
    paste_y = int(round(mc_bb[1] - new_h * 0.05))
    open_rgba = np.zeros((H, W, 4), np.uint8)
    x0, y0 = max(0, paste_x), max(0, paste_y)
    x1, y1 = min(W, paste_x + new_w), min(H, paste_y + new_h)
    tx0, ty0 = x0 - paste_x, y0 - paste_y
    open_rgba[y0:y1, x0:x1] = tile_r[ty0:ty0 + (y1 - y0), tx0:tx0 + (x1 - x0)]
    oa = open_rgba[:, :, 3]
    # 리사이즈 반투명 정리: 윤곽 살리고 노이즈 제거
    hard = oa > 50
    open_rgba[:, :, 3] = np.where(hard, 255, 0).astype(np.uint8)
    # 알파 morph close로 윤곽 끊김 복구
    a_bin = open_rgba[:, :, 3]
    a_bin = cv2.morphologyEx(a_bin, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    open_rgba[:, :, 3] = a_bin
    open_rgba[:, :, :3][open_rgba[:, :, 3] == 0] = 0
    o_mouth_t = open_rgba[:, :, 3] > 0
    print(f"mouth_close {mc_bb[2]}x{mc_bb[3]} → mouth_open {new_w}x{new_h} "
          f"(uniform scale {sx:.2f}, from {ow}x{oh})")

    # --- 레이어 마스크 (하드 겹침) ---
    # face가 눈 테두리+내부를 받침대으로 갖고, eyewhite는 interior만
    eye_for_face = dil(eye_mask, OVERLAP)
    mouth_for_face = dil(mouth_close_mask, OVERLAP) | dil(o_mouth_t, OVERLAP)
    covered_face = (eye_for_face | mouth_for_face) & char
    face_mask = face0 | covered_face  # 눈 테두리는 eyewhite/eye_close에

    face_sample_skin = skin & face0 & ~covered_face
    face_sample_hair = hairred & face0 & ~covered_face
    face_rgb = src.copy()
    face_rgb = solid_fill(
        face_rgb, covered_face,
        face_sample_skin if face_sample_skin.any() else skin)
    hair_zone = dil(hair, 8) & covered_face & ~dil(eye_mask, 2)
    if hair_zone.any() and face_sample_hair.any():
        face_rgb = solid_fill(face_rgb, hair_zone, face_sample_hair)
    # 눈 자리는 살색만 (뜬 눈 테두리 잔상 방지)

    # topwear
    ext = dil(jersey, 14) & (face_mask | arms[0] | arms[1]) & char
    jersey_full = fill_holes(jersey | ext)
    jersey_sample = (navy | white) & jersey
    jersey_rgb = src.copy()
    jersey_rgb = solid_fill(
        jersey_rgb, ext, navy & jersey if (navy & jersey).any() else jersey_sample)
    stripe_ext = ext & dil(white & jersey, 4)
    if stripe_ext.any():
        jersey_rgb = inpaint_fill(jersey_rgb, stripe_ext, jersey_sample)

    # eyewhite = interior only, 동공 구멍 빨간 링 채움
    pupil_hole = dil(irides, 2) & eye_interior if have_irides else np.zeros((H, W), bool)
    ew_rgb = src.copy()
    if pupil_hole.any():
        ring_s = darkred & eye_interior
        white_s = white & eye_interior
        if ring_s.any():
            ew_rgb = solid_fill(ew_rgb, pupil_hole, ring_s)
        elif white_s.any():
            ew_rgb = solid_fill(ew_rgb, pupil_hole, white_s)
        else:
            ew_rgb = solid_fill(ew_rgb, pupil_hole, eyewhite_sample)

    # --- RGBA: 내부 하드, 실루엣만 soft ---
    def to_rgba(mask, rgb=None, hard_interior=True):
        out = np.zeros((H, W, 4), np.uint8)
        out[:, :, :3] = src if rgb is None else rgb
        m = mask.astype(bool)
        a = np.zeros((H, W), np.float32)
        if hard_interior:
            a[m] = 255.0
            edge = m & band
            a[edge] = sil_alpha[edge] * 255.0
            a[background] = 0
            a[~m] = 0
        else:
            a[m] = sil_alpha[m] * 255.0
        out[:, :, 3] = np.clip(a, 0, 255).astype(np.uint8)
        out[:, :, :3][out[:, :, 3] == 0] = 0
        return out

    face = to_rgba(face_mask, rgb=face_rgb)
    topwear = to_rgba(jersey_full, rgb=jersey_rgb)
    # 테두리 링 색은 원본 검정 유지
    ew_rgb2 = ew_rgb.copy()
    ew_rgb2[thin_rim] = src[thin_rim]
    eyewhite = to_rgba(eyewhite_mask, rgb=ew_rgb2)
    irides_rgba = to_rgba(irides) if have_irides else None
    mouth_close = to_rgba(mouth_close_mask)

    hand1 = to_rgba(arms[0])
    hand2 = to_rgba(arms[1])

    # 레이어 순서 (아래→위). eye_close는 기본 숨김용으로 두되 PSD에 포함
    layers = [
        ("topwear", topwear),
        ("face", face),
        ("eyewhite", eyewhite),
    ]
    if have_irides:
        layers.append(("irides", irides_rgba))
    eyelash = to_rgba(eyelash_mask)
    layers += [
        ("eyelash", eyelash),
        ("eye_close", eye_close),
        ("mouth_open", open_rgba),
        ("mouth_close", mouth_close),
        ("handwear_1", hand1),
        ("handwear_2", hand2),
    ]

    # --- PSD ---
    # eye_close / mouth_open 은 상태 레이어 → 기본 숨김 (idle = 뜬 눈 + 다문 입)
    HIDDEN_DEFAULT = {"eye_close", "mouth_open"}
    psd = PSDImage.new(mode="RGBA", size=(W, H))
    for name, canvas in layers:
        ys, xs = np.where(canvas[:, :, 3] > 0)
        if not len(ys):
            print(f"!! {name}: empty, skipped")
            continue
        tile = Image.fromarray(canvas[ys.min():ys.max() + 1, xs.min():xs.max() + 1])
        layer = PixelLayer.frompil(
            tile, psd, name, int(ys.min()), int(xs.min()), Compression.RLE)
        if name in HIDDEN_DEFAULT:
            layer.visible = False
        psd.append(layer)
        Image.fromarray(canvas).save(os.path.join(DEBUG_DIR, f"{name}.png"))
        vis = "hidden" if name in HIDDEN_DEFAULT else "show"
        print(f"{name}: {int((canvas[:, :, 3] > 0).sum())}px [{vis}]")
    psd.save(OUT_PSD)
    print(f"psd -> {OUT_PSD}")

    # --- 프리뷰 + QA ---
    def composite(names):
        prev = np.zeros((H, W, 3), np.float32)
        prev[:] = bg_color
        for name, canvas in layers:
            if name not in names:
                continue
            a = canvas[:, :, 3:4].astype(np.float32) / 255.0
            prev = canvas[:, :, :3] * a + prev * (1 - a)
        return prev.astype(np.uint8)

    closed_names = {"topwear", "face", "eyewhite", "irides", "eyelash", "mouth_close",
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

    # 레이어 마스크 디버그 오버레이
    debug = np.zeros((H, W, 3), np.uint8)
    debug[jersey_full] = [40, 60, 180]
    debug[face_mask] = [240, 180, 140]
    debug[eye_mask] = [255, 255, 255]
    if have_irides:
        debug[irides] = [20, 20, 20]
    debug[mouth_close_mask] = [255, 0, 100]
    debug[arms[0]] = [100, 200, 100]
    debug[arms[1]] = [100, 255, 100]
    Image.fromarray(debug).save(os.path.join(DEBUG_DIR, "masks_debug.png"))


if __name__ == "__main__":
    build()
