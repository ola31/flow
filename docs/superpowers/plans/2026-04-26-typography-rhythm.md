# Typography Rhythm Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Flow PySide6 데스크톱 앱의 타이포그래피 토큰 시스템을 8단계(2XS 10pt → DISPLAY 24pt)로 재정의하고 위젯 13개를 마이그레이션한다.

**Architecture:** `src/flow/ui/styles.py`에 토큰 추가/변경/제거를 한 번에 한 다음, 위젯별 마이그레이션을 수행한다. 신규 토큰(`FONT_2XS`, `FONT_HEAD`, `FONT_DISPLAY`)이 등장할 자리(워크스페이스/프로젝트/곡 편집 화면 페이지 헤더)는 현재 UI에 존재하지 않으므로 새 라벨 위젯을 추가한다.

**Tech Stack:** Python 3.10+, PySide6, Pretendard Variable 폰트, pytest (Qt offscreen).

**Spec:** `docs/superpowers/specs/2026-04-26-typography-rhythm-design.md`

---

## File map

**Modified:**
- `src/flow/ui/styles.py` — 토큰 정의
- `src/flow/ui/dialogs.py` — 다이얼로그 헤더/본문
- `src/flow/ui/empty_state.py` — title→HEAD
- `src/flow/ui/workspace_dialog.py` — 헤더→HEAD, 카드→LG
- `src/flow/ui/editor/mapping_panel.py` — 섹션 헤더→TITLE
- `src/flow/ui/editor/slide_preview_panel.py` — 패널 헤더→TITLE
- `src/flow/ui/editor/song_list_widget.py` — XL 사용처 정리
- `src/flow/ui/editor/verse_selector.py` — 토큰 import 정리
- `src/flow/ui/settings_dialog.py` — 토큰 import 정리
- `src/flow/ui/project_launcher.py` — 카드 title + 워크스페이스명 DISPLAY
- `src/flow/ui/screens/project_screen.py` — 하드코딩 정리 + 프로젝트명 DISPLAY
- `src/flow/ui/song_manager_dialog.py` — 하드코딩 정리
- `src/flow/ui/main_window.py` — song edit 모드 진입 시 곡명 DISPLAY 표시 연결

**Removed:** 없음 (스크립트 `scripts/typography_preview.py`는 유지)

---

## Token reference (for engineer)

```python
# 신규 토큰 시스템 (styles.py)
FONT_2XS    = 10   # 메타·타임스탬프
FONT_XS     = 11   # 라벨·캡션
FONT_SM     = 12   # 본문 기본              ← 11에서 +1
FONT_MD     = 13   # 강조 본문·리스트 제목
FONT_LG     = 15   # 카드 헤더·다이얼로그 본문 강조  ← 13에서 +2 (값 변경)
FONT_TITLE  = 18   # 패널 섹션 헤더          ← 22에서 -4 (값 변경)
FONT_HEAD   = 20   # 다이얼로그·EmptyState 제목    ← NEW
FONT_DISPLAY= 24   # 페이지 최상위 헤드라인         ← NEW

# 제거: FONT_XL=14, FONT_2XL=16

# 가중치 권장 (위젯에서 override 가능)
2XS, XS, SM     → FW_REGULAR (400)
MD              → FW_MEDIUM  (510)
LG, TITLE, HEAD, DISPLAY → FW_SEMI (590)
```

---

## Phase A — Foundation

### Task 1: Update token definitions in styles.py

**Files:**
- Modify: `src/flow/ui/styles.py:114-130` (타이포그래피 섹션)

- [ ] **Step 1: Run baseline tests to capture current pass count**

```bash
QT_QPA_PLATFORM=offscreen pytest 2>&1 | tail -5
```

Expected: 240 passed (or current count). Note the number for comparison after each task.

- [ ] **Step 2: Update FONT_* tokens**

Replace lines 122-130 of `src/flow/ui/styles.py`:

