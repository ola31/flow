# 🤖 AGENT.md: LLM을 위한 개발 가이드

이 파일은 **Flow** 프로젝트를 이해하고 LLM(AI 어시스턴트)이 효율적으로 코딩을 지원할 수 있도록 핵심 컨텍스트를 제공합니다. 새로운 작업을 시작하기 전 가장 먼저 읽어야 합니다.

---

## 📋 프로젝트 개요
- **목적**: 악보(이미지) 상의 특정 지점(Hotspot)에 PPT 슬라이드를 매핑하여, 한 번의 클릭이나 키보드 조작으로 찬양 자막 등을 즉시 송출하는 도구.
- **핵심 가치**: "끊김 없는 예배 송출 경험", "가사와 시각 정보의 직관적 연결".

## 🛠 기술 스택
- **Language**: Python 3.13+
- **UI Framework**: PySide6 (Qt for Python).
- **Core Dependencies**: 
  - `python-pptx`: PPT 분석.
  - `pdf2image` + `LibreOffice`: PPT를 고화질 이미지로 변환 (리눅스 호환성 중요).
  - `pytest`: 테스트 프레임워크.
- **Build**: PyInstaller (Windows용 `.exe` 타겟).
- **Deployment Strategy**: 실행 속도 최적화를 위해 **`--onedir` (폴더 방식)** + **Splash Screen** 조합을 권장합니다.

## 🎨 디자인 미학 및 스타일 가이드 (Design Aesthetics)

본 프로젝트는 "Qt 특유의 거친 느낌(Raw Look)"을 배제하고, 현대적이고 스타일리시한 다크 인터페이스를 지향합니다.

### 1. 시각적 정체성
- **Aesthetic**: Vibrant Dark, Glassmorphism(subtle), Premium Finishes.
- **Color Palette**: 
  - Background: `#1e1e1e` (Main), `#252525` (Panel).
  - Accent: `#2196f3` (Vibrant Blue) - 활성/선택 상태의 고유 색상.
- **Styling Rules**:
  - 패널 테두리는 얇게(`1px`), 큰 컨테이너는 부드러운 곡률(`border-radius: 12px`) 적용.
  - 마우스 호버 및 선택 시 명확하지만 과하지 않은 배경색 변화(ex: `#333` -> `#444`) 필수.

## 🏗 아키텍티럴 설계 (Architecture)
프로젝트는 크게 세 가지 계층으로 나뉩니다:

1.  **Domain (비즈니스 엔티티)**: `src/flow/domain`
    - `Project`: 전체 세션 관리 (시트 목록, 현재 선택 정보).
    - `ScoreSheet`: 개별 곡 단위 (악보 이미지, 핫스팟 목록).
    - `Hotspot`: 악보 위 버튼 (가사 텍스트, **절(Verse)별 슬라이드 매핑**).
2.  **Services (비즈니스 로직)**: `src/flow/services`
    - `SlideManager`: PPT 이미지 로딩 및 캐싱.
    - `ConfigService`: 최근 프로젝트, 사용자 설정 (OS 통합 경로 처리 필수).
    - `SlideConverter`: PPT -> PDF -> Image 변환 파이프라인.
3.  **UI (표현 계층)**: `src/flow/ui`
    - `MainWindow`: 메인 컨테이너 및 전역 이벤트 필터링.
    - `LiveController`: **Preview-Live 2단계 송출** 상태 머신.
    - `Editor/ScoreCanvas`: 핫스팟 배치 및 조작 그래픽 뷰.

---

## ⚠️ LLM을 위한 치명적 함정 및 방어 규칙 (Guardrails)

### 1. 전역 키보드 내비게이션 (Navigation & Focus Policy)
- **상하(Up/Down) 키**: 핫스팟 리스트를 이동합니다. 이때 **라이브 송출은 되지 않지만, 하단 Preview 패널은 즉시 업데이트**되어야 합니다. 사용자는 미리보기를 보면서 엔터를 누를지 말지 결정합니다.
  - **주의**: 리스트의 `currentItemChanged` 시그널이 발생할 때 오직 `LiveController.set_preview`만 호출되도록 보장해야 합니다. 실수로 라이브 송출 시그널과 엉키면 안 됩니다.
- **엔터(Enter) 키**: 방향키로 정한 Preview를 최종 확정하여 Live로 쏘는 '결정타'입니다. 이 연동이 끊기면 사용자는 방향키로만 헤매게 됩니다.
- **좌우(Left/Right) 키**: 현재 프로젝트 내의 곡(ScoreSheet)을 넘깁니다. 곡이 넘어가면 첫 번째 핫스팟이 자동으로 Preview에 잡혀야 합니다.

### 2. 라이브 모드 중 편집 잠금 (Live Mode Edit Guard)
- **함정**: 라이브 송출 중(화면이 하나라도 송출 중일 때)에 실수로 핫스팟을 드래그하거나 이름을 바꾸는 등의 편집이 수행되면 방송 사고로 이어집니다.
- **방어**: 
  - `ScoreCanvas`와 `SongListWidget` 등에서 라이브 모드가 활성화되어 있는지 항상 체크해야 합니다.
  - 편집 로직 입구에서 `if self._is_live_mode: return`과 같은 가드 문구를 배치하는 것이 관례입니다.
  - 관련 메서드: `SlidePreviewPanel.set_editable()`, `SongListWidget.set_editable()` 등을 통해 위젯 레벨에서 편집 기능을 끄고 켜는 로직을 철저히 확인하십시오.

