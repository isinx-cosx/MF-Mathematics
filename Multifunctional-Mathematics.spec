# -*- mode: python ; coding: utf-8 -*-
#  onefile 模式：所有代码编译为 .pyc 并打包进单个 .exe，不暴露源码

block_cipher = None

a = Analysis(
    ['MF_UI\\main.py'],
    pathex=['.', 'MF_UI'],
    binaries=[],
    datas=[
        # 仅非 Python 资源文件（.py 源码由 PyInstaller 分析、编译、归档到 PYZ，不会暴露）
        ('config.json', '.'),
        ('assets/icon.ico', 'assets'),
        ('assets/titlebar_icon.ico', 'assets'),
        ('MF_UI/styles', 'styles'),
        ('MF_UI/components/formula_input.html', 'components'),
        ('MF_Tutorial/tutorials', 'tutorials'),
        ('MF_AI/config.yaml', 'MF_AI'),
    ],
    hiddenimports=[
        '_import_all',
        # calc
        'calc.basic_arithmetic.workspace', 'calc.basic_arithmetic.calculator',
        # plot
        'plot', 'plot.fractal', 'plot.fractal.workspace',
        'plot.basic', 'plot.basic.workspace', 'plot.basic.function_box',
        'plot.basic.plot_canvas', 'plot.basic.slider_function_box',
        'plot.complex', 'plot.complex.workspace',
        'plot.vector_field', 'plot.vector_field.workspace',
        'plot.plot_3d', 'plot.plot_3d.workspace', 'plot.plot_3d.canvas',
        'plot.plot_3d.function_box',
        'plot.arbitrary', 'plot.arbitrary.workspace',
        'plot.arbitrary.geometry_canvas', 'plot.arbitrary.shapes',
        'plot.arbitrary.undo_manager',
        'plot.mpl_setup', 'plot.plot_colors', 'plot.grid_renderer',
        # MF_User — 用户认证系统
        'MF_User', 'MF_User.auth_service', 'MF_User.auth_worker',
        'MF_User.api_client', 'MF_User.login_dialog',
        # MF_Online — 在线功能
        'MF_Online', 'MF_Online.config', 'MF_Online.cache', 'MF_Online.search',
        # 版本检测
        'requests',
    ],
    cipher=block_cipher,
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
    a.binaries,
    a.datas,
    [],
    exclude_binaries=False,  # onefile：全部打入单个 exe
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
    icon=['assets\\icon.ico'],
)
