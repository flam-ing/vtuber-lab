# vtuber-lab

`flam-ing` 버튜버 실험 모노레포. **활성 서브프로젝트는 번호 폴더**에 둔다.

| # | 폴더 | 한 줄 요약 | 상태 |
|---|------|-----------|------|
| **1** | **[01-mingo-4cut/](01-mingo-4cut/)** | 플라밍고 **4컷 PNG** — 입/눈 크로스페이드 + 웹캠 | ✅ 활성 |
| **2** | **[02-chibi-25d/](02-chibi-25d/)** | 치비 **Anime2.5D** — 레이어 PSD · 고개/시선/손 | ✅ 활성 |
| **3** | **[03/](03/)** | (예정) | 🔒 예약 |
| **4** | **[04-vroid-base-custom-girl/](04-vroid-base-custom-girl/)** | **VRoid/VRM 3D** Electron 전신 VTuber (구 mingo-mate) | ✅ 활성 |
| — | **[archive/](archive/)** | 구 live2d · flamingo2 · transparent-widget · 실험 QA | 보관만 |

새 작업은 **01 / 02 / 04** 안에서. 폐기물은 `archive/`로.

---

## 1) mingo 4cut — 가벼운 PNGTuber

```bash
cd 01-mingo-4cut
../tuber-env/bin/python run_pngtuber.py
```

→ [01-mingo-4cut/README.md](01-mingo-4cut/README.md)

---

## 2) chibi-style 2.5 VTuber

```bash
cd 02-chibi-25d
../tuber-env/bin/python assemble_chibi.py
# Chrome: https://852wa.github.io/Anime2.5DRig/ 에 chibi_anime25d.psd 드롭
```

→ [02-chibi-25d/README.md](02-chibi-25d/README.md)

---

## 4) vroid-base-custom-girl — 3D 전신 VTuber

Electron + three.js + VRM + MediaPipe Pose (전신/손/얼굴).

```bash
cd 04-vroid-base-custom-girl
npm install
npm run dev
```

→ [04-vroid-base-custom-girl/README.md](04-vroid-base-custom-girl/README.md)

---

## 환경

### Python (01 / 02)

```bash
# repo 루트
uv venv --python 3.12 tuber-env
uv pip install --python ./tuber-env/bin/python -r requirements.txt
```

시스템 `/usr/bin/python3` 로 4컷 GUI 돌리지 말 것 (Tk 8.5 흰 화면).

### Node (04)

```bash
cd 04-vroid-base-custom-girl && npm install
```

---

## 레이아웃

```
vtuber-lab/
├── 01-mingo-4cut/                 # 4컷 PNGTuber
├── 02-chibi-25d/                  # 치비 Anime2.5D
├── 03/                            # reserved
├── 04-vroid-base-custom-girl/     # VRoid/VRM Electron 3D (구 mingo-mate)
├── archive/
├── requirements.txt               # Python deps
├── tuber-env/                     # local only
└── README.md
```
