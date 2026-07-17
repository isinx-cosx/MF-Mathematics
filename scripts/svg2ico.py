"""
svg2ico.py — 从 assets/icon.svg 生成多尺寸 .ico 文件
纯 Python 实现，仅依赖 Pillow（无需 Cairo/Inkscape）。
"""

import xml.etree.ElementTree as ET
import math
from PIL import Image, ImageDraw
import os
import re


# ---------- SVG 路径解析 ----------

SVG_NS = "http://www.w3.org/2000/svg"


def parse_svg_path(d_str: str) -> list:
    """解析 SVG d 属性，返回 [(cmd, params), ...] 列表。"""
    tokens = re.findall(r"[MLQCZmlqcz]|[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", d_str)
    commands = []
    i = 0
    while i < len(tokens):
        cmd = tokens[i]
        i += 1
        params = []
        # 收集后续数字参数
        while i < len(tokens) and re.match(r"^[-+]?\d", tokens[i]):
            params.append(float(tokens[i]))
            i += 1
        commands.append((cmd, params))
    return commands


def eval_bezier_cubic(t, p0, p1, p2, p3):
    """三次 Bézier 在 t ∈ [0,1] 的值。"""
    u = 1 - t
    return (
        u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0],
        u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1],
    )


def eval_bezier_quad(t, p0, p1, p2):
    """二次 Bézier 在 t ∈ [0,1] 的值。"""
    u = 1 - t
    return (
        u**2 * p0[0] + 2 * u * t * p1[0] + t**2 * p2[0],
        u**2 * p0[1] + 2 * u * t * p1[1] + t**2 * p2[1],
    )


def path_to_polyline(d_str: str, num_segments: int = 40) -> list[tuple[float, float]]:
    """将 SVG 路径转为折线点列表。"""
    commands = parse_svg_path(d_str)
    points = []
    x, y = 0.0, 0.0  # current point

    for cmd, params in commands:
        if cmd == "M":
            x, y = params[0], params[1]
            points.append((x, y))
        elif cmd == "L":
            x, y = params[0], params[1]
            points.append((x, y))
        elif cmd == "C":
            p0 = (x, y)
            p1 = (params[0], params[1])
            p2 = (params[2], params[3])
            p3 = (params[4], params[5])
            for j in range(1, num_segments + 1):
                t = j / num_segments
                x, y = eval_bezier_cubic(t, p0, p1, p2, p3)
                points.append((x, y))
        elif cmd == "Q":
            p0 = (x, y)
            p1 = (params[0], params[1])
            p2 = (params[2], params[3])
            for j in range(1, num_segments + 1):
                t = j / num_segments
                x, y = eval_bezier_quad(t, p0, p1, p2)
                points.append((x, y))
        # 忽略其他命令

    return points


# ---------- 颜色解析 ----------

def parse_color(attr: str) -> tuple[int, int, int, int]:
    """解析 SVG 颜色属性为 RGBA。"""
    if attr is None:
        return (0, 0, 0, 255)
    attr = attr.strip()
    if attr.startswith("#"):
        h = attr[1:]
        if len(h) == 6:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)
        elif len(h) == 3:
            h = "".join(c * 2 for c in h)
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)
    if attr == "none":
        return (0, 0, 0, 0)
    if attr.startswith("url("):
        # 简化：渐变引用返回默认亮青/深蓝
        return (0, 212, 255, 255)  # 默认亮青
    return (0, 0, 0, 255)


def get_gradient_stops(root, grad_id: str) -> list[tuple[float, tuple[int, int, int, int]]]:
    """获取渐变定义中的色标。"""
    stops = []
    grad = root.find(f'.//*[@id="{grad_id}"]')
    if grad is None:
        return stops
    for stop in grad.findall(f"{{{SVG_NS}}}stop"):
        offset_str = stop.get("offset", "0%")
        offset = float(offset_str.replace("%", "")) / 100.0
        color = parse_color(stop.get("stop-color"))
        stops.append((offset, color))
    return stops


