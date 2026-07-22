# -*- coding: utf-8 -*-
"""软著源代码文档生成器。

提取前 30 页 + 后 30 页（50 行/页），生成带页眉的 TXT 文档。
"""
import os, sys

LINES_PER_PAGE = 50
FIRST_PAGES = 30
LAST_PAGES = 30
TOTAL_NEEDED = (FIRST_PAGES + LAST_PAGES) * LINES_PER_PAGE

# 软件信息
SOFTWARE_NAME = "MF-Mathematics"
VERSION = "1.0.0"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dist", "copyright")

# 逻辑排序
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


def collect_files(root: str) -> list[str]:
    all_files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in ("__pycache__", "_archive", ".vscode",
                                    ".git", "build", "dist", "scripts", "docs")]
        for fn in filenames:
            if fn.endswith(".py"):
                rel = os.path.relpath(os.path.join(dirpath, fn), root)
                all_files.append(rel.replace(os.sep, "/"))
    return all_files


def sort_key(f: str) -> int:
    for i, prefix in enumerate(PRIORITY):
        if f.startswith(prefix) or f == prefix:
            return i
    return len(PRIORITY)


def format_page(lines: list[str], page_num: int, part_label: str) -> str:
    """格式化一页，添加页眉。"""
    header = (
        f"{'=' * 70}\n"
        f"  {SOFTWARE_NAME}  V{VERSION}"
        f"          {part_label}          第 {page_num} 页\n"
        f"{'=' * 70}\n\n"
    )
    return header + "".join(lines)


def write_document(
    all_lines: list[str],
    first_count: int,
    last_start: int,
    part_label: str,
    filename: str,
) -> list[str]:
    """写入一册文档，返回页信息。"""
    pages = []
    lines = all_lines[:first_count] if part_label == "前部" else all_lines[last_start:]

    for page_idx in range(0, len(lines), LINES_PER_PAGE):
        page_lines = lines[page_idx:page_idx + LINES_PER_PAGE]
        page_num = (page_idx // LINES_PER_PAGE) + 1
        if part_label == "后部":
            page_num += FIRST_PAGES
        pages.append(format_page(page_lines, page_num, part_label))

    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(pages))

    return pages


def main():
    project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    project_root = os.path.normpath(project_root)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"项目根目录: {project_root}")

    all_files = collect_files(project_root)
    all_files.sort(key=sort_key)

    all_lines = []
    for fpath in all_files:
        full = os.path.join(project_root, fpath)
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
            # 在文件之间加分隔
            if all_lines and not all_lines[-1].endswith("\n"):
                all_lines.append("\n")
            all_lines.extend(lines)
        except Exception as e:
            print(f"  跳过 {fpath}: {e}")

    total = len(all_lines)
    print(f"源文件数: {len(all_files)}")
    print(f"总行数: {total}")
    print(f"需求: 前{FIRST_PAGES}页 + 后{LAST_PAGES}页 = {TOTAL_NEEDED} 行")

    first_count = FIRST_PAGES * LINES_PER_PAGE
    last_start = max(0, total - LAST_PAGES * LINES_PER_PAGE)

    if total <= TOTAL_NEEDED:
        first_count = total
        last_start = total

    print(f"前部: 第 1 - {first_count} 行")
    print(f"后部: 第 {last_start + 1} - {total} 行")

    # 生成前 30 页
    print("\n生成前 30 页...")
    p1 = write_document(all_lines, first_count, last_start, "前部", "source_front_30.txt")
    print(f"  → {OUTPUT_DIR}/source_front_30.txt  ({len(p1)} 页)")

    # 生成后 30 页
    print("生成后 30 页...")
    p2 = write_document(all_lines, first_count, last_start, "后部", "source_back_30.txt")
    print(f"  → {OUTPUT_DIR}/source_back_30.txt  ({len(p2)} 页)")

    # 汇总
    print(f"\n{'=' * 60}")
    print(f"软著源代码文档生成完毕")
    print(f"前部: {len(p1)} 页, 后部: {len(p2)} 页, 合计: {len(p1) + len(p2)} 页")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
