# AGENTS.md - AI Agent Guidelines for Flow

## Project Overview

**Flow** is a desktop slide broadcasting system for worship/presentation contexts.
Maps hotspots on score sheet images to PPT slides for one-click live broadcasting.

**Core Stack**: Python 3.10+, PySide6 (Qt Widgets), python-pptx, PyInstaller
**Architecture**: Domain → Services → UI (layered)

**Two-tier structure**:
- **Song** — reusable unit: score sheet images + PPT + hotspot mappings
- **Project** — setlist: ordered collection of songs for one worship session

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
│   ├── project.py, score_sheet.py, hotspot.py, song.py
├── services/         # Business logic
│   ├── config_service.py, slide_manager.py, slide_converter.py
├── repository/       # Data persistence
├── resources/        # Bundled assets (icon font)
└── ui/               # PySide6 UI layer
    ├── styles.py     # Design tokens (colors, spacing, typography)
    ├── icons.py      # Material Symbols icon helper
    ├── screens/      # Home screen, project screen
    ├── editor/       # Score canvas, song list, mapping panel, verse selector
    ├── live/         # Live controller
    └── display/      # Display window (fullscreen output)

tests/
├── conftest.py       # Shared fixtures (headless Qt: --platform offscreen)
├── domain/, services/, ui/
```

---

## Design System

### Color Palette (defined in `styles.py`)

All colors must be referenced from `styles.py` tokens. Never hardcode hex values.

| Token | Value | Usage |
|-------|-------|-------|
| `BG_DEEP` | `#121212` | Window background |
| `BG_SURFACE` | `#1a1a1a` | Panel/sidebar background |
| `BG_ELEVATED` | `#222222` | Cards, elevated surfaces |
| `BG_HOVER` | `#2a2a2a` | Hover state |
| `BORDER` | `#2e2e2e` | Default border |
| `TEXT_PRIMARY` | `#e8e8e8` | Body text, titles |
| `TEXT_SECONDARY` | `#a0a0a0` | Supporting text |
| `TEXT_TERTIARY` | `#606060` | Disabled, hints |
| `ACCENT` | `#5b8def` | Selection, CTA, links |
| `GREEN` | `#34d399` | Success, mapped |
| `AMBER` | `#f59e0b` | Warning, incomplete |
| `RED` | `#ef4444` | Live mode, danger |

### Typography
- Font weights: 300 (light, titles), 500 (medium, body/buttons), 600 (semibold, section headers)
- **Never use `font-weight: bold` or `900`** — causes smudgy text at small sizes
- Sizes defined as tokens: `FONT_SM`(11), `FONT_MD`(12), `FONT_LG`(13), `FONT_XL`(14), `FONT_2XL`(18)

### Icons
- Material Symbols Rounded (subset, 66KB TTF in `resources/`)
- Use `icons.py`: `icon_qicon("home")` for QAction, `icon_label("save")` for QLabel
- Render via `icon_pixmap()` / `icon_qicon()` for toolbar buttons

### Spacing (8px base)
- `SP_XS`(4), `SP_SM`(8), `SP_MD`(12), `SP_LG`(16), `SP_XL`(24), `SP_2XL`(32)

### Visual Depth
- Use background color difference, not borders, to separate regions
- `QGraphicsDropShadowEffect` for floating panels (blur 24-32, offset 4-6)
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
- **Up/Down**: Move through hotspots (Preview only, NOT Live)
- **Enter/Space**: Confirm Preview → Live
- **Left/Right**: Switch songs (ScoreSheets)
- **Number keys 1-5, C**: Change verse
- **B**: Blackout (live mode)
- **Esc**: Exit live mode (with confirmation)
- **Tab/Shift+Tab**: Cycle hotspots within current verse layer

### UI Modes
- **Edit mode** (default): hotspot creation/editing, mapping panel visible
- **Song edit mode**: standalone single-song editing, yellow accent toolbar
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
