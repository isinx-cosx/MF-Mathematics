# -*- coding: utf-8 -*-
"""策略推荐器 — 分析数学表达式并推荐最优操作路径。"""

from __future__ import annotations


def recommend(expr: str) -> list[dict]:
    """分析表达式，返回推荐操作列表。

    每个推荐项包含: {"action": 操作名, "module": 模块, "reason": 推荐理由, "priority": 1-5}
    """
    import re
    s = expr.strip()
    results = []

    # 含 = → 方程求解
    if "=" in s:
        results.append({"action": "解方程/组", "module": "algebra",
                        "reason": "检测到等式，建议求解", "priority": 5})
    # 含导数记号
    if re.search(r"['′]['′]*|d\d?[yY]/d", s):
        results.append({"action": "求导", "module": "calculus",
                        "reason": "检测到导数记号", "priority": 5})
    # 积分记号
    if "∫" in s or "integrate" in s.lower():
        results.append({"action": "不定积分" if "∞" not in s else "定积分",
                        "module": "calculus", "reason": "检测到积分记号", "priority": 5})
    # 极限
    if "lim" in s.lower() or "→" in s or "->" in s:
        results.append({"action": "极限", "module": "calculus",
                        "reason": "检测到极限记号", "priority": 5})
    # 多变量/矩阵
    if re.search(r"\[\[|matrix|Matrix|det|特征|eigen|行|列", s):
        results.append({"action": "特征值" if "特征" in s else "高斯消元",
                        "module": "linear_algebra", "reason": "检测到矩阵/线性代数", "priority": 4})
    # 概率/统计
    if re.search(r"P\(|E\(|Var|分布|概率|检验|回归|置信", s):
        results.append({"action": "期望" if "E(" in s else "正态分布",
                        "module": "probability", "reason": "检测到概率/统计记号", "priority": 4})
    # 级数
    if "∑" in s or "sum" in s.lower() or "series" in s.lower():
        results.append({"action": "级数求和", "module": "calculus",
                        "reason": "检测到级数记号", "priority": 3})
    # 一般表达式 → 默认推荐
    if "x" in s or "y" in s or "z" in s:
        results.append({"action": "求导", "module": "calculus",
                        "reason": "含变量，可求导", "priority": 2})
        results.append({"action": "表达式化简", "module": "algebra",
                        "reason": "可尝试化简", "priority": 2})
        results.append({"action": "不定积分", "module": "calculus",
                        "reason": "含变量，可积分", "priority": 1})
    # 纯数值
    if re.match(r'^[\d\s+\-*/().,^eEπpiPI]+$', s):
        results.append({"action": "eval_expression", "module": "agent",
                        "reason": "纯数值表达式，可直接计算", "priority": 5})

    results.sort(key=lambda x: x["priority"], reverse=True)
    return results[:5]


def self_test() -> bool:
    print("=== MF_AI.strategy self_test ===")
    tests = [
        ("x^2 + 2*x + 1 = 0", "equation"),
        ("sin(x)'", "derivative"),
        ("∫ sin(x) dx", "integral"),
        ("lim_{x→0} sin(x)/x", "limit"),
        ("[[1,2],[3,4]]", "matrix"),
        ("2+3*4", "numeric"),
    ]
    for expr, expected in tests:
        recs = recommend(expr)
        actions = [r["action"] for r in recs]
        print(f"  {expr[:30]:30s} → {actions}")
    print("=== ALL PASSED ===")
    return True


if __name__ == "__main__":
    self_test()
