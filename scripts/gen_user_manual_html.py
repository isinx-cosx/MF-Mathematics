# -*- coding: utf-8 -*-
"""生成带截图的 HTML 用户手册，用于 Edge 无头打印 PDF。"""
import os

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(PROJECT, "dist", "copyright", "screenshots")
OUT = os.path.join(PROJECT, "dist", "copyright", "user_manual.html")


def img(fname):
    path = os.path.join(IMG_DIR, fname)
    if os.path.exists(path):
        return (
            f'<img src="{path}" alt="{fname}" style="max-width:100%;margin:10px 0;'
            f'border:1px solid #e2e0dd;border-radius:4px">'
            f'<p style="text-align:center;color:#78716c;font-size:10px">'
            f'图：{fname.replace(".png","").replace("_"," ")}</p>'
        )
    return (
        '<p style="text-align:center;color:#a8a29e;border:1px dashed #d6d3d1;'
        f'padding:30px;border-radius:4px">[ 截图占位：{fname} ]</p>'
    )


CSS = """body{font-family:"Microsoft YaHei",sans-serif;max-width:780px;margin:0 auto;
padding:20px 30px;color:#1c1917;line-height:1.7}
h1{font-size:22px;border-bottom:2px solid #e2e0dd;padding-bottom:6px;margin:36px 0 14px;
page-break-before:always}h1:first-of-type{page-break-before:avoid}
h2{font-size:17px;margin:24px 0 10px}h3{font-size:14px;margin:18px 0 8px}
p,li{font-size:12px;margin:6px 0}
table{width:100%;border-collapse:collapse;margin:12px 0;font-size:12px}
th,td{border:1px solid #d6d3d1;padding:6px 10px;text-align:left}
th{background:#f5f5f4;font-weight:600}
.tip{background:#eff6ff;border-left:4px solid #3b82f6;padding:8px 14px;margin:12px 0;font-size:12px}
.warn{background:#fffbeb;border-left:4px solid #f59e0b;padding:8px 14px;margin:12px 0;font-size:12px}
.cover{text-align:center;padding:80px 0 50px}
.cover h1{font-size:32px;border:none}.cover p{font-size:14px;color:#78716c}
.toc a{color:#3b82f6;text-decoration:none}.toc li{margin:4px 0}
@media print{body{padding:0}h1{page-break-before:always}h1:first-of-type{page-break-before:avoid}}"""


