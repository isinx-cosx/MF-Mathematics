# -*- coding: utf-8 -*-
"""重新截取用户手册所需截图。"""
import subprocess, time, os, ctypes, sys
from ctypes import wintypes
from PIL import ImageGrab

out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "dist", "copyright", "screenshots")
os.makedirs(out, exist_ok=True)

proc = subprocess.Popen([sys.executable, "MF_UI/main.py"])
time.sleep(5)

user32 = ctypes.windll.user32
keybd = user32.keybd_event
KEVUP = 0x0002
VK_TAB, VK_RET, VK_ESC, VK_MENU, VK_V, VK_DOWN, VK_RIGHT = \
    0x09, 0x0D, 0x1B, 0x12, 0x56, 0x28, 0x27

def pk(vk, n=1):
    for _ in range(n):
        keybd(vk, 0, 0, 0); time.sleep(0.02)
        keybd(vk, 0, KEVUP, 0); time.sleep(0.03)

def snap(title, fname):
    hwnd = user32.FindWindowW(None, title)
    if not hwnd:
        print(f"  X {title}")
        return
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.5)
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    img = ImageGrab.grab((r.left, r.top, r.right, r.bottom))
    path = os.path.join(out, fname)
    img.save(path)
    print(f"  OK {fname} ({w}x{h})")

hwnd = user32.FindWindowW(None, "Multifunctional-Mathematics")
if not hwnd:
    print("ERROR: App window not found!")
    proc.terminate(); proc.wait(); sys.exit(1)

user32.SetForegroundWindow(hwnd)
time.sleep(0.5)
user32.ShowWindow(hwnd, 3)  # maximize
time.sleep(1)

# 1. Main window light
snap("Multifunctional-Mathematics", "01_main_light.png")

# 2. Login dialog
import pyautogui
r = wintypes.RECT()
user32.GetWindowRect(hwnd, ctypes.byref(r))
# Click login button area (toolbar right side)
pyautogui.click(r.left + 1100, r.top + 40)
time.sleep(1.5)
snap("账户 — MF-Mathematics", "02_login.png")
pk(VK_ESC); time.sleep(0.5)

# 3. Algebra calc — click combo, select 代数计算 (2nd item)
user32.SetForegroundWindow(hwnd); time.sleep(0.3)
pyautogui.click(r.left + 250, r.top + 85); time.sleep(0.5)
pk(VK_DOWN); pk(VK_RET); time.sleep(1)
snap("Multifunctional-Mathematics", "03_calc_algebra.png")

# 4. Plot mode — click "绘图" then select 普通模式
pyautogui.click(r.left + 130, r.top + 40); time.sleep(0.5)  # plot btn
pyautogui.click(r.left + 250, r.top + 85); time.sleep(0.5)  # combo
pk(VK_RET); time.sleep(1)
snap("Multifunctional-Mathematics", "04_plot_2d.png")

# 5. Dark theme — Alt+V → Down*2 to "暗色主题" → Enter
user32.SetForegroundWindow(hwnd); time.sleep(0.3)
pk(VK_MENU); time.sleep(0.2); pk(VK_V); time.sleep(0.3)
pk(VK_DOWN, 2); pk(VK_RET); time.sleep(1)
snap("Multifunctional-Mathematics", "05_main_dark.png")

# 6. Switch back to light, show keyboard
pk(VK_MENU); time.sleep(0.2); pk(VK_V); time.sleep(0.3)
pk(VK_DOWN, 2); pk(VK_RET); time.sleep(1)
# Enable keyboard via menu
pk(VK_MENU); time.sleep(0.2); pk(VK_V); time.sleep(0.3)
pk(VK_RET); time.sleep(0.5)
snap("Multifunctional-Mathematics", "06_keyboard.png")

# 7. AI dialog — Alt→Right×3(工具)→Down×2(AI助手)→Enter
pk(VK_MENU); time.sleep(0.2)
pk(VK_RIGHT, 3); time.sleep(0.3); pk(VK_DOWN, 2); time.sleep(0.2)
pk(VK_RET); time.sleep(2)
snap("AI 数学助手", "07_ai_dialog.png")
pk(VK_ESC); time.sleep(0.5)

# 8. Settings dialog — open via PySide6
from PySide6.QtWidgets import QApplication
from MF_UI.dialogs.settings_dialog import SettingsDialog
app = QApplication.instance()
mw = None
for w in QApplication.topLevelWidgets():
    if hasattr(w, "_switch_to_light"):
        mw = w; break
if mw:
    dlg = SettingsDialog(mw)
    dlg.show(); app.processEvents(); time.sleep(1)
    snap("设置", "08_settings.png")
    dlg.close()

proc.terminate(); proc.wait()
print("\nDone!")
