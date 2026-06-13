# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

# Definición de rutas base para el build
tardis_dir = Path('.').resolve()

block_cipher = None

a = Analysis(
    ['app_core/main.py'],
    pathex=[str(tardis_dir)],
    binaries=[],
    datas=[
        ('.env.example', '.'),
        ('modules', 'modules'),
        ('noco_lib', 'noco_lib'),
    ],
    hiddenimports=[
        'requests',
        'dotenv',
        'typer',
        'questionary',
        'modules.localmail.module',
        'modules.localmail.service',
        'modules.localmail.views.composer_view',
        'modules.localmail.views.inbox_view',
        'modules.localmail.views.reader_view',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'noco_lib',
        'noco_core',
        'noco_discovery',
        'noco_ext',
        'noco_modules',
        'noco_cli'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Tardis',
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
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Tardis',
)
