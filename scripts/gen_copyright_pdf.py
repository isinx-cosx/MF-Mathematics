# -*- coding: utf-8 -*-
"""软著源代码 PDF 生成器 — 前30页 + 后30页，50行/页，A4 纵向。
自动排除第三方库源码（PySide6/SymPy/NumPy/site-packages），
页眉统一为 "MF-Mathematics V1.0.0"。
"""
import os
import re

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── 参数 ──
LINES_PER_PAGE = 50
FIRST_PAGES = 30
LAST_PAGES = 30
SOFTWARE_NAME = "MF-Mathematics"
VERSION = "V1.0.0"

PAGE_W, PAGE_H = A4
MARGIN_LEFT = 20 * mm
MARGIN_RIGHT = 10 * mm
MARGIN_TOP = 15 * mm
MARGIN_BOTTOM = 15 * mm

FONT_SIZE = 7.5
LINE_HEIGHT = 12  # pt

# ── 需要从源代码中替换的敏感模式 ──
_SANITIZE_PATTERNS = [
    # 本地绝对路径 → 相对路径
    (re.compile(r'[A-Za-z]:\\[Uu]sers\\[^\\"\'\n\r,;]+'), './'),
    (re.compile(r'[A-Za-z]:/[Uu]sers/[^"\'\n\r,;]+'), './'),
    # 硬编码邮箱
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'), '***@***.com'),
]


def register_fonts() -> str:
    """注册中文字体，返回字体名。"""
    candidates = [
        ("C:/Windows/Fonts/simhei.ttf", "SimHei"),
        ("C:/Windows/Fonts/msyh.ttc", "MSYH"),
        ("C:/Windows/Fonts/simsun.ttc", "SimSun"),
    ]
    for path, name in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                return name
            except Exception:
                continue
    return "Courier"


def sanitize_line(line: str) -> str:
    """脱敏处理：替换路径和邮箱。"""
    for pattern, replacement in _SANITIZE_PATTERNS:
        line = pattern.sub(replacement, line)
    return line


def collect_and_sort(project_root: str) -> list[str]:
    """收集项目自有 .py 文件（自动排除 site-packages 等第三方目录）。"""
    EXCLUDE_DIRS = {
        "__pycache__", "_archive", ".vscode", ".git", "build", "dist",
        "scripts", "docs", "site-packages", "Lib", ".env", "node_modules",
    }
    # 第三方包名前缀 — 这些不会作为项目目录出现，但以防万一
    THIRD_PARTY_PREFIXES = (
        "PySide6", "shiboken6", "sympy", "numpy", "scipy", "matplotlib",
        "PIL", "lxml", "pydantic", "sqlalchemy", "passlib", "jose",
        "requests", "urllib3", "certifi", "charset_normalizer", "idna",
        "dotenv", "uvicorn", "fastapi", "starlette", "reportlab",
        "setuptools", "packaging", "psutil", "pytest",
        "dateutil", "six", "yaml", "markupsafe", "jinja2",
    )

    def _is_third_party(path_components: list[str]) -> bool:
        for comp in path_components:
            if comp.startswith(THIRD_PARTY_PREFIXES):
                return True
        return False

    PRIORITY = [
        "MF_UI/main.py", "MF_UI/main_window.py", "MF_UI/_import_all.py",
        "MF_Mathematics/core/", "MF_Mathematics/algebra/", "MF_Mathematics/calculus/",
        "MF_Mathematics/linear_algebra/", "MF_Mathematics/real_analysis/",
        "MF_Mathematics/complex_analysis/", "MF_Mathematics/functional_analysis/",
        "MF_Mathematics/numerical/", "MF_Mathematics/probability/",
        "MF_Mathematics/number_theory/", "MF_Mathematics/algebraic_topology/",
        "MF_Mathematics/measure_theory/", "MF_Mathematics/harmonic_analysis/",
        "MF_Mathematics/utils/", "MF_Mathematics/tests/",
        "MF_UI/calc/", "MF_UI/plot/", "MF_UI/components/", "MF_UI/dialogs/",
        "MF_UI/utils/", "MF_UI/calc_engine.py", "MF_UI/compute_worker.py",
        "MF_UI/math_keyboard.py",
        "MF_User/", "MF_AI/", "MF_Online/", "MF_Tutorial/",
    ]

    all_files = []
    for dirpath, dirnames, filenames in os.walk(project_root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            if fn.endswith(".py"):
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, project_root).replace(os.sep, "/")
                # 跳过第三方库目录
                components = rel.split("/")
                if _is_third_party(components):
                    continue
                all_files.append(rel)

    def sort_key(f: str) -> int:
        for i, prefix in enumerate(PRIORITY):
            if f.startswith(prefix) or f == prefix:
                return i
        return len(PRIORITY)

    all_files.sort(key=sort_key)

    all_lines = []
    for fpath in all_files:
        full = os.path.join(project_root, fpath)
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
            if all_lines and not all_lines[-1].endswith("\n"):
                all_lines.append("\n")
            # 脱敏处理
            sanitized = [sanitize_line(ln) for ln in lines]
            all_lines.extend(sanitized)
        except Exception:
            pass
    return all_lines


