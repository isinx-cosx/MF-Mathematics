# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('config.json', '.'), ('assets/icon.ico', 'assets'), ('MF_Mathematics', 'MF_Mathematics'), ('MF_AI', 'MF_AI'), ('MF_Online', 'MF_Online'), ('MF_Tutorial', 'MF_Tutorial'), ('MF_User', 'MF_User'), ('MF_UI/styles', 'styles'), ('MF_UI/components/formula_input.html', 'components')]
binaries = []
hiddenimports = []
tmp_ret = collect_all('plot')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('calc')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['MF_UI\\main.py'],
    pathex=['.', 'MF_UI'],
    binaries=binaries,
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
    name='MF-Mathematics',
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
    name='MF-Mathematics',
)
