# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['MF_UI\\main.py'],
    pathex=['.', 'MF_UI'],
    binaries=[],
    datas=[('config.json', '.'), ('assets/icon.ico', 'assets'), ('assets/titlebar_icon.ico', 'assets'), ('MF_Mathematics', 'MF_Mathematics'), ('MF_AI', 'MF_AI'), ('MF_Online', 'MF_Online'), ('MF_Tutorial', 'MF_Tutorial'), ('MF_User', 'MF_User'), ('MF_UI/styles', 'styles'), ('MF_UI/components/formula_input.html', 'components'), ('MF_UI/plot', 'plot'), ('MF_UI/calc', 'calc')],
    hiddenimports=['_import_all', 'calc.basic_arithmetic.workspace', 'calc.basic_arithmetic.calculator', 'plot', 'plot.fractal', 'plot.fractal.workspace', 'plot.basic', 'plot.basic.workspace', 'plot.basic.function_box', 'plot.basic.plot_canvas', 'plot.basic.slider_function_box', 'plot.complex', 'plot.complex.workspace', 'plot.vector_field', 'plot.vector_field.workspace', 'plot.plot_3d', 'plot.plot_3d.workspace', 'plot.plot_3d.canvas', 'plot.plot_3d.function_box', 'plot.arbitrary', 'plot.arbitrary.workspace', 'plot.arbitrary.geometry_canvas', 'plot.arbitrary.shapes', 'plot.arbitrary.undo_manager', 'plot.mpl_setup', 'plot.plot_colors', 'plot.grid_renderer'],
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
    name='Multifunctional-Mathematics-v1.0',
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
    name='Multifunctional-Mathematics-v1.0',
)
