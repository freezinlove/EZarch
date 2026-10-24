# 所选区域的面积、覆盖与填色

面积、扣除与覆盖几何计算，以及独立区域填色。`from ezarch.measurements import measure_area, coverage` 接收 Shapely 几何，返回数值和区域；`from ezarch.diagrams import fill_regions` 把已有区域加入 Canvas。CAD 可用 [polygon_symbol](wall-regions.md#转成可编辑图元) 或 Drawing.poly 接续同一几何。

## 面积与扣除

源码：[`ezarch.measurements`](../src/ezarch/measurements.py)。`measure_area(boundary, *, unit_mm, exclusions=None, basis=None, source=None)` 接受有效二维 Shapely Polygon/MultiPolygon；`unit_mm` 为一个输入坐标单位对应的毫米数。boundary 允许空；exclusions 为可选的本次局部 ID → 非空区域映射，不要求对象属于房间或建筑类型。

结果保留 boundary、扣除后的 geometry、实际 removed、输入 exclusions、各项 effects 和 outside_exclusions，几何都使用输入单位。数值 boundary_area_m2、removed_area_m2、area_m2 是未主动舍入的平方米。原边界孔洞已不计入面积；扣除先求并集再与边界相交，不重复扣除相交的多个遮罩。各 effects 可能重叠，不能简单相加；界外遮罩不会减少边界面积。空结果可表示全部被扣除。

basis 和 source 原样深拷贝保存，可承载调用者选定的口径、文件版本或对象依据；不会据此认证“净面积”或法定建筑面积，也不自动跟踪来源变更。阳台、公区、墙柱等是否计入，取决于实际传入边界与扣除，不由函数名称推断。统计精度、展示舍入和汇总方式由调用者决定。

## 覆盖位置

`coverage(domain, regions, *, unit_mm)` 接受一个选定域和局部 ID → 区域映射。返回域内 covered、uncovered、overlap，各输入对象的 outside，以及 overlap_pairs、checked_ids、pair_count 和对应平方米数值。overlap 是所有正面积成对交集的并集；三重覆盖不会在该数值中重复累计。成对面积不能相加冒充重叠并集面积。只有边界接触时不记录面积重叠。

空选择返回零对象、零对比较及整个域未覆盖。结果没有总体通过字段；not_checked 说明未判断的用途、有意留白/叠放、未选对象及楼层坐标对应。uncovered 只是几何空缺，不自动命名、分区或填满。所有输入应位于调用者选定的同一平面；跨层、坐标转换或完整性解释可由 AI 另行处理。

这些运算不修改输入、不自动修复或吸附。无效、非二维或非有限几何报错；浮点叠置可能保留极小碎片，结果不是按建筑容差清理过的轮廓。是否需清理及其容差可另行选择，不能把数值噪声直接当作设计错误。

## 独立填色

源码：[`ezarch.diagrams.fill_regions`](../src/ezarch/diagrams.py)。`fill_regions(canvas, regions, *, colors, transform=None, stroke=None, width=.18)` 将选定区域加入已有 Canvas。regions 和 colors 以本次局部 ID 对应，每个区域明确给颜色；支持 Polygon/MultiPolygon 及透明孔洞。先核对整组选定几何、颜色和变换，再绘制，返回 ID → 新增 Canvas 图元元组，图元可继续编辑。

transform 是可选的六系数仿射变换，转换后的坐标为 Canvas 纸面 mm、Y 向下；未传时输入即为纸面坐标。可选用 [坐标工具](coordinate-transforms.md) 计算映射，函数不自动 fit、猜测比例或改变画布。stroke/width 采用 Canvas 颜色与纸面线宽语义。空选择不新增图元。没有隐式测量、房间分类、标签、标题、图表或文件导出。

画布大小、文字、保存位置和 formats 使用 [Canvas 独立能力](diagrams-boards.md)。原生 CAD 的区域填充可用现有 `polygon_symbol`/`place_symbol` 或 Drawing.poly，见 [组件资源](editable-components.md)，无需经过 Canvas。

## 来源和验证范围

区域差集、覆盖及带孔填充来源于住宅真实任务和既有生成器；去掉了固定退界/墙厚、房间类别映射、剩余区域归类、配色与页面策略。独立接口、单位/输入校验和作用范围记录是本轮补充。历史几何数值核对与通用旋转、孔洞、扣除并集、单位、空选择测试分别验证；它们不证明历史面积口径正确或任何项目必需这些分析。

## 旧项目数据接口

`ezarch.diagrams.generate_diagrams(project, out, level=None, *, kinds=None, formats=None)` 与 `diagram` 命令保留 project.yml 兼容；选项和输出见 [旧房间图例](diagrams-boards.md#旧房间图例接口)。kinds 空列表不输出文件，指定一项仅生成该图及报告，不删除历史文件。旧面积图标题为边界面积。

`brief` 的 interior_boundary_area_m2 与兼容别名 interior_net_area_m2 均未额外扣除；舍入和重叠行为见 [旧面积助手](design-reference.md#面积与重叠助手)，不作用于独立 measure_area。
