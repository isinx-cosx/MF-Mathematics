# -*- coding: utf-8 -*-
"""数值分析计算块 — 继承 BaseCalcBlock，仅定义模式列表和分派映射。"""

from __future__ import annotations

import MF_Mathematics.numerical  # noqa: 注册后端函数
from MF_UI.calc.base_calc_block import BaseCalcBlock


class CalcBlock(BaseCalcBlock):
    """数值分析计算块。"""

    def get_mode_list(self) -> list[str]:
        return [
            "条件数", "截断误差", "舍入误差", "稳定性判断",
            "拉格朗日插值", "牛顿插值", "三次样条", "最小二乘拟合",
            "梯形法则", "辛普森法则", "高斯求积", "数值求导", "最优步长",
            "LU分解", "雅可比迭代", "高斯-赛德尔", "共轭梯度", "幂法", "QR算法",
            "欧拉方法", "RK4", "隐式欧拉", "刚性检测",
        ]

    def get_action_map(self) -> dict[str, tuple[str, str]]:
        return {
            "条件数":         ("numerical", "condition_number"),
            "截断误差":       ("numerical", "truncation_error"),
            "舍入误差":       ("numerical", "rounding_error_estimate"),
            "稳定性判断":     ("numerical", "is_stable"),
            "拉格朗日插值":   ("numerical", "lagrange_interpolation"),
            "牛顿插值":       ("numerical", "newton_interpolation"),
            "三次样条":       ("numerical", "cubic_spline"),
            "最小二乘拟合":   ("numerical", "least_squares_fit"),
            "梯形法则":       ("numerical", "trapezoidal_rule"),
            "辛普森法则":     ("numerical", "simpson_rule"),
            "高斯求积":       ("numerical", "gauss_quadrature"),
            "数值求导":       ("numerical", "numerical_derivative"),
            "最优步长":       ("numerical", "optimal_step"),
            "LU分解":         ("numerical", "lu_decomposition"),
            "雅可比迭代":     ("numerical", "jacobi_iteration"),
            "高斯-赛德尔":    ("numerical", "gauss_seidel"),
            "共轭梯度":       ("numerical", "conjugate_gradient"),
            "幂法":           ("numerical", "power_method"),
            "QR算法":         ("numerical", "qr_algorithm"),
            "欧拉方法":       ("numerical", "euler_method"),
            "RK4":            ("numerical", "rk4"),
            "隐式欧拉":       ("numerical", "implicit_euler"),
            "刚性检测":       ("numerical", "stiff_detector"),
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
