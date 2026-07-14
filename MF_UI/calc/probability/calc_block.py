# ————————————MF-Mathematics 概率统计计算块———————————

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
import MF_Mathematics.probability
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
            "条件概率", "独立性", "全概率公式", "贝叶斯公式",
            "伯努利分布", "二项分布", "泊松分布",
            "均匀分布", "指数分布", "正态分布",
            "期望", "方差", "协方差", "相关系数",
            "大数定律", "中心极限定理",
            "样本均值", "样本方差", "矩估计", "MLE",
            "置信区间", "z检验", "t检验", "卡方检验", "p值",
            "线性回归", "预测", "残差",
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
            "条件概率":        ("probability", "conditional_probability"),
            "独立性":          ("probability", "is_independent"),
            "全概率公式":       ("probability", "total_probability"),
            "贝叶斯公式":       ("probability", "bayes_theorem"),
            "伯努利分布":       ("probability", "bernoulli"),
            "二项分布":         ("probability", "binomial"),
            "泊松分布":         ("probability", "poisson"),
            "均匀分布":         ("probability", "uniform"),
            "指数分布":         ("probability", "exponential"),
            "正态分布":         ("probability", "normal"),
            "期望":             ("probability", "expectation"),
            "方差":             ("probability", "variance"),
            "协方差":           ("probability", "covariance"),
            "相关系数":         ("probability", "correlation_coefficient"),
            "大数定律":         ("probability", "law_of_large_numbers"),
            "中心极限定理":     ("probability", "central_limit_theorem"),
            "样本均值":         ("probability", "sample_mean"),
            "样本方差":         ("probability", "sample_variance"),
            "矩估计":           ("probability", "moment_estimate"),
            "MLE":              ("probability", "mle"),
            "置信区间":         ("probability", "confidence_interval"),
            "z检验":            ("probability", "z_test"),
            "t检验":            ("probability", "t_test"),
            "卡方检验":         ("probability", "chi_square_test"),
            "p值":              ("probability", "p_value"),
            "线性回归":         ("probability", "linear_regression"),
            "预测":             ("probability", "predict"),
            "残差":             ("probability", "residuals"),
        }

        try:
            mod, act = action_map[mode]

            if "=" in expr and expr.count("=") <= 3:
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