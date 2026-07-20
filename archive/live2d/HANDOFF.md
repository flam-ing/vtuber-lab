# 인수인계: 플라밍고 Live2D 레이어드 PSD (v5 — 제자리 절단)

> 이 문서 하나만 읽으면 어떤 에이전트든 이어서 작업할 수 있게 작성됨. (2026-07-07)

## ✅ 현재 상태: PSD 완성 + 실사용 검증 통과

`make_psd_v5.py`가 **원본 스프라이트 제자리 절단** 방식으로 PSD 2종을 생성하며,
검증까지 끝났다:

- 정지 합성 vs 원본 픽셀 diff **0.35%** (전부 실루엣 가장자리 안티앨리어싱)
- psd-tools 재오픈·레이어 오프셋·가시성 무결성 확인
- **Anime2.5DRig 실기 테스트 통과**: 자동 리깅 성공(10파츠), 눈 깜빡임 자연스러움(사용자 확인),
  입 벌림 정상, 시선용 eyewhite/irides 분리 인식

## 방식 (v4에서 왜 바꿨나)

v4(AI가 그린 독립 파츠를 끼워맞춤)는 눈 얼룩·화풍 불일치·팔 각도 어긋남이 한계였다.
v5는 **모든 보이는 픽셀이 원본 `assets/1_green_idle.png` 그대로**다:

1. 색 기반 + 폴리곤 마스크로 원본을 11파츠로 분할 (제자리, 좌표 보존)
2. 파츠가 가리던 뒤쪽만 인페인트로 메꿈 — 두피(하드 타원), 부리 뒤 볼, 칼라 뒤 목(60px 압출), 팔 뒤 셔츠
3. 모든 채움은 원본 실루엣 **안쪽**에만 → 정지 합성 = 원본과 픽셀 일치
4. 눈 감음은 `3_green_blink.png`(눈 외 정합 확인됨), 입안 색은 `2_green_talk.png`에서 샘플링

## 실행

```bash
cd ~/Documents/GitHub/vtuber-lab
./tuber-env/bin/python live2d/make_psd_v5.py
```

산출물 (git 제외, 재생성 가능):
- `flamingo_live2d.psd` — Cubism용 13레이어 2048², 상태 레이어(eye_closed/mouth_inside)는 기본 숨김
- `flamingo_anime25d.psd` — Anime2.5DRig용 9레이어 (명명 규약 준수)
- `preview.png`, `compare.png`(원본|정지|눈감음|입벌림), `masks_debug.png`(마스크 색코딩), `parts_v5/*.png`

## 조정 포인트 (전부 스크립트 상단 상수)

| 상수 | 용도 |
|---|---|
| `BEAK_CLIP` | 부리 탐색 한계 폴리곤 (칼라·턱선이 섞이면 여기 조정) |
| `BEAK_SEAM` | 입 이음선 (아래=아랫부리). 아랫부리는 5px 위로 겹쳐 틈 방지 |
| `HAIR_CUT` | 머리카락/얼굴 컷라인 (눈 y≥305, 부리 윗선 y≈350 피할 것) |
| `GAPE`, `MOUTH_ANGLE` | 입꼬리 피벗, 벌림 각(+24° = 화면상 아래) |
| `EYE_OPEN_BOX` / `EYE_CLOSED_BOX` | 눈 추출 탐색 범위 |
| `SKULL` | 머리카락 뒤 두피 타원 |

## 축적된 함정 (반복 금지)

- **int16으로 알파 연산 금지** — `(60-greenness)*255`가 오버플로우해 알파가 뒤집힌다 (int32 사용 중)
- **cv2.inpaint에 "차단" 픽셀을 검정으로 칠해 넘기지 말 것** — 검정이 새어들어 어두운 링 생김.
  차단 픽셀은 인페인트 마스크(미지 영역)에 포함시켜라 (`inpaint_into` 참고)
- **내부 경계 페더링 금지** — 인접 파츠 사이 반투명 실선 틈이 생긴다. 하드 엣지 + 겹침이 정답
- **디스필은 언믹스 방식** — `G=min(G,max(R,B))` 클램프는 올리브빛 테두리를 남긴다
  (다크 배경 송출에서 티 남). `art=(obs-bg·(1-α))/α`로 복원
- **입안은 스윕(sweep) 영역** — 아랫부리 발자국 전체를 채우면 슬라브처럼 보인다.
  아랫부리 마스크를 0→24°로 회전시킨 합집합에서 최종 턱(+3px)을 뺀 것이 "벌어진 틈"
- pytoshop은 깨진 PSD 생성 — psd-tools `PixelLayer.frompil` 사용
- `2_green_talk.png`는 idle과 포즈 불일치 — 색 샘플링에만 사용
- 시스템 python3(Tk 8.5) GUI 금지 — 흰 화면

## Anime2.5DRig 명명 규약 요점 (https://852wa.github.io/Anime2.5DRig/ README)

- `face`(필수) / `eyewhite` / `irides` / `eyelash` / `eye_close` / `mouth_open` / `mouth_close` /
  `topwear` / `handwear`(팔·손) / `front hair` / `back hair`
- **미지의 레이어명은 위치로 head/몸에 붙어버린다** (left_arm/right_arm → head 취급됐었음. handwear로 병합)
- 목은 face에 통합(一体型)이 안정적. 레이어 그룹(폴더) 미지원 — 플랫 구성만
- **사용자 피드백 반영: 앞머리는 face에 병합** (房 물리가 과했음). Cubism PSD에는 hair_front
  분리 유지 — 리깅에서 물리를 원하는 만큼만 주면 됨

## 사용법

1. **빠른 데뷔**: Chrome에서 https://852wa.github.io/Anime2.5DRig/ → `flamingo_anime25d.psd`
   업로드 → 캠·마이크 허용 → OBS 크롬 창 캡처. (검증 완료 상태)
2. **정식 리깅**: Cubism Editor FREE에 `flamingo_live2d.psd` 임포트 →
   `ParamMouthOpenY` = 아랫부리 회전(피벗 GAPE≈(588,414)·mouth_inside 노출),
   `ParamEyeLOpen` = eye_white+eye_iris+eye_lash ↔ eye_closed 전환,
   `ParamEyeBallX/Y` = eye_iris 이동(eye_white 클리핑), 머리 워프 디포머,
   hair_front 물리 → .moc3 → VTube Studio(맥, iPhone 트래킹 권장).
