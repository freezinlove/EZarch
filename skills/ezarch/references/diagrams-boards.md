# SVG、分析图与排版工具

原生 SVG、Canvas 和 PDF 合成可用于图解、分析图与版面。Canvas 接收几何、组件与媒体；board 接收版面配置文件；原生 SVG 可直接接入现有矢量项目。

## Canvas 画布

`from ezarch.graphics import Canvas`。`Canvas(width, height, background="#ffffff", font=None, *, font_roles=None)` 新建纸面 mm 画布，X 向右、Y 向下。方法向 `canvas.items` 添加内容，保存时渲染；源码见 [graphics.py](../src/ezarch/graphics.py)，运行方法见 [项目脚本接入](environment.md#命令与项目脚本)。

| 方法 | 接收的内容与连接方式 |
|---|---|
| `poly / line / rect / circle` | 纸面几何；线宽与 dash 也用纸面 mm。`poly(..., close=True, holes=...)` 保留透明孔洞，无效区域报错。原始区域可用 [fill_regions](area-regions.md#独立填色) 加入画布。 |
| `symbol / cad` | 接收 Symbol 或现有 ezdxf 文档，在保存时重绘当前实体；[组件接入](editable-components.md#接入正在使用的画图方式) 说明模型单位、纸面位置和比例。 |
| `text / text_box / rich_text` | 单行、换行和 HTML 富文本；字体、字高、后备和塑形见 [字体与排版](typography.md)。普通文字默认 em 字号与基线锚点，`valign="middle"` 用字号高度中线，指定字体时可用 `size_mode="cap"`。 |
| `image / pdf / svg` | 接收文件及纸面 x/y/w/h。`pdf(..., page=0)` 页码从 0 开始；SVG 经矢量视图合成，保留范围受 MuPDF 支持限制。 |
| `save(stem, formats=..., svg_text="editable")` | 输出所选 SVG/PDF/PNG，并返回尺寸、文字/媒体等报告；stem 为项目文件路径。普通文字可编辑性和转曲区别见 [导出说明](typography.md#导出后的文字形式)。 |

`canvas.svg(path,x,y,w,h)` 和 PDF 合成时分别命名嵌套资源，避免 clip/defs 冲突；复杂浏览器特性、滤镜和外部资源不保证完整保留。嵌入 CAD 的文字为轮廓。需要保留原 SVG 的 text、DOM 或 CSS 时，可直接编辑或组合原 SVG。

Canvas 的颜色、线宽和孔洞语义见 [绘图属性](geometry-drawings.md#绘图属性与多格式表达)。需要量取实际字体进宽或轮廓时见 [字体测量](text-dimensions.md#字体发现与字形依据)，测量本身不改动排版。

## 直接 SVG

SVG 可承载地图、统计图、关系图、技术线稿和自由图板。数据可以是 JSON/CSV、图像坐标、地理数据、现有矢量或临时计算结果。原生 SVG 支持路径、任意角度文字、文字沿路径、分组、clipPath、渐变等；语义图层、独立样式和译名表有助于后续编辑。

需要可编辑文字时保留 text 元素；转曲会失去文字编辑性。SVG 的 viewBox 与纸面 width/height 可分开，图像坐标不必换成 mm。PDF/PNG 可经项目已有渲染器导出，或用兼容的 SVG/浏览器工具；不同渲染器对字体、滤镜、裁剪的支持可能不同。

## 可选 board 排版器

`board <board.yml> --formats pdf --out <dir>` 接收独立模板，适合 PDF/图片和简单文字、线框的纸面合成。命令启动方式见 [环境接入](environment.md#命令与项目脚本)。

输入 `sheets` 列表；每项包含纸幅 `size_mm`、可选 background/font 和 items。每个 item 用 type 选择 text/line/rect/pdf/image，x/y/w/h 是纸面 mm，file 相对模板。文字支持 size/rotation；提供 w/h 时有界换行，否则逐行定位。媒体默认保持宽高比。内容按 items 顺序叠放，允许重叠和页面裁切；旧 allow_overlap 字段不再参与判断。模板由本次需求决定，工具不内置图量或槽位布局。

`scale_lock` 对 PDF 槽位要求物理比例不变；可不启用，但图纸标注的比例仍需与实际缩放一致。图片保持宽高比，返回实际有效 PPI；显式提供 minimum_ppi 才按该要求限制尺寸。固定槽位算法不会自动决定优秀的版式。

formats 选择 SVG/PDF/PNG；选择 PDF 时同时生成合订 presentation.pdf，并附带布局报告。PDF 槽位在合成 PDF 中保持矢量，但转入 SVG 时文字会转曲。需要保留原 SVG 文字/图层时，可直接组合 SVG，不必经 PDF 槽位。PDF/X、CMYK 等是另行配置的印前能力，不包含在默认输出中。

## 三维图解的可选表达

模型投影、隐藏线、Blender 正交渲染与自由矢量都可用于轴测/爆炸，选择取决于所需精度和风格。用分组展示位移可保留原模型；概念分解也可直接画 SVG。复杂相交面按平均深度排序可能出现穿透，真实深度缓冲或隐藏线算法可解决这类遮挡问题。网格精细度、材质和标签可按图面需要处理，没有必须采用的镜头组或表现形式。

局部改字与 SVG 组合要点见 [原生操作](edit-existing.md#svg)。

## 内容与版面质量

分析的对象、比较维度和结论由本次问题决定。[功能分区与交通流线知识](analysis-representation.md)说明区域边界、入口、路线及图例怎样对应实际空间。环境图需要数据与方法依据；示意性表达说明其性质，不虚构技术模拟。可以直接从原图和已有模型制作，不强迫先建立房间 schema。

按叙事分配主图、辅助图和文字的面积，选择对齐关系、层级、疏密和节奏；不用固定格子代替设计。用户提供模板时先理解纸幅、留白、字体、裁切和图文关系，再决定沿用或适配的部分。实际检查导出后的可读性、技术图比例、跨图对应、图片有效分辨率和文字溢出；工具允许的重叠也要看是否有明确的视觉作用。

静态 SVG 预览使用 resvg（`resvg-py`），正确处理物理单位、常见 CSS、分组变换和裁剪。复杂网页特性、外部字体或不支持的 SVG 特性可改用浏览器/其他可靠矢量工具；不要把 PyMuPDF 对 SVG 的不完整渲染当成原稿设计问题。[resvg-py API](https://resvg-py.readthedocs.io/en/latest/api.html)

## 旧房间图例接口

`diagram <project.yml> --level <id> --out <dir>` 保留已有房间多边形的功能/概念路线/虚实/面积绘制器。`--kinds` 和 `--formats` 选择输出，省略时兼容旧四图行为；多楼层需要 level 选择本次输入。参数数据见 [旧接口](project-data.md)。自由分析图可直接使用上面的 Canvas、SVG 和区域填色。
