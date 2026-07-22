# -*- coding: utf-8 -*-
"""MF-Mathematics 用户手册 Word 文档生成器（含截图）。"""
import os
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(PROJECT, "dist", "copyright", "screenshots")
OUTPUT = os.path.join(PROJECT, "dist", "copyright", "MF-Mathematics_用户手册_V1.0.0.docx")

# 截图映射
IMG = lambda name: os.path.join(IMG_DIR, name)

# ═══════════════════════════════════════════════════════════════════════
#  辅助函数
# ═══════════════════════════════════════════════════════════════════════

def add_img(doc, filename, width_inches=5.5):
    """插入截图，不存在则用占位文字。"""
    path = IMG(filename)
    if os.path.exists(path):
        doc.add_picture(path, width=Inches(width_inches))
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(f"图：{filename.replace('.png','').replace('_',' ')}")
        r.font.size = Pt(9)
        r.italic = True
        r.font.color.rgb = RGBColor(0x78, 0x71, 0x6C)
    else:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(f"[ 截图占位：{filename} ]")
        r.font.size = Pt(10)
        r.font.color.rgb = RGBColor(0xA8, 0xA2, 0x9E)
    doc.add_paragraph()


def set_cell_shading(cell, color):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), color)
    shading.set(qn("w:val"), "clear")
    tcPr.append(shading)


def add_table(doc, headers, rows):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Light Grid Accent 1"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        cell = table.cell(0, i)
        cell.text = h
        for p in cell.paragraphs:
            for r in p.runs:
                r.bold = True
                r.font.size = Pt(10)
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            cell = table.cell(ri + 1, ci)
            cell.text = str(val)
            for p in cell.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(10)
    doc.add_paragraph()


def tip(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.5)
    r = p.add_run("提示：")
    r.bold = True; r.font.size = Pt(10); r.font.color.rgb = RGBColor(0x3B, 0x82, 0xF6)
    r2 = p.add_run(text); r2.font.size = Pt(10)


def warn(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.5)
    r = p.add_run("注意：")
    r.bold = True; r.font.size = Pt(10); r.font.color.rgb = RGBColor(0xF5, 0x9E, 0x0B)
    r2 = p.add_run(text); r2.font.size = Pt(10)


