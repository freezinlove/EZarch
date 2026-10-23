# 几何与二维技术图纸

随库提供 [Blender 原生建模](blender-modeling.md) 操作知识与助手，二维 CAD 可直接使用 ezdxf，图解和排版可用 SVG/PDF。模块独立；是否从二维建模、从模型出图或共享参数，由任务决定。

所选二维区域/路径的有效性、短边、回折及精确重复可用独立的 [几何观测与定位](geometry-diagnostics.md)。结果包含实际范围和未检查内容，诊断不修改源图，也不代替设计判断。

## 独立二维

门框、门扇、开启弧、窗框分格及家具的可编辑几何见 [组件与表达资源](editable-components.md)。生成、表达和放置可分开使用，原生曲线可直接修改；不自动切墙、配家具、标注或规定输出样式。

所选路径或边界生成墙面、区域合并与显式开洞见 [墙面与洞口](wall-regions.md)；梯段、折断线、方向标记及电梯局部几何见 [楼梯与电梯资源](vertical-components.md)。这些入口彼此独立，不要求按某个顺序调用。

`ezarch.drafting.Drawing(bounds, scale=100, title="", number="", margin=12, *, style=None, font=None)` 新建文档，可输出 DXF/PDF/SVG/PNG。bounds、物体坐标以模型 mm 输入；scale 为比例分母，文字和笔宽用纸面 mm。方法包括 poly、text、axis、dimension、chain、level、north、section_mark、index、leader、furniture；签名见 [drafting.py](../src/ezarch/drafting.py)。默认不添加图框或比例尺。样式、字体和组合由任务决定。

轴线、轴号、引折线与柱截面可按需取用 [独立资源](grids-columns.md)，既有 `Drawing.axis` 的行为保留。带文字/形状的复杂线型、块、斜向/径向尺寸等可直接用 ezdxf；修改已有 CAD 可保留原图层、块、布局和样式。见 [中国制图](chinese-drafting.md) 与 [连续修改](edit-existing.md)。

## 绘图属性与多格式表达

`Drawing.poly/line/rect`、`circle` 和 `text` 支持下述属性；这是这些助手的接口范围，原生 CAD、SVG、其他库与自写代码仍可独立使用。颜色、粗细、线型、孔洞及文字方向由调用者决定，没有固定建筑风格或必须导出的格式。

| 参数或能力 | 含义与支持边界 |
|---|---|
| `color`，`poly(..., fill=...)` | 可用 `#RRGGBB`、0..1 的 RGB 三元组、ACI 整数 1..255 或 `"BYLAYER"`。描边/文字默认继承图层；新建文档的默认图层保留原助手墨色，绑定模式保留所选源图层。`color=None` 不生成轮廓，`fill=None` 不填充；文字仍需颜色。RGB 写入真彩色，要求 R2004+；R2000 可用 ACI/图层继承，不静默近似或升级文件。ACI 7 在白色纸面按黑色解释。 |
| `width` | 纸面 mm；省略时继承图层线宽，显式值写入新增实体，不改图层。DXF 线宽有有限档位，不能准确保存的数值会报错并列出支持值，调用者可自行选择近似值；独立 Canvas 可用任意非负有限线宽。0 表示设备细线，PDF/DXF 保留 0，SVG 使用一个不随缩放变化的像素，不能用于精确物理线宽比较。 |
| `dash` | 以纸面 mm 交替给出正的线段/间隔长度；空值为实线，奇数长度数组重复成偶数。按目标单位换算并复用相同线型定义；同名但不同定义另取名称，明确指定的数组不会被原有轴线线型替代。新实体补偿当前 `$LTSCALE`，不改文档全局设置。之后改变全局比例、块 INSERT 缩放、纸空间视口线型设置或打印样式，仍会影响 CAD 显示。 |
| `poly(..., close=True, holes=...)` | points 为外环，holes 为内环集合；可单独控制轮廓和填充。返回外环、内环的原生多段线和 HATCH；无轮廓时仅 HATCH。CAD 中先画填充再画边界；返回元组仍先列边界、最后填充。SVG/PDF 使用真实多环填充，孔洞透出下方内容。自交、孔洞越界或重叠等无效区域报错，不自动修复几何。此接口接受直边二维环，曲线边界可用原生 HATCH。 |
| `text(..., size, align, rotation)` | size 为纸面大写字高，位置为该高度中线上的左/中/右锚点；rotation 为模型 Y 向上坐标中的逆时针角度。新建 Drawing 的 CAD 与 Canvas 使用同一所选字体，Canvas 按字体度量换算字号，并围绕同一锚点旋转；文字保留可编辑性。绑定模式使用已有文字样式。 |

`circle` 在 CAD 保留原生圆，SVG 使用 circle，PDF 使用矢量圆曲线，支持颜色、线宽与 dash。轮廓与填充属性分别写入文件，未显式修改的原实体及资源保持不变。

多格式对应指上述参数在所选格式中按同一含义保存；不承诺不同查看器、替代字体、打印配置、细线和曲线近似得到逐像素相同图像。文字定位已覆盖随库字体下的旋转与三种对齐；任意外部字体、SHX 替代及复杂排版需要相应检查。字体选择与交付说明见 [字体支持](chinese-drafting.md)。原生 DIMENSION 等组合对象的全部排版参数不属于本次属性映射范围。

新建 Drawing 同步记录的是绘制调用；后来直接修改返回的 CAD 实体、图层或样式，不会追溯修改已有 Canvas 内容。此时可从修改后的完整 CAD 原生渲染，或自行同步所需图形。绑定模式保持纯 CAD，不为新增内容建立虚假的整图预览。

## 绘制到已有文档

`Drawing.from_layout(layout, *, scale, unit_mm, style=None, text_style="Standard", dimstyle="Standard", resource_policy="rename")` 接收已附属文档的 ezdxf modelspace、paperspace 或 block。支持 DXF R2000 及以上；绑定不新建文档、不改变源单位或视口、不创建 Canvas，不要求完整项目数据。

- 几何点和半径使用目标自身坐标；`unit_mm` 是每目标单位的 mm 数，`scale` 是物理比例分母。纸面字高与符号尺寸乘 `scale / unit_mm` 后写入目标。不从 doc.units 猜测纸空间或图块单位；这两个参数由调用者按目标提供。
- `dimension/chain` 仍仅支持目标坐标中的水平/竖直尺寸；显示值和 `dimensions[].measured_mm` 按 mm，原生实测值仍是目标单位。尺寸样式长度按纸面 mm 解释，单个尺寸的 `dimscale` 按 `scale / unit_mm` 设置，避免既有全局缩放再次放大字高或遗漏文字间隙；源样式不变。`level` 的 `value_mm` 仍为 mm。其他单位标注与斜向尺寸可用原生接口。
- 新旧两种入口的绘制方法均返回本次新增的原生实体元组；`entities` 汇总该助手新增的目标实体，尺寸测量在 `dimensions`。尺寸的匿名图块等附属资源由 ezdxf 管理，不列入目标实体元组。返回对象可直接通过原生 API 调整。
- `text_style`、`dimstyle` 使用源文档已有定义；缺失时报错，不自动替换字体。所需图层/线型在绘制时创建。图层 `rename` 为同名冲突另取名称；`reuse` 明确沿用现有定义，均不覆盖源定义。同名图层被冻结或采用不同线宽时，复用即保留其状态；显式 dash 按数组取得匹配线型。
- `style` 仍可调整随库符号与笔宽默认值；颜色、线宽、虚线及孔洞参数见上文。返回原生实体可继续自由修改。
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
