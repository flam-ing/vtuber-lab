# vtuber-lab

`flam-ing` 버튜버 실험 모노레포. **활성 서브프로젝트는 번호 폴더**에 둔다.

| # | 폴더 | 한 줄 요약 | 상태 |
|---|------|-----------|------|
| **1** | **[01-mingo-4cut/](01-mingo-4cut/)** | 플라밍고 **4컷 PNG** — 입 열림/닫힘 · 눈 깜빡임 크로스페이드 + 웹캠 | ✅ 활성 |
| **2** | **[02-chibi-25d/](02-chibi-25d/)** | 치비 **Anime2.5D** — 레이어 PSD · 고개/시선/손 파츠 트래킹 | ✅ 활성 |
| **3** | **[03/](03/)** | (예정) | 🔒 예약 |
| **4** | **[04/](04/)** | (예정) | 🔒 예약 |
| — | **[archive/](archive/)** | 구 live2d · flamingo2 · transparent-widget · 실험 QA | 보관만 |

새 기능은 **01 / 02** 안에서만. 실험 폐기물은 `archive/`로.

---

## 1) mingo 4cut — 가벼운 PNGTuber

같은 포즈 표정 **4장**을 크로스페이드:

| 컷 | 파일 | 상태 |
|----|------|------|
| 1 | `1_green_idle.png` | 입 닫 · 눈 뜸 |
| 2 | `2_green_talk.png` | 입 열 · 눈 뜸 |
| 3 | `3_green_blink.png` | 입 닫 · 눈 감 |
| 4 | `4_green_talk_blink.png` | 입 열 · 눈 감 |

```bash
cd 01-mingo-4cut
../tuber-env/bin/python run_pngtuber.py
```

자세한 내용: [01-mingo-4cut/README.md](01-mingo-4cut/README.md)

---

## 2) chibi-style 2.5 VTuber

`closed.png` / `open.png` → 파츠 분리 → `chibi_anime25d.psd`  
[Anime2.5DRig](https://852wa.github.io/Anime2.5DRig/)에 드롭 → 고개 · 시선 · 입 · 손 레이어 트래킹.

```bash
cd 02-chibi-25d
../tuber-env/bin/python assemble_chibi.py   # PSD 재생성
# Chrome: https://852wa.github.io/Anime2.5DRig/ 에 chibi_anime25d.psd 드롭
```

자세한 내용: [02-chibi-25d/README.md](02-chibi-25d/README.md)

---

## 환경 (최초 1회, repo 루트)

```bash
uv venv --python 3.12 tuber-env
uv pip install --python ./tuber-env/bin/python -r requirements.txt
```

| 항목 | 메모 |
|------|------|
| `tuber-env/` | 로컬 venv (gitignore) |
| 시스템 `/usr/bin/python3` | **금지** — Tk 8.5면 4컷 GUI 흰 화면 |
| `*.psd` / `face_landmarker.task` | 대용량 · 생성물 — gitignore |

---

## 레이아웃

```
vtuber-lab/
├── 01-mingo-4cut/     # 4컷 PNGTuber (MediaPipe + Tk)
├── 02-chibi-25d/      # 치비 Anime2.5D PSD 파이프라인
├── 03/                # reserved
├── 04/                # reserved
├── archive/           # 구버전·실험 (새 작업 금지)
├── requirements.txt
├── tuber-env/         # local only
└── README.md
```
