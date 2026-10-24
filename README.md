# EZarch

让 AI 更容易把自己的想法准确画出来、看清楚、继续改。

EZarch 是供 AI 开展建筑与空间设计时使用的制图、建模与表达工具 skill。适用于从自然语言需求开始的新设计，也适用于既有图纸或模型的修改与深化，支持平立剖图、场地与室内空间表达、三维模型、分析图、渲染和排版。

它提供可调用的工具、可编辑组件、原生 API 操作知识、实际成果预览和制图依据，减少基础绘图与格式衔接的重复工作；设计构思、布局与视觉判断由 AI 结合用户需求和实际图纸完成。

## 结构与能力

仓库中的可安装 skill 位于 [skills/ezarch](skills/ezarch/SKILL.md)。SKILL.md 是简短导航，references 按操作展开，src 和 scripts 提供可直接调用的工具，assets 保存字体与轻量制图样式。tests、tools 和发布配置用于维护，不是用户项目流程。

- 绘图与修改：Drawing、ezdxf、原生 CAD/3DM/SVG/BLEND 操作。
- 几何资源：门窗、家具、墙面、楼梯、电梯、柱和轴网；生成与放置分开，返回可编辑实体。
- 看图与排版：当前 CAD 的 PDF/SVG/PNG 视图，Canvas 的 CAD/组件接入，Blender 视图和渲染。
- 工具知识：单位、坐标、尺寸、字体、规范依据、格式交换和素材接入。

具体调用从 [能力索引](skills/ezarch/SKILL.md#按需发现能力) 查找；看图提示见 [视图与视觉判断](skills/ezarch/references/viewing-editing.md)。不包含设计审查、碰撞判定、通行判定或自动验收程序；直接测量与技术错误提示保留。

## 安装与基础设施

可安装内容全部位于 **skills/ezarch**；复制或通过 skill 安装器安装整个目录。入口为 [SKILL.md](skills/ezarch/SKILL.md)。已有可用环境或纯 SVG 脚本可以直接使用；需要随库依赖时，AI 可按需运行：

```sh
# macOS，仓库根目录；model / draft / render / all 也是可选 profile
sh skills/ezarch/scripts/bootstrap.sh --profile core --home "<工具总目录>"
```

```powershell
# Windows
powershell -File skills/ezarch/scripts/bootstrap.ps1 -Profile core -RuntimeHome "<工具总目录>"
```

core 含独立二维、参考提取、分析和排版助手；draft 保持独立二维；model 增加 Blender 与网格/3DM 交换库；render 检测或安装 Blender；all 安装建模与渲染能力。安装配置增量生效；依赖、下载和可控临时文件位于用户选定的工具总目录，相同依赖可跨安装副本复用，不修改系统 Python。Windows 首次下载前需选位置，已有偏好继续沿用。具体操作和其他运行入口见 [环境说明](skills/ezarch/references/environment.md)，文件保护和轻量更新见 [安装与版本管理](skills/ezarch/references/storage-updates.md)。这些安装项不意味着任务需要使用所有工具。

包含 rhino3dm 的建模环境要求 macOS 14 或更高版本；Windows 目标为 x64。原生 Python 依赖使用预编译安装包，Windows 和 macOS 的自动测试结果见本仓库 Actions。

分发包含脚本、Python 源码、依赖锁、轻量二维规则和开放仿宋字体；运行依赖按目标机器准备。三维模型、PBR 与 HDRI 从公开可读可下载来源按项目获取，不捆绑素材库。字体、图块和样式可按用户要求选择，仿宋不是所有图面的指定字体。

## 兼容与技术边界

DWG/DXF 通过可选免费闭源 ODA 转换器双向适配。随库重点支持 Blender 原生三维能力，rhino3dm 保留原生对象读取/局部修改；Blender 可导出网格 3DM、GLB 和 DAE。Rhino 曲面导入通常需要文件内的显示网格，缺失网格的复杂 BRep 不能保证完整转换；网格不冒充 NURBS/BRep。旧 CadQuery/STEP 路线目前未继续维护，需要独立 legacy-cad 依赖，不由默认安装启用。商业应用控制、SKP 写入和 IFC 未提供随库适配；这不限制任务使用其他可用工具。

Blender 保留工程单位，几何快照和二维助手使用 mm，GLB 显式转换为 m；自由 SVG、地图或其他程序不必采用同一坐标体系。图纸缩放、字体和转换损失见 [格式说明](skills/ezarch/references/exchange-verification.md)。开放库回读不等于在目标商业软件中实际打开验收。

原生入口可直接运行用户/AI 的脚本：`blender run <script.py> --source <existing.blend> --save <result.blend> --out <dir>`；无 source 时从空场景开始。`blender extract/export/view` 为可选网格交换和出图助手，见 [建模操作](skills/ezarch/references/blender-modeling.md)、[模型出图](skills/ezarch/references/geometry-drawings.md) 与 [社区接入](skills/ezarch/references/blender-ecosystem.md)。完整场景可继续直接使用 bpy，不要求统一 schema。

## 仓库维护

以下命令用于维护工具，不是用户项目的工作步骤：

```sh
sh skills/ezarch/scripts/bootstrap.sh --profile dev --home "<工具总目录>"
# 使用 bootstrap 返回的 python 路径；旧 .venv 也仍可使用
"<环境 python>" -m pytest -q tests
"<环境 python>" -m ruff check --config ruff.toml skills/ezarch/src skills/ezarch/scripts tests tools
"<环境 python>" tools/package_skill.py --out ../EZarch-dist
```

发布配置仅覆盖 Windows/macOS，自动检查结果见本仓库 Actions。开发验证、用户资料、下载素材和项目成果位于库外；项目规划和实施记录保留在本地，不随仓库发布。

正式 ZIP 内含版本和逐文件摘要，使用时可轻提示新版；agent 可代办准备、启用和回退。启用后的 skill 需重新加载，自动更新偏好不会把下载完成误报为当前对话已换版。按版本标签发布的工作流已提供，只有实际发布后的版本才能被用户查询到。

ZIP 的公开文件由 `tools/skill-files.txt` 明确列出；wheel 的文件在 `pyproject.toml` 中逐项指定。增加发行文件时更新相应清单。打包不扫描额外项目文件，所选文件及其父目录中的软链接/Windows junction 会被拒绝；这些维护配置不参与用户作图流程。

## License

代码为 **AGPL-3.0-or-later**，见 [LICENSE](LICENSE)。字体及第三方依赖保留各自许可，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。仓库不含商业 CAD 安装包、付费模型或参考案例原图。
