---
name: ezarch
description: Programmatic architectural drawings, Blender and Rhino models, model-based visualization, diagrams and layouts. Use for architectural design or editing from DWG/3DM/BLEND/PDF/image/link references, including native Rhino modeling through McNeel's official MCP with the user's chosen AI client.
---

# EZarch

帮助 AI 用程序化工具实现用户要求的建筑与空间表达。用户需求、参考内容及其使用意图决定目标；模型判断设计、分析、表达、工具组合和工作安排。工具的默认值和封装能力不决定成果的类型、风格或深度。

制作时建立、编辑实际图纸或模型，保留可继续编辑的源成果。三维透视、概念图和效果图也属于这个制作目标，通常由 Blender 模型与相机出图；二维任务可以直接使用 ezdxf、SVG 等，无需先建三维。本 skill 中生成式图像仅用于已完成设计成果的渲染替代，不代替构思、设计、作图或建模；使用边界见 [渲染](references/rendering.md#基于完成设计的生成式渲染)。

用户想在 Rhino 中建模、修改 Rhino 当前文档或通过自然语言操作 Rhino/Grasshopper 时，先读 [Rhino 官方 MCP](references/rhino-mcp.md)，检查现有连接；需要时按该流程从 McNeel 官方包源安装、协助用户连接其选定的 AI 客户端并启动会话。适用于不同客户端，不限定 Codex。仅离线读取/导出 3DM 时按文件接口处理，不因文件后缀启动应用或安装 MCP。

**Rhino 渲染出图的暂行限制：** Rhino 建模可正常开展，暂不默认由 AI 操控 Rhino 渲染出图。用户提出此要求时，先明确提示可能消耗大量 token、反复调试后仍无法完成，并建议不使用此方式、改由用户在 Rhino 中手动渲染。风险提示后，用户第一次明确坚持时再次简短提醒，等待第二次明确确认后才继续本次渲染任务；原始请求、建模授权或设计方案确认不能替代这两次确认。范围与执行方式见 [Rhino 渲染确认规则](references/rhino-mcp.md#rhino-渲染出图的暂行限制)。

对新创作、新设计，以及在已有成果基础上的修改，先向用户提出适合当前任务的详细的方案，待用户确认后实施。方案的内容、形式和详细程度，由用户需求、参考资料、项目特点及模型判断决定，不预设统一结构或必填内容。忠实复刻、复现可直接开展，以尽可能达到 1:1、细节完整一致为目标。

方案用于支持用户讨论与决策：围绕当前项目的关键问题，讲清依据、具体设计及其影响，让用户理解将做成什么、为什么这样做、哪些选择仍值得推敲。按决策所需展开，不能在关键问题尚未讲清时，仅凭简短摘要或一张图就索取确认。表达形式自由，图片辅助说明空间关系，关键论证在对话中讲清，见 [设计判断](references/design-judgment.md#让方案能够被理解和判断)。影响主要形象或空间的假设与制作方式在确认前讲清楚；具体细节仍可在已确认范围内深化。

资料读取与分析可先行；已确认的方案无需重复确认，用户明确要求跳过方案确认时按其授权处理。

依据提示词判断参考的作用和接近程度：空间方法、整体形象、材质氛围、表达风格或忠实复现可能各不相同。会导向明显不同成果且无法从上下文确定时再澄清；已明确的视觉相似要求不能自行降为抽象灵感，也不把每个参考都当作外形复制要求。指定资料读取不全时说明缺失及其影响；影响当前设计或验收依据时，取得用户对补充资料或按现有依据推进的选择，详见 [读取不足](references/file-understanding.md#读取不够时)。

模块供按需查阅，可以独立使用或组合。沿用现有项目、直接调用原生 API、修改辅助代码或另写脚本均可；不要求任务表、统一数据模型、固定流程、图量或交付包，也无需为未使用封装补写理由。具体接口的字段和单位只约束该接口。

列出的工具、网站与方法是起点，不是完整清单或优先顺序。根据任务可主动联网查其他资料、资源和官方接口，选用其他适合的程序化方法。

用户可直接提供原始文件与提示词。AI 负责读取、必要转换和工具选择，内部工作格式不由用户承担。修改已有项目时延续源文件的几何、对象及关系；用户提供的新版本优先于旧生成脚本。

理解、设计逻辑、适用规范、精度、必要细节和美感都属于成果要求。按本次阶段和用途做充分深化；概念表达不等于粗糙图形拼接，局部任务不必扩张成整套项目。源事实、推断与新增设计值分清，未知尺寸不能伪装成精确复原。

## 工具入口

| 当前需要 | 查阅内容 |
|---|---|
| 准备或排查环境 | [Windows/macOS 按需安装](references/environment.md) |
| 在 Rhino 建模、修改当前模型、连接或启动 Rhino/Grasshopper MCP | [Rhino 官方 MCP：检查、安装、连接与建模](references/rhino-mcp.md)；按需读 [客户端配置](references/rhino-mcp-clients.md) |
| 要求 AI 使用 Rhino 渲染出图，包括建模后出图 | 先执行 [暂行限制与两次风险确认](references/rhino-mcp.md#rhino-渲染出图的暂行限制) |
| 理解 DWG/3DM/PDF/图片/链接及定位对象 | [原始资料读取](references/file-understanding.md)、[参考与尺度](references/design-reference.md) |
| 设计、深化、判断空间与表达质量 | [建筑设计判断](references/design-judgment.md) |
| 三维建模、场景理解、节点与局部编辑 | [Blender 建模与操作](references/blender-modeling.md) |
| 新建 CAD、模型剖切、平立剖联动 | [几何与图纸](references/geometry-drawings.md) |
| 修改已有 DXF/SVG/BLEND，二维三维衔接 | [原生操作与局部修改](references/edit-existing.md) |
| 适用技术要求及制图表达 | [规范适用](references/standards.md)、[中国制图](references/chinese-drafting.md) |
| 地图、统计、环境或使用空间计算 | [地图与分析参考](references/site-analysis.md)、[空间测量](references/spatial-measurement.md) |
| SVG、分析图、图表或版面 | [矢量与排版](references/diagrams-boards.md) |
| 材质、灯光、相机或素材 | [Blender 渲染](references/rendering.md)、[公开素材入口](references/public-assets.md) |
| 插件、节点资产、社区工具接入 | [Blender 社区能力](references/blender-ecosystem.md) |
| 格式转换、单位、文件回读 | [交换与检查](references/exchange-verification.md) |

技术规范按地区、图种和阶段选用；模型依据本次要求判断设计、内容和视觉效果。运行成功、文件能打开或数值检查通过，只说明相应工具实际验证的事项。

未指定三维应用时以 Blender 原生 Python 为主，可以直接创建和继续编辑完整 .blend；用户指定 Rhino 时通过官方 MCP 调用 Rhino 原生 API。几何、节点、材质、灯光和表达方式由任务决定。按需复用社区插件及资产，也可自行编程，不受随库函数和默认值限制。旧 [project.yml 接口](references/project-data.md) 只用于已有兼容任务，不是新建模的入口要求。

## 基础设施范围

提供 Windows/macOS 的 Blender 与开放 Python 工具环境、字体及轻量二维符号；DWG 双向适配可选外部免费闭源 ODA。3DM 支持原生对象读取与局部编辑，以及适用的网格交换；网格不冒充 NURBS。Rhino 应用控制按需使用外部的 McNeel 官方 Rhino-MCP-Platform，需用户已安装并获许可的 Rhino、兼容运行时和支持本地 MCP 的客户端；本 skill 不捆绑 Rhino 或官方插件，也不自行替代官方桥接。CadQuery/STEP 主线、SketchUp/AutoCAD 应用控制与 IFC 暂缓。具体边界见格式说明。

三维素材按项目从公开可读取下载的来源获取；skill 不捆绑模型库或依赖个人素材目录。用户提供的模型和其他资料可直接使用。资料、素材与成果保存在项目中，仓库开发验证在库外进行。
