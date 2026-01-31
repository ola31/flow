# AGENTS.md - AI Agent Guidelines for Flow

## Project Overview

**Flow** is a desktop slide broadcasting system for worship/presentation contexts.  
Maps hotspots on score sheet images to PPT slides for one-click live broadcasting.

**Core Stack**: Python 3.10+, PySide6 (Qt), python-pptx, PyInstaller  
**Architecture**: Domain → Services → UI (layered)

---

## Build, Lint, and Test Commands

```bash
# Install (dev mode)
pip install -e ".[dev]"

# Run application
flow
# or: python -m flow.main

# === TESTING ===
# Run all tests
pytest

# Run single test file
pytest tests/domain/test_hotspot.py

# Run single test class
pytest tests/domain/test_hotspot.py::TestHotspotCreation

# Run single test method
pytest tests/domain/test_hotspot.py::TestHotspotCreation::test_create_hotspot_with_coordinates

# Run with coverage
pytest --cov=flow --cov-report=term-missing

# Run tests matching pattern
pytest -k "test_preview"

# === LINTING ===
ruff check src/ tests/           # Lint
ruff check --fix src/ tests/     # Auto-fix
black src/ tests/                 # Format
mypy src/                         # Type check

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
└── ui/               # PySide6 UI layer
    ├── editor/, live/, display/

tests/
├── conftest.py       # Shared fixtures (headless Qt: --platform offscreen)
├── domain/, services/, ui/
```

---

## Code Style Guidelines

### Imports (order: stdlib → third-party → local)
```python
from __future__ import annotations  # ALWAYS first
import uuid
from dataclasses import dataclass, field
from PySide6.QtCore import QObject, Signal
from flow.domain.hotspot import Hotspot
```

### Type Hints (Python 3.10+ syntax)
```python
def get_slide_index(self, verse_index: int = 0) -> int: ...
def __init__(self, parent: QObject | None = None) -> None: ...
slide_mappings: dict[str, int] = field(default_factory=dict)  # Not Dict[]
```

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Classes | PascalCase | `LiveController`, `ScoreSheet` |
| Functions/methods | snake_case | `get_slide_index`, `send_to_live` |
| Private members | `_prefix` | `self._preview_hotspot` |
| Qt Signals | snake_case | `preview_changed`, `load_finished` |
| Test classes/methods | `Test*` / `test_*` | `TestHotspotCreation`, `test_create_hotspot` |

### Dataclasses (Domain Models)
```python
@dataclass
class Hotspot:
    x: int
    y: int
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> dict[str, Any]: ...      # JSON serialization
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Hotspot: ...
```

### Qt/PySide6 Patterns
```python
class LiveController(QObject):
    preview_changed = Signal(str)  # Signals as class attributes
    
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._preview_hotspot: Hotspot | None = None
```

### Error Handling
```python
class SlideLoadError(Exception):
    """PPTX load failure"""

try:
    prs = Presentation(str(path))
except PackageNotFoundError:
    raise SlideLoadError(f"Invalid PPTX format: {path}")
```

---

## Testing Guidelines

### SignalSpy Pattern (for Qt signals)
```python
class SignalSpy:
    def __init__(self, signal):
        self.called = False
        self.args = None
        signal.connect(self.callback)
    def callback(self, *args):
        self.called = True
        self.args = args

spy = SignalSpy(controller.preview_changed)
controller.set_preview(hotspot)
assert spy.called and spy.args[0] == "Expected"
```

---

## Critical Domain Knowledge

### Verse Mapping
- `verse_index 0-4` = Verses 1-5 (user-facing)
- `verse_index 5` = **Chorus** (fallback when no verse mapping exists)

### Navigation Flow
- **Up/Down**: Move through hotspots (Preview only, NOT Live)
- **Enter**: Confirm Preview → Live
- **Left/Right**: Switch songs (ScoreSheets)
- **Number keys 1-6**: Change verse, triggers `sync_live()`

### Path Handling
```python
path_str = Path(path).as_posix()  # CORRECT: forward slashes for JSON
# NOT: str(Path(path))  # WRONG: backslashes on Windows
```

---

## Anti-Patterns to Avoid

| ❌ Don't | ✅ Do Instead |
|----------|---------------|
| Connect both `currentItemChanged` + `itemClicked` | Use only `currentItemChanged` |
| Hardcode styles in widgets | Centralize in `MainWindow` stylesheet |
| Mutate domain directly (`hotspot.x = 10`) | Use `undo_commands` for undo/redo chain |
| Block UI thread with PPT conversion | Use `QThread` worker pattern |
| Edit during live mode | Guard with `if self._is_live_mode: return` |
