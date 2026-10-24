---
name: ezarch
description: Tools and drafting knowledge for turning architectural and spatial design ideas into editable drawings, models, diagrams and visualizations. Use when creating or revising architectural plans, sections, elevations, site or interior layouts, 3D models, renderings or presentation graphics, or working with architectural drawing conventions. Supports new work from a natural-language brief and edits based on DWG/DXF/3DM/BLEND/PDF/image/web references.
---

# EZarch

EZarch 是供 AI 开展建筑与空间设计时使用的制图、建模与表达工具 skill。它帮助 AI 把设计意图转成可编辑的图纸、模型和视觉表达，并支持读取参考、延续既有工程、查看实际结果和继续修改。

## 用途与提供的帮助

适用于建筑方案的绘制与修改、场地和室内空间表达、平立剖图、三维建模、分析图、渲染及图文排版，也适用于其中一项局部操作。任务可以从自然语言需求开始，也可以基于已有图纸、模型、PDF、图片或网页参考；不需要用户先指定软件、准备配置或提供 CAD 文件。

它提供三类可以直接取用的支持：

- **作图与文件操作**：读取和定位原对象、绘制与标注、建模与剖切、格式转换、预览和排版。AI 可以调用随库助手，也可以编写项目脚本，使用 ezdxf、Blender bpy、SVG 等原生能力。
- **可编辑的几何与表达资源**：门窗、家具、墙面、楼梯、电梯、柱和轴网等现有组件，以及字体和制图样式。组件返回可修改实体，几何、放置和表达分开，便于接入当前项目，减少重复编写基础绘图代码。
- **制图知识与看图支持**：单位、比例、线型、尺寸、字体、坐标与格式边界，适用规范的查询入口，以及支持参考理解、设计推敲、方案比较和问题发现的视图操作与视觉判断提示。

设计构思、布局、参考取舍和成果表达仍由 AI 结合本次需求决定；这些工具承接其选择的方法。目标是让 AI 更容易把自己的想法准确画出来、看清楚、继续改。

重要设计或实质改动前，简洁说明准备怎样设计、主要依据和取舍，让用户能纠正理解；是否继续推进取决于已有授权和关键不确定性，不另设审批阶段。

## 按需发现能力

下面按能力分类，没有调用顺序；只展开当前需要的说明。工具页给出接口、输入输出与接入位置，知识页解释图形所承载的专业关系。现有资源可以局部取用、组合或与原生工具混用。

### 读取资料与继续修改

| 所需能力 | 入口与用途 |
|---|---|
| 读取文件、查找对象、理解参考 | [inspect / query](references/file-understanding.md)：源文件索引和预览；[参考与尺度](references/design-reference.md)：来源、尺度与采用依据 |
| 选页、选对象、临时高亮、替换与对照 | [参考及局部操作](references/reference-views-editing.md)：接收 PDF 或现有 DXF 对象，输出选定视图、几何或文档副本 |
| 延续已有 CAD / 3DM / BLEND / SVG | [原生编辑](references/edit-existing.md)：按对象修改，保留原文件中未涉及的内容与资源 |

### 二维绘制与可编辑组件

| 所需能力 | 工具与相关知识 |
|---|---|
| 画线面、文字、尺寸与符号 | [Drawing](references/geometry-drawings.md)：新建 DXF 或绑定已有布局；[尺寸端点](references/text-dimensions.md#端点与原生尺寸)：对齐、投影与原生标注 |
| 画墙、交接与开洞 | [墙面区域](references/wall-regions.md)：路径加厚、布尔与切割；[墙柱关系知识](references/wall-column-grid-relationships.md) |
| 画门窗、家具和设备 | [门窗](references/editable-components.md#门窗接口) · [家具](references/editable-components.md#家具接口与方向)：参数化局部几何与方向；[门窗表达知识](references/door-window-representation.md) · [家具与使用空间](references/furniture-spatial-relationships.md) |
| 画楼梯、电梯、柱与轴网 | [楼梯与电梯](references/vertical-components.md) · [柱和轴线](references/grids-columns.md)；[楼梯电梯知识](references/stairs-and-lifts-representation.md) · [柱网关系知识](references/wall-column-grid-relationships.md) |
| 放置或改变组件表达 | [组件接入](references/editable-components.md#接入正在使用的画图方式)：写入现有 DXF、Drawing 或 Canvas；[表达样式](references/editable-components.md#同一几何的表达)：共享几何的彩色与线稿 |
| 画场地、道路、植物与流线 | [场地图元](references/site-symbols.md)：返回可编辑组件；[总平面知识](references/site-plan-representation.md) · [地图、太阳与影长](references/site-analysis.md) |
| 变换坐标、量取或填色 | [坐标变换](references/coordinate-transforms.md) · [面积与区域填色](references/area-regions.md) · [局部截面与包络](references/spatial-measurement.md) |

### 建模、图像与版面

- **模型与剖切**：[Blender / bpy](references/blender-modeling.md) 提供脚本运行与模型操作；[模型出图](references/geometry-drawings.md#blender-模型剖切与投影) 输出可编辑投影；[剖切与投影知识](references/sections-and-projections.md) 解释建筑表达。
- **渲染与素材**：[渲染和生成式图像](references/rendering.md)、[公开素材](references/public-assets.md)、[Blender 扩展](references/blender-ecosystem.md)。
- **分析图与排版**：[Canvas / SVG / board](references/diagrams-boards.md) 接入几何、PDF、图片和文字；[字体与排版](references/typography.md) 说明选字形、富文本和可编辑性；[字体测量](references/text-dimensions.md#字体发现与字形依据) 返回字形信息与包络。

### 制图依据与视觉判断

- [制图表达](references/chinese-drafting.md)：图纸用途、比例、表达深度及随库样式；[规范适用](references/standards.md)：查询适用依据。构件与场地知识直接链接在对应工具旁。
- [视觉理解与判断](references/viewing-editing.md)：理解参考、推敲与比较方案、主动发现图面异常、选择视图并确认修改效果；包含实际取图入口。

### 运行环境与文件

- [环境与接入方式](references/environment.md)：运行独立命令、在项目 Python 脚本中导入 API、复用依赖与排查安装。
- [格式交换](references/exchange-verification.md) 说明转换与信息保留边界；[文件整理](references/delivery.md) 操作明确选择的文件，提供批量转换、PDF 合订和 ZIP 打包。
- [位置与更新](references/storage-updates.md)：项目与工具分开存放、安装副本更新与回退。

## 使用边界

源文件事实、推断与新增设计值应区分，未知尺寸不能冒充精确复原。参考的选择和采用方式依问题而定，参考本身不会证明方案合理。制图规范需要对应地区、用途、阶段与实际条文。

图面效果与问题排查主要依靠 AI 视觉阅读实际图纸和模型。制作与修改时，结合任务主动留意尚未被指出的异常，观察范围不能只由刚写的代码、已知问题或检查项决定；看图提示见上表。测量只说明所选对象的几何关系，文件能打开、命令成功都不能证明设计合理；不提供设计审查脚本或通过判定。

项目资料、脚本、素材和成果放在项目目录中，skill 目录用于可复用工具。随库支持 Blender、开放 Python 工具及可选 ODA；生成式图像不保证精确尺寸，网格不等于 NURBS/BRep。旧 [project.yml 接口](references/project-data.md) 仅为兼容入口，model/views/draft 依赖非默认 legacy-cad，已停止维护。
