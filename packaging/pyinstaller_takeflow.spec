# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

project_root = Path(SPECPATH).parent
hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("httptools")
    + collect_submodules("websockets")
    + collect_submodules("watchfiles")
)

datas = [
    (str(project_root / "app" / "templates"), "app/templates"),
    (str(project_root / "app" / "static"), "app/static"),
    (str(project_root / "data" / "examples"), "data/examples"),
    (str(project_root / ".env.example"), "."),
    (str(project_root / "README.md"), "."),
]


a = Analysis(
    [str(project_root / "takeflow_launcher.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    name="Takeflow",
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="takeflow",
)
