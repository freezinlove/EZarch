# 延续已有项目与任意程序化制作

以用户提供的最新文件为工作依据。选择内部格式是 AI 的技术决策，延续原项目不等于必须直接覆盖原后缀。修改前后保留未涉及内容，确定单位、坐标和修改对象；需要重构时由需求决定，不能因为重画几个基本形状容易，就丢掉源图的细节与关系。

## CAD

`ezdxf.readfile()` 读取整个 DXF，修改 `doc.entitydb[handle]` 或按图层/类型查询，`doc.saveas()` 延续文档。DWG 通过 [转换器](exchange-verification.md) 建立完整工作 DXF，不必安装 AutoCAD。`ezdxf.new()` 是新建文档 API，不能作为已有项目修改的默认入口。复制实体到新文档的 importer/xref 并不支持全部对象、HEADER/OBJECTS 内容。

可选 `edit <source> <output> --ids <handles> --move dx dy dz` 或 `--text <text>` 支持 DWG/DXF 全文档局部修改；坐标为源单位，保存单独文件。`--expected-sha256` 可约束编辑所依据的版本。复杂设计直接调用 ezdxf API：实体变换、块参照、HATCH 边界、弧/样条、DIMENSION、布局与样式，不受小助手提供的两种操作限制。

需要复用随库标注与符号时，可用 [Drawing.from_layout](geometry-drawings.md#绘制到已有文档) 绑定已有模型空间、纸空间或图块；目标单位、比例与样式由调用者提供，保存仍由原文档管理。独立二维数值映射见 [坐标计算](coordinate-transforms.md)，不替代原生实体变换。

块定义修改影响其所有实例；修改插入参照只改变该次放置。MINSERT 阵列、非均匀缩放、实体 OCS 与世界 WCS 不可混淆。多段线保留 bulge/closed/elevation，填充保留外环与孔洞，尺寸保留实测定义与样式，文字核对字体及 SHX/bigfont。绘图前端可用于检查，不能只抽取 LINE 就据此理解图纸。详见 [ezdxf drawing](https://ezdxf.readthedocs.io/en/stable/addons/drawing.html)、[实体导入边界](https://ezdxf.readthedocs.io/en/stable/xref.html)。

## Rhino 文件与精确实体

rhino3dm 无需 Rhino 应用即可读写原生对象。`File3dm.Read()`、`Objects.FindId()`、`Geometry.Duplicate()/Transform()`、对象属性及 `File3dm.Write()` 可延续用户文件；可选 `edit` 支持 UUID 选定对象的位移和 `--name`。它保存整个 3DM 并保留 UUID，不将其他曲面转换为网格。更深编辑按对象选择 API。

新增几何可以直接用 `NurbsCurve`、`NurbsSurface`、解析曲线、`Extrusion.CreateWithPlane()`、`AddInnerProfile()`、`Brep.CreateFrom...()`，然后 `doc.Objects.Add(geometry, attributes)`。通用 `ezarch.rhino.write_geometry(objects, target, units, tolerance)` 接收原生 geometry/attributes 对，不要求建筑 schema；需要复杂图层、材质或实例树时直接管理 File3dm。曲线闭合、孔洞方向、齐次 NURBS 权重和结点序列属于几何正确性，不能靠网格外观代替。

随库提供 Blender 三维制作与 rhino3dm 精确文件读写、局部操作的支持，按当前对象和目标选择。跨入 Blender 的曲面通常使用网格，不能默认恢复为可精确编辑的 NURBS。旧 CadQuery/STEP 接口未继续维护且需要独立依赖；详见 [交换边界](exchange-verification.md)。

## Blender

用 `bpy.ops.wm.open_mainfile(filepath=..., load_ui=False, use_scripts=False)` 读现有场景，按对象名/集合和检查结果定位；后台加 `--disable-autoexec --python-exit-code 1`。保留本次修改未涉及的相机、灯光、材质、渲染设置及外部依赖，局部修改后 `bpy.ops.wm.save_as_mainfile()` 另存。材质/网格可能被多对象共享；需要单独改造时先复制相应 datablock，而非意外影响所有实例。

`matrix_world` 处理父子与世界坐标；`evaluated_get(depsgraph)` 查看当前帧的修改器/约束结果，`depsgraph.object_instances` 提供实例变换。求值网格适合显示/导出，不宜反过来覆盖参数化源对象。剖切、自由形态、UV、材质节点和自定义程序都可直接写 bpy，不必转换为 scene.json。见 [Blender API](https://docs.blender.org/api/current/) 、[原生建模](blender-modeling.md) 与 [渲染](rendering.md)。

## SVG

保留原 SVG 的 viewBox、分组、CSS、defs、clip/mask、字体和图像引用，用 XML/DOM 按 ID 编辑。`edit` 支持指定叶级 text/tspan 文本和父坐标系位移；复杂字排、路径、嵌套变换及版式直接使用 XML/DOM 或专用矢量库。无 ID 时查询提供的 index:N 只对该源版本有效。

浏览器和 PyMuPDF 对 SVG/CSS/滤镜支持不同，实际渲染检查文字、继承样式与变换。图形组合注意 ID 冲突、坐标系和图像链接；输出可编辑 SVG 不应默认把文字全部转路径或整图栅格化。

## 二维与三维关联

关联依据是同一源版本、坐标/单位、楼层、剖切位置和视图方向。可以从三维投影出图，或从二维已确认的边界和标高建模；不假定任意平面图唯一决定三维。模型变更后重算受影响投影及尺寸，二维新增设计需要明确回写哪些三维构件。

精确剖切与建筑图纸是两个不同层面：切线之外可能还需可见线、门窗/楼梯表达、填充、图注与标注，按本次用途深化。曲线只在显示边界进行受控离散，保留精确源几何。模型坐标1:1和纸面出图比例分别管理；跨文件选择控制点、洞口、楼层与关键长度核对，不能只比较总包围盒。
