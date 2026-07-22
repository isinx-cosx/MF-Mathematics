# -*- coding: utf-8 -*-
"""从 assets/icon.png 生成多尺寸 .ico 文件（12 个尺寸：16~256）。
纯 Python + Pillow，手动构造 ICO 格式避免 Pillow append_images 的 bug。
"""
from PIL import Image
import struct, io, os

SIZES = [16, 20, 24, 32, 40, 48, 64, 72, 80, 96, 128, 256]
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def make_ico(src_path: str, ico_path: str) -> int:
    """从 JPG/PNG 生成多尺寸 ICO，返回文件字节数。"""
    img = Image.open(src_path)
    # 保留原始色彩空间：RGB 用 24bit，RGBA 用 32bit
    if img.mode == 'RGBA':
        bpp = 32
    else:
        img = img.convert('RGB')
        bpp = 24

    entries = []
    img_data = []

    for s in SIZES:
        resized = img.resize((s, s), Image.LANCZOS)

        if bpp == 32:
            # RGBA → BGRA（ICO 需要）
            r, g, b, a = resized.split()
            resized = Image.merge("RGBA", (b, g, r, a))

        buf = io.BytesIO()
        resized.save(buf, format="BMP")
        xor_data = buf.getvalue()[14:]  # 去 BMP 文件头

        # AND mask: 1bpp，每行 4 字节对齐
        and_row_size = ((s + 31) // 32) * 4
        and_mask = b"\x00" * (and_row_size * s)

        frame = xor_data + and_mask
        entries.append(struct.pack(
            "<BBBBHHII",
            0 if s == 256 else s,
            0 if s == 256 else s,
            0,        # color palette
            0,        # reserved
            1,        # planes
            bpp,      # bits per pixel
            len(frame),
            0,        # offset placeholder
        ))
        img_data.append(frame)

    # 计算偏移
    header_size = 6 + 16 * len(SIZES)
    offset = header_size
    final_entries = []
    for entry, data in zip(entries, img_data):
        vals = list(struct.unpack("<BBBBHHII", entry))
        vals[-1] = offset
        final_entries.append(struct.pack("<BBBBHHII", *vals))
        offset += len(data)

    with open(ico_path, "wb") as f:
        f.write(struct.pack("<HHH", 0, 1, len(SIZES)))
        for e in final_entries:
            f.write(e)
        for d in img_data:
            f.write(d)

    return os.path.getsize(ico_path)


if __name__ == "__main__":
    assets = os.path.join(PROJECT_ROOT, "assets")
    for name, ext in [("icon", "jpg"), ("titlebar_icon", "jpg")]:
        src = os.path.join(assets, f"{name}.{ext}")
        ico = os.path.join(assets, f"{name}.ico")
        if not os.path.exists(src):
            src = os.path.join(assets, f"{name}.png")  # 回退 PNG
        size = make_ico(src, ico)
        print(f"  {name}.ico ← {os.path.basename(src)} → {size:,} bytes ({len(SIZES)} sizes)")
    print("Done.")
