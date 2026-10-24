# 可编辑组件与表达资源

组件以 Python 函数返回可编辑的 `Symbol`，内部是原生 DXF 图元；没有独立的家具图片或整套布局模板。几何构造、放置和表达分开，接入已有文档时才返回该文档中的实体。

本页可直接查 [门窗接口](#门窗接口)、[家具接口与方向](#家具接口与方向)、[共同放置方式](#接入正在使用的画图方式) 和 [样式](#同一几何的表达)。其他组件沿用同一 Symbol：见 [墙面](wall-regions.md)、[楼梯电梯](vertical-components.md)、[柱](grids-columns.md)、[场地图元](site-symbols.md)。

## 接入正在使用的画图方式

`from ezarch.symbols import place_symbol, Symbol, SymbolStyle, color_style, linework_style`；源码见 [symbols.py](../src/ezarch/symbols.py)。导入及项目脚本运行见 [环境接入](environment.md#命令与项目脚本)。下表各放置入口都复制组件几何，原 Symbol 可再次使用。

| 目标 | 接口 |
|---|---|
| 已有 DXF | `place_symbol(symbol, layout, style=..., unit_mm=..., origin=..., rotation_deg=..., mirror_x=...)`；返回可继续修改的 Placement。 |
| Drawing | `drawing.symbol(symbol, style=..., origin=..., rotation_deg=..., mirror_x=...)` 返回 Placement；origin 为 Drawing 目标坐标，单位沿用 Drawing。新建 Drawing 的默认 save 会显示这些实体；绑定模式由源 doc 保存。 |
| Canvas / SVG / PDF | `canvas.symbol(symbol, origin=..., scale=..., style=..., rotation_deg=..., mirror_x=...)` 返回内部毫米 CAD 中的 Placement；origin 为纸面 mm，scale 为比例分母。返回实体可继续编辑，save 时重新渲染。组件保持 CAD 的 X 向右、Y 向上，自动映射到画布 Y 向下；返回锚点不包含纸面平移或比例。 |
| 自写矢量脚本 | 可将放置后的 CAD 用 `cad.plot(..., formats={"svg"})` 导出并组合；或直接取 Symbol.parts 的原生曲线。 |

Canvas 也可用 `canvas.cad(doc, origin=..., scale=..., layout_name="Model", handles=None, region=None, padding=1)` 放置完整 CAD 或选定局部；原点表示 CAD 的 (0,0) 在纸面的位置。文档需声明单位；padding 为纸面 mm 的留边，避免裁掉边界笔画。CAD 转出的 SVG/PDF 保留矢量路径，文字转轮廓；可编辑文字可留在 CAD 或直接使用 Canvas.text。

## 几何、表达与目标文档

`Symbol` 保存局部 mm 的原生 `parts`；每项有 `entity`、`role` 和是否为填充的 `fill`。保留 LINE、带 bulge 的 LWPOLYLINE、ARC、CIRCLE、ELLIPSE、实心 HATCH。`path/rect/line/segment/ellipse` 可独立构造几何，`polygon(outer, holes=(), role="outline", fill=None)` 提供直边外环和真实孔洞，`add(entity, role, fill=...)` 复制单个原生图元。自定义输入应是有限 XY 平面几何；该入口不导入复杂块、字体或外部资源。其他对象可直接使用 ezdxf 导入或绘制。

`place_symbol(symbol, layout, *, style, unit_mm, origin=(0,0), rotation_deg=0, mirror_x=False, layer="0", role_layers=None, role_linetypes=None)` 将组件复制到已有 modelspace、paperspace 或 block：

- 几何使用局部 mm，`unit_mm` 是每目标单位的 mm 数；`origin` 使用目标坐标。局部原点先放在指定位置，方向由局部 X 取反的镜像和逆时针旋转确定；镜像在旋转之前。没有任意拉伸，也不从图纸单位猜测纸空间或块内单位。
- 需要 R2004+ 以保存真彩色。目标图层须已存在，原定义、可见性和既有对象均不覆盖；新实体使用显式颜色、纸面线宽和连续线型。`role_layers/role_linetypes` 可把实际使用的角色映射到已有图层/线型，缺失资源报错且不写入部分实体。线型长度沿用目标文档单位和原生比例设置，不自动换算纸面虚线；被冻结的图层仍冻结。没有自动保存、出图或把生成内容登记到项目模型。
- 返回 `Placement.entities` 原生可编辑实体、逐实体对应的 `roles`、目标坐标的 `anchors`、四角 `nominal_envelope` 和可交给 [frames](coordinate-transforms.md) 的二维仿射 `transform`。可以自行放进块，再用原生 INSERT 复用。
- `Symbol.nominal_bounds` 是尺寸包络；家具不一定填满它，门扇、门框、窗台线也可能伸出门窗名义跨度。`geometry_bounds()` 是原生轮廓的轴向范围，椭圆范围沿用 ezdxf 的曲线近似。**两者都不是精确占地区域或合规净距**；真实轮廓保留在返回的曲线中。
- 直接编辑原生实体后，构造时的锚点和尺寸元数据不会自动更新。调用者可改元数据、重新构造或自行测量。`Drawing.furniture` 是旧的简化图形接口；详细组件用下方 symbol 入口。

## 同一几何的表达

`color_style()` 返回随库柔和色板；`linework_style(outline_mm=.18, detail_mm=.09, seam_mm=.05, glass_mm=.13)` 返回真黑线条、无填充的表达。两者都返回可修改的 `SymbolStyle(strokes, fills)`：`strokes` 按角色映射 `(RGB, 纸面线宽mm)`，`fills` 按材质角色映射 RGB。空 `fills` 跳过所有 HATCH，非空映射需覆盖用到的填充角色；描边角色缺失会报错。颜色接受 `#RRGGBB` 或 0..1 RGB 三元组，线宽须能用 DXF 有限档位准确表达。

同一个 `Symbol` 可以用不同表达放置，曲线、尺寸、零部件和位置计算不变。样式可修改或替换，也可添加角色。黑白线稿保留所有原轮廓，原先被填色遮住的交叠线可能显露；表达切换不做自动消隐或几何改写，需删线时可编辑实际实体。

## 门窗接口

`from ezarch.symbols import door_symbol, window_symbol`；返回局部 mm 的 Symbol，放置方法见 [共同接口](#接入正在使用的画图方式)。洞口、框扇、开启方式、分格及尺寸口径见 [门窗知识](door-window-representation.md)。

| 接口 | 几何参数与边界 |
|---|---|
| `door_symbol(width, *, leaf_thickness, frame_width, frame_depth, opening_angle_deg=90, frame=True, leaf=True, swing=True)` | 单扇平开门；铰点 `(0,0)`，关闭端 `(width,0)`，正角逆时针开启、负角顺时针，范围 ±180°。框、扇、弧可分别启用。门框中心在跨度两端，扇沿开启方向，弧为原生 ARC。锚点 `hinge/closed_end/leaf_end`；width 是铰点跨度，不保证等于净通行宽度。 |
| `window_symbol(length, *, frame_depth, end_inset, rail_inset, mullions=(), mullion_width=0, inner_offsets=(), sill_offsets=())` | 局部 X 沿窗长，Y 跨墙厚；框外横线在 ±frame_depth/2，端框位置由 end_inset 决定，横线端部由 rail_inset 决定。inner_offsets 为框内附加横线的 Y 坐标，sill_offsets 为全长窗台线的 Y 坐标；mullions 显式给出分格中心 X，mullion_width 给双线间距。不按长度猜分格数。锚点 `start/end/center`。 |

这两个函数提供单扇平开门和直线窗框几何；其他构造可用 Symbol 或原生 API 组合。墙面洞口另由 [切割接口](wall-regions.md) 处理，编号与尺寸用 Drawing 或原生标注。门扇扫掠几何见 [空间测量](spatial-measurement.md)。

## 家具接口与方向

`from ezarch.furniture import furniture_symbol, chair_symbol, desk_symbol, shelf_symbol`；源码见 [furniture.py](../src/ezarch/furniture.py)。`furniture_symbol(kind, width, depth, **details)` 返回 Symbol，外尺寸和细节尺寸均为局部 mm，原点在尺寸包络左下角，含 `origin/center` 锚点。项目位置与朝向交给 [放置接口](#接入正在使用的画图方式)，函数本身不安排房间布局。

| kind | 显式细节 / 资源方向 |
|---|---|
| `bed` | 必填 `mattress=(宽,长)`、`pillows`；床头在 +Y，枕头数不由床宽推断。 |
| `sofa`、`lounge` | 必填 `seats`，可选 `arm_width`；靠背在 Y=0，前侧在 +Y。 |
| `bench` | 必填 `seats`；沿 X 排坐垫，几何自身不安排周边通道。 |
| `dining_chair`、`task_chair` | 靠背在 Y=0，坐面向 +Y；保留圆角、扶手或五爪结构。 |
| `table`、`coffee`、`side_table`、`nightstand` | 桌体轮廓与细节，不附椅子；床头柜拉手在 +Y。 |
| `wardrobe`、`cabinet`、`counter`、`tv` | 必填 `modules`；tv 另需 `screen_width`。柜门和把手向 +Y；可选 `mirror`（柜上镜面线，不是几何镜像）及 `fittings`。 |
| 柜体的 `fittings` | `(类型, (xmin,ymin,xmax,ymax))` 的集合，坐标在柜体局部 mm 中；当前类型为 `sink/hob/dishwasher`，不识别的类型报错，不静默换成别的设备。 |
| `fridge`、`desk`、`washer`、`vanity`、`wc`、`bathtub` | 保留历史构造细节。desk 是带笔记本细节的桌面资源；wc 水箱在 Y=0，盆前向 +Y；浴缸长边沿 X。并非厂商产品规格。 |
| `shower` | 必填 `opening=(start,end)`，开口沿 X、位于 +Y 边；不从绝对坐标转换、不夹紧越界输入或偷偷替换开口。 |

另外三个独立入口：`chair_symbol(width,depth,back_inset=...)` 是座面和背线，背在 +Y；`desk_symbol(width,depth,computer=False)` 是桌面及可选显示器，不附椅子；`shelf_symbol(width,depth,divisions=...,axis="x"或"y")` 显式选择分隔数量与方向。它们也返回 Symbol。

改变外尺寸会重算圆角、把手、缝线和配件等对应关系，不是非等比缩放；某些小尺寸放不下细节会报错。床垫、枕头、座位、模块和配件在生成时校验，返回后可继续编辑原生几何。有效尺寸不保证满足生产、人体工学或规范要求。


## 来源与验证口径

门的框、扇与弧以及桌椅、书架原型来自一次小学 CAD 修订任务；窗框/分格同时参考住宅建筑底图修订中的已用代码。详细家具与彩色色板来自住宅任务后期家具表达代码。提取的是可编辑几何，未移入项目坐标、房间摆放、图纸编号、按长度猜数量及整图处理顺序。代码随本库许可发布；不包含私有项目图纸或第三方商品模型，运行不依赖作者目录。

历史原型经过项目使用；新尺寸与组合仍需查看实际几何。维护测试覆盖单位、旋转、镜像、表达切换与原生回读，不证明设计布置或产品规格。
