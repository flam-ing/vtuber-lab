---
name: webcam-pngtuber
description: 맥에서 웹캠 페이스 트래킹 PNGTuber를 세팅·실행·튜닝·확장할 때 사용. 캐릭터 이미지 1장으로 버튜버 아바타를 만들거나, 이 프로젝트(my_webcam_pngtuber.py)를 실행/디버깅/OBS 연동할 때 트리거.
---

# 웹캠 PNGTuber 세팅 스킬 (macOS)

캐릭터 일러스트로 실시간 웹캠 트래킹 버튜버를 만드는 전 과정. 이 폴더의 `my_webcam_pngtuber.py`가 완성본이다.

## 0. 전제 조건 체크

- Apple Silicon Mac, 웹캠, OBS Studio(32.0.2+)
- **절대 시스템 `/usr/bin/python3`를 쓰지 말 것** — Tcl/Tk 8.5라서 GUI 창이 하얗게 비는 macOS 버그가 있다.
  `python3 -c "import tkinter; print(tkinter.TkVersion)"`이 8.6 미만이면 반드시 별도 Python 필요.

## 1. 아바타 에셋 준비 (이미지 4장)

캐릭터 이미지 1장에서 시작한다. AI 이미지 편집(nano-banana 계열, "입/눈만 바꾸고 나머지는 동일하게" 프롬프트)으로 변형 생성:

| 파일명 | 상태 |
|---|---|
| `assets/1_green_idle.png` | 기본 (입닫음+눈뜸) |
| `assets/2_green_talk.png` | 입 벌림 |
| `assets/3_green_blink.png` | 눈 감음 |
| `assets/4_green_talk_blink.png` | 입 벌림 + 눈 감음 |

규칙: **4장 모두 같은 캔버스 크기·같은 위치 정렬**(어긋나면 전환 시 떨림), 배경은 순수 초록(#00FF00 근처 — 코드가 `g>140 & r<110 & b<110` 마스크로 제거), 캐릭터에 초록 계열 색 금지.

## 2. 환경 구축

```bash
cd <이 폴더>
uv venv --python 3.12 tuber-env
uv pip install --python ./tuber-env/bin/python opencv-python mediapipe numpy pillow
./tuber-env/bin/python -c "import tkinter; print(tkinter.TkVersion)"   # 8.6+ 확인
```

## 3. 실행 및 검증

```bash
./tuber-env/bin/python my_webcam_pngtuber.py
```

- 카메라 권한 프롬프트 → 허용. 로그는 `tuber_runtime.log`에 쌓인다.
- 검증: 창 하단 상태표시줄에서 말할 때 Mouth 수치가 0.5+ 올라가고, 눈 감으면 Blink가 1.0 근처로 가는지 확인.
- MediaPipe 모델(`face_landmarker.task`)은 첫 실행 시 자동 다운로드.

## 4. 튜닝 (코드 상단 Motion tuning 상수)

- `MOUTH_LO/HI`: jawOpen→입 매핑 범위. 입이 계속 열려 있으면 LO를 올린다 (사람마다 다름)
- `BLINK_LO/HI`: 눈 감김 매핑 범위
- `SMOOTH_*`: EMA 계수 (높을수록 즉각 반응, 낮을수록 부드러움)
- `MOVE_X/Y_RANGE`: 머리 따라 움직이는 폭(px)
- `BREATH_*`: idle 숨쉬기 모션

## 5. OBS 연동

macOS 화면 캡처 소스 → 방식 '윈도우 캡처' → `Webcam Face-Tracking PNGTuber` 창 선택.
배경 제거가 필요하면 창 배경색(`bg="#222222"`)을 `#00FF00`으로 바꾸고 OBS 크로마 키(그린) 필터 적용.
Zoom/Discord용은 OBS 가상 카메라 시작 (카메라 확장이 시스템 설정 → 로그인 항목 및 확장에서 켜져 있어야 함).

## 트러블슈팅 요점

- 흰 화면 = Tk 8.5. 무조건 uv 환경으로.
- `not authorized to capture video` = 실행한 터미널/앱에 카메라 권한 없음.
- 크로스페이드 반투명 잔상은 구조적 한계 — 근본 해결은 Live2D 리깅(파츠 분리 PSD 필요).
