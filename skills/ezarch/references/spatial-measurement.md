# 几何包络与局部截面

门扇扫掠、物体矩形包络和指定截面长度的计算。`from ezarch.analysis import swing_envelope, oriented_footprint` 返回二维点列；`from ezarch.measurements import measure_clear_width` 接收 Shapely 区域和截线，返回分段测量。这些值描述所选几何，不识别空间用途或判定通行、使用、合规。

## 包络

`swing_envelope(hinge, radius_mm, closed_angle_deg, opening_angle_deg=90)` 返回铰链门扫掠的多边形点列近似；坐标为 mm，角度从 +X 起按逆时针度数。点列可交给 Drawing.poly 或 Shapely Polygon。

`oriented_footprint(size_mm, position_mm, rotation_z_deg=0)` 返回以 position_mm 的 XY 为中心的四角点列。矩形包络、物体实际轮廓、运动范围和人的操作空间不是同一对象。源码见 [analysis.py](../src/ezarch/analysis.py)。

## 指定截面的宽度

`ezarch.measurements.measure_clear_width(region, section, *, unit_mm, obstacles=None, source=None)` 接收有效 Polygon/MultiPolygon、两个不同端点的 LineString 和可选 ID→障碍面域映射。unit_mm 是每坐标单位对应的毫米数。孔洞不计入区域，障碍按并集扣除。

返回自由区域、截面内部区间、边界接触和各障碍与截面的接触。每个区间有 start/end、沿截面的 stations_mm、span_mm、truncated 和位置范围。两端均受区域边界限定时 width_mm 为该段长度；截面端点仍在区域内部时 width_mm 为 None，避免将过短截面的观察长度当作完整宽度。多个区间分别保留，沿边界重合不计作内部宽度。

这个量只属于给定有限直线，不能推断全局最窄位置、人体能否通过或疏散条件。无效几何报错，空区域返回 empty_free_space；不吸附、移动或自动修复输入。

其他操作见 [面积与区域](area-regions.md)、[端点与投影长度](text-dimensions.md)、[坐标转换](coordinate-transforms.md)。测量口径和适用条件见 [规范依据](standards.md)。
