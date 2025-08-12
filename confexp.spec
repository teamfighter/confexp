# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

from PyInstaller.utils.hooks import collect_all

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'requests', 'urllib3', 'idna', 'certifi', 'chardet',
        'InquirerPy', 'prompt_toolkit',
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

# collect all submodules and data for these packages
for pkg in ['requests', 'urllib3', 'idna', 'certifi', 'chardet', 'InquirerPy', 'prompt_toolkit', 'tqdm', 'markdownify']:
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
    onefile=True  # <---- ключевой момент: один файл
)
