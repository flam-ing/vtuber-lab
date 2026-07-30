# 06 — vroid-base-custom-girl

VRoid/VRM 기반 **3D Electron 데스크톱 버튜버** (전신 골격 · 손 · 얼굴).  
예전 이름/레포: `mingo-mate` → 예전 슬롯 04 → **슬롯 06** (최종 풀 스택).

![preview](preview.jpg)

> 레포 슬롯: **6/6** · 표현 단위 = **본 + 실시간 트래킹**

## 모션 데모

![demo](../demos/06-vroid.gif)

고개/표정 · 팔·손 포즈 사이클. 촬영은 **상반신 프레이밍** (모델 자체는 전신 유지, 얼굴/웹캠 UI 없음).

## 한 줄 스펙

| 항목 | 내용 |
|------|------|
| 아바타 | VRM (`public/models/avatar.vrm` 등) |
| 트래킹 | MediaPipe Face + Hand + **Pose** (전신) |
| 셸 | macOS 투명 always-on-top 패널 (Electron) |
| 렌더 | three.js + `@pixiv/three-vrm` |

## 실행

```bash
cd 06-vroid-base-custom-girl
npm install
npm run dev
```

- 드래그: 창 아무 데나  
- 종료: 우클릭 → **종료** / `Cmd+Q`  
- 카메라 패널·스펙: 우클릭 메뉴  

⚠️ Vite 준비 후 Electron이 뜹니다 (`scripts/wait-and-electron.mjs`).

클린 모션 데모(카메라 UI 없음 · 상반신 촬영용 프레이밍):

```bash
MINGO_DEMO_MOTION=1 npm run dev
```

## 주요 경로

```
06-vroid-base-custom-girl/
├── electron/          # 패널 셸, 메뉴, IPC
├── src/
│   ├── main.ts        # 프레이밍 · 루프 · 드래그 · 디버그 UI
│   ├── model/         # VRM 리깅 · armSolver
│   ├── tracking/      # MediaPipe 래퍼
│   └── aliveness/     # 아이들 모션
├── public/models/     # avatar.vrm, landmarker tasks
├── preview.jpg        # README 정지 컷
└── package.json
```
