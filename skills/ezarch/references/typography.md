# 字体选择、文字排版与可编辑性

为现有 Canvas、Drawing 或项目脚本指定实际字形，处理换行、富文本与导出文字。字体发现、缺字信息和几何占位计算见 [字体测量](text-dimensions.md#字体发现与字形依据)。

## 字体接入

`from ezarch.fonts import FontFace, font_roles, font_bytes`。`FontFace(path, index=0)` 标识文件及 TTC/OTC face；`font_roles(mapping)` 将调用者的角色名关联到实际 face；`font_bytes(face)` 取得该 face 的独立字体数据。源码见 [fonts.py](../src/ezarch/fonts.py)。这些操作不注册系统字体；复制、嵌入或交付字体依据实际许可。

`Canvas(..., font_roles=...)` 接收角色映射；`canvas.text(..., font=... 或 font_role=..., fallbacks=...)` 选择该段的实际字体。缺字使用显式后备，否则报错；实际字重由 face 决定，文件名不能证明字重。`Drawing.text(..., font=<TTF/OTF>)` 只改变该次文字的原生字体样式；CAD 的 TTC face 需先提取为独立文件。

## 接入现有画布

以下为 [Canvas](diagrams-boards.md#canvas-画布) 的方法，坐标、框宽高与字号使用纸面 mm，X 向右、Y 向下。方法把内容加入 `canvas.items`，由 `canvas.save(...)` 生成所选文件。

| 入口 | 输入、输出与适用范围 |
|---|---|
| `text(x, y, text, ..., font=None, font_role=None, fallbacks=())` | 单行文字，默认 em 字号与基线锚点；可旋转、对齐。采用未塑形进宽。添加文字项，无独立返回对象。 |
| `text_box(x, y, w, h, text, size=3, leading=None, **kwargs)` | 按选定字体换行；放不下报错，不自动缩小。添加各行文字，返回行数及实际使用高度。 |
| `rich_text(x, y, w, h, markup, *, css="", fonts=None, scale_low=1)` | MuPDF Story 的 HTML 排版与塑形，适用于连字、混排、双向文字等。fonts 是 CSS family → 实际 face；添加富文本项，保存时排版。默认不缩字，允许缩放时显式给最小比例；保存报告记录实际比例。 |

字体和后端影响实际字形与排列，需要查看生成结果。富文本 PDF 的提取内容可能返回连字或不同 Unicode 形式，不保证与输入字符串逐字节一致。

## 导出后的文字形式

- Canvas 的普通文字默认保存为可编辑 SVG text，并嵌入实际字体；`save(..., svg_text="outline")` 选择转曲。
- `rich_text` 或导入 PDF 的 SVG 部分保留字形路径；合成 PDF 中仍为文字。
- 原生 CAD 预览默认转曲，DXF 中的文字仍可编辑。嵌入 CAD 的 Canvas 内容也沿用这个边界。

这些差异影响后续编辑和交付。画布合成与 SVG 导入见 [矢量排版](diagrams-boards.md)，CAD 文字的纸面字高与目标单位见 [Drawing](geometry-drawings.md#绘图属性与多格式表达)。
