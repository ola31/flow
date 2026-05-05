# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — cross-platform (Windows / macOS / Linux).

Per-OS icon picked automatically; macOS adds a .app BUNDLE wrapper.
Run via:  pyinstaller Flow.spec --noconfirm
"""

import sys

_IS_MAC = sys.platform == "darwin"
_IS_WIN = sys.platform == "win32"

if _IS_MAC:
    _icon = "assets/icon.icns"
elif _IS_WIN:
    _icon = "assets/icon.ico"
else:
    _icon = "assets/icon.png"


a = Analysis(
    ['src/flow/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('src/flow/resources', 'flow/resources'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Flow',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[_icon],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Flow',
)

if _IS_MAC:
    app = BUNDLE(
        coll,
        name='Flow.app',
        icon=_icon,
        bundle_identifier='com.flow.app',
        info_plist={
            'CFBundleName': 'Flow',
            'CFBundleDisplayName': 'Flow',
            'CFBundleShortVersionString': '0.1.0',
            'NSHighResolutionCapable': True,
            # Korean + English supported
            'CFBundleDevelopmentRegion': 'ko_KR',
        },
    )
