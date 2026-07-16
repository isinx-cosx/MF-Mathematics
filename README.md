# Multifunctional-Mathematics (MF-Math)

多功能数学计算与可视化桌面应用。基于 Python + PySide6，覆盖 12 个数学分支。

## 功能

- **计算** — 代数/微积分/线性代数/概率统计/数值分析，26 种计算模式
- **绘图** — 2D 函数/3D 曲面/复数域着色/向量场/自由几何构造
- **AI 助手** — 流式对话、步骤推导、复杂计算加速（DeepSeek/OpenAI/Ollama）
- **教程** — 14 篇交互式引导教程

## 安装

```bash
pip install -r requirements.txt
```

## 运行

```bash
cd MF_UI && python main.py
```

## 测试

```bash
PYTHONIOENCODING=utf-8 python -m MF_Mathematics.tests.test_runner
```

## 项目结构

```
MF_Mathematics/   # 数学后端（12 子包 + 核心 + 工具）
MF_UI/            # Qt 前端（计算区 + 绘图区 + 对话框 + 键盘）
MF_AI/            # AI 服务（多供应商 + 流式 + 配置）
MF_Tutorial/      # 教程引擎（14 篇 YAML）
MF_User/          # 用户系统
MF_Online/        # 联网搜索
```

## 技术栈

Python 3.10+ · PySide6 · SymPy · NumPy · SciPy · Matplotlib
