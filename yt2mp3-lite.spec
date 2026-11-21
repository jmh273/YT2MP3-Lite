# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for yt2mp3-lite (onedir mode).

Build: cd backend && pyinstaller ../yt2mp3-lite.spec --noconfirm --clean
Output: backend/dist/yt2mp3-lite/yt2mp3-lite.exe (+ _internal/)
"""
import sys
from pathlib import Path

# This spec is run by PyInstaller via `cd backend && pyinstaller ../yt2mp3-lite.spec`.
# So the working directory is backend/, and SPECPATH is the repo root.
BACKEND_DIR = Path.cwd().resolve()  # = backend/

datas = [
    # ship the version file (build.bat writes it before running pyinstaller)
    (str(BACKEND_DIR / "_version.txt"), "."),
]

# Include the SPA build output if present (build.bat copies frontend/dist → backend/static first)
static_dir = BACKEND_DIR / "static"
if static_dir.is_dir():
    datas.append((str(static_dir), "static"))

# yt_dlp uses dynamic imports for extractors — collect everything it ships
hiddenimports = [
    "yt_dlp",
    "yt_dlp.extractor.common",
]

a = Analysis(
    [str(BACKEND_DIR / "__main__.py")],
    pathex=[str(BACKEND_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",       # not used
        "test",          # python stdlib test
        "pytest",        # dev only
        # 守門：Lite 不得帶任何 Google API 套件（scripts/check_bundle.py 會再檢查一次）
        "google",
        "googleapiclient",
        "google_auth_oauthlib",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="yt2mp3-lite",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,    # Keep console window — shows uvicorn logs / errors
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="yt2mp3-lite",  # → backend/dist/yt2mp3-lite/
)
