# 墙面区域与显式洞口

`ezarch.wall_regions` 提供路径加厚、边界墙带、区域合并、裁剪和显式开洞。输入选定几何，返回 Shapely 区域，不读写源文件。

墙厚基准、转折交汇、共用墙与真实分缝的关系见 [墙、柱与轴网的关系](wall-column-grid-relationships.md)。

## 输入与接口

坐标和所有长度参数使用同一个调用者选择的单位。支持有限、有效、非空的 XY 直边几何；不隐式投影 Z/M、吸附坐标、关闭缝隙、过滤小面或调用 make_valid。无效输入报错并保留源对象。以下是当前小助手的接口范围；曲线、非对称偏移及其他构造可使用原生 Shapely、ezdxf 或自写算法，不必改写需求来适配这些接口。

| 接口 | 几何含义 |
|---|---|
| `wall_region(path, width=..., cap=..., join=..., mitre_limit=5)` | LineString、LinearRing 或 MultiLineString 两侧各 width/2 加厚。cap 显式选择 flat/square，join 显式选择 mitre/bevel；交汇处取实际面域并集。mitre_limit 是 GEOS 尖角延伸比，不是建筑标准。 |
| `wall_band(region, inside=..., outside=..., join=..., mitre_limit=5)` | Polygon/MultiPolygon 的外扩区域减去内缩区域。偏移非负且至少一项大于零；所有边界都参与，包括内孔。内缩可能吞掉窄区域，返回实际几何，不保证内部一定保留空腔。 |
| `opening_region(start, end, depth=..., offset=0)` | 两端限定跨度，垂直方向厚度为 depth 的矩形切割面；正 offset 沿 start→end 的左侧移动中心。跨度、深度和偏移均显式给出，不从门窗符号、名称或墙厚猜测。 |
| `compose_wall_regions(regions, cuts=None, clip=None)` | regions 是本次选择的 `局部来源ID:区域` 映射，至少一项；可选 cuts 同样映射，clip 是区域。该函数的数学定义是合并所选区域、与 clip 求交、扣除 cuts 并集。此计算次序属于函数语义，不规定任务工作顺序，也不要求建立全项目 ID 体系。 |

所有函数返回新结果，不改输入。返回区域可以直接用于原生布尔运算、测量或绘制。`compose_wall_regions` 返回的 `WallComposition` 包含：

- `geometry`：本次实际剩余墙面。全被切掉、裁剪范围不相交或只有边界接触时可为空面；不把零面积线点当墙面。
- `by_source`：各所选来源经过相同裁剪和扣除后的面域。它们可以重叠，面积不可直接相加；不表示自动识别出的独立墙体。
- `cut_effects`：每个切割面与裁剪后、扣除前面域的交集，可能含零面积接触；重叠切割面的影响不可重复累加。
- `removed`：实际扣除的面域；`clipped_out`：由 clip 排除的面域；`unused_cuts`：本次未切掉任何面积的切割 ID，包括仅接触边界的情况。

浅切会保留为浅切，未切中的洞口会保留其 ID，不扩大、不延伸、不声称已贯穿。结果解释了所给几何发生什么，不判断墙体构造、洞口用途、通行净宽、结构或建筑合理性；这些仍由 AI 结合需求和证据判断。

## 转成可编辑图元

`ezarch.symbols.polygon_symbol(geometry, *, unit_mm, role="outline", fill=None)` 将有效 Polygon/MultiPolygon 的坐标乘以 unit_mm 转为局部 mm；unit_mm 是每输入单位的 mm 数。不居中、不移原点，几何本来含平移时该平移仍在。空面返回无图元的 Symbol。生成直边 LWPOLYLINE 轮廓与可选实心 HATCH，内孔是真实内环；原生曲线填充可另用 ezdxf。

`fill` 是调用者定义的填充角色；与 `role` 的表达由 [SymbolStyle 与 place_symbol](editable-components.md#几何表达与目标文档) 决定。原生实体可直接编辑、写入自选图层/块或自行导出；不自动覆盖旧墙、编号、加门窗或创建成果文件。也可跳过 Symbol，直接使用 Shapely 结果或已有 Drawing 接口。

## 来源与验证边界

路径双侧加厚、合并、裁剪及显式门窗矩形扣除来自小学 CAD 修订；边界内外偏移墙带同时来自住宅底图重建。提取保留几何运算，去掉项目坐标、固定 240/300 mm 厚度、门窗推断、楼层策略及调用编排。住宅原脚本另有精度网格、小面删除、buffer 补缝等修复行为，这些没有移入本模块。

维护验证分别记录与历史成果的实际面域对照，以及新接口的角部/交汇、不同厚度、旋转与单位、孔洞、部分/未命中/重叠切割、空结果和原对象保留测试。历史复现不等于所有几何或构造已验证，生成成功也不代表图纸完整或设计合格。私有图纸、项目脚本与验证产物不随 skill 分发。
