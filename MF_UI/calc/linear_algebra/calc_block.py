# ————————————MF-Mathematics 线性代数计算块———————————

# 连接后台引擎
from PySide6.QtWidgets import *
from PySide6.QtCore import Qt

import sys, re, os
from ast import literal_eval

# 将项目根目录加入 sys.path
_calc_block_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(_calc_block_dir)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from MF_Mathematics.core.registry import dispatch
import MF_Mathematics.linear_algebra
from MF_Mathematics.core.math_object import MathObject

# 导入 LaTeX 组件
from calc.math_display import LatexLineEdit, ResultDialog


class CalcBlock(QWidget):
    def __init__(self, block_id: int, on_delete: callable, parent=None):
        super().__init__(parent)
        self.block_id = block_id
        self.on_delete = on_delete
        self._last_result: MathObject | None = None

        self._modes = [
            "高斯消元", "矩阵秩", "求解方程组", "零空间",
            "特征值", "特征向量", "特征多项式", "可对角化", "对角化",
            "点积", "范数", "夹角", "正交性",
            "施密特正交化", "正交投影", "二次型", "正定性判定",
        ]
        self.last_algebra_index = 0

        self.input_box = LatexLineEdit(self)
        self.input_box.returnPressed.connect(self.on_calc_clicked)

        self.calc_mode_combo = QComboBox(self)
        self.calc_mode_combo.addItems(self._modes)
        self.calc_mode_combo.setCurrentIndex(self.last_algebra_index)
        self.calc_mode_combo.currentIndexChanged.connect(self.on_calc_mode_changed)

        self.calc_btn = QPushButton("计算结果")
        self.calc_btn.setObjectName("calc_btn")
        self.calc_btn.clicked.connect(self.on_calc_clicked)

        self.delete_btn = QPushButton("✕")
        self.delete_btn.setObjectName("delete_btn")
        self.delete_btn.setFixedWidth(30)
        self.delete_btn.clicked.connect(self.on_delete_btn_clicked)

        layout = QHBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(6, 6, 6, 6)

        layout.addWidget(self.input_box, 1)
        layout.addWidget(self.calc_mode_combo, 0)
        layout.addWidget(self.calc_btn, 0)
        layout.addWidget(self.delete_btn, 0)

        self.setStyleSheet("""
            CalcBlock {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 8px;
                margin: 4px 0px;
            }

            QLineEdit {
                border: 1px solid #d1d5db;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 13px;
                background-color: #fafafa;
                selection-background-color: #3b82f6;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
                background-color: #ffffff;
                outline: none;
            }
            QComboBox {
                border: 1px solid #d1d5db;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 13px;
                background-color: #fafafa;
                min-width: 100px;
            }
            QComboBox:hover {
                background-color: #9ca3af;
            }
            QComboBox:on {
                background-color: #3b82f6;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::drop-arrow {
                width: 12px;
                height: 12px;
            }

            QPushButton#calc_btn {
                background-color: #3b82f6;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton#calc_btn:hover {
                background-color: #2563eb;
            }
            QPushButton#calc_btn:pressed {
                background-color: #1d4ed8;
            }

            QPushButton#delete_btn {
                background-color: transparent;
                border: none;
                color: #94a3b8;
                font-size: 16px;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton#delete_btn:hover {
                background-color: #fee2e2;
                color: #ef4444;
            }
            QPushButton#delete_btn:pressed {
                background-color: #fecaca;
            }
        """)

    # ---- 事件处理 ----
    def on_calc_clicked(self):
        """点击计算结果按钮或按回车触发计算"""
        expr = self.input_box.text().strip()
        if not expr:
            return

        mode = self.calc_mode_combo.currentText()

        action_map = {
            "高斯消元":        ("linear_algebra", "gaussian_elimination"),
            "矩阵秩":         ("linear_algebra", "rank"),
            "求解方程组":      ("linear_algebra", "solve_linear_system"),
            "零空间":         ("linear_algebra", "nullspace"),
            "特征值":         ("linear_algebra", "eigenvalues"),
            "特征向量":       ("linear_algebra", "eigenvectors"),
            "特征多项式":     ("linear_algebra", "characteristic_polynomial"),
            "可对角化":       ("linear_algebra", "is_diagonalizable"),
            "对角化":         ("linear_algebra", "diagonalize"),
            "点积":           ("linear_algebra", "dot"),
            "范数":           ("linear_algebra", "norm"),
            "夹角":           ("linear_algebra", "angle"),
            "正交性":         ("linear_algebra", "is_orthogonal"),
            "施密特正交化":   ("linear_algebra", "gram_schmidt"),
            "正交投影":       ("linear_algebra", "orthogonal_projection"),
            "二次型":         ("linear_algebra", "quadratic_form"),
            "正定性判定":     ("linear_algebra", "is_positive_definite"),
        }

        try:
            mod, act = action_map[mode]

            if "=" in expr and expr.count("=") <= 2:
                parts = re.split(r'[,;]\s*(?=[a-zA-Z_])', expr)
                kwargs = {}
                for p in parts:
                    if "=" in p:
                        k, v = p.split("=", 1)
                        kwargs[k.strip()] = literal_eval(v.strip())
                result = dispatch(mod, act, **kwargs)
            else:
                args = literal_eval(expr)
                if isinstance(args, (list, tuple)):
                    result = dispatch(mod, act, *args)
                else:
                    result = dispatch(mod, act, args)

            self._last_result = result

            dlg = ResultDialog(f"计算结果 — {mode}", self)
            dlg.set_result(result)
            dlg.exec()

        except Exception as e:
            dlg = ResultDialog("错误", self)
            dlg.set_result(MathObject(error=str(e)[:80]))
            dlg.exec()

    def on_calc_mode_changed(self, index: int):
        self._last_result = None

    def on_delete_btn_clicked(self):
        self.on_delete(self)


if __name__ == "__main__":
    import sys as _sys
    app = QApplication(_sys.argv)
    def dummy_delete(block):
        print(f"删除 block {block if isinstance(block, int) else block.block_id}")
    block = CalcBlock(0, dummy_delete)
    block.show()
    _sys.exit(app.exec())