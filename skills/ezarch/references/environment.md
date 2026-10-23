# 按需准备工具环境

随库 Python 工具的安装与启动方法。已有兼容环境可以复用，纯 SVG 文本生成无需安装 EZarch 或 Blender。

## 随库环境

从 SKILL.md 所在目录确定 `<skill>`。安装器使用 uv、Python 3.12 和锁文件，在 skill 内建立 `.venv`，不替换系统 Python。

```sh
# macOS；路径含空格时保留引号
sh "<skill>/scripts/bootstrap.sh" --profile core
"<skill>/.venv/bin/python" "<skill>/scripts/run.py" doctor
```

```powershell
# Windows
powershell -File "<skill>/scripts/bootstrap.ps1" -Profile core
& "<skill>/.venv/Scripts/python.exe" "<skill>/scripts/run.py" doctor
```

| 安装配置 | 实际准备的能力 |
|---|---|
| core | 参考读取、独立二维 Drawing、resvg 静态 SVG 预览、PDF、几何计算与排版助手 |
| model | core + Blender、网格与 Rhino/DAE 交换库 |
| draft | core；独立二维无需三维内核 |
| render | core + 检测或安装 Blender；不自动安装 CadQuery |
| all | 建模与渲染依赖 |
| dev | Python 开发和测试依赖；用于维护仓库 |

配置增量安装。首次准备依赖需要网络；已有兼容 Blender 会被复用，否则下载官方 4.5 LTS 并校验。受支持的平台为 Windows x64、macOS x64/arm64；实际测试状态见仓库实施记录。安装器会准备随库仿宋字体，但选用其他工具或字体不依赖该字体。

默认环境不安装 CadQuery/OCCT/VTK；独立 legacy-cad extra 服务于未继续维护的旧接口，不由 bootstrap 启用，确需调用时另行准备兼容环境。rhino3dm 安装包要求 macOS 14+。指定原生依赖使用 wheel，避免在用户电脑临时编译。Blender 使用自己的 Python，外围库留在独立环境。

`scripts/run.py` 只是启动 skill 私有 `.venv` 的便捷入口。其他兼容环境也可以安装 Python 包后运行 `python -m ezarch.cli`，或直接导入需要的 API。`doctor` 返回环境状态，适合缺命令、版本或后端不确定时使用。

## 操作入口

`<python> <skill>/scripts/run.py --help` 列出独立命令；每个命令有自己的输入，不存在必须依次执行的总流程。例如：

```text
reference <PDF|image> --out <dir>
blender run <script.py> --source <existing.blend> --save <result.blend> --out <dir>
blender view <model.blend> --spec <view.json> --formats dxf pdf --out <dir>
render <scene.json|blend|glb> --camera <id|all> --out <dir>
board <board.yml> --formats pdf --out <dir>
```

各命令会在所选输出目录写执行记录，这是封装的副产物，不要求用户把它列入交付。真实项目、下载素材和生成文件使用项目目录；安装目录保存工具。

## 原始文件操作与 DWG 可选依赖

`inspect`、`query`、`compare`、`edit` 不依赖 project.yml，入口见 [读取定位](file-understanding.md)。3DM/网格索引需要 model Python 依赖；BLEND 索引需要 Blender。STEP 的旧索引未继续维护，依赖 legacy-cad。仅处理 DWG/DXF 时 core 加 ODA 即可，不需要 Rhino/AutoCAD/CadQuery。

AI 可运行 `bootstrap.sh --profile core --install-oda`；Windows 使用 `bootstrap.ps1 -Profile core -InstallODA`。安装器先检测已有程序，再从 ODA 官方页面取得对应安装包；macOS 在私有缓存复制签名应用，Windows 验证签名后尝试 MSI 提取，不捆绑安装包到仓库。可以通过 `EZARCH_ODA` 指定现有可执行文件。免费闭源 File Converter 与收费 ODA SDK 不同；系统权限、厂商许可或安装布局变化导致无法自动完成时，返回具体问题，不绕过系统保护。

转换本身不会为每个项目安装商业 CAD。文件取自不可信来源时，不执行其内嵌脚本；BLEND 读取禁用 autoexec。资料路径和诊断存放在用户项目中，不写入公共发布包。
