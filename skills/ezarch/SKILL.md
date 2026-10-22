---
name: ezarch
description: Architectural design support and tools for reading, editing, drawing, modeling and visual expression. Use for architecture and spatial tasks from DWG/3DM/BLEND/PDF/image/link references, including design discussion, CAD edits, diagrams and visualization.
---

# EZarch

为建筑与空间任务提供可组合的读取、计算、绘制、建模、编辑、表达和交换能力，以及按需查阅的专业知识。目标、方法、工作顺序、表达深度与交付内容由用户需求和 AI 判断决定。可以只讨论、直接制作或局部修改；本 skill 不预设统一方案阶段、数据模型、成果类型或视觉风格。

支持 AI 主动参与构思与设计。对于将开展的重要设计或实质改动，通常先以适合当前任务的简洁表达，让用户了解主要意图、改动方向和重要取舍，便于纠正理解。表达可融入自然交流，不要求独立方案文档或固定内容结构。说明后是否直接推进，由用户要求、已有授权和关键不确定性决定；用户明确的合作偏好优先。具体交流与设计判断见 [设计支持](references/design-judgment.md#让方案能够被理解和判断)。

随库工具可独立使用或组合，也可沿用现有项目、直接调用原生 API、自写脚本或选择其他可用能力。工具与资源入口不是完整清单或优先顺序；可按任务查找其他资料与方法。专业参考说明属性、关系、判断依据和适用条件，代码与素材供直接取用；参数、单位和默认值只约束对应接口，不决定设计。

## 按需发现能力

按当前需要从下表选读相关参考，再按需查看命令帮助或源码签名；不必先读全部文档或运行环境检查。表中是已有入口与知识支持，操作细节和技术边界在对应参考中。命令的运行方式见 [环境入口](references/environment.md#操作入口)。

| 当前需要 | 已有能力或入口 | 按需查阅 |
|---|---|---|
| 理解参考、尺度与专业关系 | 资料依据、空间关系、测量与表达知识 | [参考与尺度](references/design-reference.md)、[设计关系](references/design-judgment.md#空间与使用关系) |
| 共同构思、说明意图、理解反馈 | 意图、依据与修改范围的信息关系；可选查询和预览入口 | [构思与交流](references/design-judgment.md#让方案能够被理解和判断)、[反馈与决定](references/design-judgment.md#反馈与决定的连续性) |
| 读取原文件、定位局部对象 | inspect / query；PDF、图片的 reference 提取 | [资料读取与查询](references/file-understanding.md) |
| 修改已有 CAD、3DM、SVG 或 BLEND | edit、ezdxf、rhino3dm、XML/DOM、bpy | [原生操作与连续修改](references/edit-existing.md) |
| 绘制二维图纸、尺寸与符号 | Drawing 新建或绑定已有 DXF；可调绘图属性、孔洞和文字定位；ezdxf | [几何与图纸](references/geometry-drawings.md) |
| 转换二维坐标、方向或纸面位置 | 独立仿射计算、逆变换与 Shapely 适配 | [坐标计算](references/coordinate-transforms.md) |
| 测量所选轮廓、定位几何疑点 | 只读区域有效性、短边、回折及精确重复检查；对象范围与裁图定位 | [几何观测与边界](references/geometry-diagnostics.md) |
| 三维建模、节点、场景编辑 | bpy / BMesh；blender run / extract | [Blender 操作](references/blender-modeling.md) |
| 从模型取得剖切、投影和可见线 | blender view 的可选网格出图助手 | [剖切与投影](references/geometry-drawings.md#blender-模型剖切与投影) |
| 适用规范、纸面比例与技术符号 | 依据查询、可选中国制图样式 | [规范适用](references/standards.md)、[制图表达](references/chinese-drafting.md) |
| 地图、环境或使用空间计算 | 太阳/影长、使用区、门扇扫掠与几何测量助手 | [地图与分析](references/site-analysis.md)、[空间测量](references/spatial-measurement.md) |
| SVG、分析图、图表或排版 | 原生 SVG、Canvas、diagram / board | [矢量与排版](references/diagrams-boards.md) |
| 材质、灯光、相机与图像表现 | bpy / render；宿主可用时的生成式图像 | [渲染与图像表达](references/rendering.md) |
| 获取素材、接入插件和节点资产 | asset 下载器、原生导入与社区接入知识 | [素材入口](references/public-assets.md)、[社区能力](references/blender-ecosystem.md) |
| 转换格式、回读或比较文件 | convert / blender export / audit / compare | [交换与检查](references/exchange-verification.md) |
| 准备或排查运行环境 | doctor、按需 bootstrap、现有兼容环境 | [Windows/macOS 环境](references/environment.md) |

## 来源、精度与支持范围

用户可直接提供原始文件和自然语言需求，AI 选择读取与必要转换。参考用途和接近程度按任务理解；源事实、推断与新增设计值分别表达。资料不足时说明实际缺口和影响，按 [读取不足](references/file-understanding.md#读取不够时) 处理；未知尺寸不冒充精确复原。修改既有工程时，用户最新文件及所选修改范围是依据，保留未涉及的内容。

原生图纸、可编辑模型、矢量图和图像按需选择。生成式图像可用于构思、探索、素材或表现，但不保证尺寸和跨视角一致，也不等于已建立 CAD/模型。设计、视觉、规范与技术检查的结论各有依据；工具执行成功只说明它实际验证的事项。“未发现问题”只适用于已检查范围；AI 可结合原始资料、设计意图和其他证据解释、补充或推翻候选判断。精细度和完成度以本次用途为准。

随库维护 Windows/macOS 的 Blender 与开放 Python 工具支持、字体及轻量二维符号；DWG 可使用外部免费闭源 ODA，3DM 可进行适用的原生编辑或网格交换。网格不等于 NURBS/BRep。旧 [project.yml 助手](references/project-data.md) 是可选接口，model/views/draft 依赖非默认的 legacy-cad；CadQuery/STEP 路线目前未继续维护，商业应用控制、SKP 写入与 IFC 未提供随库适配。这些支持事实不限制使用环境中其他可用工具。

skill 不捆绑大型素材库，也不依赖作者个人目录；用户已有素材及任务授权下可访问的其他来源均可按需使用。资料、项目脚本、素材和成果保存在项目中，仓库开发验证在库外进行。
