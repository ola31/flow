# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Companion docs to read

- `AGENTS.md` is the living project guide — design system, domain knowledge, anti-patterns. Keep it in sync when the architecture changes.
- `ROADMAP.md` — the upcoming library/projects workspace split (곡 해석 우선순위: `projects/{name}/songs/{곡}` → `library/{곡}`). `src/flow/domain/workspace.py` already exists as scaffolding for this.
- `BUILD.md` — PyInstaller packaging (uses `Flow.spec`, `--onedir` with splash).

## Commands

```bash
pip install -e ".[dev]"               # install with dev extras
flow                                  # run app (or: python -m flow.main)

pytest                                # all tests
pytest tests/domain/test_hotspot.py   # single file
pytest tests/domain/test_hotspot.py::TestHotspotCreation::test_create_hotspot_with_coordinates
pytest --cov=flow --cov-report=term-missing

ruff check --fix src/ tests/          # lint (line-length 88, rules E,F,I,N,W)
black src/ tests/
mypy src/

pyinstaller Flow.spec --noconfirm     # build
```

Qt tests run headless via `--platform offscreen` (see `tests/conftest.py`'s `qapp_args` fixture); tests must consume this fixture rather than instantiating QApplication directly.

## Architecture

Layered: `domain/` (dataclasses) → `repository/` (JSON persistence) → `services/` (SlideManager, ConfigService, SlideConverter) → `ui/` (PySide6 widgets). UI sublayers: `screens/` (containers), `editor/` (ScoreCanvas, MappingPanel, VerseSelector, SongListWidget), `live/` (LiveController — Preview→Live state machine), `display/` (fullscreen output window).

Two-tier domain: **Song** (score sheets + PPT + hotspot mappings) is the reusable unit; **Project** is an ordered setlist of songs for one service. Current on-disk layout nests `songs/` inside the project folder — this is being refactored per ROADMAP.md.

### Mutations go through `ui/undo_commands.py`

Never mutate domain objects directly from widgets. All state changes that should participate in Ctrl+Z/Y routing must be issued as an undo command.

### Live mode lockout

`LiveController._is_live` gates the entire editor. Every edit entry point must early-return `if self._is_live: return`, and widgets call `set_editable(False)` at the widget level. Missing either side lets edits through during live broadcast.

### PPT conversion threading

PPT→image conversion (via LibreOffice + pdf2image) must run on a `QThread` worker and signal the UI — never call it inline. On failure, surface a user-visible notification and display a placeholder image instead of crashing the canvas.

## Qt/PySide UI Debugging

- When fixing Qt widget styling issues, check for stylesheet conflicts FIRST before modifying setBackground/setPalette calls (stylesheets override these methods). Concretely: `QListWidget::item { background-color: ... }` in the global stylesheet silently wins over `item.setBackground()`. Either set the CSS background to `transparent` and control per-item in code, or change `setForeground()` (text color) instead — CSS does not override foreground.
- For icon/codepoint mappings, verify against the actual font file (use `fc-list` or inspect the TTF in `src/flow/resources/`) rather than guessing Unicode values.

## Critical gotchas

- **Verse index encoding**: `0–4` = verses 1–5 (user-facing), `5` = **chorus** (fallback when no verse-specific mapping exists). Getters that accept a verse index must honor this fallback.
- **Signal wiring**: connect `currentItemChanged` OR `itemClicked`, never both — connecting both fires duplicate handlers.
- **Number-key verse change**: after changing verse in live mode, `LiveController.sync_live()` must be called or the display window drifts out of sync.
- **JSON path serialization**: always `Path.as_posix()` before writing so Windows backslashes don't leak into cross-platform project files.

## Design system (enforced, not conventional)

- **All colors come from `src/flow/ui/styles.py` tokens.** Hardcoded hex values in widgets are a review-blocker. Palette: `BG_DEEP/SURFACE/ELEVATED/HOVER`, `TEXT_PRIMARY/SECONDARY/TERTIARY`, `ACCENT` (#5b8def, selection/CTA only), `GREEN/AMBER/RED` (semantic).
- **Font weights**: 300 / 500 / 600 only. `bold` and `900` are banned — they render smudgy at small sizes.
- **Icons via `src/flow/ui/icons.py`** (Material Symbols Rounded, 66KB subset). No emoji in UI text.
- **Depth via background-tone difference + `QGraphicsDropShadowEffect`**, not borders. Selected state = 3px left accent bar, not a full outline.
- Spacing on an 8px grid (`SP_XS`=4 … `SP_2XL`=32); font sizes `FONT_SM`=11 … `FONT_2XL`=18.

## Code conventions

- `from __future__ import annotations` on every module (first import).
- Python 3.10+ type syntax: `dict[str, int]`, `QObject | None`, etc.
- Qt signals declared as class attributes: `preview_changed = Signal(str)`.
