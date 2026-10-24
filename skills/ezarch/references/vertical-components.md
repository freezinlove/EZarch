# 楼梯、电梯的局部几何资源

`ezarch.vertical_symbols` 返回局部 mm 的可编辑 `Symbol`，包含独立梯段、方向标记、折断线和电梯局部几何，沿用 [组件的表达与放置](editable-components.md)。

楼层连接、级数与踏面、井道与入口等专业关系见 [楼梯与电梯的空间关系及表达](stairs-and-lifts-representation.md)。

## 梯段、折断和方向

| 接口 | 显式几何与边界 |
|---|---|
| `stair_flight_symbol(width, run, treads=..., overhead_treads=(), side_edges=False)` | 局部 X 跨梯宽，Y 沿梯长。treads/overhead_treads 分别给出普通与上方踏步的 Y 位置，须在 `[0,run]` 内且彼此不重复；不按梯长或层高猜步数。普通线角色 outline，上方线角色 overhead；可选两条梯侧线。锚点 start/end 在两端中点。 |
| `stair_break_symbol(width, amplitude=..., notch_width=...)` | 四顶点折断标记，中心在 `(width/2,0)`；上下偏移为 ±amplitude，中间折点相距 notch_width。后者须小于 width；不自动擦除踏步或决定剖切位置。 |
| `direction_symbol(points, head_length=..., head_width=...)` | 折线箭杆加两条原生箭头边线；末段决定方向，head_width 为箭头全宽，锚点 tail/tip 对应起终点。各长度使用局部 mm。可用于楼梯以外的方向表达，不附“上/下”文字或推断路线。 |

梯段不附平台、梯井、扶手和标注；这些可以用 Symbol 的线/面方法、其他组件或原生 API 自行构造。折断线与梯段是独立几何，需要留空、裁切或另一种表达时由调用者处理。普通/上方线位置是输入含义，不证明真实级数、步高、净高或上下层对应关系。

现有彩色/黑白色板没有给 overhead 指定通用表达。可向 `SymbolStyle.strokes` 加入该角色的颜色和纸面线宽，并通过 `place_symbol(role_layers=..., role_linetypes=...)` 映射到已有图层、线型。线型长度保留目标文档单位、全局比例和原生 CAD 语义；不同单位、块缩放或打印设置仍会影响显示。这些映射不修改原资源，也不要求上方线一定使用某种虚线。

## 矩形电梯局部几何

`lift_symbol(width, depth, *, wall_thickness, car_bounds, entrance_side, entrance_span, panel_count, panel_depth, panel_inset, shaft=True, car=True, doors=True, shaft_fill=None)` 返回井壁、轿厢矩形和等分门板；三个开关可分别取用。参数仍按完整几何校验，关闭部件表示省略该部件，不提供建筑默认尺寸。

- 井外包络为 `(0,0,width,depth)`，wall_thickness 为各边井壁厚度。car_bounds 显式给出局部 `(xmin,ymin,xmax,ymax)`，须位于井内；这只是该构造的几何约束，不是设备选型净距标准。
- entrance_side 为局部 bottom/top/left/right，放置时再旋转/镜像；不按建筑类型猜朝向。entrance_span 在上下边沿 X、左右边沿 Y 给出低高坐标，位于两端井壁之间；井壁只在指定边扣除该跨度。
- panel_count 为正整数，门板沿跨度等分；panel_depth 为跨壁厚方向尺寸，panel_inset 从指定外边向内量。两者需落在井壁厚度范围内；这些是本函数的矩形板件位置参数，不代表所有电梯门构造。
- shaft_fill 可指定井壁填充角色；空值只有轮廓。全部描边使用 outline 角色，返回原生实体仍可单独调整。锚点为 origin、car_center、entrance_start/end/center，名义包络为井外边界。

可以只取其中的构件，也可在返回对象上改造或另行构造异形井、不同轿厢、门系统。工具不选择厂商设备、不补门厅或路线，不自动编号、标尺寸或保存文件，也不判定无障碍、消防和设备安装条件。

## 提取依据

梯段线、折断线、方向箭头及电梯轮廓原型来自小学 CAD 修订中的 `stairs_elevators` 与 `arrow`。原项目按楼层决定上下行标记，按长度/固定间距估计示意踏步，按建筑类型选井门朝向，并使用固定井壁、轿厢退距和门宽；这些决策没有移入资源。历史楼梯本来就是示意表达，不能称为经过真实层高、级数或设备核定的构造。

维护验证对照历史图纸保留的所选非文字几何，另测新接口的不同尺寸、四个局部入口边、角色映射、旋转、镜像、单位换算和原生 DXF 回读。复现项目原型与验证泛化接口分别记录，不推导成通用设计正确性。私有历史适配脚本与图纸不随 skill 分发。
