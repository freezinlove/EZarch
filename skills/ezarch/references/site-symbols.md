# 场地、道路、植物与流线图元

入口与路径、种植与铺装、建筑轮廓和图面层次的关系见 [总平面知识](site-plan-representation.md)。这里的工具把已选定的点列、宽度和轮廓转成可编辑几何。

## 接入与接口

在项目脚本中导入 `from ezarch.site_symbols import route_symbol, direction_symbol, road_symbol, canopy_symbol`；源码见 [site_symbols.py](../src/ezarch/site_symbols.py)。各函数返回局部 mm 的 `Symbol`，沿用 [组件放置](editable-components.md#接入正在使用的画图方式) 接入已有 DXF、Drawing 或 Canvas。位置、旋转、颜色和线稿表达在放置时指定。

| 函数 | 输入与作用 |
|---|---|
| `route_symbol(points, *, head_length, head_width, start_arrow=False, end_arrow=True, role="outline", fill=None)` | 连接显式点列，按首末段方向绘制所选箭头。head 尺寸由调用者给出，不寻路或推断通行用途。 |
| `direction_symbol(direction, *, length, head_length, head_width, **kwargs)` | 按向量绘制方向箭头，可与文字或北针表达组合。向量先单位化，长度单独给出；kwargs 沿用 route_symbol 的表达选项。 |
| `road_symbol(points, *, left_width, right_width, join, fill=None, centerline=False)` | 路径两侧按显式宽度缓冲，平端封口；join 为 mitre/bevel/round。返回实际边界，可选择中心线，不求解道路转弯与交通安排。 |
| `canopy_symbol(*, radius=None, outline=None, trunk_radius=None, pit=None, fill=None)` | radius 与 outline 二选一，生成圆或指定多边形树冠，可选树干和显式树池边界；位置、树种与树距由设计提供。 |

铺装与场地分区可以把已有 Polygon/MultiPolygon 交给 [polygon_symbol](wall-regions.md#转成可编辑图元)，或在现有画布上使用 [fill_regions](area-regions.md#独立填色)，两者均保留真实孔洞。地图坐标与日影计算见 [场地分析](site-analysis.md)，文字和图例接入 [Canvas](diagrams-boards.md)。