```python
# ─── 타이포그래피 ────────────────────────────────────────────────────────────

# Pretendard 우선, 시스템 한글 폰트 폴백
FONT_FAMILY = (
    "'Pretendard Variable', 'Pretendard', "
    "-apple-system, 'Apple SD Gothic Neo', 'Malgun Gothic', "
    "'Segoe UI', 'Inter', sans-serif"
)

# 사이즈 — 8단계 hierarchy (2XS → DISPLAY)
FONT_2XS     = 10   # 메타·타임스탬프
FONT_XS      = 11   # 라벨·캡션
FONT_SM      = 12   # 본문 기본
FONT_MD      = 13   # 강조 본문·리스트 제목
FONT_LG      = 15   # 카드 헤더·다이얼로그 본문 강조
FONT_TITLE   = 18   # 패널 섹션 헤더
FONT_HEAD    = 20   # 다이얼로그·EmptyState 제목
FONT_DISPLAY = 24   # 페이지 최상위 헤드라인

# 호환 alias (Phase E에서 제거 예정 — 신규 토큰으로 교체 후)
FONT_XL  = FONT_LG    # 14 → 15 (한 단계 위)
FONT_2XL = FONT_HEAD  # 16 → 20 (HEAD로 승격)
```

- [ ] **Step 3: Run tests to verify no regressions**

```bash
QT_QPA_PLATFORM=offscreen pytest 2>&1 | tail -5
```

Expected: same pass count as baseline. Existing import statements still work via aliases.

- [ ] **Step 4: Smoke-test preview script still runs**

```bash
QT_QPA_PLATFORM=offscreen timeout 5 python -c "
import sys
sys.path.insert(0, 'src')
sys.path.insert(0, 'scripts')
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
import typography_preview as tp
tp.ensure_fonts_loaded()
w = tp.PreviewWindow()
w.show()
app.processEvents()
print('OK')
" 2>&1 | tail -3
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/flow/ui/styles.py
git commit -m "feat(styles): typography token system 재정의 (8단계 hierarchy)

신규: FONT_2XS=10, FONT_HEAD=20, FONT_DISPLAY=24
값 변경: FONT_LG 13→15, FONT_TITLE 22→18
호환 alias: FONT_XL→LG, FONT_2XL→HEAD (Phase E에서 제거)"
```

---

## Phase B — Migration of widgets that already use tokens

### Task 2: Migrate dialogs.py

**Files:**
- Modify: `src/flow/ui/dialogs.py:45` (import) + 본문 사용처

- [ ] **Step 1: Update import**

Find line 45:
```python
    FONT_SM, FONT_MD, FONT_LG, FONT_XL, FW_REGULAR, FW_MEDIUM, FW_SEMI,
```

Replace with:
```python
    FONT_SM, FONT_MD, FONT_LG, FONT_HEAD, FW_REGULAR, FW_MEDIUM, FW_SEMI,
```

- [ ] **Step 2: Apply HEAD to dialog title bar (line 118)**

`FONT_XL` is imported but unused — the new import (Step 1) drops it.

Find line 118:
```python
                font-size: {FONT_LG}px;
```

This is inside the dialog title bar QLabel stylesheet. Per spec, dialog "큰 헤더"는 HEAD 20.

Replace with:
```python
                font-size: {FONT_HEAD}px;
```

- [ ] **Step 3: Run tests + smoke test**

```bash
QT_QPA_PLATFORM=offscreen pytest tests/ -k "dialog or message" 2>&1 | tail -5
```

Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add src/flow/ui/dialogs.py
git commit -m "refactor(dialogs): 다이얼로그 헤더 → FONT_HEAD (20pt)"
```

---

### Task 3: Migrate empty_state.py

**Files:**
- Modify: `src/flow/ui/empty_state.py:36, 85, 87, 98, 100`

- [ ] **Step 1: Update import**

Find line 36:
```python
    FONT_SM, FONT_MD, FONT_LG, FW_REGULAR, FW_MEDIUM, FW_SEMI,
```

Replace with:
```python
    FONT_SM, FONT_MD, FONT_LG, FONT_HEAD, FW_REGULAR, FW_MEDIUM, FW_SEMI,
