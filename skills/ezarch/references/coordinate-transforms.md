# 二维坐标与方向计算

`from ezarch import frames`，以 `frames.<下表函数>(...)` 调用；源码见 [frames.py](../src/ezarch/frames.py)。输入普通点、方向、仿射系数或 Shapely 几何，返回新数值/几何，不读写项目。所得变换可交给 [区域填色](area-regions.md#独立填色)，或继续用于项目中的坐标计算。

## 数据与接口

变换为六个有限数值 `(a, b, d, e, xoff, yoff)`，顺序与 Shapely 一致：

`x' = a*x + b*y + xoff`；`y' = d*x + e*y + yoff`。

| 接口 | 输入与返回 |
|---|---|
| `affine_from_axes(origin, x_axis, y_axis)` | 原点、源 x/y 单位轴在目标中的向量；返回六系数。向量可包含旋转、反射、缩放；不自动归一化 |
| `transform_points(points, transform)` | 二维点序列；返回新的 `(x, y)` 列表，原输入不变 |
| `transform_direction(direction, transform)` | 二维方向；只应用线性部分，返回向量，不平移、不自动归一化 |
| `affine_determinant(transform)` | 返回有符号面积倍数；负值表示方向反转，零表示面积退化 |
| `inverse_affine(transform)` | 返回逆变换系数；奇异变换报错。接近奇异的变换仍受浮点精度影响 |
| `transform_geometry(geometry, transform)` | 二维 Shapely 几何；返回转换结果，保留环与组件结构，不自动修复输入 |
| `paper_transform(bounds, scale, *, unit_mm=1, margin=0)` | 返回模型 Y 向上到纸面 Y 向下的变换；边界为源单位，`unit_mm` 为每源单位对应的 mm，`scale` 为物理比例分母，`margin` 为纸面 mm |

单位转换通过实际系数作用于数值；仅改变单位文字没有转换效果。纸面字高、笔宽不属于模型几何变换。`paper_transform` 按给定边界和比例计算，不自动适配纸幅、不决定版式；其他观察方向可以用轴向系数表达。

## 支持范围

点与方向要求严格二维，避免无意丢弃 Z；几何入口仅支持二维 Shapely 对象，拒绝 Z/M。纯数值操作只用 Python 标准库，Shapely 仅在几何入口导入。零行列式可以用于退化映射，但没有逆变换；几何合法性及数值精度由实际输入决定。

此模块不转换原生 DXF 实体，不处理 ARC/bulge、OCS、文字可读方向或门的建筑含义，也不从文件推断单位。原生实体变换见 [连续修改](edit-existing.md)，绘制到现有文档见 [已有文档绑定](geometry-drawings.md#绘制到已有文档)。

坐标映射提炼自项目中使用过的仿射、局部坐标及纸面计算；逆变换、输入校验和独立接口经过开发测试。支持范围依据当前实现，不把原任务运行成功称为所有输入均经过真实项目验证。
