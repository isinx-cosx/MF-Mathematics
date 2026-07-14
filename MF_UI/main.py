# main.py
import sys
import os
import traceback

# 将 MF_UI 目录加入 sys.path，确保可导入同目录下的 main_window
_this_dir = os.path.dirname(os.path.abspath(__file__))
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)

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