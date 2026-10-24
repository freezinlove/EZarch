# 尺寸端点与字体测量

端点测量、原生 CAD 尺寸、字体发现及文字包络计算。按所需数据接入项目：

- `from ezarch.measurements import measure_span`：点对与单位 → 长度/投影记录；绘制尺寸用现有 `Drawing.dimension`。
- `from ezarch.fonts import FontFace, font_info, discover_fonts, measure_text`：字体文件、文字 → 字形信息、进宽与包络。
- `from ezarch.annotations import text_footprint`：文字测量 → 可继续计算的 Shapely 包络。

实际字体应用、换行和富文本见 [字体与排版](typography.md)，不必为排版先执行测量。

## 端点与原生尺寸

[`measure_span(p1, p2, *, unit_mm, direction=None, source=None)`](../src/ezarch/measurements.py) 计算任意二维端点跨度。unit_mm 是每输入单位对应的毫米数；省略 direction 量实际端点距离，传方向向量则量其投影距离。方向只归一化，不自动吸附到横竖轴。返回 p1/p2、mode、direction、measured_mm、signed_mm、endpoint_distance_mm、单位和来源快照。投影的符号保留端点顺序，measured_mm 为绝对值。零跨度可以被计算，不代表净宽或通行尺度。

[`Drawing.dimension(a, b, base, text_size=2.5, *, direction=None, decimals=0, text_override=None, source=None)`](../src/ezarch/drafting.py) 在既有水平/竖直调用上增加斜向及任意方向投影，生成原生可编辑 DIMENSION 并返回实体元组。base 指定尺寸线所经过的位置，延伸线与所选方向垂直。没有方向时与端点连线对齐；它不会替调用者选择外轮廓、轴线、净空或正确楼层。

坐标采用 Drawing 当前目标单位，text_size 为纸面 mm；显示数字与记录的 measured_mm 按 mm，decimals 为 DXF 支持的 0–8 位小数。text_override 可传非空纯单行文字，原实测值不被改写，记录明确标识人工覆盖；DXF 格式控制、测量占位符和其他单位标注可用原生 API。

`drawing.dimensions` 保留端点、基线、方向、尺寸线投影端点、实测值、显示文字/精度、实体 handle 和 source。source 是调用者提供并深拷贝的创建时依据，不是 DIMASSOC 关联或自动对象追踪；外部改动后可重新测量/生成，旧记录不会自行更新。显示值正确也不能证明选对了对象。

绑定模型空间、纸空间或图块沿用显式 unit_mm/scale，复用或另命名资源的规则见 [Drawing 绑定](geometry-drawings.md#绘制到已有文档)。既有文字/尺寸样式定义不重写；必要的数值格式和纸面尺寸作为新增实体覆盖。新建 Drawing 的 Canvas 显示同一测量值与方向；它是简化表达，未声称与任意 CAD 尺寸样式、挤压方向或查看器排版逐项等价。chain 仍是原有正交链助手，不是唯一可用的标注组织方式。

## 字体发现与字形依据

源码：[`ezarch.fonts`](../src/ezarch/fonts.py)。无自动安装、全盘扫描、全局字体注册或字体复制；可直接传项目字体、已有安装路径或按任务找到的其他字体。

- `FontFace(path, index=0)` 标识实际文件与 TTC/OTC face 索引；单独 TTF/OTF 仅 index=0。索引不会被默默忽略。
- `font_info(font, *, text="")` 返回真实 family/subfamily/PostScript 名、数值字重、斜体、字形数量、缺少的字符、可变字体标记和 embedding_fsType。后者是文件元数据，不等同完整授权许可。
- `discover_fonts(paths, *, recursive=False, family=None, weight=None, italic=None, text="")` 检查给定文件或目录；可选递归，按字体元数据精确筛选。返回全部 candidates、逐文件/face 错误和 checked_paths，不因名字带 Bold 就认定粗体，不把找不到的字重悄悄替换成别的字重。缺字信息保留在候选中，AI 可自行选择或查找其他来源。

## 单行测量

`measure_text(text, font, *, size_mm, fallbacks=(), origin=(0,0), rotation=0, align="left", valign="baseline", size_mode="em")` 接受明确字体路径或 FontFace。fallbacks 是调用者指定的顺序列表，只在当前字符缺失时选下一字体。字体角色映射与渲染器接入可另做；传入测量后备列表不会自动更改 Canvas 或 CAD 的字体样式。

结果坐标统一为 mm、Y 向上，rotation 为逆时针角度。align 支持 left/center/right；valign 支持 baseline/middle。默认 size_mm 是 em 高度；size_mode="cap" 按首选字体 x/A 轮廓换算大写高度，与现有 Canvas cap-height 计算共用底层。middle 使用指定字号高度的中线，不是把实际文字黑色轮廓居中。

advance_mm 是水平排列进宽，含空格；ink 是实际字形轮廓的合并包络，metrics 是所用字体 hhea 升部/降部形成的行包络，各返回旋转 corners_mm 及轴对齐 bbox_mm。空字符串进宽为零且没有包络；纯空格有进宽和度量包络、没有墨迹包络。缺字时 aggregate 进宽和包络为 None，missing_characters 列出缺字；glyph_coverage_complete 只说明字符都有字形，不代表排版完成或结果正确。

采用 **未塑形的水平字形进宽/轮廓**，不应用字偶距、连字、双向排序或复杂文字塑形；可变字体使用默认轴值。它适用于对应排列方式下的占位计算。需要塑形和富文本时可用 [Canvas.rich_text](typography.md#接入现有画布)、HarfBuzz、浏览器或项目既有引擎。测量本身不检查其他对象，可接入下面的占位计算。

## 文字几何包络

`ezarch.annotations.text_footprint(measurement, *, kind, transform=None)` 将 measure_text 结果的 ink 或 metrics 四角转换为 Shapely 多边形；`transform` 可映射到所需坐标系。返回 `Footprint.geometry`、basis、source、limitations 和 unavailable_reason；缺字或无包络时 geometry 为 None。包络重叠不等于实际字形遮挡，真实排版效果见导出图。

## 来源和验证范围

住宅任务提供切向/法向尺寸表达、投影和字体元数据/进宽计算依据；小学任务提供原生尺寸端点与保存修正记录。固定字体角色、系统私有路径、字号、纸幅、楼层选择及人工面积标签均未作为通用规则提取。新接口分别验证单位、任意方向、原生回读、缺字、显式后备和集合索引；只对实际运行平台及选定字体声明结果，不承诺 Windows、商业 CAD 或复杂塑形已验证。
