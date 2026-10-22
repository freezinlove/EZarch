# 几何与二维技术图纸

随库提供 [Blender 原生建模](blender-modeling.md) 操作知识与助手，二维 CAD 可直接使用 ezdxf，图解和排版可用 SVG/PDF。模块独立；是否从二维建模、从模型出图或共享参数，由任务决定。

## 独立二维

`ezarch.drafting.Drawing(bounds, scale, title, number, style=None, font=None)` 可输出同源 DXF/PDF/SVG/PNG。bounds、物体坐标以模型 mm 输入；scale 为比例分母，文字和笔宽用纸面 mm。方法包括 poly、text、axis、dimension、chain、level、north、section_mark、index、leader、furniture；签名见 src/ezarch/drafting.py。默认不添加图框或比例尺。样式、字体和组合由任务决定。

需要特殊线型、块、斜向/径向尺寸时直接用 ezdxf；修改已有 CAD 可保留原图层、块、布局和样式。见 [中国制图](chinese-drafting.md) 与 [连续修改](edit-existing.md)。

## Blender 模型剖切与投影

可直接写 bpy/几何算法，也可用 `blender view <source.blend> --spec <view.json> --formats dxf pdf --out <dir>`。支持 `--objects`、`--collections`、`--unit-scale-m`，筛选语义见建模文档。JSON 只配置这次可选视图助手，不是统一项目文件。

| 视图字段 | 此助手的含义 |
|---|---|
| id / kind | 输出名；plan、section、elevation、axon |
| scale / paper_mm / margin | 比例分母、可选纸幅与纸面边距；不静默缩放以适应纸张 |
| cut_z / floor_z | 平面剖切高度/下界，世界坐标毫米 |
| axis / at | section 的 x/y 方向与剖切坐标；默认 y 剖向 +y 看，x 剖向 -x 看 |
| normal / xdir / origin | 可覆写观察基准；normal 朝向观察者，xdir 为图面向右，origin 为世界毫米坐标；保留 normal 背侧几何 |
| exclude / exclude_ids | 排除类别/几何快照对象；也可在提取时直接筛选对象或集合 |
| tolerance_mm / crease_degrees | 网格顶点合并容差，默认 0.05 mm；特征边折角阈值，默认 25°，轮廓边独立识别 |
| max_triangles | 当前辅助算法计算量保护，默认 200000；可显式提高，或选择相关构件，不自动粗化模型 |
| drafting | 可选 Drawing 标注接口；也可导入生成 DXF 自行继续编辑 |

这个入口读取当前 viewport 求值三角网格，求平面交线并组闭合区域，对不透明表面做正交可见线计算。它不会自动读取 render-only 修改器，也不将玻璃自动视为透明投影；按图纸需要选对象。输出的 mesh-geometry.json 标明来源与容差。开放剖切轮廓会报告，不能把不闭合线条称为完整剖面。

网格曲线的精度由源细分、浮点坐标和计算容差共同决定。技术图应使用符合所需精度的模型，保留源曲线或设计参数；并检查关键控制点、开口、层高与输出比例。不同单位转换必须作用于真实坐标，不只是文字标签。

几何投影还需要按用途深化：门扇扫掠、楼梯折断、上方虚线、材质填充、轴网、尺寸和标高并不是网格切片自动决定的。辅助命令输出是可编辑图纸基础，完整度和适用规范由当前设计要求决定。艺术线稿不能单凭外观宣称精确 CAD。

## 既有兼容接口

旧 `model/views/draft <project.yml>`、geometry.Part 和 OCCT 投影代码目前未继续维护，依赖独立 legacy-cad extra；任何默认安装 profile 都不启用它。已有项目可以继续使用，其他任务也可在了解依赖与局限后按需选择；这里描述维护状态，不禁止精确实体或其他可用工具路线。详见 [可选参数接口](project-data.md)。
