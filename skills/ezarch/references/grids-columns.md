# 轴线、轴号与柱截面资源

`ezarch.grids` 提供直线端部、轴线、轴号、偏轴和圆包络间距计算；`ezarch.symbols` 提供柱截面。位置、编号和截面由调用参数给出。

墙柱交接、轴网定位与空间支承的专业关系见 [墙、柱与轴网的关系](wall-column-grid-relationships.md)。

## 截面与放置

| 入口 | 几何含义 |
|---|---|
| `rectangular_column_symbol(width, depth, fill=None)` | 局部 mm、中心在 `(0,0)` 的矩形截面；等宽深即方形。锚点 center，名义范围 `(-width/2,-depth/2,width/2,depth/2)`。不预设截面尺寸。 |
| `circular_column_symbol(radius, fill=None)` | 同样居中，保留原生 CIRCLE 与可选圆形 HATCH；radius 是实际截面半径，不是纸面定位符号尺寸。 |
| 已有 `polygon_symbol(geometry, unit_mm=..., role="outline", fill=None)` | 自定义直边 Polygon/MultiPolygon，包括凹形和孔洞；按输入单位换算，不归零、不求形心。其参考点仍由调用者定义。曲线截面也可由 Symbol/native API 自行构造。 |

快捷截面的描边角色为 outline，fill 为调用者定义的填充角色；颜色、纸面线宽与填充开关由 [SymbolStyle](editable-components.md#同一几何的表达) 选择。相同几何可以填色或纯线稿表达，不要求输出两种。

位置、旋转、镜像、单位换算复用 [place_symbol](editable-components.md#几何表达与目标文档)。可直接写入已有布局或自选块，返回原生可编辑实体与锚点；柱号可用 Drawing.text、原生 TEXT/ATTRIB 另行添加。工具不按轴交点自动布柱、夹紧到建筑边界、合并同坐标柱、编号或移动周边门窗；也不根据截面形状认定材料、承重性质或设备用途。截面生成成功不代表结构适用。

## 轴线、轴号及引折线

以下绘制接口接收现有 `Drawing` 对象，可使用新建文档或 [绑定已有文档](geometry-drawings.md#绘制到已有文档)。坐标使用该 Drawing 的目标单位；圈径、字高、端部退让、笔宽及 dash 使用纸面 mm，由上下文的 scale/unit_mm 换算。原图资源处理、字体、颜色与虚线规则沿用 Drawing，不另外创建统一图层体系。

| 接口 | 输入、返回及范围 |
|---|---|
| `axis_segment(start,end,start_trim=0,end_trim=0)` | 纯计算；坐标和退让量采用相同输入单位，返回退让后的两个端点。任意方向直线，两端不得重合，非负退让之和须小于长度。该函数没有纸面单位转换。 |
| `draw_axis(drawing,start,end,trim_start_mm=0,trim_end_mm=0,layer="A-GRID",color="BYLAYER",width=None,dash=None)` | 绘制一条轴线，返回本次原生图元。两端退让显式给出；默认不退让、不附轴号或柱、不生成维度标注。dash 和其他表达可自由选定。 |
| `draw_axis_tag(drawing,center,label,diameter_mm=...,text_height_mm=...,rotation=0,leader=(),layer="A-ANNOTATION",color="BYLAYER",width=None,text_color="BYLAYER")` | 圈与居中文字；label 不按项目名称规则筛选/截断，rotation 为目标 XY 逆时针角度。可选 leader 为完整显式折线点列，使用目标坐标，不自动寻路、连接或裁到圈边。返回 AxisTag 的 entities、目标坐标 center 和目标单位 radius；后续编辑实体不会自动更新这些构造元数据。 |

轴线与轴号互相独立，可以只画其中一项、多端标注，或由调用者把一组轴号放在自选基线上。柱号、非圆轴号和其他标记仍可直接用现有文字/原生图元。没有固定编号序列、三翼结构、横纵方向限制、自动交错轴号或统一字体要求。

## 偏轴测量与圈距

`axis_offset(point,start,end,unit_mm=...)` 将点投影到 start→end 定义的无限直线：输入点/轴线及返回 projection 使用原单位，station_mm 是从 start 沿轴的距离，signed_offset_mm 在有向轴线左侧为正。within_segment 仅说明垂足是否在所给有限线段内；外部垂足不会被吸到端点，柱不会移动。结果也保留输入 point/axis 和 unit_mm，供调用者解释。换向会改变有符号距离；偏轴正负不是固定的建筑 X/Y，局部坐标可用 [frames](coordinate-transforms.md) 转换。

`axis_tag_spacing(circles,unit_mm=...)` 接受本次选择的 `ID: (center,radius)` 映射，坐标和半径都用同一目标单位。可使用 AxisTag 的构造元数据，也可单独提供圆包络，不要求先绘图。

- 返回 checked_ids、pair_count 和每对的 IDs、中心、midpoint、center_distance_mm、circle_gap_mm；负边缘间距表示圆包络交叠，不自动判为设计错误或移动轴号。
- 空输入或单个圆没有成对比较，结果明确 pair_count=0，不给出整体通过、评分或完整覆盖结论。
- scope/not_checked 保留边界：没有测量文字占位、引线相交、其他图元、未选轴号或设计适用性。长编号可以超出圈，圈不相交也不能证明文字不相交。字体测量、自动字号/位置搜索未由本接口提供。

同一画面与单位的选择由调用者负责。跨楼层/结构单元的相同坐标不自动比较或去重；跨层匹配、结构校核、柱墙消隐和斜向原生 DIMENSION 未由本模块提供。AI 可结合原图、用途和其他工具继续判断或构造，现有接口范围不限制可采用的能力。

## 来源与验证边界

居中方柱、轮廓/填充分离和实例放置来自小学补柱及住宅结构轴网任务；斜向端部计算、纸面轴号圈和引折线来自住宅轴网表达，轴线与轴号独立位置也在小学图纸使用。提取后去掉固定截面、轴网行列、布柱策略、边界夹紧、建筑类别判断、固定偏移和整图编排。历史为方柱；圆与任意自定义截面使用已有原生图元能力，作为接口扩展另行验证，不将住宅候选柱中心圆标当成真实圆柱依据。

维护验证分别记录历史保存图元/坐标的对照，以及改变截面、方向、单位、原点、编号和纸面参数后的技术验证。私人图纸、复现脚本及设计决定不随 skill 分发。实际测试不等于通用设计、结构或视觉质量已经通过。