### 3. 절(Verse) 변경 시 라이브 동기화 (Live Sync Trap)
- **함정**: 숫자키(1~6)로 절을 바꾸면, 현재 Live로 나가고 있는 슬라이드도 **해당 절의 매핑된 슬라이드로 즉시 교체**되어야 합니다.
- **누락 주의**: 단순히 내부 변수만 바꾸고 Live 화면을 갱신하지 않는 실수가 잦습니다. `LiveController.sync_live()`가 이 역할을 수행하니 절대 누락하지 마십시오.

### 3. 경로 처리의 지옥 (The Windows-Separator Trap)
- **함정**: 파이썬의 `str(Path)`는 실행 환경에 따라 `\`를 반환합니다. 리눅스 서버나 빌드 환경에서 이 경로가 DB나 JSON에 저장되면 나중에 인지하지 못합니다.
- **방어**: 파일 시스템과 소통하는 모든 문자열은 반드시 `.as_posix()`를 사용하여 `/`로 통일하십시오. `ConfigService.add_recent_project` 로직을 참고하여 정규화되지 않은 경로는 시스템에 발을 들이지 못하게 하십시오.

### 3. 스레딩과 UI 블로킹 (The PPT Conversion Trap)
- **함정**: PPT 변환(특히 LibreOffice 연동)은 매우 무거운 작업입니다. UI 스레드에서 이를 호출하면 앱이 '응답 없음' 상태에 빠집니다.
- **방어**: `SlideManager`와 `SlideConverter`의 상호작용을 확인하십시오. 긴 작업은 반드시 별도 스레드에서 처리하고 시그널로 결과를 받아 UI를 업데이트해야 합니다.

### 4. 절(Verse) 매핑의 비밀 번호
- **도메인 지식**: `current_verse_index` 값의 의미를 정확히 파악하십시오.
  - `0~4`: 0절~4절 (사용자 UI상 1절~5절)
  - `5`: **후렴(Chorus)** - 가장 빈번하게 사용되며, 특정 절 매핑이 없을 때 폴백(Fallback)으로 사용되는 논리적 종착지입니다.
- **로직**: `Hotspot.get_slide_index(5)`는 내비게이션 실패 시의 마지막 안전장치입니다.

### 5. 폴더 방식(`--onedir`) 배포 시 유지보수
- **삭제**: 앱이 설치된(압축 해제된) 폴더 전체를 삭제하기만 하면 됩니다. 별도의 레지스트리 처리가 없으므로 폴더 삭제가 곧 언인스톨입니다.
- **업데이트**: 기존 폴더의 파일들을 새 버전 파일로 덮어쓰거나, 폴더 자체를 교체합니다. 
- **주의**: 사용자 데이터(설정 파일 등)는 보통 사용자의 홈 디렉토리(`.flow/config.json`)에 저장되므로 폴더 교체 시에도 유지되도록 설계되어 있습니다.

---

## 🛠 코드 스타일 및 관례 (Anti-Patterns to Avoid)

### ❌ 하지 말아야 할 것 (Don'ts)
- **Double-firing Signals**: `currentItemChanged`와 `itemClicked`를 동시에 연결하지 마십시오. 중복 송출의 원인이 됩니다.
- **Ad-hoc Styling**: 개별 위젯에서 스타일시트를 하드코딩하지 마십시오. `MainWindow.py`의 상단 스타일 선언부나 `ProjectLauncher`의 집중된 스타일 영역을 사용하십시오.
- **Direct Domain Mutation**: UI 클래스에서 `hotspot.slide_index = 10`과 같이 도메인을 직접 수정하지 마십시오. 반드시 `undo_commands`를 통해 캡슐화하여 Undo/Redo 체인을 유지해야 합니다.

### ✅ 권장 사항 (Dos)
- **SignalSpy for Tests**: Qt 외부 플러그인에 의존하지 말고 `tests/ui/test_live_controller.py`에 구현된 `SignalSpy` 패턴을 복사해서 사용하십시오.
- **Graceful Error Handling**: PPT 변환 실패 시 사용자에게 알리고 더미 이미지를 보여주는 안정성을 유지하십시오.

---

## 📜 주요 시나리오 가이드 (How-to)

### 새로운 편집 기능을 추가하고 싶다면?
1. `domain/` 모델에 필드 추가.
2. `undo_commands.py`에 해당 작업을 수행하고 되돌리는 `QUndoCommand` 정의.
3. `MainWindow`에서 해당 커맨드를 `undo_stack.push()`로 실행.
4. **절대** 시그택 없이 도메인만 고치지 마십시오.

### 새로운 UI 위젯을 추가하고 싶다면?
1. `ui/` 아래 적절한 디렉토리에 생성.
2. `AGENT.md`의 스타일 가이드를 준수.
3. 메인 윈도우의 `eventFilter` 등록 여부 검토.

---

*이 파일은 프로젝트의 살아있는 지도입니다. 구조적 변화나 중요한 버그 수정이 있을 때마다 업데이트하십시오.*
