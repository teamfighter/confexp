# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        # core deps
        'requests', 'urllib3', 'chardet', 'idna', 'certifi',
        # tui
        'InquirerPy', 'prompt_toolkit',
        # progress / md
        'tqdm', 'markdownify',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# extra safety: collect entire packages (useful on Windows runners)
from PyInstaller.utils.hooks import collect_all
for pkg in ['requests', 'InquirerPy', 'prompt_toolkit', 'tqdm', 'markdownify', 'urllib3', 'chardet', 'idna', 'certifi']:
    datas, binaries, hiddenimports = collect_all(pkg)
    a.datas += datas
    a.binaries += binaries
    a.hiddenimports += hiddenimports

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='confexp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='confexp',
)
