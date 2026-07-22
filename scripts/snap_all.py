# -*- coding: utf-8 -*-
"""重截全部 8 张用户手册截图。"""
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

user32 = ctypes.windll.user32


def snap(title, fname):
    hwnd = user32.FindWindowW(None, title)
    if not hwnd:
        print(f"  X {title}")
        return False
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.6)
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    img = ImageGrab.grab((r.left, r.top, r.right, r.bottom))
    img.save(os.path.join(OUT, fname))
    print(f"  {fname} ({img.size[0]}x{img.size[1]})")
    return True


tasks = []
t = tasks.append
t(("主窗口", lambda: snap("Multifunctional-Mathematics", "01_main_light.png")))

t(("登录", lambda: mw._open_login_dialog()))
t(("截登录", lambda: snap("账户 — MF-Mathematics", "02_login.png")))
t(("关登录", lambda: [w.close() for w in app.topLevelWidgets() if "账户" in w.windowTitle()]))

t(("代数", lambda: (mw._sub_combo.setCurrentIndex(1), app.processEvents())))
t(("截代数", lambda: snap("Multifunctional-Mathematics", "03_calc_algebra.png")))

t(("绘图", lambda: (mw._btn_plot.trigger(), app.processEvents(), mw._sub_combo.setCurrentIndex(0), app.processEvents())))
t(("截绘图", lambda: snap("Multifunctional-Mathematics", "04_plot_2d.png")))

t(("暗色", lambda: mw._switch_to_dark()))
t(("截暗色", lambda: snap("Multifunctional-Mathematics", "05_main_dark.png")))

t(("亮色+键盘", lambda: (mw._switch_to_light(), app.processEvents(), mw.keyboard_panel.show() if mw.keyboard_panel else None)))
t(("截键盘", lambda: snap("Multifunctional-Mathematics", "06_keyboard.png")))

t(("AI-setkey", lambda: (
    __import__("MF_AI.config", fromlist=["Config"]).Config().set_api_key("sk-placeholder"),
    print("  API key set for capture"),
)))
t(("AI", lambda: (__import__("MF_UI.dialogs.ai_dialog", fromlist=["AIDialog"]).AIDialog(mw).show(), app.processEvents())))
t(("截AI", lambda: snap("AI 数学助手", "07_ai_dialog.png")))
t(("关AI", lambda: [w.close() for w in app.topLevelWidgets() if "AI" in w.windowTitle()]))

t(("设置", lambda: (__import__("MF_UI.dialogs.settings_dialog", fromlist=["SettingsDialog"]).SettingsDialog(mw).show(), app.processEvents())))
t(("截设置", lambda: snap("设置", "08_settings.png")))
t(("关设置", lambda: [w.close() for w in app.topLevelWidgets() if "设置" == w.windowTitle()]))

t(("生成手册", lambda: (
    __import__("scripts.gen_user_manual_html", fromlist=["build"]).build(),
    print("HTML done"),
)))
t(("PDF", lambda: (
    __import__("subprocess").run([
        "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
        "--headless", "--disable-gpu",
        f"--print-to-pdf={os.path.join(os.path.dirname(OUT), 'MF-Mathematics_用户手册_V1.0.0.pdf')}",
        f"file:///{os.path.join(os.path.dirname(OUT), 'user_manual.html')}",
    ], capture_output=True),
    print("PDF done"),
)))
t(("Word", lambda: (
    __import__("scripts.gen_user_manual_docx", fromlist=["build"]).build(),
    print("Word done"),
)))

t(("退出", lambda: app.quit()))

i = [0]


def run():
    idx = i[0]
    if idx >= len(tasks):
        return
    name, fn = tasks[idx]
    print(f"[{idx+1}/{len(tasks)}] {name}")
    try:
        fn()
    except Exception as e:
        print(f"  ERR: {e}")
    i[0] += 1
    QTimer.singleShot(2000, run)


QTimer.singleShot(3000, run)
app.exec()
