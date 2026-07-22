"""生成 Inno Setup 安装向导 Banner 图 + 圆角图标 (MF-Mathematics 深色品牌风格)。"""
from __future__ import annotations
from PIL import Image, ImageDraw, ImageFont
import os

PROJECT_ROOT = r"C:\Users\fsafsafsa\Desktop\Multifunctional-Mathematics"
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")
OUTPUT_DIR = os.path.join(ASSETS_DIR, "installer")
ICON_SRC = os.path.join(ASSETS_DIR, "icon.png")       # RGBA 2048x2048

# ── MF-Mathematics 深色品牌色 ──
C_BASE    = "#181825"   # Catppuccin base (最底)
C_MANTLE  = "#1e1e2e"   # 主背景
C_SURFACE = "#252540"   # 卡片
C_BORDER  = "#313244"   # 边框
C_TEXT    = "#cdd6f4"   # 主文字
C_SUBTEXT = "#a6adc8"   # 副文字
C_BLUE    = "#3b82f6"   # 品牌蓝
C_PURPLE  = "#6366f1"   # 鸢尾紫
C_TEAL    = "#10b981"   # 翡翠绿


def _hex(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _blend(c1: tuple, c2: tuple, t: float) -> tuple[int, int, int]:
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def make_wizard_banner() -> str:
    """WizardImageFile: 164x314 左侧深色 Banner。"""
    W, H = 164, 314
    img = Image.new("RGBA", (W, H), _hex(C_MANTLE))
    draw = ImageDraw.Draw(img)

    # ── 顶部：品牌标志区 (深蓝紫渐变) ──
    top_h = 180
    a = _hex(C_MANTLE)     # 顶部起始
    b = _hex("#1a1c3b")    # 深蓝
    c = _hex("#161b4a")    # 更深蓝
    for y in range(top_h):
        t = y / max(top_h - 1, 1)
        if t < 0.5:
            color = _blend(a, b, t * 2)
        else:
            color = _blend(b, c, (t - 0.5) * 2)
        draw.line([(0, y), (W, y)], fill=color)

    # ── 圆角图标区域（白色半透明圆角矩形底） ──
    icon_sz = 72
    icon_x = (W - icon_sz) // 2
    icon_y = 28
    # 淡白圆角底
    draw.rounded_rectangle(
        [icon_x - 4, icon_y - 4, icon_x + icon_sz + 4, icon_y + icon_sz + 4],
        radius=16, fill=(255, 255, 255, 25))

    # ── 图标本身 ──
    if os.path.exists(ICON_SRC):
        icon = Image.open(ICON_SRC).convert("RGBA")
        icon = icon.resize((icon_sz, icon_sz), Image.LANCZOS)
        img.paste(icon, (icon_x, icon_y), icon)

    # ── 标题 ──
    try:
        tfont = ImageFont.truetype("segoeuib.ttf", 14)
    except OSError:
        tfont = ImageFont.load_default()
    title = "MF-Mathematics"
    bbox = draw.textbbox((0, 0), title, font=tfont)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, icon_y + icon_sz + 12), title,
              font=tfont, fill=_hex(C_TEXT))

    # ── 版本 ──
    try:
        verfont = ImageFont.truetype("segoeui.ttf", 9)
    except OSError:
        verfont = ImageFont.load_default()
    ver = "Version 1.0"
    vb = draw.textbbox((0, 0), ver, font=verfont)
    draw.text(((W - (vb[2] - vb[0])) // 2, icon_y + icon_sz + 30),
              ver, font=verfont, fill=_hex(C_BLUE))

    # ── 分隔线 ──
    sep_y = top_h + 6
    draw.line([(20, sep_y), (W - 20, sep_y)], fill=_hex(C_BORDER), width=1)

    # ── 功能列表 ──
    features = [
        ("▸", "14 种数学计算模式"),
        ("▸", "7 种绘图可视化"),
        ("▸", "AI 智能推导助手"),
        ("▸", "交互式教程引导"),
        ("▸", "联网数学搜索"),
    ]
    try:
        feat_font = ImageFont.truetype("segoeui.ttf", 10)
    except OSError:
        feat_font = ImageFont.load_default()

    feat_y = sep_y + 16
    for i, (bullet, feat) in enumerate(features):
        y = feat_y + i * 22
        draw.text((10, y), bullet, font=feat_font, fill=_hex(C_BLUE))
        draw.text((26, y), feat, font=feat_font, fill=_hex(C_SUBTEXT))

    # ── 底部强调条 ──
    bottom_y = H - 12
    draw.line([(30, bottom_y), (W - 30, bottom_y)], fill=_hex(C_BLUE), width=2)

    out = os.path.join(OUTPUT_DIR, "WizardImage.bmp")
    img = img.convert("RGB")
    img.save(out, "BMP")
    print(f"  WizardImage ({W}x{H}) -> {out}")
    return out


def make_wizard_small() -> str:
    """WizardSmallImageFile: 55x55 右上角小图标。"""
    S = 55
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 深色圆角底
    draw.rounded_rectangle([1, 1, S - 1, S - 1], radius=12, fill=_hex(C_MANTLE))

    # 图标
    if os.path.exists(ICON_SRC):
        icon = Image.open(ICON_SRC).convert("RGBA")
        inner = S - 16
        icon = icon.resize((inner, inner), Image.LANCZOS)
        px = (S - inner) // 2
        py = (S - inner) // 2
        img.paste(icon, (px, py), icon)

    out = os.path.join(OUTPUT_DIR, "WizardSmallImage.bmp")
    img.save(out, "BMP")
    print(f"  WizardSmallImage ({S}x{S}) -> {out}")
    return out


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("Generating MF-Mathematics installer assets:\n")
    make_wizard_banner()
    make_wizard_small()
    print("\nDone.")
