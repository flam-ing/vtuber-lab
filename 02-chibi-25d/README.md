# 02 — chibi-style 2.5 VTuber

치비 캐릭터 **레이어드 PSD** → [Anime2.5DRig](https://852wa.github.io/Anime2.5DRig/).  
입·눈뿐 아니라 **고개 움직임 · 시선 · 손(handwear)** 파츠를 트래킹하는 쪽이 목표.

> 레포 슬롯: **2/4** · 예전 폴더명 `chibi/`

## 파이프라인

```
closed.png + open.png  →  assemble_chibi.py  →  chibi_anime25d.psd
                                              →  parts/*.png (검수)
                                              →  preview.png
```

## 파일

| 파일 | 설명 |
|------|------|
| `closed.png` / `open.png` | 원본 (입 닫힘 / 벌림) |
| `assemble_chibi.py` | 파츠 분리·PSD 조립 |
| `parts/*.png` | 파츠 디버그/검수 |
| `chibi_anime25d.psd` | Anime2.5DRig 드롭용 (gitignore · 스크립트로 재생성) |
| `preview.png` | idle 합성 미리보기 |

## 레이어 (아래→위)

`topwear` · `face` · `eyewhite` · `irides` · `eyelash` · `eye_close`(기본 숨김) · `mouth_open`(기본 숨김) · `mouth_close` · `handwear_1` · `handwear_2`

## 재생성

```bash
cd 02-chibi-25d
../tuber-env/bin/python assemble_chibi.py
```

## 사용

1. https://852wa.github.io/Anime2.5DRig/  
2. `chibi_anime25d.psd` 드롭  
3. 캠·마이크 허용 → OBS는 Chrome 창 캡처  
