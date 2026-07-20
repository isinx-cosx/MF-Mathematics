"""生成 Inno Setup 安装向导 Banner 图 (MF-Mathematics 风格)。"""
from __future__ import annotations
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os

PROJECT_ROOT = r"C:\Users\fsafsafsa\Desktop\Multifunctional-Mathematics"
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")
OUTPUT_DIR = os.path.join(ASSETS_DIR, "installer")
ICON_PATH = os.path.join(ASSETS_DIR, "icon.png")

# ── MF-Mathematics Light 配色 ──
BG_LIGHT = "#f8fafc"
PRIMARY = "#3b82f6"
PRIMARY_DARK = "#1e40af"
TEXT_PRIMARY = "#0f172a"
TEXT_MUTED = "#475569"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _blend(c1: tuple, c2: tuple, t: float) -> tuple[int, int, int]:
    return tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3))


def make_wizard_banner() -> str:
    """生成 164×314 左侧 Banner（品牌色渐变 + 图标 + 文字）。"""
    W, H = 164, 314
    img = Image.new("RGB", (W, H), _hex_to_rgb(BG_LIGHT))
    draw = ImageDraw.Draw(img)

    # ── 上半部：蓝色渐变背景 ──
    top_rgb = _hex_to_rgb(PRIMARY)
    bot_rgb = _hex_to_rgb(PRIMARY_DARK)
    grad_h = 200
    for y in range(grad_h):
        t = y / max(grad_h - 1, 1)
        color = _blend(top_rgb, bot_rgb, t)
        draw.line([(0, y), (W, y)], fill=color)

    # ── 分隔波浪 ──
    wave_y = grad_h - 2
    draw.ellipse([(-W // 2, wave_y - 20), (W + W // 2, wave_y + 20)],
                 fill=top_rgb)

    # ── 图标 (居中放在渐变区域) ──
    icon_size = 68
    if os.path.exists(ICON_PATH):
        icon = Image.open(ICON_PATH).convert("RGBA")
        icon = icon.resize((icon_size, icon_size), Image.LANCZOS)
        icon_x, icon_y = (W - icon_size) // 2, 48
        img.paste(icon, (icon_x, icon_y), icon)

    # ── 文字 ──
    title_font = None
    subtitle_font = None
    try:
        title_font = ImageFont.truetype("segoeuib.ttf", 15)
        subtitle_font = ImageFont.truetype("segoeuil.ttf", 10)
    except OSError:
        try:
            title_font = ImageFont.truetype("segoeui.ttf", 15)
            subtitle_font = ImageFont.truetype("segoeui.ttf", 10)
        except OSError:
            title_font = ImageFont.load_default()
            subtitle_font = title_font

    # 品牌名
    brand_text = "MF-Mathematics"
    bbox = draw.textbbox((0, 0), brand_text, font=title_font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((W - tw) // 2, icon_y + icon_size + 14),
              brand_text, font=title_font, fill="#ffffff")

    # 版本号
    ver_text = "Version 1.0"
    bbox2 = draw.textbbox((0, 0), ver_text, font=subtitle_font)
    tw2 = bbox2[2] - bbox2[0]
    draw.text(((W - tw2) // 2, icon_y + icon_size + 36),
              ver_text, font=subtitle_font, fill="#bfdbfe")

    # ── 下半部：功能特性列表 ──
    features = [
        "● 14 种数学计算模式",
        "● 7 种绘图可视化",
        "● AI 智能推导助手",
        "● 交互式教程引导",
        "● 联网数学搜索",
    ]
    feat_y = grad_h + 18
    for i, feat in enumerate(features):
        try:
            ffont = ImageFont.truetype("segoeui.ttf", 9)
        except OSError:
            ffont = ImageFont.load_default()
        draw.text((14, feat_y + i * 20), feat, font=ffont, fill=TEXT_MUTED)

    # ── 底部品牌线 ──
    bottom_y = H - 10
    draw.line([(20, bottom_y), (W - 20, bottom_y)], fill=PRIMARY, width=2)

    out = os.path.join(OUTPUT_DIR, "WizardImage.bmp")
    img.save(out, "BMP")
    print(f"  WizardImage ({W}×{H}) → {out}")
    return out


def make_wizard_small() -> str:
    """生成 55×55 小图标（右上角品牌 logo）。"""
    S = 55
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 蓝色圆角方块背景
    margin = 2
    draw.rounded_rectangle([margin, margin, S - margin, S - margin],
                           radius=10, fill=_hex_to_rgb(PRIMARY))

    # 叠加图标
    if os.path.exists(ICON_PATH):
        icon = Image.open(ICON_PATH).convert("RGBA")
        icon = icon.resize((S - 16, S - 16), Image.LANCZOS)
        # 居中叠加
        paste_x = (S - icon.width) // 2
        paste_y = (S - icon.height) // 2
        img.paste(icon, (paste_x, paste_y), icon)

    out = os.path.join(OUTPUT_DIR, "WizardSmallImage.bmp")
    img.save(out, "BMP")
    print(f"  WizardSmallImage ({S}×{S}) → {out}")
    return out


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("生成 MF-Mathematics 安装向导图片:\n")
    make_wizard_banner()
    make_wizard_small()
    print("\n✅ 完成")
