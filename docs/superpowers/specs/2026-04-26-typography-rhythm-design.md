# Typography rhythm 개편 설계

**날짜:** 2026-04-26
**작업 단계:** 시각적 쾌감 부여 3-of-3 중 1단계 (타이포 → 깊이감 → 모션)
**대상 파일:** `src/flow/ui/styles.py` 외 위젯 다수

## 배경

현재 UI는 "정적인 깔끔함"은 있지만 시각적 쾌감이 부족하다는 사용자 피드백. 원인 중 하나는 **타이포그래피 리듬이 평탄**한 것 — 본문(11pt)과 제목(13~16pt)의 차이가 1.2× 수준에 그쳐, 화면별 정체성이 흐릿하다.

본 스펙은 폰트 토큰 시스템을 재설계하여 분명한 hierarchy(2XS 10pt → DISPLAY 24pt, 8단계)를 부여한다.

## 비목표

- 색상 / 간격 / 모션 변경 (다음 단계에서 다룸)
- 폰트 패밀리 교체 (Pretendard Variable 유지)
- bold (700) 사용 부활 (FW_SEMI 590이 최대)

## 토큰 시스템

### 사이즈 + 가중치

```
FONT_2XS    = 10   FW_REGULAR (400)   메타·타임스탬프
FONT_XS     = 11   FW_REGULAR (400)   라벨·캡션
FONT_SM     = 12   FW_REGULAR (400)   본문 기본       ← 11에서 +1
FONT_MD     = 13   FW_MEDIUM  (510)   강조 본문·리스트 제목
FONT_LG     = 15   FW_SEMI    (590)   카드 헤더·다이얼로그 본문 강조  ← 신설
FONT_TITLE  = 18   FW_SEMI    (590)   패널 섹션 헤더
FONT_HEAD   = 20   FW_SEMI    (590)   다이얼로그·EmptyState 제목      ← 신설
FONT_DISPLAY= 24   FW_SEMI    (590)   페이지 최상위 헤드라인           ← 신설
```

비율: 10 → 11 → 12 → 13 → 15 → 18 → 20 → 24 (~1.10× 증가하다 헤드라인부터 1.20× 점프)

### 가중치는 권장 기본값

각 토큰에 "전형적 가중치"가 있지만 위젯에서 override 가능. 예: 라벨 강조하려면 FONT_XS + FW_MEDIUM.

## Per-screen 적용 매핑

| 위치 | 신규 토큰 | 현재 |
|---|---|---|
| 워크스페이스 런처 상단 "Workspaces" | DISPLAY 24 | ~16pt |
| 프로젝트 화면 좌상단 프로젝트명 | DISPLAY 24 | 13~14pt |
| 곡 편집 화면 좌상단 곡명 | DISPLAY 24 | 동일 |
| 다이얼로그 큰 헤더 (워크스페이스 선택, 곡 라이브러리) | HEAD 20 | FONT_2XL=16 |
| EmptyState 제목 | HEAD 20 | 13~14pt |
| 셋리스트 패널 헤더 "Setlist" | TITLE 18 | 본문급 |
| 매핑 패널 섹션 헤더 (Verses, Hotspots) | TITLE 18 | 13pt |
| 슬라이드 미리보기 패널 헤더 | TITLE 18 | 동일 |
| 카드 안 제목 (워크스페이스/프로젝트 카드) | LG 15 | 13pt |
| 다이얼로그 본문 강조 (확인 메시지 첫 줄) | LG 15 | FONT_MD=12 |
| 본문·리스트 아이템 제목 | MD 13 | 13pt |
| 본문 기본 | SM 12 | 11pt → +1pt |
| 라벨·캡션 (예: "최근 항목" kicker) | XS 11 | 11pt (변동 없음, 명칭만 변경) |
| 메타·타임스탬프 | 2XS 10 | 11pt → −1pt |

## Letter-spacing

기존 codebase에 이미 적용 중인 패턴(`project_launcher.py:237`, `project_screen.py:55`, `:454`) 유지·확장:

- 작은 kicker/badge 라벨 (10~11pt, 한글 또는 짧은 영문)에 `QFont.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)` 적용
- 적용 대상: "최근 항목", "MAPPED" 같은 짧은 라벨
- DISPLAY/HEAD/TITLE 토큰에는 적용하지 않음 — 한글 폰트에서 효과 미미하고 어색해짐
- 본 단계에서 letter-spacing 토큰은 신설하지 않음 (기존 패턴 그대로)

## 하드코딩 마이그레이션 리스트

