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
- **制图知识与看图支持**：单位、比例、线型、尺寸、字体、坐标与格式边界，适用规范的查询入口，以及实际图纸和模型的视图操作与视觉判断提示。

设计构思、布局、参考取舍和成果表达仍由 AI 结合本次需求决定；这些工具承接其选择的方法。目标是让 AI 更容易把自己的想法准确画出来、看清楚、继续改。

重要设计或实质改动前，简洁说明准备怎样设计、主要依据和取舍，让用户能纠正理解；是否继续推进取决于已有授权和关键不确定性，不另设审批阶段。

## 按需发现能力

下表按操作连接已有能力；需要某项操作时再展开相应参考，调用参数在源码与 `--help` 中。用途说明用于判断是否调用，操作细节按需读取。

| 当前操作 | 入口 |
|---|---|
| 选页提取、嵌套选择、临时视图或局部替换 | [读取与修改操作](references/reference-views-editing.md) |
| 读取原文件、定位对象或参考尺度 | [inspect / query、文件预览](references/file-understanding.md) · [参考与尺度](references/design-reference.md) |
| 绘制、标注或修改二维图纸 | [Drawing 与原生 CAD](references/geometry-drawings.md) · [编辑现有 CAD/3DM/SVG/BLEND](references/edit-existing.md) |
| 取用可编辑组件、切换彩色或线稿 | [门窗与家具、CAD/Canvas 放置](references/editable-components.md) · [楼梯与电梯](references/vertical-components.md) · [轴网与柱](references/grids-columns.md) |
| 构造墙面、开洞或处理区域 | [墙面与区域布尔操作](references/wall-regions.md) · [面积与填色](references/area-regions.md) |
| 换算坐标、量取几何或文字 | [坐标变换](references/coordinate-transforms.md) · [长度与字体](references/text-dimensions.md) · [局部截面与包络](references/spatial-measurement.md) |
| 建模、剖切、投影或渲染 | [Blender / bpy](references/blender-modeling.md) · [模型出图](references/geometry-drawings.md#blender-模型剖切与投影) · [渲染与图像](references/rendering.md) |
| 制作 SVG、分析图或版面 | [Canvas 与矢量排版](references/diagrams-boards.md) · [地图、太阳与影长](references/site-analysis.md) |
| 看清实际结果、继续修改 | [视图选择与视觉判断](references/viewing-editing.md) |
| 采用制图规范或查找技术依据 | [制图表达](references/chinese-drafting.md) · [规范适用](references/standards.md) |
| 获取素材、扩展工具或交换格式 | [素材](references/public-assets.md) · [Blender 扩展](references/blender-ecosystem.md) · [格式交换](references/exchange-verification.md) |
| 保存项目、管理安装副本 | [文件位置与仓库边界](references/storage-updates.md) |
| 准备运行环境或排查依赖 | [Windows/macOS 环境与命令入口](references/environment.md) |

## 使用边界

源文件事实、推断与新增设计值应区分，未知尺寸不能冒充精确复原。参考的选择和采用方式依问题而定，参考本身不会证明方案合理。制图规范需要对应地区、用途、阶段与实际条文。

设计判断依靠 AI 阅读实际图纸和模型；看不清时取得能回答问题的视图。测量只说明所选对象的几何关系，文件能打开、命令成功都不能证明设计合理。视觉提示见上表，不提供设计审查脚本或通过判定。

项目资料、脚本、素材和成果放在项目目录中，skill 目录用于可复用工具。随库支持 Blender、开放 Python 工具及可选 ODA；生成式图像不保证精确尺寸，网格不等于 NURBS/BRep。旧 [project.yml 接口](references/project-data.md) 仅为兼容入口，model/views/draft 依赖非默认 legacy-cad，已停止维护。