def build():
    h = []
    w = h.append

    w(f"<!DOCTYPE html><html lang='zh-CN'><head><meta charset='UTF-8'>")
    w(f"<title>MF-Mathematics V1.0.0 用户手册</title>")
    w(f"<style>{CSS}</style></head><body>")

    # 封面
    w('<div class="cover"><h1>MF-Mathematics</h1>')
    w('<p>多功能数学计算与可视化平台</p>')
    w('<p>用户手册 · V1.0.0 · 2026年7月</p>')
    w('<p>MF-Vis-Science 工作室</p></div>')

    # 目录
    w('<div class="toc"><h1>目  录</h1><ol>')
    for ch in ["软件概述", "安装与启动", "主界面概览", "计算功能",
               "绘图功能", "用户账户系统", "AI智能助手", "键盘面板",
               "设置与主题", "常见问题"]:
        w(f'<li><a href="#ch{ch[0]}">{ch}</a></li>')
    w('</ol></div>')

    # 第1章
    w('<h1 id="ch软">第1章 · 软件概述</h1>')
    w('<h2>1.1 产品简介</h2>')
    w('<p>MF-Mathematics 是一款面向数学学习、科研与工程计算的桌面端多功能数学平台。'
      '集成符号计算、数值分析、函数绘图、分形探索、AI辅助等核心能力，覆盖从初等到高等数学。</p>')
    w('<h2>1.2 核心功能</h2>')
    w('<table><tr><th>类别</th><th>内容</th><th>数量</th></tr>'
      '<tr><td>计算模块</td><td>基础运算/代数/微积分/解析几何/数列/线代/概率统计/数值分析/数论/实分析/泛函分析/复分析/代数拓扑/测度论</td><td>14</td></tr>'
      '<tr><td>绘图模块</td><td>普通2D/极坐标/3D曲面/复数映射/向量场/任意做图/分形探索</td><td>7</td></tr>'
      '<tr><td>AI助手</td><td>自然语言输入，逐步推理与解答</td><td>—</td></tr>'
      '<tr><td>用户系统</td><td>在线注册/登录/邮箱验证/余额管理</td><td>—</td></tr>'
      '<tr><td>主题</td><td>亮色+暗色双主题</td><td>2</td></tr></table>')
    w('<h2>1.3 系统要求</h2>')
    w('<table><tr><th>项目</th><th>要求</th></tr>'
      '<tr><td>操作系统</td><td>Windows 10/11（64位）</td></tr>'
      '<tr><td>内存</td><td>建议4GB及以上</td></tr>'
      '<tr><td>硬盘</td><td>约300MB</td></tr>'
      '<tr><td>网络</td><td>登录/注册/AI需要互联网</td></tr></table>')

    # 第2章
    w('<h1 id="ch安">第2章 · 安装与启动</h1>')
    w('<h2>2.1 获取安装包</h2>')
    w('<p>官网下载：<code>https://www.mvs-studio.com/download</code></p>')
    w('<h2>2.2 安装步骤</h2><ol>'
      '<li>双击 Multifunctional-Mathematics-Setup.exe</li>'
      '<li>选择语言（简体中文 / English）</li>'
      '<li>阅读并接受许可协议</li>'
      '<li>选择安装目录</li>'
      '<li>勾选"创建桌面快捷方式"</li>'
      '<li>点击"安装"</li></ol>')
    w('<h2>2.3 启动</h2><p>双击桌面快捷方式。启动时自动检测新版本。</p>')

    # 第3章
    w('<h1 id="ch主">第3章 · 主界面概览</h1>')
    w(img("01_main_light.png"))
    w('<h2>3.1 界面布局</h2>')
    w('<table><tr><th>编号</th><th>区域</th><th>说明</th></tr>'
      '<tr><td>①</td><td>菜单栏</td><td>文件/编辑/视图/工具/帮助</td></tr>'
      '<tr><td>②</td><td>工具栏</td><td>计算绘图切换/子导航/搜索/历史/AI/登录</td></tr>'
      '<tr><td>③</td><td>子导航栏</td><td>当前模式的二级标签页</td></tr>'
      '<tr><td>④</td><td>工作区</td><td>计算块/绘图画布</td></tr>'
      '<tr><td>⑤</td><td>键盘面板</td><td>虚拟数学键盘</td></tr>'
      '<tr><td>⑥</td><td>状态栏</td><td>就绪信息/当前用户</td></tr></table>')
    w('<h2>3.2 菜单栏</h2>')
    w('<table><tr><th>菜单</th><th>功能</th></tr>'
      '<tr><td>文件</td><td>新建计算/保存/导出/退出</td></tr>'
      '<tr><td>编辑</td><td>撤销/重做/复制/粘贴/清空</td></tr>'
      '<tr><td>视图</td><td>亮色暗色切换/键盘面板</td></tr>'
      '<tr><td>工具</td><td>AI助手/搜索/计算历史</td></tr>'
      '<tr><td>帮助</td><td>用户手册/交互引导/示例库/关于</td></tr></table>')

    # 第4章
    w('<h1 id="ch计">第4章 · 计算功能</h1>')
    w('<p>14个计算模块。多数采用CalcBlock交互模式：输入表达式→计算→分步结果。基础运算为单块即时求值。</p>')
    w(img("10_calc_algebra.png"))
    for title, desc in [
        ("4.1 基础运算", "四则运算、乘方、开方、阶乘、对数。单块即时求值。"),
        ("4.2 代数计算", "多项式展开、因式分解、方程求解。支持多计算块并行。"),
        ("4.3 微积分", "求导、不定积分、定积分、极限、级数展开。符号+数值双模式。"),
        ("4.4 解析几何", "直线、圆、椭圆、双曲线、抛物线方程分析与几何性质。"),
        ("4.5 数列", "等差/等比/递推数列通项与求和，收敛性判断。"),
        ("4.6 线性代数", "矩阵运算、行列式、特征值、线性方程组、二次型标准化。"),
        ("4.7 概率统计", "概率分布、期望方差、假设检验、ANOVA、回归、时间序列。"),
        ("4.8 数值分析", "数值积分、ODE求解、插值拟合、非线性求根、误差分析。"),
        ("4.9 数论", "素数筛法、GCD/LCM、模运算、同余方程、算术函数。"),
        ("4.10 实分析", "实数完备性、序列极限、函数极限、可微性、黎曼积分。"),
        ("4.11 泛函分析", "赋范空间、内积空间、线性算子、对偶空间、谱理论。"),
        ("4.12 复分析", "全纯函数、复积分、留数定理、共形映射、黎曼ζ函数。"),
        ("4.13 代数拓扑", "同伦群、同调群、上同调环、度理论、持续同调。"),
        ("4.14 测度论", "σ-代数、测度构造、勒贝格积分、收敛定理、乘积测度。"),
    ]:
        w(f"<h2>{title}</h2><p>{desc}</p>")
    w('<div class="tip">代数计算等模块支持多块管理 — 点击"添加计算块"可并行进行多个独立计算。</div>')

    # 第5章
    w('<h1 id="ch绘">第5章 · 绘图功能</h1>')
    w('<p>7个绘图模式，支持交互式缩放、平移、导出。</p>')
    w(img("05_plot_2d.png"))
    for title, desc in [
        ("5.1 普通2D绘图", "一元函数曲线。多函数叠加、颜色自定义。"),
        ("5.2 极坐标绘图", "极坐标曲线r=f(θ)。玫瑰线、心形线、螺线。"),
        ("5.3 3D曲面绘图", "二元函数曲面z=f(x,y)。旋转视角（鼠标拖拽）。"),
        ("5.4 复数映射", "复变函数w=f(z)作用于网格，展示复平面映射。"),
        ("5.5 向量场", "二维向量场F(x,y)=(P,Q)。流线、箭头密度。"),
        ("5.6 任意做图", "自由几何构造。撤销/重做、几何约束。"),
        ("5.7 分形探索", "Mandelbrot集、Julia集、Newton分形。无限缩放。"),
    ]:
        w(f"<h2>{title}</h2><p>{desc}</p>")

    # 第6章
    w('<h1 id="ch用">第6章 · 用户账户系统</h1>')
    w('<h2>6.1 登录</h2><p>点击工具栏"登录"，输入用户名和密码。</p>')
    w(img("02_login.png"))
    w('<h2>6.2 注册</h2><ol>'
      '<li>切换到"注册"标签页</li>'
      '<li>输入用户名（3-20字符，字母/数字/下划线）</li>'
      '<li>输入邮箱 → 点击"发送验证码"</li>'
      '<li>查收邮件，输入6位验证码</li>'
      '<li>设置密码（至少8位，含字母+数字）→ 点击"注册"</li></ol>')
    w(img("03_register.png"))
    w('<div class="warn">验证码5分钟有效，60秒内不可重复发送。注册成功自动登录，赠送10次免费额度。</div>')
    w('<h2>6.3 邮箱验证</h2><p>未提供验证码时发送验证邮件，输入验证码激活。</p>')
    w('<h2>6.4 登录后</h2><p>工具栏显示"用户名(余额:N)"，点击可登出。</p>')

    # 第7章
    w('<h1 id="chAI">第7章 · AI智能助手</h1>')
    w('<p>自然语言输入数学问题，DeepSeek/OpenAI大模型驱动。</p>')
    w(img("08_ai_dialog.png"))
    w('<h2>7.1 使用</h2><ol><li>输入数学问题</li><li>点击发送</li><li>AI返回分步推理</li></ol>')
    w('<h2>7.2 配置API Key</h2><ol>'
      '<li>菜单→工具→AI设置</li><li>选择服务商</li><li>填入Key</li><li>保存</li></ol>')
    w('<div class="tip">AI助手自动读取当前工作区计算内容作为上下文。</div>')

    # 第8章
    w('<h1 id="ch键">第8章 · 键盘面板</h1>')
    w('<p>内置虚拟数学键盘，提供常用符号和函数快速输入。</p>')
    w(img("07_keyboard.png"))
    w('<h2>8.1 面板布局</h2>')
    w('<table><tr><th>区域</th><th>内容</th></tr>'
      '<tr><td>数字区</td><td>0-9 / 小数点 / 正负号</td></tr>'
      '<tr><td>运算符</td><td>+ - × ÷ ^ √ =</td></tr>'
      '<tr><td>函数区</td><td>sin cos tan log ln exp abs</td></tr>'
      '<tr><td>特殊符号</td><td>π e i ∞ ( ) ,</td></tr>'
      '<tr><td>微积分</td><td>d/dx ∫ lim Σ</td></tr>'
      '<tr><td>希腊字母</td><td>α β γ θ λ μ σ φ ω</td></tr></table>')
    w('<h2>8.2 显示/隐藏</h2><p>菜单→视图→键盘面板，或点击底部折叠按钮。</p>')

    # 第9章
    w('<h1 id="ch设">第9章 · 设置与主题</h1>')
    w('<h2>9.1 主题切换</h2><p>亮色（Slate）/ 暗色（Catppuccin Mocha）。菜单→视图→切换，Ctrl+T。</p>')
    w(img("04_main_dark.png"))
    w('<h2>9.2 设置</h2><p>菜单→工具→设置：默认绘图范围/数值精度/AI服务商。</p>')
    w(img("09_settings.png"))
    w('<h2>9.3 关于</h2><p>菜单→帮助→关于：版本信息和开发团队。</p>')
    w(img("06_about.png"))

    # 第10章
    w('<h1 id="ch常">第10章 · 常见问题</h1>')
    for q, a in [
        ("Q1：无法连接到服务器？", "登录和AI需要网络。本地计算和绘图可离线使用。"),
        ("Q2：忘记密码？", "通过注册邮箱联系管理员重置。"),
        ("Q3：计算超时？", "复杂表达式可能超出时间限制。尝试简化或分步计算。"),
        ("Q4：3D图形无法旋转？", "按住鼠标左键拖拽旋转视角，滚轮缩放。"),
        ("Q5：如何导出结果？", "菜单→文件→导出，支持图片或LaTeX格式。"),
        ("Q6：验证码未收到？", "检查垃圾邮件箱。60秒后可重新发送。"),
        ("Q7：如何切换语言？", "当前为简体中文，后续版本添加多语言。"),
    ]:
        w(f"<h2>{q}</h2><p>{a}</p>")

    w('<hr><p style="text-align:center;color:#a8a29e;font-size:11px">'
      'MF-Mathematics V1.0.0 · MF-Vis-Science工作室 ©2026 · www.mvs-studio.com</p>')
    w("</body></html>")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(h))
    print(f"HTML: {OUT}")
    print(f"大小: {os.path.getsize(OUT)/1024:.0f} KB")


if __name__ == "__main__":
    build()
