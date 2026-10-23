# 流线、场地图元和字体排版

## 可编辑场地图元

`ezarch.site_symbols` 返回既有 Symbol，可用 Drawing.symbol、Canvas.symbol 或 place_symbol 放置，颜色与纯线稿共用几何。局部长度使用 mm，不包含场地安排、交通规划或自动布树。

| 函数 | 输入与作用 |
|---|---|
| `route_symbol(points,head_length=...,head_width=...,start_arrow=False,end_arrow=True,role="outline",fill=None)` | 连接显式点列，按首末段方向绘制所选箭头。head 尺寸由调用者给出；不寻路，不推断通行用途。 |
| `direction_symbol(direction,length=...,head_length=...,head_width=...,...)` | 按向量绘制方向箭头，可与文字或北针表达组合。方向向量先单位化，长度单独给出；纸面旋转由已有变换处理。 |
| `road_symbol(points,left_width=...,right_width=...,join=...,fill=None,centerline=False)` | 路径两侧按显式宽度缓冲，平端封口；join 为 mitre/bevel/round。返回实际边界，可选择中心线，不判断道路宽度、转弯半径或规范。 |
| `canopy_symbol(radius=... 或 outline=...,trunk_radius=None,pit=None,fill=None)` | 圆或指定多边形树冠，可选树干和显式树池边界，不选择树种、位置或树距。 |

铺装与场地分区直接复用 polygon_symbol / fill_regions，真实孔洞保留；道路或景观更新后与建筑的关系由 AI 看图判断。这些资源不设图种、配色、图量或版式。

## 字体与文字

`fonts.font_roles(mapping)` 将任意角色名关联到实际 FontFace；不预设角色分类。`font_bytes(FontFace(path,index))` 取得选定 TTC/OTC face 的独立字体数据，不安装系统字体。字体实际字重由选中的 face 决定，文件名不代表字重。复制、嵌入或交付字体时依据实际许可。

`Canvas(...,font_roles=...)` 可接收角色映射；`Canvas.text(...,font=... 或 font_role=...,fallbacks=...)` 按段选用实际字体，缺字时使用显式后备，否则报错。单行文字仍采用未塑形进宽；`text_box` 按选定字体换行，不自动缩小。`Drawing.text(...,font=<TTF/OTF>)` 只改变该次文字的原生字体样式；CAD 的 TTC face 需先明确提取为独立文件，随库不擅自打包用户字体。

`Canvas.rich_text(x,y,w,h,markup,css="",fonts=None,scale_low=1)` 使用 MuPDF Story 的 HTML 排版/塑形能力，fonts 是 CSS family 到实际 face 的映射。默认不缩字，放不下返回错误；允许缩放时通过 scale_low 明确最小比例，报告记录实际比例。适用于连字、混排、双向文字等，实际字体和后端仍影响效果，需查看生成结果。PDF 保留文字，但提取可能返回连字或不同 Unicode 形式，不能假称与源字符串逐字节一致。

Canvas 保存默认生成可编辑 SVG text，并嵌入实际字体；`save(...,svg_text="outline")` 可选择转曲。rich_text 或导入 PDF 的 SVG 部分以字形路径保留外观，PDF 中仍是文字。原生 CAD 预览继续默认转曲，而 DXF 文字可编辑；这些可编辑性边界不能混为一谈。

`Canvas.svg(path,x,y,w,h)` 将指定 SVG 转为矢量视图再合成，嵌套资源在输出时分别命名，避免 clip/defs 冲突。复杂外部资源和浏览器特性仍受 MuPDF 支持范围限制；不保证任意网页 SVG 完整等价。纸幅、文字和槽位由调用者指定。