기존 위젯 중 토큰을 거치지 않고 px값을 직접 박은 곳을 모두 정리한다.

### `src/flow/ui/screens/project_screen.py`
- L51: `font-size: 10px; font-weight: 500;` → `FONT_2XS, FW_MEDIUM`
- L70: `font-size: 10px; color: #aaa;` → `FONT_2XS + TEXT_TERTIARY`
- L309: `font-size: 11px; font-weight: 500;` → `FONT_XS, FW_MEDIUM`
- L324: `font-size: 13px; font-weight: 500; color: #e0e0e0;` → `FONT_MD, FW_MEDIUM, TEXT_PRIMARY`
- L343: `font-size: 11px; font-weight: 500;` → `FONT_XS, FW_MEDIUM`

### `src/flow/ui/song_manager_dialog.py`
- L307: `color: #ccc; font-size: 11px;` → `TEXT_SECONDARY + FONT_XS`
- L309: `color: #eee; font-weight: bold; font-size: 12px;` → `TEXT_PRIMARY + FW_SEMI + FONT_SM`
- L324: `font-size: 8px;` — 특수 작은 배지. 토큰화 안 함 (인라인 유지, 1회용).

### 신규 토큰명에 맞춰 갱신할 위젯

토큰명은 유지되지만 의미하는 사이즈가 달라지므로 (예: `FONT_SM` 11→12, `FONT_MD` 12→13), 사용 중인 위젯에서 의도와 토큰이 맞는지 재검토 + 신규 토큰(LG 15, HEAD 20, DISPLAY 24, 2XS 10) 적용 위치 결정:

- `src/flow/ui/dialogs.py` — 다이얼로그 헤더에 HEAD 도입, 본문 강조에 LG 검토
- `src/flow/ui/empty_state.py` — title 토큰을 HEAD로 교체
- `src/flow/ui/workspace_dialog.py` — 헤더에 HEAD, 카드 제목에 LG
- `src/flow/ui/editor/mapping_panel.py` — 섹션 헤더에 TITLE 18 적용
- `src/flow/ui/editor/slide_preview_panel.py` — 패널 헤더에 TITLE 18
- `src/flow/ui/project_launcher.py` — 화면 상단 "Workspaces"에 DISPLAY
- `src/flow/ui/screens/project_screen.py` — 프로젝트명 표시부에 DISPLAY (현 위치 식별 필요)
- `src/flow/ui/screens/song_edit_screen.py`(존재 시) — 곡명 표시부에 DISPLAY

## 리스크 및 대응

| 리스크 | 대응 |
|---|---|
| 본문 11→12로 키우면 매핑 패널처럼 빽빽한 곳에서 줄바꿈 빈도 ↑ | 적용 후 시각 검증. 문제 시 매핑 패널만 11pt 유지 (override). |
| 프로젝트명 길면(28자 한글+) DISPLAY 24pt에서 두 줄 가거나 클립 | 단일 줄 + ellipsis 처리 (기존 패턴 유지). |
| 13인치 노트북에서 DISPLAY 24pt가 페이지 상단 비율을 과하게 차지 | 시각 검증 후 결정. 필요 시 화면 폭 조건부로 22pt 폴백. |

## 검증 방법

자동화된 타이포 회귀 테스트는 만들지 않는다(시각 변화이므로). 적용 후 직접 확인할 체크리스트:

1. 워크스페이스 런처 (DISPLAY)
2. 프로젝트 화면 진입 (DISPLAY + TITLE 패널 헤더)
3. 곡 편집 모드 (DISPLAY + TITLE)
4. 워크스페이스 선택 다이얼로그 (HEAD)
5. EmptyState (프로젝트가 빈 상태)
6. 매핑 패널 (TITLE 섹션 헤더, 본문 12pt 빽빽함 체크)
7. 슬라이드 미리보기 패널 (TITLE)
8. 셋리스트 카드 (LG 15)
9. `pytest`로 기존 회귀 없음 확인

## 산출물

- `src/flow/ui/styles.py` — 토큰 정의 추가/변경
- 매핑 표에 등장한 위젯 파일들 — import + 사이즈 교체
- `scripts/typography_preview.py` — 1회용. 작업 종료 후 삭제 또는 유지 결정 (개발용 도구로 두는 것도 한 옵션)

## 다음 단계

본 작업 완료 후 진행할 단계 (오늘 세션과는 별도 spec):
- **Phase 2:** 깊이감 (그라디언트 / 글로우 / shadow)
- **Phase 3:** 모션 (hover/focus 트랜지션, dialog fade-in)
