# 04 — vroid-base-custom-girl

VRoid/VRM 기반 **3D Electron 데스크톱 버튜버** (전신 골격 · 손 · 얼굴).  
예전 이름/레포: `mingo-mate` → vtuber-lab 슬롯 **4** 로 이관.

| 항목 | 내용 |
|------|------|
| 아바타 | VRM (`public/models/avatar.vrm` 등) |
| 트래킹 | MediaPipe Face + Hand + **Pose** (전신) |
| 셸 | macOS 투명 always-on-top 패널 (Electron) |
| 렌더 | three.js + `@pixiv/three-vrm` |

## 실행

```bash
cd 04-vroid-base-custom-girl
npm install
npm run dev
```

- 드래그: 창 아무 데나  
- 종료: 우클릭 → **종료** / `Cmd+Q`  
- 카메라 패널·스펙: 우클릭 메뉴  

⚠️ Vite 준비 후 Electron이 뜹니다 (`scripts/wait-and-electron.mjs`).

## 주요 경로

```
04-vroid-base-custom-girl/
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

## 빌드 (DMG)

```bash
# 권장: dmgbuild 이슈 우회 (hdiutil)
npm run dist:dmg
# → release/MingoMate-0.2.0-arm64.dmg
# → release/vroid-base-custom-girl-0.2.0-arm64.dmg  (동일 내용, 슬롯4 이름)
```

`npm run dist` (electron-builder dmg)는 이 Mac에서 hdiutil attach 실패가 날 수 있음.  
`release/` 는 gitignore — 로컬 배포용으로 보관.

## 원본

- GitHub: https://github.com/minwoo19930301/mingo-mate (형제 레포, PR #2 fullbody 머지 기준 스냅샷)
