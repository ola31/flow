# 마크다운 슬라이드 형식 설계

- **작성일**: 2026-05-01
- **상태**: 설계 승인 대기 → 구현 플랜
- **관련 이슈**: PowerPoint/LibreOffice 의존성 제거를 위한 대체 슬라이드 소스

## 배경

현재 Flow는 곡 슬라이드를 `slides.pptx` 파일에서 PowerPoint 또는 LibreOffice를 통해 렌더링한다. 이로 인해:

- PPT 변환 엔진이 시스템에 없으면 슬라이드를 못 봄
- PPT 편집은 별도 외부 앱 필요 (PowerPoint / LibreOffice GUI)
- 단순 가사 슬라이드를 만들고 수정하는 데 무거운 도구가 필요
- 텍스트 검색, git 버전 관리 어려움

해결책: **마크다운 형식의 곡 파일** (`slides.md`)을 PPT 대안으로 도입한다. Flow가 마크다운 텍스트를 직접 파싱해 슬라이드 이미지로 렌더링한다. 외부 도구 의존성 없음.

## 핵심 결정

| 결정 | 선택 | 이유 |
|---|---|---|
| 곡당 형식 | `.md` 또는 `.pptx` 중 하나만 | 단순. 둘 다 있으면 `.md` 우선 |
| 형식 문법 | 표준 Markdown (헤더 + 본문) | 친숙, 외부 에디터/Github 친화적 |
| 슬라이드 단위 | 빈 줄로 구분된 블록 | 직관적, 명시적 |
| 슬라이드 콘텐츠 모델 | 메인 텍스트 + 서브 텍스트 | 사용자 기존 PPT 형식과 매칭 |
| 핫스팟 매핑 | 기존 PPT와 동일 (수동) | 일관성, 마크다운은 슬라이드 생성 대체만 |
| 캔버스 크기 default | PowerPoint 표준 13.333"×7.5" | 업계 표준 |
| 렌더링 의존성 | Qt만 (외부 라이브러리 0) | 자기완결적, 가벼움 |

## 마크다운 형식 스펙

### 파일 위치

곡 폴더 안 `slides.md`. 같은 폴더에 `slides.pptx`도 있으면 `.md` 우선.

```
song/folder/
├── slides.md       ← 우선 사용
├── slides.pptx     ← 무시됨 (slides.md 있을 때)
└── sheets/
```

### 전체 구조

```markdown
---
main_font: "Pretendard Variable"
main_size: 56
main_color: "#FFFFFF"
sub_font: "Pretendard Variable"
sub_size: 18
sub_color: "#CCCCCC"
background: "bg.jpg"
resolution: "1920x1080"
slide_inches: "13.333x7.5"
---

# 어떤 곡

## 1절 :: 어떤 곡 1절

첫 슬라이드 메인 텍스트
둘째 줄

다음 슬라이드 가사

{background: "verse-bg.jpg", main_size: 72}
강조 슬라이드
> 어떤 곡 1절 (special)

## 후렴

후렴 가사 첫 줄
둘째 줄
```

### 파싱 규칙

| 요소 | 의미 |
|---|---|
| `---` ~ `---` (파일 맨 위) | YAML frontmatter (선택) |
| `# 제목` | 곡 제목 — 슬라이드 sub 기본값으로 쓰임 |
| `## 섹션` | 섹션 마커 (네비게이션용). 렌더링 직접 영향 X |
| `## 섹션 :: 섹션-sub-default` | 이 섹션 내 슬라이드 sub 기본값 |
| 빈 줄로 구분된 블록 | 1 슬라이드 |
| 슬라이드 내 일반 라인 | 메인 텍스트 (여러 줄 가능, line-height 1.4) |
| `> sub text` (블록 마지막) | 이 슬라이드 sub 텍스트 (override) |
| `{key: val, ...}` (블록 첫 줄) | 이 슬라이드 속성 override |

### Frontmatter 필드

| 필드 | 타입 | Default | 비고 |
|---|---|---|---|
| `main_font` | string | "Pretendard Variable" | 시스템에 없으면 fallback + 경고 |
| `main_size` | number (pt) | 56 | |
| `main_color` | hex string | "#FFFFFF" | |
| `sub_font` | string | "Pretendard Variable" | |
| `sub_size` | number (pt) | 18 | |
| `sub_color` | hex string | "#CCCCCC" | |
| `background` | string | "#000000" | 이미지 경로(곡 폴더 기준 상대) 또는 색상 |
| `resolution` | "WxH" | "1920x1080" | 출력 픽셀 (렌더링 화질에만 영향) |
| `slide_inches` | "WxH" | "13.333x7.5" | 캔버스 물리 크기. pt 비례 + 종횡비 결정 |

