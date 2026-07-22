from PIL import Image

# 打开你的 PNG 图标（替换成你的文件名）
img = Image.open("titlebar_icon.png")

# 定义需要的尺寸（Windows 标准）
sizes = [
    (16, 16), (24, 24), (32, 32), (48, 48),
    (64, 64), (96, 96), (128, 128), (256, 256)
]

# 保存为多尺寸 ICO
img.save("titlebar_icon.ico", format="ICO", sizes=sizes)

print("✅ 多尺寸 icon.ico 已生成！")