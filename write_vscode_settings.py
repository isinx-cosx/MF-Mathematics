# encoding: utf-8
import json
import os

path = r"C:\Users\fsafsafsa\Desktop\Multifunctional-Mathematics\.vscode\settings.json"

settings = {
    "files.encoding": "utf-8",
    "files.autoGuessEncoding": True,
    "editor.fontSize": 14,
    "editor.fontFamily": "Consolas, 'Courier New', monospace",
    "editor.tabSize": 4,
    "editor.insertSpaces": True,
    "editor.renderWhitespace": "selection",
    "editor.bracketPairColorization.enabled": True,
    "editor.guides.bracketPairs": "active",
    "editor.suggestSelection": "first",
    "editor.minimap.enabled": True,
    "editor.scrollBeyondLastLine": False,
    # Python 设置
    "[python]": {
        "editor.defaultFormatter": "ms-python.python",
        "editor.formatOnSave": False,  # 避免缺少 formatter 时报错
        "editor.codeActionsOnSave": {
            "source.organizeImports": "explicit"
        }
    },
    # 文件关联
    "files.associations": {
        "*.py": "python"
    },
    # 资源管理器
    "explorer.confirmDelete": True,
    "explorer.confirmDragAndDrop": True,
    # 终端
    "terminal.integrated.defaultProfile.windows": "Command Prompt",
    "terminal.integrated.fontSize": 13,
    # 工作区
    "workbench.colorTheme": "Default Dark Modern",
    "workbench.iconTheme": "vs-seti",
    "workbench.startupEditor": "none",
    "workbench.settings.editor": "ui",
    # 搜索
    "search.exclude": {
        "**/__pycache__": True,
        "**/.git": True,
        "**/.vscode": True,
        "**/*.pyc": True
    }
}

with open(path, 'w', encoding='utf-8') as f:
    json.dump(settings, f, indent=4, ensure_ascii=False)

print("VS Code settings written OK")