종횡비는 `slide_inches`에서 자동 결정 (기본 16:9). 4:3 슬라이드는 `slide_inches: "10x7.5"` 설정.

### Cascading 적용 우선순위

**일반 속성 (font, size, color, background 등)**:
`슬라이드 override (`{...}`) > frontmatter > 시스템 기본값`

(예: `main_size`는 frontmatter에서 56이지만 특정 슬라이드에서 `{main_size: 72}` override 가능)

**서브 텍스트 내용 (별도 cascade)**:
`슬라이드 sub override (`> ...`) > 섹션 sub default (`## X :: Y`) > 곡 제목 (`# Title`)`

(예: `## 1절 :: 어떤 곡 1절` 아래 슬라이드들은 default sub = "어떤 곡 1절", 개별 `> ...` 있으면 그게 우선)

### 배경 처리

- **이미지 경로**: 곡 폴더 기준 상대 경로 (절대 경로도 허용)
- **색상**: `#RRGGBB` 또는 `#RRGGBBAA` (알파 포함)
- **이미지 스케일링**: 항상 "cover" — 캔버스 꽉 채우고 잘림. v1엔 옵션 없음
- **이미지 못 찾으면**: 배경 색상(default 검정)으로 폴백 + 콘솔 경고. 다른 슬라이드는 정상 렌더

## 레이아웃

사용자 기존 PPT (28cm × 15.75cm, 16:9)에서 추출한 비례를 따른다.

```
┌─────────────────────────────────────────────────┐ y=0%
│                                                 │
│                                                 │
│ ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄ │ y=36.3%  ┐
│                                                 │          │
│              메인 텍스트                         │          │ height
│         (가로 100%, 세로 30%, 중앙 정렬)         │          │ 30%
│                                                 │          │
│ ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄ │ y=65.9%  ┘
│                                                 │
│                                                 │
│            ┌─────────────────────┐              │ y=89.7%  ┐
│            │   서브 텍스트         │              │          │ ~8%
│            └─────────────────────┘              │ y=98%    ┘
└─────────────────────────────────────────────────┘ y=100%
       └──── 가로 46% width, 중앙 ────┘
```

| 영역 | 위치 (% of canvas) | 크기 | 정렬 |
|---|---|---|---|
| 메인 텍스트 | top 36.3%, left 0% | width 100%, height 30% | 가로/세로 중앙 |
| 서브 텍스트 | top 89.7%, left 27% | width 46%, height ~8% | 가로/세로 중앙 |
| 배경 | (0,0) → (100%,100%) | full | cover |

v1엔 레이아웃 비례 hardcoded. 향후 frontmatter에 `main_box`, `sub_box` 같이 노출할 수 있음.

## 아키텍처

```
song/folder/slides.md
       │
       ▼
  MarkdownParser
       │
       │  SongSpec(title, frontmatter, slides[])
       │  Slide(main_text, sub_text, attrs)
       ▼
  MarkdownRenderer  (Qt QPainter — 외부 의존성 0)
       │
       │  list[QImage]
       ▼
MarkdownSlideConverter  (SlideConverter 인터페이스 구현)
       │
       │  convert_slide(path, index) → QImage
       ▼
SlideManager (기존 그대로 — 마크다운/PPT 차이 모름)
       │
       ▼
UI / Live 모드
```

### 새 패키지: `src/flow/services/markdown/`

```
markdown/
├── __init__.py
├── parser.py         # MarkdownParser, SongSpec, Slide 데이터클래스
└── renderer.py       # MarkdownRenderer (SongSpec → QImage list)
```

### `slide_converter.py` 변경

- 새 클래스 `MarkdownSlideConverter(SlideConverter)` 추가
- `create_slide_converter()` 진입 시점이 아니라, **곡 단위로 결정**해야 함 (한 프로젝트 안에 마크다운 곡과 PPT 곡이 섞일 수 있음)

다만 현재 구조는 SlideManager가 단일 converter를 들고 있어서 **converter는 곡과 독립적**. 변경 두 가지 방안:

