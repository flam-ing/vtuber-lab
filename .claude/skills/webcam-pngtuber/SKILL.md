---
name: webcam-pngtuber
description: 맥에서 웹캠 페이스 트래킹 PNGTuber를 세팅·실행·튜닝·확장할 때 사용. 01-mingo-4cut 4컷 파이프라인 또는 02-chibi-25d Anime2.5D PSD 작업 시 트리거.
---

# 웹캠 PNGTuber / 버튜버 (macOS) — vtuber-lab

## 현재 레이아웃

| 폴더 | 역할 |
|------|------|
| **`01-mingo-4cut/`** | 4컷 PNG 크로스페이드 + MediaPipe (`run_pngtuber.py`) |
| **`02-chibi-25d/`** | 레이어드 PSD → Anime2.5DRig |
| **`03/` · `04/`** | reserved |
| **`archive/`** | 구 live2d / flamingo2 / transparent-widget 등 |

## 01 mingo 4cut

```bash
cd 01-mingo-4cut
../tuber-env/bin/python run_pngtuber.py
```

에셋: `assets/1_green_idle.png` … `4_green_talk_blink.png`  
경로·모델: 스크립트가 `BASE_DIR` 기준 (`face_landmarker.task` 자동 다운로드)

OBS: 창 캡처 `Webcam Face-Tracking PNGTuber`. 시스템 python3(Tk 8.5) 금지.

## 02 chibi 2.5D

```bash
cd 02-chibi-25d
../tuber-env/bin/python assemble_chibi.py   # → chibi_anime25d.psd
```

https://852wa.github.io/Anime2.5DRig/ 에 PSD 드롭.

## 환경

```bash
# repo 루트
uv venv --python 3.12 tuber-env
uv pip install --python ./tuber-env/bin/python -r requirements.txt
```