def draw_page_header(c: canvas.Canvas, font_name: str, page_num: int,
                     part_label: str) -> float:
    """绘制统一页眉：MF-Mathematics V1.0.0。"""
    # 顶部细线
    c.setStrokeColorRGB(0.4, 0.4, 0.4)
    c.setLineWidth(0.5)
    y_line = PAGE_H - MARGIN_TOP + 5
    c.line(MARGIN_LEFT, y_line, PAGE_W - MARGIN_RIGHT, y_line)

    # 单行居中标题
    y_text = PAGE_H - MARGIN_TOP + 10
    c.setFont(font_name, 10)
    header_text = f"{SOFTWARE_NAME}  {VERSION}"
    c.drawCentredString(PAGE_W / 2, y_text, header_text)

    # 左右页码
    c.setFont(font_name, 8)
    c.drawString(MARGIN_LEFT, y_text, f"{part_label}")
    c.drawRightString(PAGE_W - MARGIN_RIGHT, y_text, f"第 {page_num} 页")

    # 底部细线
    c.line(MARGIN_LEFT, PAGE_H - MARGIN_TOP + 18,
           PAGE_W - MARGIN_RIGHT, PAGE_H - MARGIN_TOP + 18)

    return PAGE_H - MARGIN_TOP - 28  # 正文起始 y


def generate_pdf(lines: list[str], output_path: str, font_name: str,
                 start_page: int, total_pages: int, part_label: str) -> int:
    """生成 PDF 文件，返回实际页数。"""
    c = canvas.Canvas(output_path, pagesize=A4)
    c.setTitle(f"{SOFTWARE_NAME} {VERSION} 源代码 - {part_label}")

    usable_w = PAGE_W - MARGIN_LEFT - MARGIN_RIGHT
    char_width = c.stringWidth("W", font_name, FONT_SIZE)
    chars_per_line = max(40, int(usable_w / char_width) - 2)

    page_num = start_page
    line_idx = 0
    total_lines = len(lines)

    while line_idx < total_lines and page_num < start_page + total_pages:
        body_top = draw_page_header(c, font_name, page_num, part_label)
        y = body_top
        lines_on_page = 0

        while lines_on_page < LINES_PER_PAGE and line_idx < total_lines:
            raw = lines[line_idx].rstrip("\n\r")
            raw = raw.replace("\t", "    ")
            if len(raw) > chars_per_line:
                raw = raw[:chars_per_line]
            if raw == "":
                raw = " "

            c.setFont(font_name, FONT_SIZE)
            c.drawString(MARGIN_LEFT, y, raw)
            y -= LINE_HEIGHT
            lines_on_page += 1
            line_idx += 1

        # 底部页码
        c.setFont(font_name, 7)
        c.drawCentredString(PAGE_W / 2, MARGIN_BOTTOM - 8,
                            f"— {page_num} —")

        if line_idx < total_lines:
            c.showPage()
        page_num += 1

    c.save()
    return page_num - start_page


def main():
    project_root = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    output_dir = os.path.join(project_root, "dist", "copyright")
    os.makedirs(output_dir, exist_ok=True)

    font_name = register_fonts()
    print(f"字体: {font_name}")

    all_lines = collect_and_sort(project_root)
    total = len(all_lines)
    print(f"总行数: {total}")

    first_count = FIRST_PAGES * LINES_PER_PAGE
    last_start = max(0, total - LAST_PAGES * LINES_PER_PAGE)

    # 前30页
    front_path = os.path.join(output_dir, "source_front_30.pdf")
    print("生成前30页 PDF...")
    p1 = generate_pdf(all_lines[:first_count], front_path, font_name,
                      1, FIRST_PAGES, "前部")
    print(f"  → {front_path} ({p1} 页)")

    # 后30页
    back_path = os.path.join(output_dir, "source_back_30.pdf")
    print("生成后30页 PDF...")
    p2 = generate_pdf(all_lines[last_start:], back_path, font_name,
                      FIRST_PAGES + 1, LAST_PAGES, "后部")
    print(f"  → {back_path} ({p2} 页)")

    # 检查报告
    print(f"\n{'='*60}")
    print(f"软著源代码 PDF 生成完毕")
    print(f"  页眉: {SOFTWARE_NAME} {VERSION}")
    print(f"  页数: 前部 {p1} + 后部 {p2} = {p1 + p2} 页")
    print(f"  第三方库: 已自动排除 (PySide6/SymPy/NumPy/... 共 30+ 包)")
    print(f"  脱敏处理: 本地路径 → ./ | 邮箱 → ***@***.com")
    print(f"  输出目录: {output_dir}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