A. **SlideManager가 곡별로 converter 결정** — `load_pptx`처럼 `load_song(song)` 메서드를 도입, 곡 path 보고 적절한 converter 골라 사용. 기존 PPT-only converter는 그대로, 마크다운은 새 converter
B. **모든 converter가 모든 형식 지원** — `MarkdownSlideConverter`가 PPT도 처리(내부적으로 LibreOffice 위임), 또는 그 반대

A가 깔끔. `MarkdownSlideConverter`는 `.md` 파일만, 기존 converter들은 `.pptx`만. SlideManager가 path 확장자(또는 곡 폴더 검사) 보고 dispatch.

### `Song` 도메인 변경

```python
@property
def markdown_path(self) -> Path:
    """slides.md 절대 경로."""
    p = self.slides_path.parent / "slides.md" if self.slides_path else (self.folder / "slides.md")
    return self._resolve_abs(p)

@property
def has_markdown(self) -> bool:
    return self.markdown_path.exists()

@property
def slide_source(self) -> Literal["markdown", "pptx", "none"]:
    if self.has_markdown:
        return "markdown"
    if self.has_slides:  # 기존 메서드 — slides.pptx 존재 검사
        return "pptx"
    return "none"
```

### SlideManager dispatch

기존 `load_pptx(path)` 진입점은 사용처가 많아 유지. 호출자(예: ProjectScreen, song 로드 흐름)가 `song.slide_source`를 보고 적절한 path 전달:
- `slide_source == "markdown"` → `song.markdown_path` 전달
- `slide_source == "pptx"` → `song.abs_slides_path` 전달 (기존)

SlideManager 내부에서 path 확장자 보고 적절한 converter 선택. 다중 converter를 동시 보유하거나, MarkdownSlideConverter / PPT converter 중 path별로 dispatch하는 방식.

내부 구조 옵션:
- A. SlideManager가 PPT converter + Markdown converter 둘 다 들고 path 보고 dispatch (단순)
- B. 단일 dispatch converter가 내부에 둘 다 위임 (추가 추상화)

A가 단순해서 추천.

## 렌더링 파이프라인

`MarkdownRenderer.render_all(spec, song_dir) -> list[QImage]`:

각 슬라이드마다:
1. `QImage(width, height, Format_RGB32)` 생성 (frontmatter resolution)
2. `QPainter` 시작
3. 배경 그리기:
   - 색상이면 `fillRect`
   - 이미지면 `drawImage(target=full canvas, source=cover-cropped)`
4. 메인 텍스트 박스 (top 36.3%, height 30%, full width):
   - `QFont(main_font, main_size)` 설정
   - `QPainter.drawText(box, Qt.AlignCenter | Qt.TextWordWrap, main_text)`
   - 색상: `main_color`
5. 서브 텍스트 박스 (top 89.7%, height 8%, width 46% centered):
   - 동일 방식, sub 속성 사용
6. `QPainter.end()` → QImage 반환

### pt → 픽셀 변환

캔버스 물리 크기 (`slide_inches`)와 출력 해상도(`resolution`)로 DPI 결정:
- DPI = `resolution_height / slide_inches_height`
- 픽셀 사이즈 = `pt × DPI / 72`

이렇게 하면 사용자 PPT의 캔버스 크기가 같으면 pt → 픽셀 비례가 같아 시각 인상 동일.

### 폰트 fallback 체인

1. frontmatter `main_font` (또는 `sub_font`)
2. "Pretendard Variable" (시스템에 있으면)
3. Qt 시스템 sans-serif default

해당 폰트 없으면 `QFontDatabase.systemFont(SystemFont)`로 폴백 + 콘솔 경고.

## 캐시 + 파일 워처

- `MarkdownSlideConverter`가 메모리 캐시 유지: `dict[Path, list[QImage]]`
- 기존 SlideManager의 watchdog observer가 `.pptx`처럼 `.md` 변경도 감지 → cache invalidate → UI 자동 리프레시
- 외부 에디터(VS Code 등)에서 `.md` 저장 → Flow 즉시 리렌더 (라이브 모드에서도)

## 에러 처리

| 시나리오 | 동작 |
|---|---|
| frontmatter 파싱 실패 | 빨간 placeholder 슬라이드 + 콘솔 경고. 워처 재로드 시 재시도 |
| 잘못된 frontmatter 값 (예: `aspect: "abc"`) | 잘못된 값 무시, default 사용 + 경고 |
| 슬라이드 override 파싱 실패 | 그 슬라이드만 default로 폴백 + 경고 |
| 배경 이미지 못 찾음 | 배경 색상으로 폴백 + 경고 |
| 폰트 시스템에 없음 | fallback + 경고 |
| 빈 .md 파일 | 슬라이드 0장 (PPT 0장과 동일 흐름) |
| `.md` + `.pptx` 둘 다 있음 | `.md` 우선 |

