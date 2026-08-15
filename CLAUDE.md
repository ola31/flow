# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Companion docs to read

- `AGENTS.md` is the living project guide — design system, domain knowledge, anti-patterns. Keep it in sync when the architecture changes.
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

Qt tests run headless: `tests/conftest.py` forces `QT_QPA_PLATFORM=offscreen` at import time (the old `qapp_args` fixture did NOT actually apply — local runs silently used wayland and diverged from CI). Tests must use the `qapp`/`qtbot` fixtures rather than instantiating QApplication directly. To run against a real display: `QT_QPA_PLATFORM=wayland pytest ...`.

## Architecture

Layered: `domain/` (dataclasses) → `repository/` (JSON persistence) → `services/` (SlideManager, ConfigService, SlideConverter) → `ui/` (PySide6 widgets). UI sublayers: `screens/` (containers), `editor/` (ScoreCanvas, MappingPanel, VerseSelector, SongListWidget), `live/` (LiveController — Preview→Live state machine), `display/` (fullscreen output window).

Two-tier domain: **Song** (score sheets + PPT/markdown + hotspot mappings) is the reusable unit; **Project** is an ordered setlist of songs for one session.

On disk a workspace holds `library/` (shared songs) and `projects/`; a project may also keep private copies under `projects/{name}/songs/{song}`, which take priority over `library/{song}` when a name resolves. `ProjectRepository.save_to_workspace`/`load_from_workspace` own that layout, and `domain/workspace.py` locates the root.

### Hotspot and mapping edits go through `ui/undo_commands.py`

Anything a user expects Ctrl+Z to reverse — creating, moving or deleting a hotspot, mapping or unmapping slides — must be issued as an undo command, never mutated straight from a widget. The stack currently holds exactly those: `AddHotspot`, `RemoveHotspot`, `MoveHotspot`, `MapSlide`, `UnlinkAllSlides`, `ClearSheetMappings`.

Structural edits (rename/add/delete/replace a sheet, reorder or section the setlist) deliberately sit outside the stack: they mutate the domain object and call `_mark_dirty()`. Follow the sibling operation you are next to rather than mixing the two styles.

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
- **Verse change is preview-only in live mode**: changing the verse (number keys / nav bar) must move Preview only — Live changes solely on Enter/Space. `send_to_live()` commits `_live_slide_index` (+ `_live_verse_index`); `sync_live()` re-emits that committed index and must **not** recompute from `project.current_verse_index`, or the output screen jumps the moment a verse button is pressed.
- **Live slides that aren't converted yet**: `LiveController` keeps the last frame and polls `_pending_slide_index` until the image lands. Never rely on `load_finished` alone — it's suppressed during screen transitions and lost when the worker queue is flushed. Any code that empties the worker queue (`stop_workers`, `reset_worker`, `add_task`) must also reset `_pending_conversions`/`_loading`, or `SlideManager` stops scheduling conversions entirely.
- **A background thread must never own a Qt object.** If a thread's closure holds the last reference to a `QObject`/`QWidget`, `Thread.run`'s `del self._target` destroys it *on that worker thread* when the thread ends — Qt cannot stop a timer or tear down a widget off its owning thread, and the process segfaults (this was the long-running intermittent crash in CI and in the app). Either capture only plain data (`services/hotspot.py` hands the prewarm thread a backend and a list box) or keep a strong reference elsewhere and release it from the main thread (`ScoreCanvas` holds the canvas in `_PREFETCH_KEEPALIVE` until the worker signals completion). Sampling another thread's Python frames (`sys._current_frames()` + `traceback.format_stack`) crashes the same way — it is why `perf_probe` no longer has a watchdog.
- **JSON path serialization**: always `Path.as_posix()` before writing so Windows backslashes don't leak into cross-platform project files.
- **Workspace root is marked by `.flow-workspace`** (`domain/workspace.py`), the same idea as `.git`/`.idea`: `Workspace.find_root()` walks up from any nested path to locate it, so picking `library/` or a song folder still resolves to the workspace. The marker is *not* a validity condition — `is_valid()` still only requires `library/` and `projects/`, so pre-marker workspaces keep working; `create()`/`open()` backfill it. Never make code require the marker, or existing workspaces stop opening.
- **A setlist may hold the same song twice** (sung in both the morning and afternoon slot). `Project.selected_songs` is an *occurrence* list, not a set of songs: repeats are `Song.duplicate_reference()` copies that **share the same `score_sheets` list object**, so sheets/hotspots/mappings stay single while `section` differs per slot. Anything that walks `selected_songs` and mutates sheet state must dedupe by `id(sheet)` — `_shift_project_indices` and `ensure_unique_ids` do. Applying a slide offset per song instead of per sheet double-shifts every mapping; regenerating "duplicate" ids on the second occurrence severs them. Slide offsets (`SlideManager._slide_offsets`) are keyed by song name and counted once.

## Design system (enforced, not conventional)

- **All colors come from `src/flow/ui/styles.py` tokens.** Hardcoded hex values in widgets are a review-blocker. Palette: `BG_DEEP/SURFACE/ELEVATED/HOVER`, `TEXT_PRIMARY/SECONDARY/TERTIARY`, `ACCENT` (#5E6AD2, selection/CTA) and `ACCENT_INTER` (#7170FF, interactive/active), `GREEN/AMBER/RED` (semantic). The palette has been retuned before — read the tokens, don't memorise the hex.
- **Font weights**: `FW_REGULAR`(400) / `FW_MEDIUM`(510) / `FW_SEMI`(590) only. `bold` and `900` are banned — they render smudgy at small sizes.
- **Icons via `src/flow/ui/icons.py`** (Material Symbols Rounded, ~5KB subset). No emoji in UI text.
- **Depth via background-tone difference**, not borders. Selected state = 3px left accent bar, not a full outline. `QGraphicsDropShadowEffect` is reserved for small floating widgets (the hotspot popover) — Qt re-blurs the whole pixmap on every paint, which measured 11× the paint cost on full-size panels, so the home screen panels carry none (guarded by a test).
- Spacing on an 8px grid (`SP_XS`=4 … `SP_2XL`=32); font sizes `FONT_2XS`=10 … `FONT_DISPLAY`=24 (`FONT_SM`=12 is the body default).

## Code conventions

- `from __future__ import annotations` on every module (first import).
- Python 3.10+ type syntax: `dict[str, int]`, `QObject | None`, etc.
- Qt signals declared as class attributes: `preview_changed = Signal(str)`.
