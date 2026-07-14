# main.py
import sys
import os
import traceback

# 将项目根目录和 MF_UI/ 加入 sys.path
_this_dir = os.path.dirname(os.path.abspath(__file__))          # MF_UI/
_project_root = os.path.dirname(_this_dir)                       # 项目根
for _d in (_project_root, _this_dir):
    if _d not in sys.path:
        sys.path.insert(0, _d)

from PySide6.QtWidgets import QApplication
from main_window import MainWindow

def main():
    try:
        app = QApplication(sys.argv)
        # 设置应用名称，避免加载某些全局配置干扰
        app.setApplicationName("MF-Mathematics")
        
        window = MainWindow()
        window.show()
        
        sys.exit(app.exec())
    except Exception as e:
        # 捕获所有未处理的异常，打印详细信息
        print("=" * 60)
        print("程序启动时发生严重错误：")
        traceback.print_exc()
        print("=" * 60)
        # 暂停一下，让用户看到错误信息（在命令行窗口）
        input("按 Enter 键退出...")
        sys.exit(1)

if __name__ == "__main__":
    main()