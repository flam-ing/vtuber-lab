# 🦩 플라밍고 웹캠 PNGTuber

플라밍고 캐릭터 일러스트 1장에서 출발해, **비용 0원**으로 만든 실시간 웹캠 페이스 트래킹 버튜버 시스템.
웹캠으로 얼굴을 추적해서 입 벌림·눈 깜빡임·머리 위치를 아바타에 실시간 반영하고, OBS로 송출한다.

## 폴더 구성

```
버튜버/
├── my_webcam_pngtuber.py     # 메인 프로그램 (트래킹 + 렌더링)
├── assets/                   # 아바타 스프라이트 4종 (초록 배경, 코드가 자동 투명 처리)
│   ├── 1_green_idle.png        # 기본
│   ├── 2_green_talk.png        # 입 벌림
│   ├── 3_green_blink.png       # 눈 감음
│   └── 4_green_talk_blink.png  # 입 벌림 + 눈 감음
├── .claude/skills/webcam-pngtuber/SKILL.md   # Claude Code용 재현 스킬
└── README.md
```

`face_landmarker.task`(MediaPipe 모델, ~3MB)는 첫 실행 시 자동 다운로드된다.

## 실행 방법

### 1. 환경 구축 (최초 1회)

⚠️ **맥 기본 `python3`(/usr/bin/python3)로 실행하면 안 된다.** Xcode CommandLineTools 부속 Python 3.9는
Tcl/Tk **8.5**를 쓰는데, 이 버전은 최신 macOS 그래픽 엔진과 호환되지 않아 **창이 하얗게 비어 보이는** 버그가 있다
(코드는 뒤에서 정상 동작하지만 화면을 못 그림). Tk 8.6 이상이 붙은 Python이 필요하다.

