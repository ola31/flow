# AGENTS.md - AI Agent Guidelines for Flow

## Project Overview

**Flow** is a desktop slide broadcasting system for live presentation contexts.
Maps hotspots on score sheet images to PPT slides for one-click live broadcasting.

**Core Stack**: Python 3.10+, PySide6 (Qt Widgets), python-pptx, PyInstaller
**Architecture**: Domain → Services → UI (layered)

**Two-tier structure**:
- **Song** — reusable unit: score sheet images + PPT + hotspot mappings
- **Project** — setlist: ordered collection of songs for one session

---

## Build, Lint, and Test Commands

```bash
# Install (dev mode)
pip install -e ".[dev]"

# Run application
flow
# or: python -m flow.main

# === TESTING ===
pytest                                    # All tests
pytest tests/domain/test_hotspot.py       # Single file
pytest tests/domain/test_hotspot.py::TestHotspotCreation::test_create_hotspot_with_coordinates  # Single test
pytest --cov=flow --cov-report=term-missing  # With coverage

# === LINTING ===
ruff check src/ tests/
ruff check --fix src/ tests/
black src/ tests/
mypy src/

# === BUILD ===
pyinstaller Flow.spec --noconfirm
```

---

## Project Structure

```
src/flow/
├── domain/           # Business entities (dataclasses)
│   ├── project.py, score_sheet.py, hotspot.py, song.py, workspace.py
├── services/         # Business logic
│   ├── config_service.py, slide_manager.py, slide_converter.py
│   ├── song_index.py # mtime-keyed cache of song folder metadata (+ lyrics)
│   ├── markdown/     # markdown slide parser + renderer (slides.md songs)
│   ├── web_broadcast.py  # HTTP + WebSocket slide broadcast to phones
│   └── hotspot.py    # Wi-Fi hotspot / captive portal (Linux, Windows)
├── repository/       # Data persistence (workspace: library/ + projects/)
├── perf_probe.py     # opt-out probe writing ~/.flow/perf.log
├── resources/        # Bundled assets (icon font)
└── ui/               # PySide6 UI layer
    ├── styles.py     # Design tokens (colors, spacing, typography)
    ├── icons.py      # Material Symbols icon helper
    ├── screens/      # home, project, library, projects, markdown editor,
    │                 # web broadcast, _browser_widgets (shared toolbar/cards)
    ├── editor/       # score canvas, song list, mapping panel, verse selector,
    │                 # markdown editor, slide preview panel
    ├── live/         # live controller, emergency patch panel, live song add
    └── display/      # Display window (fullscreen output)

tests/
├── conftest.py       # forces QT_QPA_PLATFORM=offscreen before Qt loads
├── domain/, services/, ui/
```

---

## Design System

### Color Palette (defined in `styles.py`)

All colors must be referenced from `styles.py` tokens. Never hardcode hex values.

| Token | Value | Usage |
|-------|-------|-------|
| `BG_DEEP` | `#08090A` | Window background |
| `BG_SURFACE` | `#0F1011` | Panel/sidebar background |
| `BG_ELEVATED` | `#191A1B` | Cards, elevated surfaces |
| `BG_HOVER` | `#28282C` | Hover state |
| `BORDER` | `#23252A` | Default border |
| `TEXT_PRIMARY` | `#F7F8F8` | Body text, titles |
| `TEXT_SECONDARY` | `#D0D6E0` | Supporting text |
| `TEXT_TERTIARY` | `#8A8F98` | Disabled, hints |
| `ACCENT` | `#5E6AD2` | Selection, CTA |
| `ACCENT_INTER` | `#7170FF` | Links, active state |
| `GREEN` | `#10B981` | Success, mapped |
| `AMBER` | `#F5A623` | Warning, incomplete |
| `RED` | `#EB5757` | Live mode, danger |

Values change when the palette is retuned — read `styles.py`, never copy hex
from here into code.

### Typography
- Weight tokens: `FW_REGULAR`(400) body, `FW_MEDIUM`(510) UI default, `FW_SEMI`(590) headings
- **Never use `font-weight: bold` or `900`** — 590 is the ceiling; heavier renders smudgy at small sizes
- Size tokens: `FONT_2XS`(10), `FONT_XS`(11), `FONT_SM`(12), `FONT_MD`(13), `FONT_LG`(15), `FONT_TITLE`(18), `FONT_HEAD`(20), `FONT_DISPLAY`(24)
- Radius tokens: `RADIUS_SM`(4), `RADIUS_MD`(6), `RADIUS_LG`(8), `RADIUS_XL`(12), `RADIUS_PILL`

