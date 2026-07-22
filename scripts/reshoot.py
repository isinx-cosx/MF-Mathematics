# -*- coding: utf-8 -*-
"""重截全部 8 张用户手册截图 + 生成手册。"""
import sys, os, time, ctypes
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
app.processEvents()
time.sleep(2)

user32 = ctypes.windll.user32


def snap(title, fname):
    hwnd = user32.FindWindowW(None, title)
    if not hwnd:
        print(f"  X {title}")
        return
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.5)
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    img = ImageGrab.grab((r.left, r.top, r.right, r.bottom))
    img.save(os.path.join(OUT, fname))
    print(f"  OK {fname} ({img.size[0]}x{img.size[1]})")


# ── 预设 AI key，防止弹窗 ──
from MF_AI.config import Config
cfg = Config()
if not cfg.api_key:
    cfg.set_api_key("sk-placeholder")

# ── 非模态对话框引用 ──
_dialogs = []


def open_dlg(cls, *args):
    dlg = cls(*args)
    dlg.setAttribute(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.WA_DeleteOnClose)
    dlg.show()
    _dialogs.append(dlg)
    app.processEvents()
    return dlg


def close_all(pattern):
    for w in list(app.topLevelWidgets()):
        try:
            if pattern in w.windowTitle() and w.isVisible():
                w.close()
        except RuntimeError:
            pass
    app.processEvents()


from MF_User.login_dialog import LoginRegisterDialog
from MF_UI.dialogs.ai_dialog import AIDialog
from MF_UI.dialogs.settings_dialog import SettingsDialog

# ── 步骤序列 ──
step = [0]

def next_step():
    step[0] += 1
    s = step[0]

    if s == 1:
        print("1/8 主窗口")
        snap("Multifunctional-Mathematics", "01_main_light.png")

    elif s == 2:
        print("2/8 登录")
        open_dlg(LoginRegisterDialog, mw)

    elif s == 3:
        snap("账户 — MF-Mathematics", "02_login.png")
        close_all("账户")

    elif s == 4:
        print("3/8 计算")
        mw._sub_combo.setCurrentIndex(1)  # 代数
        app.processEvents()

    elif s == 5:
        snap("Multifunctional-Mathematics", "03_calc_algebra.png")

    elif s == 6:
        print("4/8 绘图")
        mw._btn_plot.trigger()
        mw._sub_combo.setCurrentIndex(0)
        app.processEvents()

    elif s == 7:
        snap("Multifunctional-Mathematics", "04_plot_2d.png")

    elif s == 8:
        print("5/8 暗色")
        mw._switch_to_dark()

    elif s == 9:
        snap("Multifunctional-Mathematics", "05_main_dark.png")

    elif s == 10:
        print("6/8 键盘")
        mw._switch_to_light()
        mw.keyboard_panel.show()
        app.processEvents()

    elif s == 11:
        snap("Multifunctional-Mathematics", "06_keyboard.png")
        mw.keyboard_panel.hide()

    elif s == 12:
        print("7/8 AI")
        open_dlg(AIDialog, mw)

    elif s == 13:
        snap("AI 数学助手", "07_ai_dialog.png")
        close_all("AI")

    elif s == 14:
        print("8/8 设置")
        dlg = open_dlg(SettingsDialog, mw)
        dlg.resize(800, 600)

    elif s == 15:
        snap("设置", "08_settings.png")
        close_all("设置")
        mw._sub_combo.setCurrentIndex(0)
        mw._btn_calc.trigger()

    elif s == 16:
        print("\n生成 HTML...")
        from scripts.gen_user_manual_html import build
        build()
        print("生成 PDF...")
        import subprocess
        edge = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
        html = os.path.join(os.path.dirname(OUT), "user_manual.html")
        pdf = os.path.join(os.path.dirname(OUT), "MF-Mathematics_用户手册_V1.0.0.pdf")
        subprocess.run([edge, "--headless", "--disable-gpu",
                        f"--print-to-pdf={pdf}", f"file:///{html}"],
                       capture_output=True)
        print(f"PDF: {os.path.getsize(pdf)/1024:.0f} KB")
        from scripts.gen_user_manual_docx import build as build_docx
        build_docx()
        print("\n全部完成！")
        app.quit()
        return

    QTimer.singleShot(1800, next_step)


QTimer.singleShot(2000, next_step)
app.exec()
