# 인수인계: 플라밍고 Live2D 파츠 시트 → 레이어드 PSD 조립

> 이 문서 하나만 읽으면 어떤 에이전트든 이어서 작업할 수 있게 작성됨. (2026-07-06)

## 목표

AI가 그려준 **독립 파츠 시트 1장**을 잘라서, Live2D(Cubism) / Anime2.5DRig에서 쓸 수 있는
**레이어드 PSD**로 조립한다. 파츠는 원본과 픽셀 일치하지 않아도 된다(사용자 확인됨) —
합성했을 때 원본 캐릭터와 "충분히 닮은" 자연스러운 포즈면 성공.

## 입력 파일

| 파일 | 설명 |
|---|---|
| `~/Downloads/2844d490-5e70-4182-bf69-5978037041b1.png` | **파츠 시트** (4×3 그리드 + 하단 범례). 셀: ①right_arm ②left_arm ③body_visible ④hair_front ⑤upper_beak ⑥lower_beak ⑦mouth_inside(벌린 입) ⑧eye_closed ⑨eye_open ⑩head_base(눈 구멍 있음) ⑪body_fill(전체 유니폼) + 원본 참고 이미지. 배경은 체커보드(진짜 알파 아님 — 제거 필요) |
| `assets/1_green_idle.png` | 원본 스프라이트 1024×1024, 초록 배경. **배치 기준** |
| `live2d/parts_v3/*.png` | 이전 시도(원본 크롭) 파츠. 픽셀은 안 쓰더라도 **각 파츠의 원본 내 목표 bbox를 알파에서 계산하는 용도**로 유용 |

## 작업 순서

1. **시트 절단**: 그리드 셀 경계(밝은 회색 구분선) 검출 → 셀별 크롭.
2. **배경 제거**: 체커보드(저채도 밝은 회색 2색)를 셀 테두리에서 flood-fill로 제거.
   ⚠️ 부리 흰색·유니폼 흰 줄무늬는 파츠 안에 갇혀 있으므로 edge-connected 제거만 안전.
   라벨 칩·번호 배지는 "가장 큰 연결 성분만 유지"로 탈락시킴.
3. **배치**: 각 파츠를 원본 스프라이트의 해당 부위 bbox(parts_v3 알파에서 계산)에
   **비율 유지(contain) + 중앙 정렬**로 스케일·배치. 미세조정은 파츠별 offset/scale 오버라이드.
4. **PSD 저장**: psd-tools의 `PixelLayer.frompil(...)` + RLE. **pytoshop은 깨진 파일을 만드니 금지.**
   캔버스 2048×2048. 레이어 순서(아래→위):
   `body_fill, head_base, eye_open, eye_closed, body_visible, mouth_inside, lower_beak, upper_beak, hair_front, left_arm, right_arm`
   (부리 끝이 가슴 위에 뜨는 포즈라 부리 > body_visible)
5. **Anime2.5DRig 변형 PSD**도 함께: 레이어명 `face / eyelash(뜬 눈) / eye_close / topwear(body 병합) / mouth_open / mouth_close(부리 병합) / front hair / left_arm / right_arm`.
   `mouth_open` = mouth_inside + 아랫부리를 뿌리 피벗 기준 ~27° 아래로 회전 + 윗부리 합성.
6. **검증**: 전체 합성 preview.png를 원본과 나란히 놓고 눈으로 확인. 눈/부리/머리 위치가
   원본과 크게 어긋나면 offset 조정 후 재실행.

## 환경 / 실행

```bash
cd ~/Documents/GitHub/vtuber-lab
./tuber-env/bin/python live2d/assemble_v4.py   # 이 스크립트가 위 전 과정 수행
```

- Python은 반드시 `./tuber-env/bin/python` (uv venv, numpy/cv2/PIL/psd-tools 설치됨).
- 기존 스크립트: `assemble_psd.py`(v3용, 참고만), `make_parts_v3.py`, `extract_eyes.py`.
- 산출물: `live2d/flamingo_live2d.psd`, `live2d/flamingo_anime25d.psd`, `live2d/preview.png`.

## 이후 로드맵 (PSD 완성 다음)

1. **빠른 데뷔**: Chrome에서 https://852wa.github.io/Anime2.5DRig/ 열고 `flamingo_anime25d.psd`
   드래그 → 캠·마이크 허용 → OBS 크롬 창 캡처.
2. **정식 리깅**: Cubism Editor FREE에 `flamingo_live2d.psd` 임포트 → ParamMouthOpenY(부리 회전),
   ParamEyeLOpen(eye_open↔eye_closed 스왑), 머리 워프 디포머, hair_front 물리 → .moc3 →
   VTube Studio(맥, iPhone 트래킹 권장).

## 실패 이력 (반복 금지)

- AI에게 파츠를 "제자리 분해"로 시켰으나 조립 품질 불만족 → **독립 파츠 + 수동 배치**로 전환(현재).
- pytoshop → 깨진 PSD. psd-tools 사용.
- `2_green_talk.png`는 idle과 포즈 불일치 — 벌린 입 소스로 쓰지 말 것.
- 시스템 python3(Tk 8.5)로 GUI 실행 금지 — 흰 화면.
