# -*- coding: utf-8 -*-
"""ICO 尺寸合并工具 — 双击运行，选择多个 .ico 文件，合并所有尺寸为一个 .ico。"""
import struct
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from collections import OrderedDict


def _real_size_from_frame(raw: bytes) -> tuple[int, int, int]:
    """从 ICO 帧数据中读取真实宽高和 bpp。
    优先从 BMP DIB 头读取，失败则返回 (0, 0, 0)。
    """
    if len(raw) < 40:
        return (0, 0, 0)
    # 检查是否是 PNG 压缩（ICO 帧可能存 PNG）
    if raw[:8] == b'\x89PNG\r\n\x1a\n':
        # PNG: IHDR 在偏移 8 处，前 8 字节是长度和 'IHDR'
        if len(raw) >= 24:
            w = int.from_bytes(raw[16:20], 'big')
            h = int.from_bytes(raw[20:24], 'big')
            # PNG bpp 从 IHDR 第 9 字节（颜色类型）推断
            color_type = raw[24]
            bpp = 32 if color_type in (2, 6) else 24
            return (w, h, bpp)
        return (0, 0, 0)
    # BMP DIB 头：偏移 0=DIB 大小(4B), 4=width(4B), 8=height(4B), 14=bpp(2B)
    try:
        dib_size = struct.unpack_from("<I", raw, 0)[0]
        w = struct.unpack_from("<i", raw, 4)[0]
        h_raw = struct.unpack_from("<i", raw, 8)[0]
        h = abs(h_raw)  # height 可能为负（top-down）
        bpp = struct.unpack_from("<H", raw, 14)[0]
        return (w, h, bpp)
    except Exception:
        return (0, 0, 0)


def read_ico_sizes(path: str) -> OrderedDict:
    """读取 ICO 的所有尺寸帧，返回 {(w, h, bpp): raw_bytes}。
    优先从帧内 BMP/PNG 头读取真实尺寸，兜底用目录条目。
    """
    frames = OrderedDict()
    with open(path, "rb") as f:
        data = f.read()
    if len(data) < 6:
        return frames
    reserved, img_type, count = struct.unpack_from("<HHH", data, 0)
    if reserved != 0 or img_type != 1:
        return frames
    for i in range(count):
        off = 6 + i * 16
        if off + 16 > len(data):
            break
        w, h, colors, res, planes, bpp_dir, fsize, foffset = struct.unpack_from(
            "<BBBBHHII", data, off
        )
        if foffset + fsize > len(data):
            continue
        raw = data[foffset : foffset + fsize]

        # 从帧数据读取真实尺寸（更可靠）
        rw, rh, rbpp = _real_size_from_frame(raw)
        if rw > 0 and rh > 0:
            w, h, bpp = rw, rh, rbpp
        else:
            # 兜底：使用目录条目值
            w = 256 if w == 0 else w
            h = 256 if h == 0 else h
            bpp = bpp_dir

        key = (w, h, bpp)
        if key not in frames:
            frames[key] = raw
    return frames


def merge_ico_files(file_paths: list[str], output_path: str) -> tuple[int, list[str]]:
    """合并多个 ICO，返回 (尺寸数, 详情列表)。"""
    all_frames = OrderedDict()
    details = []

    for fp in file_paths:
        for key, raw in read_ico_sizes(fp).items():
            if key not in all_frames:
                all_frames[key] = raw
                w, h, bpp = key
                details.append(f"{os.path.basename(fp)}: {w}×{h} @ {bpp}bit")

    if not all_frames:
        return 0, []

    sorted_keys = sorted(all_frames.keys(), key=lambda k: (k[0], -k[2]))
    header_size = 6 + 16 * len(sorted_keys)
    entries, img_data, offset = [], [], header_size

    for w, h, bpp in sorted_keys:
        raw = all_frames[(w, h, bpp)]
        entries.append(struct.pack(
            "<BBBBHHII",
            0 if w == 256 else w, 0 if h == 256 else h,
            0, 0, 1, bpp, len(raw), offset,
        ))
        img_data.append(raw)
        offset += len(raw)

    with open(output_path, "wb") as f:
        f.write(struct.pack("<HHH", 0, 1, len(sorted_keys)))
        for e in entries:
            f.write(e)
        for d in img_data:
            f.write(d)

    return len(sorted_keys), details


