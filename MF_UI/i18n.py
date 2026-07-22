# -*- coding: utf-8 -*-
"""国际化模块 — 中文/English 双语言支持。"""
from __future__ import annotations

TRANSLATIONS: dict[str, dict[str, str]] = {
    "zh": {
        # 菜单
        "menu.file": "文件",
        "menu.edit": "编辑",
        "menu.view": "视图",
        "menu.tools": "工具",
        "menu.help": "帮助",
        "menu.new": "新建计算",
        "menu.save": "保存工作区",
        "menu.export": "导出图片",
        "menu.exit": "退出",
        "menu.undo": "撤销",
        "menu.redo": "重做",
        "menu.copy": "复制",
        "menu.paste": "粘贴",
        "menu.clear": "清空历史",
        "menu.theme_light": "亮色主题",
        "menu.theme_dark": "暗色主题",
        "menu.keyboard": "键盘面板",
        "menu.ai": "AI 助手",
        "menu.search": "搜索面板",
        "menu.history": "计算历史",
        "menu.settings": "设置",
        "menu.guide": "交互式引导",
        "menu.examples": "示例任务库",
        "menu.about": "关于",
        "menu.help_doc": "帮助文档",
        # 工具栏
        "tb.calc": "计算",
        "tb.plot": "绘图",
        "tb.search": "搜索",
        "tb.history": "历史",
        "tb.ai": "AI",
        "tb.login": "登录",
        "tb.help": "帮助",
        "tb.settings": "设置",
        # 计算模式
        "calc.basic": "基础运算",
        "calc.algebra": "代数计算",
        "calc.calculus": "微积分",
        "calc.geometry": "解析几何",
        "calc.sequences": "数列",
        "calc.linear_algebra": "线性代数",
        "calc.probability": "概率论与数理统计",
        "calc.numerical": "数值分析",
        "calc.number_theory": "数论",
        "calc.real_analysis": "实分析",
        "calc.functional": "泛函分析",
        "calc.complex": "复分析",
        "calc.topology": "代数拓扑",
        "calc.measure": "测度论",
        # 绘图模式
        "plot.normal": "普通模式",
        "plot.polar": "极坐标",
        "plot.3d": "3D 模式",
        "plot.complex": "复数模式",
        "plot.vector": "向量场",
        "plot.arbitrary": "任意做图",
        "plot.fractal": "分形探索",
        # 状态栏
        "status.ready": "就绪",
        "status.not_logged_in": "未登录",
        "status.current_user": "当前用户",
        # 通用
        "lang.name": "简体中文",
        "lang.code": "zh",
    },
    "en": {
        # Menu
        "menu.file": "File",
        "menu.edit": "Edit",
        "menu.view": "View",
        "menu.tools": "Tools",
        "menu.help": "Help",
        "menu.new": "New Calculation",
        "menu.save": "Save Workspace",
        "menu.export": "Export Image",
        "menu.exit": "Exit",
        "menu.undo": "Undo",
        "menu.redo": "Redo",
        "menu.copy": "Copy",
        "menu.paste": "Paste",
        "menu.clear": "Clear History",
        "menu.theme_light": "Light Theme",
        "menu.theme_dark": "Dark Theme",
        "menu.keyboard": "Keyboard Panel",
        "menu.ai": "AI Assistant",
        "menu.search": "Search Panel",
        "menu.history": "History",
        "menu.settings": "Settings",
        "menu.guide": "Interactive Guide",
        "menu.examples": "Example Library",
        "menu.about": "About",
        "menu.help_doc": "Help Documentation",
        # Toolbar
        "tb.calc": "Calc",
        "tb.plot": "Plot",
        "tb.search": "Search",
        "tb.history": "History",
        "tb.ai": "AI",
        "tb.login": "Login",
        "tb.help": "Help",
        "tb.settings": "Settings",
        # Calc modes
        "calc.basic": "Basic",
        "calc.algebra": "Algebra",
        "calc.calculus": "Calculus",
        "calc.geometry": "Analytic Geometry",
        "calc.sequences": "Sequences",
        "calc.linear_algebra": "Linear Algebra",
        "calc.probability": "Probability & Statistics",
        "calc.numerical": "Numerical Analysis",
        "calc.number_theory": "Number Theory",
        "calc.real_analysis": "Real Analysis",
        "calc.functional": "Functional Analysis",
        "calc.complex": "Complex Analysis",
        "calc.topology": "Algebraic Topology",
        "calc.measure": "Measure Theory",
        # Plot modes
        "plot.normal": "2D Plot",
        "plot.polar": "Polar",
        "plot.3d": "3D Surface",
        "plot.complex": "Complex Map",
        "plot.vector": "Vector Field",
        "plot.arbitrary": "Free Draw",
        "plot.fractal": "Fractal",
        # Status bar
        "status.ready": "Ready",
        "status.not_logged_in": "Not logged in",
        "status.current_user": "Current user",
        # General
        "lang.name": "English",
        "lang.code": "en",
    },
}

_current_lang = "zh"


def set_language(code: str) -> None:
    """切换语言（'zh' 或 'en'）。"""
    global _current_lang
    if code in TRANSLATIONS:
        _current_lang = code


def get_language() -> str:
    """返回当前语言代码。"""
    return _current_lang


def tr(key: str) -> str:
    """翻译指定键，找不到则返回键本身。"""
    return TRANSLATIONS.get(_current_lang, {}).get(key, key)


def get_calc_modes() -> list[str]:
    """返回当前语言的 14 个计算模式名称列表。"""
    keys = [
        "calc.basic", "calc.algebra", "calc.calculus", "calc.geometry",
        "calc.sequences", "calc.linear_algebra", "calc.probability",
        "calc.numerical", "calc.number_theory", "calc.real_analysis",
        "calc.functional", "calc.complex", "calc.topology", "calc.measure",
    ]
    return [tr(k) for k in keys]


def get_plot_modes() -> list[str]:
    """返回当前语言的 7 个绘图模式名称列表。"""
    keys = [
        "plot.normal", "plot.polar", "plot.3d", "plot.complex",
        "plot.vector", "plot.arbitrary", "plot.fractal",
    ]
    return [tr(k) for k in keys]