### Icons
- Material Symbols Rounded (subset, ~5KB TTF in `resources/`; `PretendardVariable.ttf`
  ships alongside it as the bundled UI font — see `FONT_FAMILY`)
- Use `icons.py`: `icon_qicon("home")` for QAction, `icon_label("save")` for QLabel
- Render via `icon_pixmap()` / `icon_qicon()` for toolbar buttons

### Spacing (8px base)
- `SP_XS`(4), `SP_SM`(8), `SP_MD`(12), `SP_LG`(16), `SP_XL`(24), `SP_2XL`(32)

### Visual Depth
- Use background color difference, not borders, to separate regions
- `QGraphicsDropShadowEffect` only on small floating widgets (hotspot popover).
  Qt re-blurs the entire pixmap on every paint — measured 11× paint cost on
  full-size panels, so the home panels carry none (a test guards this)
- Selected state: left accent bar (3px) instead of full border

---

## Code Style Guidelines

### Imports
```python
from __future__ import annotations  # ALWAYS first
```

### Type Hints (Python 3.10+ syntax)
```python
def get_slide_index(self, verse_index: int = 0) -> int: ...
slide_mappings: dict[str, int] = field(default_factory=dict)
```

### Qt/PySide6 Patterns
```python
class LiveController(QObject):
    preview_changed = Signal(str)  # Signals as class attributes

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
```

---

## Critical Domain Knowledge

### Verse Mapping
- `verse_index 0-4` = Verses 1-5 (user-facing)
- `verse_index 5` = **Chorus** (fallback when no verse mapping exists)

### Navigation Flow
- **Left/Right**: Move through hotspots in the current verse layer (Preview only, NOT Live)
- **Enter/Space**: Confirm Preview → Live
- **Up/Down**: Switch sheets/songs across the whole setlist (sections do not stop it)
- **Number keys 1-5, C**: Change verse (Preview only in live mode — Live moves on Enter)
- **B**: Blackout (live mode)
- **Esc**: Exit live mode (with confirmation)
- **Tab/Shift+Tab**: Cycle hotspots within current verse layer

### Hotspot Coordinates
Hotspots store **image pixel** coordinates (`Hotspot.x/y`), not ratios — the
canvas scales them for display. Anything that swaps a sheet image for one with
different dimensions must rescale them proportionally, or every hotspot drifts
off its lyrics (`SongListWidget._replace_sheet_image` does).

### UI Modes
- **Edit mode** (default): hotspot creation/editing, mapping panel visible
- **Song edit mode**: standalone single-song editing (`MainWindow._is_standalone`),
  entered from the library or the song switcher; the setlist panel becomes a
  sheet list plus a library song switcher
- **Live mode** (F5): red accent, PIP panel, keyboard hint bar, editing locked

---

## Anti-Patterns to Avoid

| Don't | Do Instead |
|-------|------------|
| Connect both `currentItemChanged` + `itemClicked` | Use only `currentItemChanged` |
| Hardcode color values in widgets | Import tokens from `styles.py` |
| Use `font-weight: bold` or `900` | Use `500` (medium) or `600` (semibold) |
| Use emoji in UI text | Use Material Symbols via `icons.py` |
| Mutate domain directly | Use `undo_commands` for undo/redo chain |
| Block UI thread with PPT conversion | Use `QThread` worker pattern |
| Edit during live mode | Guard with `if self._is_live: return` |
| Use `setBackground()` on QListWidget items | Stylesheet overrides it; use `setForeground()` |
| Read `song.json` / `slides.md` directly when listing songs | Use `services/song_index.py` (`song_info`, `song_lyrics`) — mtime-cached |
| Re-filter a list on every `textChanged` | Debounce (`BrowserToolbar` does 120ms); Korean IME fires per jamo |
| Rebuild all cards when a search filter changes | Keep a card pool keyed by path and swap text via setters |
| Touch the filesystem while the user types | Build an index when the disk fingerprint changes; filter that index (`LibraryScreen._rebuild_index` / `_apply_view`). Keeping the search text in the fingerprint re-stats the whole library per keystroke |
| Let a background thread hold the last reference to a `QObject` | Pass plain data into the thread, or keep the object alive from the main thread until the worker reports back — otherwise it is destroyed on the worker thread and the process segfaults |
