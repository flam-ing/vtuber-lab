# 06 — vroid-base-custom-girl

VRoid/VRM 기반 **3D Electron 데스크톱 버튜버** (전신 골격 · 손 · 얼굴).  
예전 이름/레포: `mingo-mate` → 예전 슬롯 04 → **슬롯 06** (최종 풀 스택).

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
│   ├── tracking/      # MediaPipe + landmark overlay
│   └── aliveness/     # idle 모션 합성
├── public/models/     # .vrm + MediaPipe .task
├── docs/              # BRIEF / pipeline
└── package.json
```

## 이전 슬롯과의 관계

| 슬롯 | 역할 |
|------|------|
| 03 OBJ | 본 없는 가벼운 메시 |
| 04 Meshy | 생성 3D 외형 |
| 05 flamingo_motion.vrm | 리그 VRM 모델 (mingo-vtuber2) |
| **06 (여기)** | Electron + 트래킹 **제품형 앱** |
