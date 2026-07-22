# -*- coding: utf-8 -*-
"""独立截图脚本 — 启动应用并用 QTimer 分时截图后自动退出。"""
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

user32 = ctypes.windll.user32
screenshots = []
_step = 0


def snap(title, fname):
    hwnd = user32.FindWindowW(None, title)
    if not hwnd:
        print(f"  X {title}")
        return
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    img = ImageGrab.grab((r.left, r.top, r.right, r.bottom))
    path = os.path.join(OUT, fname)
    img.save(path)
    print(f"  OK {fname}")


def step():
    global _step
    _step += 1
    print(f"-- Step {_step} --")

    if _step == 1:
        snap("Multifunctional-Mathematics", "01_main_light.png")
        mw._open_login_dialog()

    elif _step == 2:
        snap("账户 — MF-Mathematics", "02_login.png")
        for w in app.topLevelWidgets():
            if "账户" in w.windowTitle():
                w.close()
        # Switch to algebra calc
        mw._sub_combo.setCurrentIndex(1)

    elif _step == 3:
        snap("Multifunctional-Mathematics", "03_calc_algebra.png")
        # Switch to plot mode
        mw._btn_plot.trigger()
        mw._sub_combo.setCurrentIndex(0)

    elif _step == 4:
        snap("Multifunctional-Mathematics", "04_plot_2d.png")
        mw._switch_to_dark()

    elif _step == 5:
        snap("Multifunctional-Mathematics", "05_main_dark.png")
        mw._switch_to_light()
        mw.keyboard_panel.show()

    elif _step == 6:
        snap("Multifunctional-Mathematics", "06_keyboard.png")
        from MF_UI.dialogs.ai_dialog import AIDialog
        dlg = AIDialog(mw)
        dlg.show()

    elif _step == 7:
        snap("AI 数学助手", "07_ai_dialog.png")
        for w in app.topLevelWidgets():
            if "AI" in w.windowTitle():
                w.close()
        from MF_UI.dialogs.settings_dialog import SettingsDialog
        dlg = SettingsDialog(mw)
        dlg.show()

    elif _step == 8:
        snap("设置", "08_settings.png")
        for w in app.topLevelWidgets():
            if "设置" == w.windowTitle():
                w.close()
        # Done
        print("All screenshots done!")
        app.quit()
        return

    QTimer.singleShot(1500, step)


# Start after app is rendered
QTimer.singleShot(3000, step)
app.exec()
