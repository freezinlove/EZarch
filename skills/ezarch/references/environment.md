# 按需准备工具环境

随库 Python 工具的安装与启动方法。已有兼容环境可以复用，纯 SVG 文本生成无需安装 EZarch 或 Blender。

## 随库环境

从 SKILL.md 所在目录确定 `<skill>`。安装器使用 uv、Python 3.12 和锁文件，在用户的受管总目录准备依赖，不替换系统 Python。相同依赖锁内容、平台和 extras 复用同一依赖环境，只有 skill 自身版本号变化不重建依赖；启动器从当前安装的 src 加载代码，避免多个副本串用代码。旧 skill 内 `.venv` 仍可使用，不自动搬动或删除。

```sh
# macOS；路径含空格时保留引号
sh "<skill>/scripts/bootstrap.sh" --profile core --home "<工具总目录>"
"<bootstrap 返回的 python>" "<skill>/scripts/run.py" doctor
```

```powershell
# Windows
powershell -File "<skill>/scripts/bootstrap.ps1" -Profile core -RuntimeHome "<工具总目录>"
& "<bootstrap 返回的 python>" "<skill>/scripts/run.py" doctor
```

| 安装配置 | 实际准备的能力 |
|---|---|
| core | 参考读取、独立二维 Drawing、resvg 静态 SVG 预览、PDF、几何计算与排版助手 |
| model | core + Blender、网格与 Rhino/DAE 交换库 |
| draft | core；独立二维无需三维内核 |
| render | core + 检测或安装 Blender；不自动安装 CadQuery |
| all | 建模与渲染依赖 |
| dev | Python 开发和测试依赖；用于维护仓库 |

配置增量安装。首次准备依赖需要网络；已有 Blender 4.5 或更新版本会优先复用，但仅安装配置中的 4.5 LTS 属于已选测试版本，较新版本的具体操作仍需实际验证。缺少可用程序时下载固定版本并校验。支持 Windows x64、macOS x64/arm64；平台支持不等于本次已在全部平台运行。随库字体可直接使用文件；只有显式 `--install-font` / `-InstallFont` 才注册到系统。

位置优先级：显式 home、`EZARCH_HOME`、用户配置、平台默认目录。Windows 没有位置偏好时，在首次下载前要求指定目录；不擅自选盘。小配置保存在 `%LOCALAPPDATA%/EZarch/settings.json` 或 macOS 的 `~/Library/Application Support/EZarch/settings.json`，可用 `EZARCH_CONFIG` 改位置。工具、Python、缓存和可控临时文件均跟随总目录；不承诺第三方程序或系统零占用 C 盘。

`python -m ezarch.runtime status` 只读取位置；`configure <目录>` 验证可写性并记住位置，不搬迁旧内容。更换总目录后可重新 bootstrap，旧环境保留至新环境成功；不直接移动含绝对路径的 venv。位置内的 state 保存环境绑定、锁和失败原因。`runtime register-tool oda|blender|uv <可执行文件>` 可登记已有工具供多个安装副本复用，不复制或搬迁软件；安装入口也会登记成功使用的程序。登记仅说明路径存在，Blender 版本及具体操作仍按实际探测，已失效路径不复用。下载采用有限重试、完整性校验和临时文件替换；依赖准备失败不覆盖前一个成功绑定。可选 Blender、ODA、字体分别返回状态，某项失败不会把其他就绪项写成失败。

默认环境不安装 CadQuery/OCCT/VTK；独立 legacy-cad extra 服务于未继续维护的旧接口，不由 bootstrap 启用，确需调用时另行准备兼容环境。rhino3dm 安装包要求 macOS 14+。指定原生依赖使用 wheel，避免在用户电脑临时编译。Blender 使用自己的 Python，外围库留在独立环境。

`scripts/run.py` 查找当前安装绑定的环境，兼容旧 `.venv`。其他兼容环境也可以安装 Python 包后运行 `python -m ezarch.cli` 或导入 API。`doctor` 返回版本、位置和小型实际操作结果；`environment.probe_capability(name)` 可只探测 cad/pdf/geometry/model 中一项，不触发安装。

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
