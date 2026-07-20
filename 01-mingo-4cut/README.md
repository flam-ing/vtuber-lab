# 01 — mingo 4cut (PNGTuber)

플라밍고 **4컷** 표정 스위치 + 웹캠 Face Landmarker.  
입 열림·눈 깜빡임을 크로스페이드로 붙이고, 머리 위치도 살짝 따라간다.

> 레포 슬롯: **1/4** · 예전 폴더명 `flamingo/`

## 4컷 매핑

| # | 파일 | 입 | 눈 |
|---|------|----|----|
| 1 | `assets/1_green_idle.png` | 닫 | 뜸 |
| 2 | `assets/2_green_talk.png` | 열 | 뜸 |
| 3 | `assets/3_green_blink.png` | 닫 | 감 |
| 4 | `assets/4_green_talk_blink.png` | 열 | 감 |

배경은 초록 계열 — 런타임이 마스크로 제거한다. **캐릭터에 초록 쓰지 말 것.**

## 파일

| 파일 | 설명 |
|------|------|
| `run_pngtuber.py` | 메인 (구 `my_webcam_pngtuber.py`) |
| `assets/*.png` | 4컷 스프라이트 |
| `face_landmarker.task` | MediaPipe 모델 (없으면 첫 실행 시 다운로드, gitignore) |

## 실행

```bash
# repo 루트에서 venv 준비 후
cd 01-mingo-4cut
../tuber-env/bin/python run_pngtuber.py
```

⚠️ 시스템 `python3`(Tk 8.5)로 돌리면 창이 하얗게 비는 경우가 많다. 반드시 `tuber-env`.

## OBS

1. 소스 → macOS 화면 캡처 → `Webcam Face-Tracking PNGTuber` 창  
2. 배경까지 빼려면 크로마 키 (또는 코드 `bg`를 `#00FF00`으로)  
3. 회의용: OBS 가상 카메라

## 튜닝

`run_pngtuber.py` 상단 Motion tuning:

- `MOUTH_LO` / `MOUTH_HI` — 입 민감도  
- `BLINK_LO` / `BLINK_HI` — 눈 감김  
- `MOVE_X_RANGE` / `MOVE_Y_RANGE` — 머리 따라가기 폭  
