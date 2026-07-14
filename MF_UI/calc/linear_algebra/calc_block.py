# -*- coding: utf-8 -*-
"""线性代数计算块 — 继承 BaseCalcBlock，仅定义模式列表和分派映射。"""

from __future__ import annotations

import MF_Mathematics.linear_algebra  # noqa: 注册后端函数
from MF_UI.calc.base_calc_block import BaseCalcBlock


class CalcBlock(BaseCalcBlock):
    """线性代数计算块。"""

    def get_mode_list(self) -> list[str]:
        return [
            "高斯消元", "矩阵秩", "求解方程组", "零空间",
            "特征值", "特征向量", "特征多项式", "可对角化", "对角化",
            "点积", "范数", "夹角", "正交性",
            "施密特正交化", "正交投影", "二次型", "正定性判定",
        ]

    def get_action_map(self) -> dict[str, tuple[str, str]]:
        return {
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


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    def dummy_delete(block):
        print(f"删除 block {block.block_id}")
    block = CalcBlock(0, dummy_delete)
    block.show()
    sys.exit(app.exec())
