# 05 — mingo-vtuber2 / flamingo_motion.vrm

**리그가 있는 VRM** 단계. 형제 레포 [mingo-vtuber2](https://github.com/minwoo19930301/mingo-vtuber2) (Swift/Metal 네이티브) 계열 모델.

| 항목 | 내용 |
|------|------|
| 모델 | `models/flamingo_motion.vrm` |
| 풀 앱 | `mingo-vtuber2` (Vision 트래킹 + 가상캠) |
| 이 슬롯 | 모델 스냅샷 + 웹 뷰어 비교용 |
| 다음 | **06** Electron + MediaPipe 풀 스택 제품형 |

## 미리보기

```bash
# 레포 루트에서
python3 -m http.server 8799
# http://127.0.0.1:8799/demos/view3d/ → 패널 D (VRM)
```

네이티브 앱:

```bash
cd ../../mingo-vtuber2
# README의 swift test / FlamingoStudio 실행
```

## 06과의 차이

| | 05 | 06 |
|--|----|----|
| 모델 | flamingo_motion.vrm | VRoid 계열 avatar + 커스텀 룩 |
| 셸 | Swift/Metal (형제 레포) | Electron + three-vrm |
| 이 모노레포 역할 | 모델·비교 슬롯 | 실행 가능한 풀 트래킹 앱 |
