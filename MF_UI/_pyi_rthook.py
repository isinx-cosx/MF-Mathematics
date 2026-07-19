"""PyInstaller 运行时 hook — 将 MF_UI 目录加入 sys.path，确保 plot/calc 等子包可导入。"""
import sys, os
_mf_ui_dir = os.path.dirname(os.path.abspath(__file__))
if _mf_ui_dir not in sys.path:
    sys.path.insert(0, _mf_ui_dir)
