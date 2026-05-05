# Third-Party Notices

Flow incorporates and/or distributes the following third-party software.
Each component is governed by its own license, listed below. Where the
license requires it, copies of the license texts and source pointers are
provided so end users can exercise their rights (e.g. replace bundled
LGPL libraries with their own builds).

---

## Qt 6 / PySide6

- **License**: GNU Lesser General Public License v3.0 (LGPL-3.0)
  - Triple-licensed by upstream as `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`.
  - Flow uses Qt 6 / PySide6 under **LGPL v3**.
- **License text**: https://www.gnu.org/licenses/lgpl-3.0.html
- **Source code**:
  - PySide6: https://code.qt.io/cgit/pyside/pyside-setup.git/
  - Qt 6: https://code.qt.io/cgit/
- **Where it lives in the build**: PySide6/Qt shared libraries are
  bundled inside the PyInstaller `--onedir` output (e.g.
  `Flow/_internal/PySide6/` and `Flow/_internal/Qt/`).
- **Replacing the bundled library** (LGPL relinking right): users may
  replace the `.so` / `.dll` / `.dylib` files inside the install
  directory with their own builds of the same Qt/PySide6 version. The
  `--onedir` layout is dynamically linked at runtime.

## PyMuPDF (`pymupdf` / `fitz`)

- **License**: GNU Affero General Public License v3.0 (AGPL-3.0) or a
  commercial license from Artifex Software.
- **License text**: https://www.gnu.org/licenses/agpl-3.0.html
- **Source code**: https://github.com/pymupdf/PyMuPDF
- **Where it lives in the build**: bundled in PyInstaller output as a
  Python extension.
- **Note**: AGPL-3.0 is GPL-compatible. Combining Flow (GPL-3.0-or-later)
  with PyMuPDF (AGPL-3.0) means the combined distribution must satisfy
  AGPL terms — for a desktop app this is effectively the same as GPL,
  since AGPL's additional source-disclosure clause only triggers for
  network-served use.

## Pretendard Variable (font)

- **License**: SIL Open Font License v1.1 (OFL-1.1)
- **License text**: https://openfontlicense.org/open-font-license-official-text/
- **Source / project**: https://github.com/orioncactus/pretendard
- **Where it lives**: `src/flow/resources/PretendardVariable.ttf`
- **Note**: Bundled and loaded at app start
  (`flow.ui.styles.ensure_fonts_loaded`). OFL-1.1 permits embedding
  in any document or program, free or commercial; the font itself
  retains its license but does not affect Flow's overall license.

## Material Symbols Rounded (font, subset)

- **License**: Apache License 2.0
- **License text**: https://www.apache.org/licenses/LICENSE-2.0
- **Source / project**: https://github.com/google/material-design-icons
- **Where it lives**: `src/flow/resources/MaterialSymbolsRounded-Subset.ttf`
- **Note**: A subset built from the upstream font, containing only the
  glyphs used by Flow's UI (see `src/flow/ui/icons.py` `_CODEPOINTS`).

## watchdog

- **License**: Apache License 2.0
- **Source**: https://github.com/gorakhargosh/watchdog

## pdf2image

- **License**: MIT License
- **Source**: https://github.com/Belval/pdf2image

## python-pptx

- **License**: MIT License
- **Source**: https://github.com/scanny/python-pptx

## PyYAML

- **License**: MIT License
- **Source**: https://github.com/yaml/pyyaml

## pywin32 (Windows only)

- **License**: Python Software Foundation License
- **Source**: https://github.com/mhammond/pywin32

---

## License of the rest

Everything else in this repository — the Flow application source code,
build scripts, documentation, and bundled assets (icons, default
backgrounds) — is licensed under **GNU General Public License v3.0
or later**. See [LICENSE](LICENSE) for the full text.
