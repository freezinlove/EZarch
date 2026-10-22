# EZarch

**面向 AI 的建筑与空间表达工具指南。** 提供模块化的工具操作知识、Windows/macOS 基础设施和适用的技术制图参考。用户需求、参考内容和模型判断决定怎么设计、分析、绘制和交付；skill 提供帮助，不规定固定的制作流程。

AI 可主动参与构思与设计。对于重要设计或实质改动，通常先简洁说明主要意图与取舍，让用户了解准备怎么做；说明后的行动由用户要求、已有授权和关键不确定性决定，不设统一的方案审批阶段。用户明确的合作偏好优先，具体原则见 [Skill 入口](skills/ezarch/SKILL.md)。

## 按需使用

| 需要的能力 | 可选工具 |
|---|---|
| 二维 CAD / 技术线稿 | ezdxf，独立 Drawing |
| 三维建模 / 场景 / 渲染 / 合成 | Blender Python、BMesh、Geometry Nodes、适用社区插件和资产 |
| 图像构思 / 探索 / 素材 / 表现 | 宿主可用的生成式图像工具；不保证精确几何或跨视角一致 |
| 模型剖切 / 正交可见线 | Blender 求值网格 + 可选几何与二维助手 |
| 地图 / 分析图 / 图表 / 自由版式 | 原生 SVG、项目脚本、可选 Canvas/PDF 合成 |
| 技术制图参考 | 适用的尺寸、轴线、标高、索引、比例等规则 |
| 格式交换 | DWG/DXF、原生 3DM、网格 3DM/DAE、GLB、BLEND |

可以只用一个模块、直接调用原生 API、修改辅助脚本或完全绕过封装。已有文件和脚本可以继续使用。没有固定 task.yml、project.yml、quality.yml、四维验收表或全格式交付要求。辅助工具的参数约定只在调用该工具时生效。

名称与描述帮助发现 skill；[入口导航](skills/ezarch/SKILL.md#按需发现能力) 按当前需要连接已有工具和知识；相关参考再展开调用方法、参数和局限，无需先读完整手册。新增能力时同步相应导航和参考，未实现的能力不列为可用。

正常输入是 DWG、3DM、图片、PDF、链接和自然语言需求，用户无需预转换或填写配置。AI 可按需查阅 [读取定位](skills/ezarch/references/file-understanding.md)、[设计判断](skills/ezarch/references/design-judgment.md)、[规范适用](skills/ezarch/references/standards.md) 与 [连续修改](skills/ezarch/references/edit-existing.md)。成果的精度、深度、可编辑性和视觉要求以本次用途为准，讨论、草图和成品可以采用不同表达；工具成功日志不是设计质量证明。

## 安装与基础设施

可安装内容全部位于 **skills/ezarch**；复制或通过 skill 安装器安装整个目录。入口为 [SKILL.md](skills/ezarch/SKILL.md)。已有可用环境或纯 SVG 脚本可以直接使用；需要随库依赖时，AI 可按需运行：

```sh
# macOS，仓库根目录；model / draft / render / all 也是可选 profile
sh skills/ezarch/scripts/bootstrap.sh --profile core
```

```powershell
# Windows
powershell -File skills/ezarch/scripts/bootstrap.ps1 -Profile core
```

core 含独立二维、参考提取、分析和排版助手；draft 保持独立二维；model 增加 Blender 与网格/3DM 交换库；render 检测或安装 Blender；all 安装建模与渲染能力。安装配置增量生效，不修改系统 Python。具体操作和其他运行入口见 [环境说明](skills/ezarch/references/environment.md)。这些安装项不意味着任务需要使用所有工具。

包含 rhino3dm 的建模环境要求 macOS 14 或更高版本；Windows 目标为 x64。原生 Python 依赖使用预编译安装包，Windows 和 macOS 的自动测试结果见本仓库 Actions。

分发包含脚本、Python 源码、依赖锁、轻量二维规则和开放仿宋字体；运行依赖按目标机器准备。三维模型、PBR 与 HDRI 从公开可读可下载来源按项目获取，不捆绑素材库。字体、图块和样式可按用户要求选择，仿宋不是所有图面的指定字体。

## 兼容与技术边界

DWG/DXF 通过可选免费闭源 ODA 转换器双向适配。随库重点支持 Blender 原生三维能力，rhino3dm 保留原生对象读取/局部修改；Blender 可导出网格 3DM、GLB 和 DAE。Rhino 曲面导入通常需要文件内的显示网格，缺失网格的复杂 BRep 不能保证完整转换；网格不冒充 NURBS/BRep。旧 CadQuery/STEP 路线目前未继续维护，需要独立 legacy-cad 依赖，不由默认安装启用。商业应用控制、SKP 写入和 IFC 未提供随库适配；这不限制任务使用其他可用工具。

Blender 保留工程单位，几何快照和二维助手使用 mm，GLB 显式转换为 m；自由 SVG、地图或其他程序不必采用同一坐标体系。图纸缩放、字体和转换损失见 [格式说明](skills/ezarch/references/exchange-verification.md)。开放库回读不等于在目标商业软件中实际打开验收。

原生入口可直接运行用户/AI 的脚本：`blender run <script.py> --source <existing.blend> --save <result.blend> --out <dir>`；无 source 时从空场景开始。`blender extract/export/view` 为可选网格交换和出图助手，见 [建模操作](skills/ezarch/references/blender-modeling.md)、[模型出图](skills/ezarch/references/geometry-drawings.md) 与 [社区接入](skills/ezarch/references/blender-ecosystem.md)。完整场景可继续直接使用 bpy，不要求统一 schema。

`audit` 可按单文件或所选输出检查结构、单位和几何。旧 `review` 是依赖既有记录的可选兼容助手。技术检查不裁定设计、规范合规或审美。

## 仓库维护

以下命令用于维护工具，不是用户项目的工作步骤：

```sh
sh skills/ezarch/scripts/bootstrap.sh --profile dev
EZARCH_TEST_BLENDER=1 skills/ezarch/.venv/bin/python -m pytest -q tests
skills/ezarch/.venv/bin/ruff check --config ruff.toml skills/ezarch/src skills/ezarch/scripts tests tools
skills/ezarch/.venv/bin/python tools/package_skill.py --out ../EZarch-dist
```

发布配置仅覆盖 Windows/macOS，自动检查结果见本仓库 Actions。开发验证、用户资料、下载素材和项目成果位于库外；项目规划和实施记录保留在本地，不随仓库发布。

ZIP 的公开文件由 `tools/skill-files.txt` 明确列出；wheel 的文件在 `pyproject.toml` 中逐项指定。增加发行文件时更新相应清单。打包不扫描额外项目文件，所选文件及其父目录中的软链接/Windows junction 会被拒绝；这些维护配置不参与用户作图流程。

## License

代码为 **AGPL-3.0-or-later**，见 [LICENSE](LICENSE)。字体及第三方依赖保留各自许可，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。仓库不含商业 CAD 安装包、付费模型或参考案例原图。
