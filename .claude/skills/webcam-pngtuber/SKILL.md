---
name: webcam-pngtuber
description: 맥 버튜버 작업 시 사용. 01 4컷 PNGTuber, 02 chibi Anime2.5D PSD, 04 VRoid/VRM Electron 전신 트래킹.
---

# vtuber-lab 스킬

## 레이아웃

| 폴더 | 역할 |
|------|------|
| **`01-mingo-4cut/`** | 4컷 PNG + MediaPipe (`run_pngtuber.py`) |
| **`02-chibi-25d/`** | 레이어드 PSD → Anime2.5DRig |
| **`03/`** | reserved |
| **`04-vroid-base-custom-girl/`** | Electron + VRM 전신 (구 mingo-mate) |
| **`archive/`** | 구버전 |

## 01 mingo 4cut

```bash
cd 01-mingo-4cut
../tuber-env/bin/python run_pngtuber.py
```

## 02 chibi 2.5D

```bash
cd 02-chibi-25d
../tuber-env/bin/python assemble_chibi.py
```

## 04 vroid-base-custom-girl

```bash
cd 04-vroid-base-custom-girl
npm install
npm run dev
```

전신 프레이밍 FOV 17, 드래그, 우클릭 종료, landmark 디버그 패널.

## 환경

```bash
# Python (01/02) — repo 루트
uv venv --python 3.12 tuber-env
uv pip install --python ./tuber-env/bin/python -r requirements.txt

# Node (04)
cd 04-vroid-base-custom-girl && npm install
```