def resolve_fill_color(root, element) -> tuple[int, int, int, int]:
    """解析填充颜色（处理渐变引用）。"""
    fill = element.get("fill", "")
    if fill is None or fill == "none":
        return (0, 0, 0, 0)
    if fill.startswith("url(#"):
        grad_id = fill[5:-1]
        stops = get_gradient_stops(root, grad_id)
        if stops:
            return stops[-1][1]  # 简化为最后一个色标
        return (26, 54, 93, 255)
    return parse_color(fill)


def resolve_stroke_color(root, element) -> tuple[int, int, int, int]:
    """解析描边颜色。"""
    stroke = element.get("stroke", "")
    return parse_color(stroke)


def get_opacity(element) -> float:
    """获取透明度。"""
    op = element.get("opacity")
    if op:
        return float(op)
    return 1.0


# ---------- 主渲染函数 ----------

def render_svg_to_image(svg_path: str, width: int, height: int) -> Image.Image:
    """将 SVG 渲染为 Pillow Image。"""
    tree = ET.parse(svg_path)
    root = tree.getroot()

    # 获取 viewBox 进行缩放映射
    vb = root.get("viewBox", "0 0 512 600")
    vb_parts = [float(x) for x in vb.split()]
    vb_x, vb_y, vb_w, vb_h = vb_parts

    scale_x = width / vb_w
    scale_y = height / vb_h
    scale = min(scale_x, scale_y)

    img = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)

    def sx(x):
        return (x - vb_x) * scale + (width - vb_w * scale) / 2

    def sy(y):
        return (y - vb_y) * scale + (height - vb_h * scale) / 2

    def sp(x, y):
        return (sx(x), sy(y))

    # 渲染顺序：先背景，再元素
    # 收集所有要渲染的元素
    all_elements = list(root.iter())
    # 跳过根和 defs
    drawable = [e for e in all_elements
                if e.tag not in (f"{{{SVG_NS}}}svg", f"{{{SVG_NS}}}defs", f"{{{SVG_NS}}}stop",
                                 f"{{{SVG_NS}}}linearGradient")]

    for elem in drawable:
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

        # 获取 transform
        transform_str = elem.get("transform", "")
        dx, dy = 0, 0
        if transform_str and "translate" in transform_str:
            m = re.search(r"translate\(([^)]+)\)", transform_str)
            if m:
                parts = [float(x.strip()) for x in m.group(1).split(",")]
                if len(parts) == 1:
                    dx, dy = parts[0], 0
                else:
                    dx, dy = parts[0], parts[1]

        if tag == "rect":
            x = float(elem.get("x", 0)) + dx
            y = float(elem.get("y", 0)) + dy
            w = float(elem.get("width", 0))
            h = float(elem.get("height", 0))
            rx = float(elem.get("rx", 0))

            fill_color = resolve_fill_color(root, elem)
            stroke_color = resolve_stroke_color(root, elem)
            if stroke_color == (0, 0, 0, 0):
                stroke_color = fill_color

            if fill_color[3] > 0:
                coords = [sx(x), sy(y), sx(x + w), sy(y + h)]
                if rx > 0:
                    draw.rounded_rectangle(coords, radius=sx(rx) - sx(0), fill=fill_color, outline=stroke_color)
                else:
                    draw.rectangle(coords, fill=fill_color, outline=stroke_color)

        elif tag == "line":
            x1 = float(elem.get("x1", 0)) + dx
            y1 = float(elem.get("y1", 0)) + dy
            x2 = float(elem.get("x2", 0)) + dx
            y2 = float(elem.get("y2", 0)) + dy
            sw_raw = float(elem.get("stroke-width", 1))
            stroke_color = resolve_stroke_color(root, elem)

            sw = sw_raw * scale
            draw.line([sp(x1, y1), sp(x2, y2)], fill=stroke_color, width=max(1, int(sw)))

        elif tag == "circle":
            cx = float(elem.get("cx", 0)) + dx
            cy = float(elem.get("cy", 0)) + dy
            r = float(elem.get("r", 0))
            fill_color = resolve_fill_color(root, elem)
            op = get_opacity(elem)

            color = (*fill_color[:3], int(fill_color[3] * op))
            r_scaled = r * scale
            draw.ellipse(
                [sx(cx) - r_scaled, sy(cy) - r_scaled,
                 sx(cx) + r_scaled, sy(cy) + r_scaled],
                fill=color,
            )

        elif tag == "polygon":
            pts_str = elem.get("points", "")
            pts = [float(x) for x in pts_str.replace(",", " ").split()]
            fill_color = resolve_fill_color(root, elem)
            stroke_color = resolve_stroke_color(root, elem)

            poly_pts = []
            for i in range(0, len(pts), 2):
                poly_pts.append(sp(pts[i] + dx, pts[i + 1] + dy))

            if fill_color[3] > 0:
                draw.polygon(poly_pts, fill=fill_color, outline=stroke_color)

        elif tag == "path":
            d_str = elem.get("d", "")
            stroke_color = resolve_stroke_color(root, elem)
            if stroke_color == (0, 0, 0, 0):
                stroke_color = (26, 54, 93, 255)
            sw_raw = float(elem.get("stroke-width", 1))
            sw = max(1, int(sw_raw * scale))

            polyline = path_to_polyline(d_str, num_segments=60)

            # 应用 transform
            scaled_pts = [sp(pt[0] + dx, pt[1] + dy) for pt in polyline]

            if len(scaled_pts) >= 2 and stroke_color[3] > 0:
                draw.line(scaled_pts, fill=stroke_color, width=sw, joint="curve")

        elif tag == "text":
            text_content = (elem.text or "").strip()
            if text_content:
                x = float(elem.get("x", 0)) + dx
                y = float(elem.get("y", 0)) + dy
                font_size = float(elem.get("font-size", 12))
                fill_color = resolve_fill_color(root, elem)
                text_anchor = elem.get("text-anchor", "start")

                fs = font_size * scale
                px = sx(x)
                py = sy(y)

                # 简化的文字渲染
                try:
                    from PIL import ImageFont
                    # 尝试系统字体
                    font = None
                    for fn in ["segoeui.ttf", "arial.ttf", "helvetica.ttf"]:
                        try:
                            font = ImageFont.truetype(fn, int(fs))
                            break
                        except Exception:
                            continue
                    if font is None:
                        font = ImageFont.load_default()

                    bbox = draw.textbbox((0, 0), text_content, font=font)
                    tw = bbox[2] - bbox[0]
                    if text_anchor == "middle":
                        tx = px - tw / 2
                    elif text_anchor == "end":
                        tx = px - tw
                    else:
                        tx = px
                    draw.text((tx, py - fs * 0.8), text_content, fill=fill_color, font=font)
                except Exception:
                    pass

    return img


# ---------- 生成 ICO ----------

def main():
    svg_path = "assets/icon.svg"
    ico_path = "assets/icon.ico"

    sizes = [16, 32, 48, 64, 128, 256]
    images = []

    for size in sizes:
        print(f"Rendering {size}x{size}...")
        # 保持比例：viewBox 512×600
        h = int(size * 600 / 512)
        img = render_svg_to_image(svg_path, size, h)
        # 裁切为正方形（取图标区域）
        icon_h = int(size * 480 / 512)
        img_sq = img.crop((0, 0, size, size))
        images.append(img_sq)

    # 保存 ICO
    images[0].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )

    file_size = os.path.getsize(ico_path)
    print(f"\nICO: {ico_path}")
    print(f"   Size: {file_size:,} bytes")
    print(f"   Sizes: {sizes}")


if __name__ == "__main__":
    main()
