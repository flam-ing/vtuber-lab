# 04 — Meshy 3D FBX

**Meshy** 로 뽑은 블루 저지 플라밍고 **생성 3D 메시**.  
그림(01/02) 다음, 본 트래킹(05/06) 전에 두는 “입체 외형” 슬롯.

| 항목 | 내용 |
|------|------|
| 모델 | `models/meshy_flamingo.fbx` |
| 텍스처 | `models/meshy_flamingo.png` (+ normal/metallic 등은 Downloads 원본) |
| 트래킹 | 없음 (뷰어 회전만) |
| 크기 | FBX ~31MB |

## 미리보기

```bash
# 레포 루트에서
python3 -m http.server 8799
# http://127.0.0.1:8799/demos/view3d/ → 패널 B (Meshy)
```

## 비고

버튜버 구동용 휴머노이드 본은 약함. 03 OBJ보다 디테일·텍스처는 풍부하고,  
05/06 VRM 리타게팅 전 **형태 확인용**으로 쓴다.
