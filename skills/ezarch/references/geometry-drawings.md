# 几何与二维技术图纸

随库提供 [Blender 原生建模](blender-modeling.md) 操作知识与助手，二维 CAD 可直接使用 ezdxf，图解和排版可用 SVG/PDF。模块独立；是否从二维建模、从模型出图或共享参数，由任务决定。

## 独立二维

`ezarch.drafting.Drawing(bounds, scale=100, title="", number="", margin=12, *, style=None, font=None)` 新建文档，可输出 DXF/PDF/SVG/PNG。bounds、物体坐标以模型 mm 输入；scale 为比例分母，文字和笔宽用纸面 mm。方法包括 poly、text、axis、dimension、chain、level、north、section_mark、index、leader、furniture；签名见 [drafting.py](../src/ezarch/drafting.py)。默认不添加图框或比例尺。样式、字体和组合由任务决定。

需要特殊线型、块、斜向/径向尺寸时直接用 ezdxf；修改已有 CAD 可保留原图层、块、布局和样式。见 [中国制图](chinese-drafting.md) 与 [连续修改](edit-existing.md)。

## 绘制到已有文档

`Drawing.from_layout(layout, *, scale, unit_mm, style=None, text_style="Standard", dimstyle="Standard", resource_policy="rename")` 接收已附属文档的 ezdxf modelspace、paperspace 或 block。支持 DXF R2000 及以上；绑定不新建文档、不改变源单位或视口、不创建 Canvas，不要求完整项目数据。

- 几何点和半径使用目标自身坐标；`unit_mm` 是每目标单位的 mm 数，`scale` 是物理比例分母。纸面字高与符号尺寸乘 `scale / unit_mm` 后写入目标。不从 doc.units 猜测纸空间或图块单位；这两个参数由调用者按目标提供。
- `dimension/chain` 仍仅支持目标坐标中的水平/竖直尺寸；显示值和 `dimensions[].measured_mm` 按 mm，原生实测值仍是目标单位。尺寸样式长度按纸面 mm 解释，单个尺寸的 `dimscale` 按 `scale / unit_mm` 设置，避免既有全局缩放再次放大字高或遗漏文字间隙；源样式不变。`level` 的 `value_mm` 仍为 mm。其他单位标注与斜向尺寸可用原生接口。
- 新旧两种入口的绘制方法均返回本次新增的原生实体元组；`entities` 汇总该助手新增的目标实体，尺寸测量在 `dimensions`。尺寸的匿名图块等附属资源由 ezdxf 管理，不列入目标实体元组。返回对象可直接通过原生 API 调整。
- `text_style`、`dimstyle` 使用源文档已有定义；缺失时报错，不自动替换字体。所需图层/轴线线型在绘制时创建。`rename` 为同名冲突另取名称；`reuse` 明确沿用现有定义，均不覆盖源定义。同名图层被冻结或采用不同线宽时，复用即保留其状态。
- `style` 仍可调整随库符号与笔宽默认值。当前 `color/width/dash/fill` 在 DXF 与 Canvas 中的映射尚未完全一致：DXF 线条主要采用图层属性，dash 选择轴线线型，填充仍为外环且颜色为 ACI 7；可通过返回实体修改。不将绑定能力称为多格式样式一致性已完成。
- 绑定模式不使用 `Drawing.save()`；调用者用 `doc.saveas(...)` 保存完整文档，或按需采用原生渲染/转换。没有只包含新增内容的 Canvas 预览，也不会把它冒充源图完整预览。

位置或方向计算可单独使用 [二维坐标工具](coordinate-transforms.md)。绑定接口不自动转换整张图的坐标、旋转尺寸或处理任意实体 OCS，也不修改既有图元；绘制内容与调用组合由任务决定。

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
