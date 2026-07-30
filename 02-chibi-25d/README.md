# 02 — chibi / 라우디 러프 2.5D (슬롯 2)

슬롯 **2**의 대표 런타임은 형제 레포  
[`mingo-vtuber` / `apps/chibi`](https://github.com/minwoo19930301/mingo-vtuber)  
(**라우디 러프 보이즈** 풍 + 플라밍고 후드 레이어 리그).

이 폴더 `02-chibi-25d/` 는 후드 없는 Anime2.5D **실험 잔여** (혼동 주의).

![preview](preview.png)

> 레포 슬롯: **2/6** · 표현 단위 = **파츠(머리·팔·손·입·눈)**

## 모션 데모 (대표 런타임 · 후드 치비)

![demo](../demos/02-chibi25d.gif)

고개 · 입 · 윙크 · 손 포즈 사이클 (얼굴/웹캠 UI 없음).

정지 컷: ![still](../demos/02-preview.jpg)

## 이 폴더 (실험 잔여) 파이프라인

```
closed.png + open.png  →  assemble_chibi.py  →  chibi_anime25d.psd
                                              →  parts/*.png (검수)
                                              →  preview.png
```

| 파일 | 설명 |
|------|------|
| `closed.png` / `open.png` | 원본 (입 닫힘 / 벌림) |
| `assemble_chibi.py` | 파츠 분리·PSD 조립 |
| `parts/*.png` | 파츠 디버그/검수 |
| `chibi_anime25d.psd` | Anime2.5DRig 드롭용 (gitignore · 스크립트로 재생성) |
| `preview.png` | idle 합성 미리보기 |

## 대표 런타임 실행

```bash
cd ../mingo-vtuber
npm install && npm run chibi:dev
```

## 이 폴더 PSD 재생성

```bash
cd 02-chibi-25d
../tuber-env/bin/python assemble_chibi.py
```
