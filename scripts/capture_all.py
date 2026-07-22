# -*- coding: utf-8 -*-
"""一键重截用户手册全部截图。"""
import sys, os, time, ctypes, base64
sys.path.insert(0, "MF_UI")
sys.path.insert(0, ".")

from ctypes import wintypes
from PIL import ImageGrab
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from main_window import MainWindow

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "dist", "copyright", "screenshots")
os.makedirs(OUT, exist_ok=True)

app = QApplication(sys.argv)
mw = MainWindow()
mw.show()

user32 = ctypes.windll.user32


def snap(title, fname):
    hwnd = user32.FindWindowW(None, title)
    if not hwnd:
        print(f"  X 未找到窗口: {title}")
        # 枚举所有窗口帮助调试
        def enum_cb(h, _):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(h, buf, 256)
            t = buf.value
            if t:
                print(f"    现有窗口: [{t}]")
            return True
        ctypes.windll.user32.EnumWindows(ctypes.WINFUNCTYPE(
            ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(enum_cb), 0)
        return False
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.5)
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    img = ImageGrab.grab((r.left, r.top, r.right, r.bottom))
    path = os.path.join(OUT, fname)
    img.save(path)
    print(f"  OK {fname} ({img.size[0]}x{img.size[1]})")
    return True


_step = 0


def step():
    global _step
    _step += 1

    if _step == 1:
        print("1/8 主窗口亮色")
        user32.ShowWindow(user32.FindWindowW(None, "Multifunctional-Mathematics"), 1)
        time.sleep(0.5)
        snap("Multifunctional-Mathematics", "01_main_light.png")

    elif _step == 2:
        print("2/8 登录对话框")
        mw._open_login_dialog()
        app.processEvents()

    elif _step == 3:
        snap("账户 — MF-Mathematics", "02_login.png")
        for w in app.topLevelWidgets():
            if "账户" in w.windowTitle():
                w.close()
        # 切到代数计算
        mw._sub_combo.setCurrentIndex(1)
        app.processEvents()

    elif _step == 4:
        print("3/8 计算功能")
        snap("Multifunctional-Mathematics", "03_calc_algebra.png")
        mw._btn_plot.trigger()
        app.processEvents()
        mw._sub_combo.setCurrentIndex(0)
        app.processEvents()

    elif _step == 5:
        print("4/8 绘图功能")
        snap("Multifunctional-Mathematics", "04_plot_2d.png")
        mw._switch_to_dark()
        app.processEvents()

    elif _step == 6:
        print("5/8 暗色主题")
        snap("Multifunctional-Mathematics", "05_main_dark.png")
        mw._switch_to_light()
        app.processEvents()
        # 显示键盘面板
        if hasattr(mw, "keyboard_panel") and mw.keyboard_panel:
            mw.keyboard_panel.show()
        app.processEvents()

    elif _step == 7:
        print("6/8 键盘面板")
        snap("Multifunctional-Mathematics", "06_keyboard.png")

        # 预填 API key 避免弹窗
        try:
            from MF_AI.config import Config
            cfg = Config()
            if not cfg.api_key:
                cfg.set_api_key("sk-placeholder")
                cfg.save_to_files()
        except Exception:
            pass
        from MF_UI.dialogs.ai_dialog import AIDialog
        dlg = AIDialog(mw)
        dlg.show()
        app.processEvents()

    elif _step == 8:
        print("7/8 AI助手")
        snap("AI 数学助手", "07_ai_dialog.png")
        for w in app.topLevelWidgets():
            if "AI" in w.windowTitle():
                w.close()
        app.processEvents()
        from MF_UI.dialogs.settings_dialog import SettingsDialog
        sdlg = SettingsDialog(mw)
        sdlg.resize(800, 600)
        sdlg.show()
        app.processEvents()

    elif _step == 9:
        print("8/8 设置")
        snap("设置", "08_settings.png")
        for w in app.topLevelWidgets():
            if "设置" == w.windowTitle():
                w.close()
        app.processEvents()
        mw._sub_combo.setCurrentIndex(0)
        mw._btn_calc.trigger()
        app.processEvents()

        # 生成 HTML + PDF
        print("\n生成 HTML 用户手册...")
        from scripts.gen_user_manual_html import build
        build()

        print("生成 PDF...")
        import subprocess
        html_path = os.path.join(os.path.dirname(OUT), "user_manual.html")
        pdf_path = os.path.join(os.path.dirname(OUT), "MF-Mathematics_用户手册_V1.0.0.pdf")
        edge = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
        subprocess.run([
            edge, "--headless", "--disable-gpu",
            f"--print-to-pdf={pdf_path}",
            f"file:///{html_path}",
        ], capture_output=True)
        print(f"PDF: {os.path.getsize(pdf_path)/1024:.0f} KB")

        # Word
        from scripts.gen_user_manual_docx import build as build_docx
        build_docx()
        print("全部完成！")
        app.quit()
        return

    QTimer.singleShot(2000, step)


QTimer.singleShot(3000, step)
app.exec()