class IcoMerger:
    """最小化 GUI：选文件 → 合并。"""

    def __init__(self):
        self.files: list[str] = []
        self.root = tk.Tk()
        self.root.title("ICO 尺寸合并工具")
        self.root.geometry("520x420")
        self.root.resizable(True, True)
        self.root.minsize(420, 320)

        # 顶部按钮
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill="x", padx=12, pady=(12, 4))

        tk.Button(btn_frame, text="选择 ICO 文件", command=self._select_files,
                  height=1, width=14).pack(side="left", padx=(0, 6))
        tk.Button(btn_frame, text="清空列表", command=self._clear,
                  height=1, width=10).pack(side="left", padx=(0, 6))
        tk.Button(btn_frame, text="合并为 merged.ico", command=self._merge,
                  height=1, width=18, bg="#3b82f6", fg="white").pack(side="left")

        # 文件列表
        list_frame = tk.Frame(self.root)
        list_frame.pack(fill="both", expand=True, padx=12, pady=(6, 0))

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        self.listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set,
                                  font=("Microsoft YaHei", 9))
        self.listbox.pack(fill="both", expand=True)
        scrollbar.config(command=self.listbox.yview)

        # 状态栏
        self.status = tk.Label(self.root, text="就绪 — 请选择 .ico 文件",
                               anchor="w", fg="#78716c", font=("Microsoft YaHei", 9))
        self.status.pack(fill="x", padx=12, pady=(4, 8))

        # 支持拖拽（仅 Windows）
        try:
            from tkinterdnd2 import DND_FILES
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<Drop>>", self._on_drop)
        except ImportError:
            pass

        self.root.mainloop()

    def _select_files(self):
        paths = filedialog.askopenfilenames(
            title="选择 ICO 文件",
            filetypes=[("ICO 图标文件", "*.ico"), ("所有文件", "*.*")],
        )
        if paths:
            for p in paths:
                if p not in self.files:
                    self.files.append(p)
            self._refresh_list()

    def _on_drop(self, event):
        # 解析拖放的文件路径
        raw = event.data
        # tkinterdnd2 格式: {path1} {path2} ...
        import re
        dropped = re.findall(r"\{([^}]+)\}|(\S+)", raw)
        for g1, g2 in dropped:
            p = g1 or g2
            if p.lower().endswith(".ico") and p not in self.files:
                self.files.append(p)
        self._refresh_list()

    def _clear(self):
        self.files.clear()
        self.listbox.delete(0, "end")
        self.status.config(text="列表已清空")

    def _refresh_list(self):
        self.listbox.delete(0, "end")
        for fp in self.files:
            self.listbox.insert("end", os.path.basename(fp))
        self.status.config(text=f"已选择 {len(self.files)} 个文件")

    def _merge(self):
        if not self.files:
            messagebox.showwarning("提示", "请先选择 ICO 文件。")
            return

        script_dir = os.path.dirname(os.path.abspath(__file__))
        output = os.path.join(script_dir, "merged.ico")
        output = filedialog.asksaveasfilename(
            title="保存合并后的 ICO",
            initialdir=script_dir,
            initialfile="merged.ico",
            defaultextension=".ico",
            filetypes=[("ICO 图标文件", "*.ico")],
        )
        if not output:
            return

        n_sizes, details = merge_ico_files(self.files, output)
        if n_sizes == 0:
            messagebox.showerror("错误", "所选文件中没有有效的 ICO 尺寸。")
            return

        # 显示结果
        result = "\n".join(details[:20])
        if len(details) > 20:
            result += f"\n... 等共 {len(details)} 条"

        self.status.config(
            text=f"✅ 合并完成 — {n_sizes} 个尺寸 — {os.path.getsize(output)/1024:.0f} KB"
        )
        messagebox.showinfo(
            "合并完成",
            f"输出: {os.path.basename(output)}\n尺寸数: {n_sizes}\n文件大小: {os.path.getsize(output):,} bytes",
        )
        try:
            os.startfile(script_dir)
        except Exception:
            pass


if __name__ == "__main__":
    IcoMerger()