```

- [ ] **Step 2: Apply HEAD to title (non-compact mode)**

Find lines 85-87:
```python
            title_size = FONT_MD if compact else FONT_LG
            self._title.setStyleSheet(
                f"color: {TEXT_PRIMARY}; font-size: {title_size}px; "
```

Replace with:
```python
            title_size = FONT_MD if compact else FONT_HEAD
            self._title.setStyleSheet(
                f"color: {TEXT_PRIMARY}; font-size: {title_size}px; "
```

- [ ] **Step 3: Verify description sizes still work with new token meanings**

Lines 98-100 currently:
```python
            desc_size = FONT_SM if compact else FONT_MD
            self._desc.setStyleSheet(
                f"color: {TEXT_TERTIARY}; font-size: {desc_size}px; "
```

`FONT_SM` was 11, now 12. `FONT_MD` was 12, now 13. No code change needed — values shift naturally per token system.

- [ ] **Step 4: Run tests**

```bash
QT_QPA_PLATFORM=offscreen pytest 2>&1 | tail -3
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/flow/ui/empty_state.py
git commit -m "refactor(empty_state): title → FONT_HEAD (20pt)"
```

---

### Task 4: Migrate workspace_dialog.py

**Files:**
- Modify: `src/flow/ui/workspace_dialog.py:34-37, 77, 81, 113, 121, 136, 153, 167, 189`

- [ ] **Step 1: Update imports**

Find lines 34-37:
```python
    FONT_LG,
    FONT_MD,
    FONT_SM,
    FONT_2XL,
```

Replace with:
```python
    FONT_LG,
    FONT_MD,
    FONT_SM,
    FONT_HEAD,
```

- [ ] **Step 2: Migrate FONT_2XL header to FONT_HEAD**

Find line 113:
```python
            f"font-size: {FONT_2XL}px; font-weight: 600; color: {TEXT_PRIMARY};"
```

Replace with:
```python
            f"font-size: {FONT_HEAD}px; font-weight: 600; color: {TEXT_PRIMARY};"
```

- [ ] **Step 3: Migrate workspace card title FONT_LG (15)**

Line 77 already uses FONT_LG which now equals 15. Per spec, workspace cards should use LG 15 for titles. No change needed (the value shift handles it).

- [ ] **Step 4: Run tests**

```bash
QT_QPA_PLATFORM=offscreen pytest tests/ -k "workspace" 2>&1 | tail -5
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/flow/ui/workspace_dialog.py
git commit -m "refactor(workspace_dialog): FONT_2XL → FONT_HEAD"
```

---

### Task 5: Migrate mapping_panel.py

**Files:**
- Modify: `src/flow/ui/editor/mapping_panel.py:22, 221, 234`

- [ ] **Step 1: Update import**

Find line 22:
```python
    FONT_XS, FONT_SM, FONT_MD, FONT_LG, FW_REGULAR, FW_MEDIUM, FW_SEMI,
```

Replace with:
```python
    FONT_XS, FONT_SM, FONT_MD, FONT_LG, FONT_TITLE, FW_REGULAR, FW_MEDIUM, FW_SEMI,
```

- [ ] **Step 2: Apply TITLE 18 to section headers**

Find line 221 ("Verses" section header):
```python
            f"font-size: {FONT_LG}px; font-weight: {FW_SEMI}; "
```

Replace with:
```python
            f"font-size: {FONT_TITLE}px; font-weight: {FW_SEMI}; "
```

Find line 234 (the verse count/secondary header):
```python
                font-size: {FONT_LG}px; padding: 0;
```

Replace with:
```python
                font-size: {FONT_TITLE}px; padding: 0;
```

- [ ] **Step 3: Verify body 12pt density**

Run app manually if possible (`flow`) and check mapping panel doesn't suffer from increased line wraps in tight columns. If problem found, override SM 12 → XS 11 only in mapping_panel.

- [ ] **Step 4: Run tests**

```bash
QT_QPA_PLATFORM=offscreen pytest tests/ -k "mapping" 2>&1 | tail -5
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/flow/ui/editor/mapping_panel.py
git commit -m "refactor(mapping_panel): 섹션 헤더 → FONT_TITLE (18pt)"
```

---

### Task 6: Migrate slide_preview_panel.py

**Files:**
- Modify: `src/flow/ui/editor/slide_preview_panel.py:58, 78, 188`

- [ ] **Step 1: Update import**

Find line 58:
```python
            FONT_XS, FONT_SM, FONT_MD, FONT_LG, FW_MEDIUM, FW_SEMI,
```

Replace with:
```python
            FONT_XS, FONT_SM, FONT_MD, FONT_LG, FONT_TITLE, FW_MEDIUM, FW_SEMI,
```

- [ ] **Step 2: Apply TITLE 18 to panel header**

Find line 78:
```python
            f"font-size: {FONT_MD}px; color: {TEXT_PRIMARY}; font-weight: {FW_SEMI};"
```

Replace with:
```python
            f"font-size: {FONT_TITLE}px; color: {TEXT_PRIMARY}; font-weight: {FW_SEMI};"
```

Find line 188 (secondary panel header — slide count area):
```python
            f"background-color: transparent; font-size: {FONT_LG}px; }}"
```

Keep as `FONT_LG` (15pt) — this is a count/meta label, not the panel title.

- [ ] **Step 3: Run tests**

```bash
QT_QPA_PLATFORM=offscreen pytest tests/ -k "slide_preview" 2>&1 | tail -5
```

Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add src/flow/ui/editor/slide_preview_panel.py
git commit -m "refactor(slide_preview): 패널 헤더 → FONT_TITLE (18pt)"
```

---

### Task 7: Migrate song_list_widget.py XL usages

**Files:**
- Modify: `src/flow/ui/editor/song_list_widget.py:38, 150, 785`

- [ ] **Step 1: Update import**

Find line 38:
```python
    RADIUS_SM, RADIUS_MD, RADIUS_LG, FONT_SM, FONT_MD, FONT_LG, FONT_XL,
```

Replace with:
```python
    RADIUS_SM, RADIUS_MD, RADIUS_LG, FONT_SM, FONT_MD, FONT_LG, FONT_TITLE,
```

- [ ] **Step 2: Migrate FONT_XL usages to FONT_TITLE**

Find line 150:
```python
            f"font-size: {FONT_XL}px; font-weight: 500; color: {TEXT_PRIMARY}; background: transparent;"
```

Replace with:
```python
            f"font-size: {FONT_TITLE}px; font-weight: 500; color: {TEXT_PRIMARY}; background: transparent;"
```

Find line 785:
```python
            f"font-size: {FONT_XL}px; font-weight: {FW_SEMI}; color: {TEXT_PRIMARY};"
```

Replace with:
```python
            f"font-size: {FONT_TITLE}px; font-weight: {FW_SEMI}; color: {TEXT_PRIMARY};"
```

Rationale: these were headings that previously used 14pt — now upgraded to TITLE 18 to match panel-section-header level.

- [ ] **Step 3: Run tests**

```bash
QT_QPA_PLATFORM=offscreen pytest tests/ -k "song_list" 2>&1 | tail -5
```

Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add src/flow/ui/editor/song_list_widget.py
git commit -m "refactor(song_list): FONT_XL → FONT_TITLE (18pt)"
```

---

### Task 8: Verify verse_selector.py and settings_dialog.py inherit new sizes correctly

**Files:** none modified — verification only

`verse_selector.py` only uses `FONT_MD`, `settings_dialog.py` only uses `FONT_MD` and `FONT_LG`. Both names persist post-Task 1 (only values shift: MD 12→13, LG 13→15). No code change needed.

- [ ] **Step 1: Confirm no FONT_XL/2XL leakage**

```bash
grep -n "FONT_XL\|FONT_2XL" src/flow/ui/editor/verse_selector.py src/flow/ui/settings_dialog.py
```

Expected: empty (no matches).

- [ ] **Step 2: No commit needed (no file changes)**

This task confirms the files already get the value shift via Task 1's token redefinition.

---

### Task 9: Migrate project_launcher.py card titles

**Files:**
- Modify: `src/flow/ui/project_launcher.py:31, 209`

- [ ] **Step 1: Update import**

Find line 31:
```python
    FONT_XS, FONT_SM, FONT_MD, FONT_LG, FONT_XL, FONT_2XL, FONT_TITLE,
```

Replace with:
```python
    FONT_XS, FONT_SM, FONT_MD, FONT_LG, FONT_TITLE, FONT_HEAD, FONT_DISPLAY,
```

- [ ] **Step 2: Apply HEAD to card titles**

Find line 209:
```python
            f"font-size: {FONT_2XL}px; font-weight: {FW_SEMI}; color: {TEXT_PRIMARY};"
```

Replace with:
```python
            f"font-size: {FONT_HEAD}px; font-weight: {FW_SEMI}; color: {TEXT_PRIMARY};"
```

- [ ] **Step 3: Run tests**

```bash
QT_QPA_PLATFORM=offscreen pytest tests/ -k "launcher" 2>&1 | tail -5
```

Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add src/flow/ui/project_launcher.py
git commit -m "refactor(launcher): 카드 title → FONT_HEAD"
```

---

## Phase C — Hardcoded migration

### Task 10: Migrate project_screen.py hardcoded font sizes

**Files:**
- Modify: `src/flow/ui/screens/project_screen.py:26, 51, 70, 309, 324, 343, 450`

- [ ] **Step 1: Update import**

Find line 26:
```python
    FONT_SM,
```

Replace with:
```python
    FONT_2XS, FONT_XS, FONT_SM, FONT_MD, FW_MEDIUM,
```

(Add what's needed for the migration below.)

- [ ] **Step 2: Add color token imports if missing**

Verify the file imports `TEXT_PRIMARY`, `TEXT_TERTIARY`. If not, add them to the existing import statement around line 26.

- [ ] **Step 3: Migrate slot badge (line 51)**

Find:
```python
        self._badge.setStyleSheet(
            f"font-size: 10px; font-weight: 500; color: {color};"
        )
```

Replace with:
```python
        self._badge.setStyleSheet(
            f"font-size: {FONT_2XS}px; font-weight: {FW_MEDIUM}; color: {color};"
        )
```

- [ ] **Step 4: Migrate slot text (line 70)**

Find:
```python
        self._text.setStyleSheet("font-size: 10px; color: #aaa;")
```

Replace with:
```python
        self._text.setStyleSheet(
            f"font-size: {FONT_2XS}px; color: {TEXT_TERTIARY};"
        )
```

- [ ] **Step 5: Migrate `_nav_btn_style` (lines 275-282) — convert to f-string**

The whole `_nav_btn_style` is a regular triple-quoted string. To use tokens, convert to f-string and **escape all CSS braces** (`{` → `{{`, `}` → `}}`).

Find:
```python
        _nav_btn_style = """
            QPushButton {
                background: #2a2a2a; color: #aaa; border: 1px solid #444;
                border-radius: 4px; padding: 2px 10px; font-size: 11px; font-weight: 500;
            }
            QPushButton:hover { background: #3a3a3a; color: white; }
        """
```

Replace with:
```python
        _nav_btn_style = f"""
            QPushButton {{
                background: #2a2a2a; color: #aaa; border: 1px solid #444;
                border-radius: 4px; padding: 2px 10px; font-size: {FONT_XS}px; font-weight: {FW_MEDIUM};
            }}
            QPushButton:hover {{ background: #3a3a3a; color: white; }}
        """
```

- [ ] **Step 6: Migrate nav song name label (line 324)**

Find:
```python
        self._nav_song_name.setStyleSheet(
            "font-size: 13px; font-weight: 500; color: #e0e0e0;"
        )
```

Replace with:
```python
        self._nav_song_name.setStyleSheet(
            f"font-size: {FONT_MD}px; font-weight: {FW_MEDIUM}; color: {TEXT_PRIMARY};"
        )
```

- [ ] **Step 7: Migrate `_verse_btn_style` (lines 340-351) — convert to f-string**

Find:
```python
        _verse_btn_style = """
            QPushButton {
                background: #2a2a2a; color: #999; border: 1px solid #444;
                border-radius: 4px; padding: 2px 6px; font-size: 11px; font-weight: 500;
                min-width: 32px;
            }
            QPushButton:hover { background: #3a3a3a; color: white; }
            QPushButton:checked {
                background: #1a2a40; color: #64b5f6;
                border: 1px solid #42a5f5; font-weight: 500;
            }
        """
```

Replace with:
```python
        _verse_btn_style = f"""
            QPushButton {{
                background: #2a2a2a; color: #999; border: 1px solid #444;
                border-radius: 4px; padding: 2px 6px; font-size: {FONT_XS}px; font-weight: {FW_MEDIUM};
                min-width: 32px;
            }}
            QPushButton:hover {{ background: #3a3a3a; color: white; }}
            QPushButton:checked {{
                background: #1a2a40; color: #64b5f6;
                border: 1px solid #42a5f5; font-weight: {FW_MEDIUM};
            }}
        """
```

- [ ] **Step 8: Run tests**

```bash
QT_QPA_PLATFORM=offscreen pytest tests/ -k "project_screen" 2>&1 | tail -5
```

Expected: pass.

- [ ] **Step 9: Commit**

```bash
git add src/flow/ui/screens/project_screen.py
git commit -m "refactor(project_screen): 하드코딩된 font-size를 토큰으로 교체"
```

---

### Task 11: Migrate song_manager_dialog.py hardcoded font sizes

**Files:**
- Modify: `src/flow/ui/song_manager_dialog.py:84, 307, 309`

- [ ] **Step 1: Update import**

Find line 84:
```python
            FONT_MD, FONT_LG, FW_MEDIUM, FW_SEMI,
```

Replace with:
```python
            FONT_XS, FONT_SM, FONT_MD, FONT_LG, FW_MEDIUM, FW_SEMI,
```

- [ ] **Step 2: Migrate hardcoded font-sizes**

Find line 307:
```python
        style = "color: #ccc; font-size: 11px;"
```

Replace with:
```python
        from flow.ui.styles import TEXT_SECONDARY
        style = f"color: {TEXT_SECONDARY}; font-size: {FONT_XS}px;"
```

Find line 309:
```python
            style = "color: #eee; font-weight: bold; font-size: 12px;"
```

Replace with:
```python
            from flow.ui.styles import TEXT_PRIMARY
            style = f"color: {TEXT_PRIMARY}; font-weight: {FW_SEMI}; font-size: {FONT_SM}px;"
```

Line 324 (`font-size: 8px;`) — leave as inline (1회용 작은 배지, 토큰화 안 함; spec 명시).

- [ ] **Step 3: Run tests**

```bash
QT_QPA_PLATFORM=offscreen pytest tests/ -k "song_manager" 2>&1 | tail -5
```

Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add src/flow/ui/song_manager_dialog.py
git commit -m "refactor(song_manager): 하드코딩된 font-size를 토큰으로 교체"
```

---

## Phase D — Add new DISPLAY-level page headers

DISPLAY 24pt 토큰의 home은 현재 UI에 없다. 다음 세 위치에 새 라벨을 추가한다.

### Task 12: Add workspace name DISPLAY label to ProjectLauncher

**Files:**
- Modify: `src/flow/ui/project_launcher.py:341-410` (`_setup_ui` 헤더 영역)

**Design:** `_ws_button` 위에 워크스페이스 이름을 큰 글자로 표시하는 QLabel을 추가한다. 워크스페이스가 없으면 빈 상태 메시지나 로고 자리. `_ws_button`은 작은 "변경 ▾" 트리거로 demote.

- [ ] **Step 1: Add DISPLAY label widget**

In `_setup_ui` (around line 341), insert after `root.setSpacing(0)` and before `# ── 워크스페이스 헤더`:

```python
        # ── 페이지 헤드라인: 현재 워크스페이스 이름
        self._workspace_title = QLabel("워크스페이스 없음")
        self._workspace_title.setStyleSheet(
            f"font-size: {FONT_DISPLAY}px; font-weight: {FW_SEMI}; "
            f"color: {TEXT_PRIMARY}; background: transparent;"
        )
        root.addWidget(self._workspace_title)
        root.addSpacing(SP_XS)
```

- [ ] **Step 2: Demote `_ws_button` style to small subtitle action**

Find the `self._ws_button.setStyleSheet(...)` block (around line 355). Change `font-size` to `FONT_XS` and color to `TEXT_TERTIARY`. The button text becomes "워크스페이스 변경 ▾" or similar small action.

- [ ] **Step 3: Update set_workspace to update both label and button**

Find `set_workspace` method (around line 448). After updating `self._ws_button.setText(...)`:

```python
        self._workspace_title.setText(
            ws.name if ws else "워크스페이스 없음"
        )
        self._ws_button.setText("워크스페이스 변경 ▾")
```

(Replace the previous text-setting logic accordingly.)

- [ ] **Step 4: Run tests + manual smoke test**

```bash
QT_QPA_PLATFORM=offscreen pytest 2>&1 | tail -3
```

Expected: pass. Open app manually if possible to verify visual.

- [ ] **Step 5: Commit**

```bash
git add src/flow/ui/project_launcher.py
git commit -m "feat(launcher): 워크스페이스 이름 DISPLAY 24pt 헤드라인 추가"
```

---

### Task 13: Add project name DISPLAY label to ProjectScreen

**Files:**
- Modify: `src/flow/ui/screens/project_screen.py:_setup_ui`

**Design:** 현재 `_song_nav_bar` 위에 프로젝트 이름을 표시하는 헤더 영역을 추가한다. 곡 편집 모드에서는 곡 이름으로 텍스트가 바뀐다.

- [ ] **Step 1: Add header widget setup**

In `_setup_ui` (around line 290 — after `self._toolbar` is added to main_layout, before `self._song_nav_bar`):

```python
        # ── 페이지 헤드라인: 프로젝트명 (또는 곡 편집 모드에서는 곡명)
        from flow.ui.styles import FONT_DISPLAY, FW_SEMI, TEXT_PRIMARY, SP_LG
        self._page_title = QLabel("")
        self._page_title.setStyleSheet(
            f"font-size: {FONT_DISPLAY}px; font-weight: {FW_SEMI}; "
            f"color: {TEXT_PRIMARY}; background: transparent; "
            f"padding: {SP_LG}px {SP_LG}px {SP_XS}px {SP_LG}px;"
        )
        main_layout.addWidget(self._page_title)
```

- [ ] **Step 2: Add `set_page_title` method**

In ProjectScreen class, add:

```python
    def set_page_title(self, text: str) -> None:
        """페이지 최상단의 큰 헤드라인 텍스트를 설정 (DISPLAY 24pt)."""
        self._page_title.setText(text)
        self._page_title.setVisible(bool(text))
```

- [ ] **Step 3: Run tests**

```bash
QT_QPA_PLATFORM=offscreen pytest tests/ -k "project_screen" 2>&1 | tail -5
```

Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add src/flow/ui/screens/project_screen.py
git commit -m "feat(project_screen): 페이지 헤드라인 영역 + set_page_title API 추가"
```

---

### Task 14: Wire MainWindow to update page title on project/song changes

**Files:**
- Modify: `src/flow/ui/main_window.py` (callsites of `setWindowTitle` related to project/song)

- [ ] **Step 1: Find places where window title is set with project name**

```bash
grep -n "setWindowTitle.*project\|setWindowTitle.*name\|setWindowTitle.*self._project" src/flow/ui/main_window.py
```

Look for matches like `setWindowTitle(f"Flow - {self._project.name}")`.

- [ ] **Step 2: Add page-title sync alongside window-title**

After every `self.setWindowTitle(f"Flow - {self._project.name}")`, add:

```python
            if hasattr(self, '_project_screen'):
                self._project_screen.set_page_title(self._project.name)
```

For song edit mode (`setWindowTitle(f"Flow - [곡 편집] {song.name}")` at line 892, 1401):

```python
            self._project_screen.set_page_title(f"[곡 편집] {song.name}")
```

For live mode (line 1460):
```python
            # live mode은 page title 유지 (별도 처리 불필요)
```

- [ ] **Step 3: Hide page title when no project loaded**

In `_show_launcher` method (around line 284 of `main_window.py`), add at the beginning:

```python
        if hasattr(self, '_project_screen'):
            self._project_screen.set_page_title("")
```

Also in `_close_current_project` (find via `grep -n "_close_current_project" src/flow/ui/main_window.py`), add:

```python
        self._project_screen.set_page_title("")
```

- [ ] **Step 4: Run tests + manual smoke test**

```bash
QT_QPA_PLATFORM=offscreen pytest 2>&1 | tail -3
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/flow/ui/main_window.py
git commit -m "feat(main_window): 프로젝트명/곡명 페이지 헤드라인 sync"
```

---

## Phase E — Cleanup

### Task 15: Remove deprecated FONT_XL and FONT_2XL aliases

**Files:**
- Modify: `src/flow/ui/styles.py`

- [ ] **Step 1: Verify no remaining usages**

```bash
grep -rn "FONT_XL\|FONT_2XL" src/ --include="*.py" | grep -v "styles.py"
```

Expected: empty (no matches outside styles.py). If any matches remain, fix the file (replace with `FONT_LG` or `FONT_HEAD` as appropriate) and commit before proceeding.

- [ ] **Step 2: Remove aliases from styles.py**

Find the alias block:
```python
# 호환 alias (Phase E에서 제거 예정 — 신규 토큰으로 교체 후)
FONT_XL  = FONT_LG    # 14 → 15 (한 단계 위)
FONT_2XL = FONT_HEAD  # 16 → 20 (HEAD로 승격)
```

Delete those 3 lines.

- [ ] **Step 3: Run full test suite**

```bash
QT_QPA_PLATFORM=offscreen pytest 2>&1 | tail -5
```

Expected: all pass (matching baseline from Task 1).

- [ ] **Step 4: Commit**

```bash
git add src/flow/ui/styles.py
git commit -m "refactor(styles): FONT_XL, FONT_2XL alias 제거"
```

---

### Task 16: Visual verification checklist (manual)

**Files:** none (manual verification)

이 단계는 자동화 안 됨. 사람이 확인.

- [ ] **Step 1: Run app**

```bash
flow
```

- [ ] **Step 2: Verify each checklist item from spec**

1. 워크스페이스 런처: 워크스페이스 이름이 DISPLAY 24pt로 보이는가?
2. 프로젝트 화면 진입: 프로젝트명이 좌상단에 큰 글자로 보이는가?
3. 곡 편집 모드 진입: 헤드라인이 "[곡 편집] {곡명}"으로 바뀌는가?
4. 워크스페이스 선택 다이얼로그: 헤더가 HEAD 20pt 무게감 있게 보이는가?
5. EmptyState (프로젝트가 빈 워크스페이스): 제목이 HEAD 20pt인가?
6. 매핑 패널: TITLE 18pt 섹션 헤더가 본문과 분명히 구분되는가? 본문 12pt가 빽빽함을 유발하지는 않는가?
7. 슬라이드 미리보기 패널: TITLE 18pt 헤더 OK인가?
8. 셋리스트 카드: LG 15pt 카드 제목이 너무 크거나 작지 않은가?

- [ ] **Step 3: 회귀 검사 — pytest 전체**

```bash
QT_QPA_PLATFORM=offscreen pytest 2>&1 | tail -5
```

Expected: same baseline pass count.

- [ ] **Step 4: 시각적 결함이 발견되면 follow-up commit으로 수정**

특히 주의:
- 매핑 패널 본문 12pt 빽빽함 → SM 11로 override 가능 (mapping_panel만)
- 프로젝트명/곡명이 너무 길어 두 줄 가는 경우 → ellipsis 처리

발견된 결함은 즉시 별도 commit으로 수정:
```bash
git commit -m "fix(typography): <구체적인 문제> 수정"
```

---

## Notes

- **Test discipline:** 자동 회귀 테스트는 pytest baseline(현재 240 통과 가정) 유지로 검증. 시각적 변화는 manual.
- **Commit cadence:** 각 task end → commit. 한 task 안의 작은 step은 단일 commit으로 묶음.
- **Rollback:** 시각적으로 마음에 안 들면 `git revert <commit>`으로 단계별 롤백 가능.
- **Preview script:** `scripts/typography_preview.py`는 이번 작업 끝나도 유지 — 향후 토큰 조정 시 재사용 가능.
