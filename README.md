# Multifunctional-Mathematics (MF-Math)

多功能数学计算与可视化桌面应用。基于 Python + PySide6，覆盖 14 个数学分支。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![tests](https://github.com/MF-Mathematics/MF-Mathematics/actions/workflows/tests.yml/badge.svg)](https://github.com/MF-Mathematics/MF-Mathematics/actions/workflows/tests.yml)

## 功能

### 计算（14 种模式）
基础运算 · 代数 · 微积分 · 解析几何 · 数列 · 线性代数 · 概率统计 · 数值分析 · 数论 · 实分析 · 泛函分析 · 复分析 · 代数拓扑 · 测度论

### 绘图（7 种模式）
2D 函数 · 极坐标 · 3D 曲面 · 复数域着色 · 向量场 · 自由几何构造 · 分形探索

### AI 助手
流式对话 · 步骤推导 · 复杂计算加速（支持 DeepSeek / OpenAI / Ollama）

### 教程
18 篇交互式引导教程，覆盖从快速入门到高级主题

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
MF_Mathematics/   # 数学后端（12 子包 + 核心 + 工具 + 测试）
MF_UI/            # Qt 前端（计算区 + 绘图区 + 对话框 + 键盘）
MF_AI/            # AI 服务（多供应商 + 流式 + 配置）
MF_Tutorial/      # 教程引擎（18 篇 YAML）
MF_User/          # 本地用户系统
MF_Online/        # 联网数学搜索
```

## 技术栈

Python 3.10+ · PySide6 · SymPy · NumPy · SciPy · Matplotlib · PyYAML

## 许可证

[MIT](LICENSE)