**핵심 원칙**: 렌더링은 절대 fail 안 함. 한 슬라이드 망가져도 나머지는 보임. 라이브 모드에서 silent fail이 더 위험.

## 핫스팟/매핑 시스템

**손 안 댐**. SlideManager가 N장의 슬라이드 이미지를 주는 한 그 위 모든 시스템(verse 매핑, 핫스팟, live 모드)은 그대로 동작. 마크다운은 슬라이드 소스를 대체할 뿐.

## 테스트

### 단위 테스트 (`tests/markdown/`)

| 모듈 | 테스트 |
|---|---|
| `parser.py` | frontmatter 파싱(유효/잘못된 값), 섹션, sub default(`::`), 슬라이드 분리(빈 줄), slide override(`{...}`), `>` sub override, 우선순위 cascading |
| `renderer.py` | 한 슬라이드 → QImage (offscreen Qt), 배경 색상 적용, 배경 이미지 cover, 메인 텍스트 박스 위치, sub 텍스트 박스 위치, 폰트 fallback |
| `markdown_slide_converter` | 캐싱 동작, invalidate, get_slide_count, 빈 파일 처리 |

### 통합 테스트

- `slide_converter` dispatch: `.md` 곡 → `MarkdownSlideConverter`, `.pptx` 곡 → 기존 PPT 흐름
- SlideManager가 `.md` 곡을 PPT 곡과 같은 인터페이스로 다룸
- 파일 워처: `.md` 수정 → cache invalidate → UI 리프레시

### 시각 회귀 테스트 (선택)

- 알려진 입력 `.md` → 알려진 출력 PNG (픽셀 일치 검증)
- 폰트 차이로 인한 false positive 가능성 → CI에서 폰트 고정 필요

## 범위

### v1 포함

1. `src/flow/services/markdown/` 신규 패키지 (parser, renderer)
2. `MarkdownSlideConverter` 추가 (`slide_converter.py`)
3. SlideManager dispatch 로직 (`.md` vs `.pptx`)
4. `Song` 도메인에 `markdown_path`, `has_markdown`, `slide_source` 추가
5. 파일 워처가 `.md` 변경 감지
6. Frontmatter 스키마: `main_*`, `sub_*`, `background`, `aspect`, `resolution`, `slide_inches`
7. 슬라이드 override (`{...}`)
8. 섹션 sub default (`::`)
9. 배경: 색상 + 이미지 (cover scaling)
10. 폰트 fallback
11. 캐시 + watcher 자동 invalidate

### v1 제외 (향후)

- 워크스페이스 전역 테마 (`workspace/theme.yaml`)
- 인라인 스타일 (굵게/기울임/밑줄)
- 텍스트 정렬 옵션 (좌/우 정렬, justify)
- 행간/자간 커스터마이징
- 이미지 스케일링 옵션 (contain, stretch)
- 배경 이미지 어둡게/오버레이
- Flow 내장 마크다운 에디터 (외부 에디터 사용 권장)
- PPT → 마크다운 자동 변환 도구
- 다국어 동시 표시 (한/영 병행)
- 차트/표 렌더링

## 리스크 / 모름 박스

- **폰트 렌더링 차이**: 같은 폰트 같은 사이즈라도 OS별로 글리프 차이로 미세 다르게 보일 수 있음. 시각 회귀 테스트가 어려운 이유. CI에서 고정 폰트 사용으로 완화.
- **PPT의 미세한 효과**: 사용자 기존 PPT가 그림자/투명도/그라디언트 같은 효과 쓰면 마크다운으론 재현 안 됨. v1은 단순 텍스트만.
- **이미 작업한 PPT 곡 마이그레이션**: 자동 변환 도구 없음. 사용자가 수동으로 마크다운 작성. v1엔 새 곡만 마크다운으로 만드는 시나리오 가정.
- **메모리 캐시**: 200 슬라이드 곡 × 1920×1080 RGB → 약 1.2GB. 큰 라이브러리에선 LRU 또는 lazy 렌더가 필요할 수 있음. v1엔 무제한 캐시.
- **Hot reload 타이밍**: watchdog 이벤트 후 디스크 동기화 시점 차이로 가끔 빈 파일을 읽을 수 있음 — 짧은 retry 또는 debounce로 완화.