# ═══════════════════════════════════════════════════════════════════════
def build():
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Cm(21); sec.page_height = Cm(29.7)
    sec.left_margin = Cm(2.0); sec.right_margin = Cm(2.0)
    sec.top_margin = Cm(2.0); sec.bottom_margin = Cm(2.0)

    style = doc.styles["Normal"]
    style.font.name = "Microsoft YaHei"
    style.font.size = Pt(10.5)
    style.paragraph_format.line_spacing = 1.5
    rPr = style.element.get_or_add_rPr()
    rFonts = OxmlElement("w:rFonts")
    rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    rPr.insert(0, rFonts)

    # ── 封面 ──
    for _ in range(6): doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("MF-Mathematics"); r.font.size = Pt(36); r.bold = True
    p2 = doc.add_paragraph(); p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = p2.add_run("多功能数学计算与可视化平台")
    r2.font.size = Pt(16); r2.font.color.rgb = RGBColor(0x78, 0x71, 0x6C)
    p3 = doc.add_paragraph(); p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r3 = p3.add_run("用户手册 · V1.0.0 · 2026 年 7 月")
    r3.font.size = Pt(12); r3.font.color.rgb = RGBColor(0xA8, 0xA2, 0x9E)
    p4 = doc.add_paragraph(); p4.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r4 = p4.add_run("MF-Vis-Science 工作室")
    r4.font.size = Pt(11); r4.font.color.rgb = RGBColor(0x78, 0x71, 0x6C)
    doc.add_page_break()

    # ── 目录 ──
    doc.add_heading("目  录", level=1)
    for item in [
        "第 1 章 · 软件概述", "第 2 章 · 安装与启动",
        "第 3 章 · 主界面概览", "第 4 章 · 计算功能（14 个模块）",
        "第 5 章 · 绘图功能（7 个模式）", "第 6 章 · 用户账户系统",
        "第 7 章 · AI 智能助手", "第 8 章 · 键盘面板",
        "第 9 章 · 设置与主题", "第 10 章 · 常见问题",
    ]:
        p = doc.add_paragraph(item)
        p.paragraph_format.left_indent = Cm(1)
        p.runs[0].font.size = Pt(11)
    doc.add_page_break()

    # ═══════════════════════════════════════════════════════════
    #  第 1 章 · 软件概述
    # ═══════════════════════════════════════════════════════════
    doc.add_heading("第 1 章 · 软件概述", level=1)
    doc.add_heading("1.1 产品简介", level=2)
    doc.add_paragraph(
        "MF-Mathematics 是一款面向数学学习、科研与工程计算的桌面端多功能数学平台。"
        "软件集成符号计算、数值分析、函数绘图、分形探索、AI 辅助等核心能力，"
        "覆盖从初等数学到高等数学的广泛领域。"
    )
    doc.add_heading("1.2 核心功能", level=2)
    add_table(doc,
        ["类别", "内容", "数量"],
        [["计算模块", "基础运算、代数、微积分、解析几何、数列、线代、概率统计、数值分析、数论、实分析、泛函分析、复分析、代数拓扑、测度论", "14"],
         ["绘图模块", "普通 2D、极坐标、3D 曲面、复数映射、向量场、任意做图、分形探索", "7"],
         ["AI 助手", "自然语言输入数学问题，逐步推理与解答", "—"],
         ["用户系统", "在线注册、登录、邮箱验证、余额管理", "—"],
         ["主题", "亮色 + 暗色双主题", "2"]]
    )
    doc.add_heading("1.3 系统要求", level=2)
    add_table(doc,
        ["项目", "要求"],
        [["操作系统", "Windows 10 / 11（64 位）"],
         ["内存", "建议 4 GB 及以上"],
         ["硬盘空间", "约 300 MB"],
         ["网络", "登录/注册/AI 功能需要互联网连接"]]
    )

    # ═══════════════════════════════════════════════════════════
    #  第 2 章 · 安装与启动
    # ═══════════════════════════════════════════════════════════
    doc.add_heading("第 2 章 · 安装与启动", level=1)
    doc.add_heading("2.1 获取安装包", level=2)
    doc.add_paragraph("访问 MF-Mathematics 官方网站下载最新安装包：")
    doc.add_paragraph("https://www.mvs-studio.com/download")
    doc.add_heading("2.2 安装步骤", level=2)
    for i, step in enumerate([
        "双击 Multifunctional-Mathematics-Setup.exe",
        "选择安装语言（简体中文 / English）",
        "阅读并接受许可协议",
        "选择安装目录（默认 C:\\Program Files\\MF-Mathematics）",
        "勾选\"创建桌面快捷方式\"",
        "点击\"安装\"，等待完成",
    ], 1):
        doc.add_paragraph(f"{i}. {step}")
    doc.add_heading("2.3 启动与更新", level=2)
    doc.add_paragraph("双击桌面快捷方式或从开始菜单启动。软件启动时会自动检测新版本。")

    # ═══════════════════════════════════════════════════════════
    #  第 3 章 · 主界面概览
    # ═══════════════════════════════════════════════════════════
    doc.add_heading("第 3 章 · 主界面概览", level=1)
    add_img(doc, "01_main_light.png", 5.5)
    doc.add_heading("3.1 界面布局", level=2)
    add_table(doc,
        ["编号", "区域", "说明"],
        [["①", "菜单栏", "文件、编辑、视图、工具、帮助"],
         ["②", "工具栏", "计算/绘图切换、子导航下拉框、搜索/历史/AI/登录"],
         ["③", "子导航栏", "当前模式下的二级标签页"],
         ["④", "工作区", "计算块 / 绘图画布"],
         ["⑤", "键盘面板", "虚拟数学键盘（可折叠）"],
         ["⑥", "状态栏", "就绪信息、当前用户"]]
    )
    doc.add_heading("3.2 菜单栏", level=2)
    add_table(doc,
        ["菜单", "功能项"],
        [["文件", "新建计算、保存工作区、导出图片、退出"],
         ["编辑", "撤销、重做、复制、粘贴、清空工作区"],
         ["视图", "切换亮色/暗色主题、显示/隐藏键盘面板"],
         ["工具", "AI 助手、搜索面板、计算历史"],
         ["帮助", "用户手册、交互式引导、示例任务库、关于"]]
    )

    # ═══════════════════════════════════════════════════════════
    #  第 4 章 · 计算功能
    # ═══════════════════════════════════════════════════════════
    doc.add_heading("第 4 章 · 计算功能", level=1)
    doc.add_paragraph(
        "软件提供 14 个计算模块。每个模块采用统一的 CalcBlock（计算块）交互模式："
        "输入数学表达式 → 点击计算 → 查看分步结果。"
    )
    for title, desc in [
        ("4.1 基础运算", "四则运算、乘方、开方、阶乘、对数等基本数学运算。"),
        ("4.2 代数计算", "多项式展开、因式分解、方程求解、不等式求解、表达式化简。"),
        ("4.3 微积分", "求导、不定积分、定积分、极限计算、级数展开。符号推导与数值双模式。"),
        ("4.4 解析几何", "直线、圆、椭圆、双曲线、抛物线的方程分析与几何性质。"),
        ("4.5 数列", "等差/等比/递推数列的通项与求和，收敛性判断。"),
        ("4.6 线性代数", "矩阵运算、行列式、特征值、线性方程组、二次型标准化。"),
        ("4.7 概率论与数理统计", "概率分布、期望方差、假设检验、ANOVA、回归分析、时间序列。"),
        ("4.8 数值分析", "数值积分、ODE 求解、插值拟合、非线性求根、误差分析。"),
        ("4.9 数论", "素数筛法、GCD/LCM、模运算、同余方程、算术函数。"),
        ("4.10 实分析", "实数完备性、序列极限、函数极限、可微性判定、黎曼积分。"),
        ("4.11 泛函分析", "赋范空间、内积空间、线性算子、对偶空间、谱理论。"),
        ("4.12 复分析", "全纯函数、柯西-黎曼方程、复积分、留数定理、共形映射。"),
        ("4.13 代数拓扑", "同伦群、同调群、上同调环、度理论与不动点。"),
        ("4.14 测度论", "σ-代数、测度构造、勒贝格积分、收敛定理、乘积测度。"),
    ]:
        doc.add_heading(title, level=2)
        doc.add_paragraph(desc)
    tip(doc, "每个计算模块支持多块管理——点击\"添加计算块\"可并行进行多个独立计算。")

    # ═══════════════════════════════════════════════════════════
    #  第 5 章 · 绘图功能
    # ═══════════════════════════════════════════════════════════
    doc.add_heading("第 5 章 · 绘图功能", level=1)
    doc.add_paragraph("软件提供 7 个绘图模式，支持交互式缩放、平移、导出。")
    add_img(doc, "05_plot_2d.png", 5.5)
    for title, desc in [
        ("5.1 普通 2D 绘图", "绘制一元函数曲线。支持多函数叠加、颜色自定义、坐标轴范围调整。"),
        ("5.2 极坐标绘图", "极坐标曲线 r=f(θ)。玫瑰线、心形线、螺线等。"),
        ("5.3 3D 曲面绘图", "二元函数曲面 z=f(x,y)。旋转视角（鼠标拖拽）、配色方案切换。"),
        ("5.4 复数映射可视化", "复变函数 w=f(z) 作用于网格，直观展示复平面映射。"),
        ("5.5 向量场", "二维向量场 F(x,y)=(P,Q)。支持流线、箭头密度调节。"),
        ("5.6 任意做图", "自由几何构造：点、线段、圆、多边形。支持撤销/重做。"),
        ("5.7 分形探索", "Mandelbrot 集、Julia 集、Newton 分形。无限缩放、色彩映射。"),
    ]:
        doc.add_heading(title, level=2)
        doc.add_paragraph(desc)

    # ═══════════════════════════════════════════════════════════
    #  第 6 章 · 用户账户系统
    # ═══════════════════════════════════════════════════════════
    doc.add_heading("第 6 章 · 用户账户系统", level=1)
    doc.add_heading("6.1 登录", level=2)
    doc.add_paragraph("点击工具栏\"登录\"按钮，输入用户名和密码，点击\"登录\"。")
    add_img(doc, "02_login.png", 3.0)
    doc.add_heading("6.2 注册", level=2)
    for i, step in enumerate([
        "切换到\"注册\"标签页",
        "输入用户名（3-20 字符，字母/数字/下划线）",
        "输入邮箱 → 点击\"发送验证码\"",
        "查收邮件，输入 6 位验证码",
        "设置密码（至少 8 位，含字母和数字）→ 点击\"注册\"",
    ], 1):
        doc.add_paragraph(f"{i}. {step}")
    add_img(doc, "03_register.png", 3.2)
    warn(doc, "验证码 5 分钟有效，60 秒内不可重复发送。注册成功自动登录并赠送 10 次免费额度。")
    doc.add_heading("6.3 邮箱验证", level=2)
    doc.add_paragraph("未提供验证码时系统发送验证邮件，在验证页面输入验证码完成激活。")
    doc.add_heading("6.4 登录后状态", level=2)
    doc.add_paragraph("工具栏显示\"用户名 (余额: N)\"，状态栏同步更新。点击可登出。")

    # ═══════════════════════════════════════════════════════════
    #  第 7 章
    # ═══════════════════════════════════════════════════════════
    doc.add_heading("第 7 章 · AI 智能助手", level=1)
    doc.add_paragraph("AI 助手支持自然语言输入数学问题，由 DeepSeek / OpenAI 大模型驱动。")
    doc.add_heading("7.1 打开 AI 助手", level=2)
    doc.add_paragraph("工具栏点击\"AI\"按钮，或菜单 → 工具 → AI 助手。")
    doc.add_heading("7.2 使用方式", level=2)
    for i, s in enumerate(["输入数学问题", "点击发送或 Enter", "AI 返回分步推理"], 1):
        doc.add_paragraph(f"{i}. {s}")
    doc.add_heading("7.3 配置 API Key", level=2)
    for i, s in enumerate(["菜单 → 工具 → AI 设置", "选择服务商", "填入 API Key", "保存"], 1):
        doc.add_paragraph(f"{i}. {s}")
    tip(doc, "AI 助手自动读取当前工作区计算内容作为上下文。")

    # ═══════════════════════════════════════════════════════════
    #  第 8 章
    # ═══════════════════════════════════════════════════════════
    doc.add_heading("第 8 章 · 键盘面板", level=1)
    doc.add_paragraph("内置虚拟数学键盘，提供常用符号和函数快速输入。")
    doc.add_heading("8.1 面板布局", level=2)
    add_table(doc,
        ["区域", "内容"],
        [["数字区", "0-9、小数点、正负号"],
         ["运算符", "+ - × ÷ ^ √ ="],
         ["函数区", "sin cos tan log ln exp abs"],
         ["符号区", "π e i ∞ ( ) ,"],
         ["微积分", "d/dx ∫ lim Σ"],
         ["希腊字母", "α β γ θ λ μ σ φ ω"]]
    )
    doc.add_heading("8.2 显示/隐藏", level=2)
    doc.add_paragraph("菜单 → 视图 → 键盘面板，或点击工作区底部折叠按钮。")

    # ═══════════════════════════════════════════════════════════
    #  第 9 章
    # ═══════════════════════════════════════════════════════════
    doc.add_heading("第 9 章 · 设置与主题", level=1)
    doc.add_heading("9.1 主题切换", level=2)
    doc.add_paragraph("内置两套完整主题，菜单 → 视图 → 切换，或快捷键 Ctrl+T。")
    add_table(doc,
        ["主题", "风格", "适用"],
        [["亮色（Slate）", "白底深色文字，蓝调强调", "日间"],
         ["暗色（Catppuccin Mocha）", "深紫黑底浅色文字", "夜间/护眼"]]
    )
    add_img(doc, "04_main_dark.png", 5.5)
    doc.add_heading("9.2 设置对话框", level=2)
    doc.add_paragraph("菜单 → 工具 → 设置，可配置：默认绘图范围、数值精度、AI 服务商与模型。")

    # ═══════════════════════════════════════════════════════════
    #  第 10 章
    # ═══════════════════════════════════════════════════════════
    doc.add_heading("第 10 章 · 常见问题", level=1)
    for q, a in [
        ("Q1：启动时提示\"无法连接到服务器\"？", "登录和 AI 功能需要网络。本地计算和绘图可离线使用。"),
        ("Q2：忘记密码怎么办？", "请通过注册邮箱联系管理员重置。后续版本将增加找回功能。"),
        ("Q3：计算结果显示\"计算超时\"？", "复杂表达式可能超出时间限制。尝试简化表达式或分步计算。"),
        ("Q4：3D 图形无法旋转？", "按住鼠标左键拖拽旋转视角，滚轮缩放。"),
        ("Q5：如何导出计算结果？", "菜单 → 文件 → 导出，支持图片或 LaTeX 格式。"),
        ("Q6：验证码未收到？", "检查垃圾邮件箱。60 秒后可重新发送。"),
        ("Q7：如何切换语言？", "当前版本为简体中文，多语言支持将在后续版本添加。"),
    ]:
        doc.add_heading(q, level=3)
        doc.add_paragraph(a)

    # ── 尾页 ──
    doc.add_paragraph(); doc.add_paragraph()
    for text in [
        "MF-Mathematics V1.0.0 用户手册",
        "MF-Vis-Science 工作室  (C) 2026",
        "https://www.mvs-studio.com",
    ]:
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(text); r.font.size = Pt(10)
        r.font.color.rgb = RGBColor(0xA8, 0xA2, 0x9E)

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    doc.save(OUTPUT)


if __name__ == "__main__":
    build()
    print(f"用户手册: {OUTPUT}")
    print(f"大小: {os.path.getsize(OUTPUT)/1024:.0f} KB")
