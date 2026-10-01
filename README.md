# MF-Mathematics v2.0

新 UI、新数学库源码与编译结果同居一处的干净版本。

- 引擎（C++）与前端（Vue 3）、桌面宿主（C#）在**同一目录树**内，不再跨目录引用。
- 全部数学计算由 `mf_mathematics.dll` 完成（424 个已注册函数，C ABI：`math_call` / `function_exists`）。
  宿主与前端只负责界面与编排。
- 本目录自包含：源码 + 已编译好的引擎 DLL + 已填好的前端产物，`MFMath.exe` 可直接启动。

## 目录结构

| 路径 | 内容 |
| --- | --- |
| `MF_Mathematics/` | 数学库源码：**仅 C++**（`.cpp` / `.h` / `.hpp` + `CMakeLists.txt`），253 个文件 |
| `MF_Mathematics/build/bin/Release/` | **编译结果**：`mf_mathematics.dll` + 5 个运行时依赖 DLL（共 21.8 MB） |
| `MF_Mathematics/tests/` | 引擎自带的 C++ 测试与探针源码（13 个测试套件） |
| `MFMath.Host/` | C# 桌面宿主（WPF + WebView2）：`NativeEngine` 走 P/Invoke 调引擎，`MathBridge` 打通 JS↔C# |
| `MF_UI/MFMath.UI.Vue/` | Vue 3 + Vite 前端源码（不含 `node_modules`），`dist/` 为已构建产物 |

合计 365 个文件、约 24.5 MB。

## 构建（三步）

```powershell
$V2 = "C:\Users\fsafsafsa\Desktop\MVS知识库\Multifunctional系列\Multifunctional-Mathematics-v2.0"

# 1) 引擎
cmake -S "$V2\MF_Mathematics" -B "$V2\MF_Mathematics\build" -G "Visual Studio 18 2026" -A x64
cmake --build "$V2\MF_Mathematics\build" --config Release --target mf_mathematics

# 2) 前端（首次需 npm install）
npm install --prefix "$V2\MF_UI\MFMath.UI.Vue"
npm run build --prefix "$V2\MF_UI\MFMath.UI.Vue"

# 3) 宿主（--no-incremental 必加：增量构建会掩盖 SDK 不兼容等编译错误）
dotnet build "$V2\MFMath.Host\MFMath.Host.csproj" -c Release --no-incremental
```

宿主 csproj 用相对路径引用引擎产物与前端 `dist`：

- `..\MF_Mathematics\build\bin\Release\*.dll` → 拷进输出目录（`CopyToOutputDirectory=PreserveNewest`，**自动跟随**，不会出现"跑的是旧引擎"）
- `..\MF_UI\MFMath.UI.Vue\dist\**` → 拷成输出目录的 `wwwroot`

所以顺序必须是「引擎 → 前端 → 宿主」；只跑前两步不跑第三步，输出目录里还是旧的。

引擎依赖 Eigen 与 SymEngine，默认取 vcpkg 安装位置
（`C:/Users/fsafsafsa/vcpkg/installed/x64-windows`），可用 `-DMF_EIGEN_INCLUDE_DIR=` /
`-DMF_SYMENGINE_ROOT=` 覆盖。

## 运行

```powershell
# Release：从 wwwroot 加载已构建的前端
& "$V2\MFMath.Host\bin\Release\net10.0-windows\MFMath.exe"
# 或双击 MFMath.Host\启动 MFMath.bat
```

开发热更新：先在 `MF_UI\MFMath.UI.Vue` 下 `npm run dev`（Vite，端口 5173），
再运行 Debug 构建的宿主——Debug 指向 Vite dev server，不依赖 `wwwroot`。

## 验证

```powershell
# 引擎自带 C++ 测试
cmake --build "$V2\MF_Mathematics\build" --config Release
foreach ($t in Get-ChildItem "$V2\MF_Mathematics\build\bin\Release\test_*.exe") { & $t.FullName }

# 通用调用探针：不起宿主就能看引擎对某输入的真实返回
& "$V2\MF_Mathematics\build\bin\Release\probe_call.exe" --list      # 全部已注册函数
& "$V2\MF_Mathematics\build\bin\Release\probe_call.exe" --has solve_sym
```

## 与旧目录的关系

| 旧位置 | 说明 |
| --- | --- |
| `Multifunctional系列\Multifunctional-Mathematics\` | v1，混合了旧 Python/Qt 后端、旧 JS UI、构建缓存与多个产物目录（约 1.46 GB）。v2.0 从它里面只取走了 Vue 前端与引擎 C++ 源码。 |
| `cppcshap\MF_Mathematics\` | 引擎源码的原权威位置。其 `BUILD_AND_SYNC.md` 曾声明"cppcshap 是唯一权威"；v2.0 建立后权威位置即本目录 `MF_Mathematics\`，那个声明已过期。 |
| `cppcshap\MFMath.Host\` | 宿主源码原位置，其 csproj 原先跨树指向 `..\..\MVS知识库\...\MFMath.UI.Vue\dist`。 |

`cppcshap\MF_Mathematics\tools\sync-engine.ps1` 仍是把引擎 DLL 分发到各处消费方
（`MFMath.Host`、`MFMath.Test`、`demo_cs_mf`、`math-assistant` 等）的脚本；
它用自身位置推导引擎根目录，跨目录使用时注意它预设的消费方路径。

## 未纳入 v2.0 的内容

- **Python 数学后端**（各域下的 `.py`、`core/registry.py` 等）。旧 Python/Qt 应用与
  `math_http_service.py` 仍依赖它们，因此这些文件保留在 v1 目录，未删除。
- **准确性套件**（`tests/accuracy/`，2180 条用例，覆盖 424/424 函数）。按"仅 C++ 部分"
  的要求未复制进来，仍留在 v1 目录；它可对任意引擎 DLL 运行（用环境变量 `MF_ACC_DLL` 指定）。
- **6 个遗留 `.pyd` 扩展**（`numerical/*.pyd`、`linear_algebra/inner_product.dll`）属旧
  Python 混合架构产物，两棵树里都没有对应的构建脚本，未纳入。
- 旧 JS UI（`MFMath.UI`）、旧 Python/Qt UI、`MFMath.Downloader`、`MFMathShell`（练习脚手架）。
