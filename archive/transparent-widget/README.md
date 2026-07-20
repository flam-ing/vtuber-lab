# 2.5D 초경량 맥 데스크톱 위젯 (Transparent PNGTuber Widget)

이 프로젝트는 macOS의 내장 WebKit(Safari)엔진과 Swift 네이티브 코드를 조합하여 만든 **초경량 항상 위에 떠 있는 투명 PNGTuber 위젯**입니다. 

Electron 방식보다 약 100배 가벼우며, 컴퓨터 자원(RAM/CPU)을 거의 소모하지 않습니다.

## 폴더 구조
* `transparent-tuber` : 빌드 완료된 Mac 실행 파일 (더블 클릭하여 실행)
* `app.swift` : 투명성, 드래그 이동, 항상 위 배치 등의 창 제어 코드가 담긴 Swift 소스 코드
* `index.html` / `style.css` / `renderer.js` : 캐릭터 렌더링, 둥둥 뜨는 애니메이션, 눈 깜빡임, 마이크 볼륨 분석 로직이 들어 있는 웹 코드
* `assets/` : 아바타 캐릭터의 4가지 상태별 PNG 파일이 모여 있는 폴더
  * `1_closed_eyes_open.png` (Idle)
  * `2_open_eyes_open.png` (Talking)
  * `3_closed_eyes_closed.png` (Blinking)
  * `4_open_eyes_closed.png` (Talking & Blinking)

---

## 실행 및 조작 방법

### 1. 프로그램 실행
맥의 **Finder(파인더)**에서 `transparent-widget/` 폴더를 열고 **`transparent-tuber` 파일**을 더블 클릭하여 실행합니다.

> [!NOTE]
> 처음 실행 시 macOS 보안상 마이크 접근 권한을 물어봅니다. 허용해 주셔야 목소리에 반응하여 캐릭터가 말을 합니다.

### 2. 마이크 및 소리 연동 활성화
* 프로그램 실행 후 캐릭터 위를 **더블 클릭(또는 그냥 클릭)**하면 마이크 감지가 활성화됩니다.
* 마이크에 소리가 감지되면 캐릭터가 자동으로 입을 뻥긋거립니다.

### 3. 캐릭터 이동
* 캐릭터를 마우스로 잡고 **화면 어느 곳이든 자유롭게 드래그**하여 놓을 수 있습니다.
* 다른 어떤 프로그램을 실행해도 캐릭터가 항상 맨 앞(z-index 가장 위)에 위치합니다.

### 4. 다른 캐릭터 PSD/PNG 테스트 방법 (하나씩 다 해보기)
사용자님이 말씀하신 여러 캐릭터 파츠들을 차례대로 직접 교체하여 테스트하려면 다음 순서로 하시면 됩니다:
1. 원하는 캐릭터 파츠 4장을 각각 `1_closed_eyes_open.png`, `2_open_eyes_open.png`, `3_closed_eyes_closed.png`, `4_open_eyes_closed.png` 이름으로 저장합니다.
2. `transparent-widget/assets/` 폴더 안의 기존 이미지들을 덮어씁니다.
3. 실행 중이던 `transparent-tuber` 위젯을 끄고 **다시 실행**하면 새로운 캐릭터로 즉시 바뀝니다!

---

## 직접 수정 후 다시 빌드하는 방법 (Swift 컴파일)
만약 `app.swift` 코드를 직접 수정하신 후 다시 컴파일하여 실행 파일을 만들고 싶으시면, 터미널에서 다음 명령어를 실행하면 됩니다:

```bash
swiftc -O -sdk $(xcrun --show-sdk-path) transparent-widget/app.swift -o transparent-widget/transparent-tuber
```