[uv](https://docs.astral.sh/uv/)로 Python 3.12 + Tk 9.0 가상환경을 만든다:

```bash
cd ~/Downloads/버튜버
uv venv --python 3.12 tuber-env
uv pip install --python ./tuber-env/bin/python opencv-python mediapipe numpy pillow
```

### 2. 실행

```bash
cd ~/Downloads/버튜버
./tuber-env/bin/python my_webcam_pngtuber.py
```

- 첫 실행 시 macOS가 터미널 앱의 **카메라 권한**을 물어본다 → 허용
  (실수로 거부했으면: 시스템 설정 → 개인정보 보호 및 보안 → 카메라)
- 창 하단 상태표시줄에 Mouth/Blink 실시간 수치가 뜬다. 트래킹 확인용.

### 3. OBS 송출

1. OBS 소스 `+` → **macOS 화면 캡처** 추가 (구형 '윈도우 캡처'는 사용 중단됨)
2. 방식: **윈도우 캡처** → 윈도우 목록에서 `Webcam Face-Tracking PNGTuber` 선택
3. 소스에 **크로마 키** 필터 추가는 불필요 — 프로그램이 이미 초록 배경을 제거하고 어두운 회색 배경 위에 그린다.
   배경까지 빼고 싶으면 **필터 → 크로마 키**를 추가하고 키 색상을 커스텀 `#222222`로 지정하거나,
   코드의 `bg="#222222"`를 `#00FF00`으로 바꾸고 그린 키를 쓴다 (캐릭터가 핑크+파랑이라 그린이 안전).
4. Zoom/Teams/Discord에서 쓰려면 OBS **가상 카메라 시작** → 해당 앱에서 카메라를 `OBS Virtual Camera`로 선택.
   가상 카메라가 목록에 없으면: 시스템 설정 → 일반 → 로그인 항목 및 확장 → 카메라 확장에서 OBS 활성화.

## 동작 원리

- **트래킹**: OpenCV로 웹캠 프레임 캡처(백그라운드 스레드) → Google MediaPipe Face Landmarker가
  블렌드셰이프(`jawOpen`, `eyeBlinkLeft/Right`)와 랜드마크(코끝 위치)를 추출
- **모션**: 입/눈은 on-off 스위칭이 아니라 **0~1 연속값으로 4장을 2축 크로스페이드** 블렌딩.
  얼굴 위치에 따라 아바타가 좌우 ±50px / 상하 ±35px 이동, idle 시 사인파 숨쉬기 모션.
  모든 값에 EMA 스무딩 적용 (프레임당 연산 ~2.5ms, 30fps 여유)
- **튜닝**: 코드 상단 `# Motion tuning` 블록의 상수 수정
  - 입이 너무 민감하면 `MOUTH_HI`↑, 둔하면 `MOUTH_LO`↓
  - 움직임이 굼뜨면 `SMOOTH_POS`↑ (0~1)
  - 흔들림 폭은 `MOVE_X_RANGE` / `MOVE_Y_RANGE`

## 트러블슈팅

| 증상 | 원인/해결 |
|---|---|
| 창이 하얗게만 나옴 | Tk 8.5 (시스템 python3)로 실행함 → 위 uv 환경으로 실행 |
| `not authorized to capture video` | 터미널 앱에 카메라 권한 없음 → 시스템 설정에서 허용 |
| 아바타가 안 나오고 "No face detected" | 조명 확인, 카메라 정면 응시. 웹캠을 다른 앱이 점유 중인지 확인 |
| 입이 계속 열려 있음 | `MOUTH_LO` 값을 올리기 (기본 0.05) |
| 크로스페이드 중 반투명 잔상 | 이 방식의 구조적 한계. 다음 단계인 Live2D로 해결 예정 |

## 제작 히스토리

1. **원본 일러스트**: ChatGPT로 플라밍고 캐릭터 이미지 1장 생성
2. **표정 변형 4종**: Antigravity(Gemini)가 nano-banana pro 3.1로 입벌림/눈감음/동시 3장 추가 생성, 배경 초록 통일
3. **초석 코드**: Antigravity(Gemini)가 OpenCV + MediaPipe + Tkinter 기반 트래킹 프로그램 작성
4. **디버깅 + 모션 업그레이드**: Claude Code가 흰 화면 원인(Tk 8.5) 규명 및 uv 가상환경 마이그레이션,
   연속 크로스페이드·머리 트래킹·숨쉬기 모션·EMA 스무딩 추가 (틸트는 넣었다가 제거)

## Live2D 모델 (`live2d/`)

0원 Live2D 루트 진행 중. AI(nano-banana)로 생성한 파츠 11장을 `live2d/parts/`에 두고,
`assemble_psd.py`가 초록 배경 제거 → 배치(PLACEMENT 딕셔너리) → **Live2D 규격 레이어드 PSD** 생성:

```bash
./tuber-env/bin/python live2d/assemble_psd.py
# → live2d/flamingo_live2d.psd (2048x2800, 12 layers) + preview.png
```

PSD(~280MB)는 재생성 가능하므로 git에서 제외. 위치 조정은 스크립트의 `PLACEMENT` 좌표(작업좌표 1024x1400)
수정 후 재실행, `preview.png`로 확인.

레이어 구성 (아래→위): body_fill(실루엣 메움) / head_base / mouth_inside / lower_beak / upper_beak /
eye_white / eye_pupil / eyelid(감은눈) / hair_front / body_base / left_arm / right_arm

### 리깅 진행 순서 (Cubism Editor FREE)
1. PSD 임포트 → 파츠 확인 → 아트메쉬 자동 생성
2. 파라미터 매핑: `ParamMouthOpenY` = 윗부리↑/아랫부리↓ 회전(부리 뿌리에 회전 디포머), 벌리면 mouth_inside 노출
3. `ParamEyeLOpen` = eye_white+eye_pupil 축소 + eyelid 표시 전환
4. `ParamAngleX/Y` = 머리 전체(머리 워프 디포머), `ParamEyeBallX/Y` = eye_pupil 이동
5. hair_front에 물리(흔들림) 설정
6. .moc3 익스포트 → VTube Studio 로드

## 다음 단계 (로드맵)

- [x] Live2D용 파츠 분리 + 레이어드 PSD 조립 (`live2d/`)
- [ ] Cubism Editor 리깅 → VTube Studio(맥 웹캠 트래킹, 무료) → OBS 연동
- [ ] 크로스페이드 잔상 개선 (Live2D 전환으로 근본 해결)
