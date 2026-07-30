# 01 — mingo 4cut (PNGTuber)

플라밍고 **4컷** 표정 스위치 + 웹캠 Face Landmarker.  
입 열림·눈 깜빡임을 크로스페이드로 붙이고, 머리 위치도 살짝 따라간다.

![preview](preview.jpg)

> 레포 슬롯: **1/6** · 표현 단위 = **장면(이미지 전체)**

## 모션 데모

![demo](../demos/01-pngtuber.gif)

입 열림 · 깜빡임 · 가벼운 흔들림 (얼굴/웹캠 UI 없음, 설명용 스크립트 모션).

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
| `run_pngtuber.py` | 메인 |
| `assets/*.png` | 4컷 스프라이트 |
| `preview.jpg` | README 정지 컷 |
| `face_landmarker.task` | MediaPipe 모델 (없으면 첫 실행 시 다운로드, gitignore) |

## 실행

```bash
cd 01-mingo-4cut
../tuber-env/bin/python run_pngtuber.py
```

⚠️ 시스템 `python3`(Tk 8.5)로 돌리면 창이 하얗게 비는 경우가 많다. 반드시 `tuber-env`.

## OBS

1. 소스 → macOS 화면 캡처 → `Webcam Face-Tracking PNGTuber` 창  
2. 배경까지 빼려면 크로마 키 (또는 코드 `bg`를 `#00FF00`으로)
