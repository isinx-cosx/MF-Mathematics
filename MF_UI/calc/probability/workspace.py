# ————————————MF-Mathematics 概率论与数理统计工作区 ————————————

# 导入必要库以及自定义组件
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from calc.probability.calc_block import CalcBlock
from PySide6.QtWidgets import *

# 定义 Workspace 类 —— 概率论与数理统计工作区 ——
class Workspace(QWidget):
    def __init__(self):
        super().__init__()

        # 初始化标题和描述标签
        title_label = QLabel("概率论与数理统计")
        title_label.setObjectName("title_label")
        desc_label = QLabel("包含：概率分布、期望、方差、假设检验；统计图绘制功能等")
        desc_label.setObjectName("desc_label")

        # 创建卡片容器
        self.card = QFrame()
        self.card.setObjectName("work_card")

        # 创建滚动区域
        self.scroll_area = QScrollArea(self.card)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)

        # 创建画布
        self.content_widget = QWidget()
        self.scroll_area.setWidget(self.content_widget)

        # 创建画布布局
        self.card_layout = QVBoxLayout(self.content_widget)
        self.card_layout.setSpacing(8)

        # 让滚动区域填满卡片
        card_inner_layout = QVBoxLayout(self.card)
        card_inner_layout.setContentsMargins(0, 0, 0, 0)
        card_inner_layout.addWidget(self.scroll_area)

        # 虚框添加计算块按钮添加
        self.btn_add = QPushButton("")
        self.btn_add.setFlat(True)
        self.btn_add.setFixedHeight(50)
        self.btn_add.setObjectName("btn_add") 
        self.card_layout.addWidget(self.btn_add)
        self.card_layout.addStretch()

    # 添加计算块函数
        self.block_counter = 1
        self.blocks = []

        self.btn_add.clicked.connect(self.on_add_block_clicked)

        # 添加计算块到容器
        self.on_add_block_clicked()

        # 设置工作区样式
        self.setStyleSheet("""
            Workspace { background-color: #f8fafc;
            }

            #title_label {
                font-size: 20px;
                font-weight: 600;
                color: #0f172a;
            }
            #desc_label {
                font-size: 14px;
                color: #475569;
            }
            #work_card {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                padding: 12px;
            }
            #btn_add {
                border-top: 1px solid #d7d7d7;
                border-left: 1px solid #d7d7d7;
                border-right: 1px solid #d7d7d7;
                border-bottom: none;
                background-color: transparent;
            }
            #btn_add:hover{
                background-color: #e0e2e4d8;
            }
        """)

        # 初始化布局
        layout = QVBoxLayout(self)
        layout.setSpacing(2)

        # 放置标题和描述标签
        layout.addWidget(title_label)
        layout.addWidget(desc_label)
        layout.addWidget(self.card, 1)

    def on_add_block_clicked(self):
        """添加计算块到工作区"""
        calc_block = CalcBlock(block_id=self.block_counter, on_delete=self.on_delete_btn_clicked )
        calc_block.setFixedHeight(120)
        self.block_counter += 1

        index = self.card_layout.indexOf(self.btn_add)

        if len(self.blocks) > 0:
            separator = QFrame()
            separator.setFixedHeight(1)
            separator.setStyleSheet("background-color: #e2e8f0; border: none;")
            self.card_layout.insertWidget(index, calc_block)
            self.card_layout.insertWidget(index, separator)
            calc_block._separator = separator
        else:
            self.card_layout.insertWidget(index, calc_block)
            calc_block._separator = None

        self.blocks.append(calc_block)

    def on_delete_btn_clicked(self, block_to_delete):
        """删除指定的计算块"""
        if len(self.blocks) <= 1:
            return

        if hasattr(block_to_delete, '_separator') and block_to_delete._separator:
            self.card_layout.removeWidget(block_to_delete._separator)
            block_to_delete._separator.deleteLater()
            block_to_delete._separator = None

        self.card_layout.removeWidget(block_to_delete)
        if block_to_delete in self.blocks:
            self.blocks.remove(block_to_delete)
        block_to_delete.deleteLater()

# 测试代码
if __name__ == "__main__":
    app = QApplication([])
    window = Workspace()
    window.resize(400, 200)
    window.setWindowTitle("代数计算测试")
    window.show()
    app.exec()