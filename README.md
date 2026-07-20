# Multifunctional-Mathematics (MF-Math)

多功能数学计算与可视化桌面应用 · A powerful desktop application for mathematical computation and visualization

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)

---

## Features 功能

### Computation 计算 (14 modes 种模式)

Basic Arithmetic · Algebra · Calculus · Analytic Geometry · Sequences · Linear Algebra · Probability & Statistics · Numerical Analysis · Number Theory · Real Analysis · Functional Analysis · Complex Analysis · Algebraic Topology · Measure Theory

> 基础运算 · 代数 · 微积分 · 解析几何 · 数列 · 线性代数 · 概率统计 · 数值分析 · 数论 · 实分析 · 泛函分析 · 复分析 · 代数拓扑 · 测度论

### Visualization 绘图 (7 modes 种模式)

2D Functions · Polar Coordinates · 3D Surfaces · Complex Domain Coloring · Vector Fields · Freeform Geometry · Fractal Exploration

> 2D 函数 · 极坐标 · 3D 曲面 · 复数域着色 · 向量场 · 自由几何构造 · 分形探索

### AI Assistant 智能助手

Streaming chat · Step-by-step derivations · Computation acceleration (DeepSeek / OpenAI / Ollama)

> 流式对话 · 步骤推导 · 复杂计算加速

### Tutorials 教程

18 interactive guided tutorials, from quick start to advanced topics

> 18 篇交互式引导教程，覆盖从快速入门到高级主题

## Installation 安装

```bash
pip install -r requirements.txt
```

## Usage 运行

```bash
cd MF_UI && python main.py
```

## Testing 测试

```bash
PYTHONIOENCODING=utf-8 python -m MF_Mathematics.tests.test_runner
```

## Project Structure 项目结构

```
MF_Mathematics/   # Math backend (12 sub-packages + core + utils + tests) 数学后端
MF_UI/            # Qt frontend (calc + plot + dialogs + keyboard) 前端界面
MF_AI/            # AI service (multi-provider + streaming) AI 服务
MF_Tutorial/      # Tutorial engine (18 YAML tutorials) 教程引擎
MF_User/          # Local user system 用户系统
MF_Online/        # Web math search 联网搜索
```

## Tech Stack 技术栈

Python 3.10+ · PySide6 · SymPy · NumPy · SciPy · Matplotlib · PyYAML

## License 许可证

[MIT](LICENSE)
