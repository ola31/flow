# AGENT.md: LLM을 위한 개발 가이드

이 파일은 **Flow** 프로젝트를 이해하고 LLM(AI 어시스턴트)이 효율적으로 코딩을 지원할 수 있도록 핵심 컨텍스트를 제공합니다.

---

## 프로젝트 개요

- **목적**: 악보 이미지의 핫스팟에 PPT 슬라이드를 매핑하여, 예배 중 한 번의 클릭으로 자막을 송출하는 도구.
- **핵심 가치**: 끊김 없는 예배 송출 경험, 가사와 시각 정보의 직관적 연결.
- **구조**: Song(곡) → Project(셋리스트) 2단계 아키텍처.

## 기술 스택

- **Language**: Python 3.10+
- **UI Framework**: PySide6 (Qt Widgets)
- **Design System**: `styles.py` (디자인 토큰), `icons.py` (Material Symbols Rounded)
- **Dependencies**: python-pptx, pdf2image + LibreOffice, pytest
- **Build**: PyInstaller (`--onedir` + Splash Screen 권장)

## 아키텍처

1. **Domain** (`src/flow/domain/`): Project, Song, ScoreSheet, Hotspot (dataclass)
2. **Services** (`src/flow/services/`): SlideManager, ConfigService, SlideConverter
3. **Repository** (`src/flow/repository/`): ProjectRepository (JSON 직렬화)
4. **UI** (`src/flow/ui/`): PySide6 위젯 계층
   - `styles.py`: 컬러 팔레트, 스페이싱, 타이포그래피, 글로벌 스타일시트
   - `icons.py`: Material Symbols Rounded 아이콘 헬퍼 (서브셋 폰트 66KB)
   - `screens/`: HomeScreen, ProjectScreen (레이아웃 컨테이너)
   - `editor/`: ScoreCanvas, SongListWidget, MappingPanel, SlidePreviewPanel, VerseSelector
   - `live/`: LiveController (Preview-Live 상태 머신)
   - `display/`: DisplayWindow (전체화면 송출)

---

## 디자인 시스템

### 컬러 (styles.py 토큰 사용 필수)

5단계 그레이 + 1 액센트 블루 + 시맨틱 컬러:

- 배경: `BG_DEEP`(#121212) → `BG_SURFACE`(#1a1a1a) → `BG_ELEVATED`(#222222) → `BG_HOVER`(#2a2a2a)
- 텍스트: `TEXT_PRIMARY`(#e8e8e8) → `TEXT_SECONDARY`(#a0a0a0) → `TEXT_TERTIARY`(#606060)
- 액센트: `ACCENT`(#5b8def) — 선택, CTA, 링크에만 사용
- 시맨틱: `GREEN`(#34d399, 성공), `AMBER`(#f59e0b, 경고), `RED`(#ef4444, 라이브/위험)

### 타이포그래피

- `font-weight: 500` (medium) 기본, `600` (semibold) 섹션 제목
- **`bold`, `900` 사용 금지** — 작은 텍스트에서 가독성 저하
- 크기: `FONT_SM`(11px) ~ `FONT_2XL`(18px)

### 아이콘

- Material Symbols Rounded 서브셋 (66KB, `src/flow/resources/`)
- `icons.py`의 `icon_qicon()` 사용 (QAction/QToolButton용)
- 이모지 사용 금지

### 시각적 깊이

- 보더 최소화, 배경색 차이로 영역 구분
- 드롭 섀도우: `QGraphicsDropShadowEffect` (홈 화면 패널 등)
- 선택 상태: 좌측 3px 액센트 바

---

## 치명적 함정 및 방어 규칙

### 1. 키보드 내비게이션
- Up/Down: 핫스팟 이동 (Preview만, Live 아님)
- Enter: Preview → Live 확정
- 숫자키로 절 변경 시 `LiveController.sync_live()` 반드시 호출

### 2. 라이브 모드 편집 잠금
- 편집 로직 입구에서 `if self._is_live: return` 필수
- `set_editable(False)` 호출로 위젯 레벨 잠금

### 3. 절(Verse) 매핑
- `verse_index 0-4`: 1-5절, `5`: 후렴
- 후렴은 절 매핑이 없을 때 폴백으로 사용

### 4. 경로 처리
- JSON 저장 시 `Path.as_posix()` 사용 (Windows 역슬래시 방지)

### 5. 스레딩
- PPT 변환은 반드시 `QThread` 워커에서 처리, 시그널로 UI 업데이트

### 6. 스타일시트 우선순위
- `QListWidget::item`의 CSS `background-color`는 `item.setBackground()`를 덮어씀
- 아이템 배경 변경이 필요하면 CSS에서 `background-color: transparent` 설정 후 코드로 제어
- 또는 `setForeground()`로 텍스트 색상 변경 (CSS에 영향 안 받음)

---

## 코드 관례

### 금지 사항
- `currentItemChanged` + `itemClicked` 동시 연결 → 중복 호출
- 위젯에 색상 하드코딩 → `styles.py` 토큰 import
- 도메인 직접 수정 → `undo_commands` 사용
- `font-weight: bold/900` → `500` 또는 `600`
- 이모지 → Material Symbols (`icons.py`)

### 권장 사항
- `from __future__ import annotations` 항상 첫 줄
- SignalSpy 패턴으로 Qt 시그널 테스트
- PPT 변환 실패 시 사용자 알림 + 더미 이미지 표시

---

## 향후 계획

### 워크스페이스 구조 개편 (예정)
현재 곡이 프로젝트 폴더 안에 포함되는 구조에서, 공용 라이브러리 분리 구조로 전환 예정:

```
워크스페이스/
├── library/              # 공용 곡 라이브러리
│   ├── 곡A/
│   └── 곡B/
└── projects/
    ├── 프로젝트1/
    │   ├── project.json  # library 곡 참조
    │   └── songs/        # 로컬 오버라이드 (커스텀 PPT 등)
    └── 프로젝트2/
```

- 곡 해석 우선순위: `projects/{name}/songs/{곡}` → `library/{곡}`
- 워크스페이스는 위치 자유, 여러 개 생성 가능
- 프로젝트 복제 = project.json만 복사

---

*이 파일은 프로젝트의 살아있는 지도입니다. 구조적 변화가 있을 때마다 업데이트하십시오.*
