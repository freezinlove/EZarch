# 工作格式、行业交付与转换边界

用户的正常输入可以是 DWG/3DM/PDF/图片/链接与文字需求。工作中选择 DXF、原生3DM对象、Blender、SVG或其他数据，由 AI 根据操作决定。输出按本次用途满足行业查看和后续编辑习惯；不要求用户处理转换，不要求每次全格式交付。

| 路线 | 当前能力及边界 |
|---|---|
| DWG ↔ DXF | 可选 ODA File Converter 双向转换；ezdxf 编辑完整工作 DXF。保留源文件与所选版本，不自动 repair。代理对象、外参、字体与专有编辑语义不能笼统保证无损 |
| 原生 3DM | rhino3dm 读取/写回精确曲线、曲面、BRep、拉伸体和网格，UUID/属性/图层可保留。能读不等于具有完整 Rhino 几何内核 |
| 旧 OCCT → 3DM 路线（未继续维护） | 需另行准备 legacy-cad 的旧 `model --formats 3dm` 对直边等截面拉伸实体生成闭合 BRep，保留对象名称/分类及洞口边界；使用原生封闭拉伸生成精确平面BRep。其他实体拒绝，不静默离散 |
| 直接创建精确 3DM | 原生 rhino3dm 曲线、NURBS曲面、解析BRep、带孔拉伸体；`write_geometry` 可写任意受支持原生对象。复杂裁剪曲面/布尔按实际库能力处理 |
| STEP（旧接口未继续维护） | 旧 CadQuery/OCCT 兼容接口需要 legacy-cad；随库 Blender 助手不生成精确 STEP，也不宣称任意 3DM↔STEP 转换 |
| 网格 3DM | `blender export <file.blend> --formats 3dm --out <dir>` 输出世界坐标毫米求值网格、对象/类别与基本颜色；不能替代 NURBS/BRep 交付 |
| DAE | 网格节点/基本颜色，供 SketchUp导入；随库毫米、Z_UP。没有原生SKP/材质完整保真承诺 |
| GLB/GLTF | .blend 使用 Blender 原生导出器，保留适用 UV/PBR 和节点；3DM/DAE 简化交换与 scene.json 的基本色出口不等于完整材质保真。GLB 为米/Y向上，不保留 Blender 节点历史 |
| BLEND | 场景、对象、修改器、相机、着色器及可打包图像；外部库/插件/缓存仍需查依赖 |
| SVG/PDF/图像 | SVG保留矢量对象、文字和分组；PDF面向出图，图片面向预览/表现。不能仅靠PDF代替可编辑CAD模型 |

## Rhino 与 Blender

现有开源 [import_3dm](https://github.com/jesterKing/import_3dm) 可作为按需插件，使用 rhino3dm 读取显示网格。复杂 BRep/Extrusion 没有缓存网格时不保证可转换，读取到包围盒也不能视为已完整理解表面。需识别不支持/遗漏对象；精确源 3DM 保留，不能全量网格化覆盖。随库未提供原生 Rhino 引擎桥接。

从 Blender 导出的 3DM 仍为可编辑网格。3DM 的原生精确对象可直接通过 rhino3dm 继续读写；这些是不同操作。Rhino 8 可交换 GLB/glTF，曲面会离散为网格。复杂程序材质需按要求烘焙，完整原工程保留 .blend；不宣称转换后在不同渲染器中外观完全相同。

## DWG 操作

`convert <source.dwg|dxf> <target.dxf|dwg> [--version ACAD2018] [--repair]` 使用独立临时输入目录，仅处理选定源文件。输出已有时拒绝覆盖；repair 是显式修复操作，不是默认。`inspect`/`edit` 可直接接收 DWG，由工具建立工作副本。跨格式的对象对应需核对，不能假定全部 handle 永远不变。

ODA 官方提供免费的闭源 File Converter，支持 macOS/Windows和命令行，不需AutoCAD；它不等同收费ODA开发SDK。`bootstrap --install-oda` 可按需取得外部安装包并检测，实际系统权限/许可提示可能需要处理。仓库不捆绑或重新分发安装包。`doctor`/`EZARCH_ODA` 可发现或指定程序。

[官方转换器](https://www.opendesign.com/guestfiles/oda_file_converter)、[免费应用说明](https://www.opendesign.com/guestfiles)、[ezdxf odafc](https://ezdxf.readthedocs.io/en/stable/addons/odafc.html)。ezdxf核心不支持DWG，其 addon 仍调用外部程序。

## 回读、比较与交付可用性

文件可解析、外观一致、几何/精度一致、特殊对象可编辑是不同验证。按受影响内容比较关键实体、曲线/块/填充、尺寸/文字、布局、图层、外部依赖、坐标和实际输出视图；数目或包围盒相同不足以证明转换完整。数值容差依据单位和任务精度确定，不用统一宽松阈值掩盖变化。

`inspect/query/compare` 为原始文件提供版本绑定查询；`audit <file|directory|project.yml> --out <dir>` 为文件回读或随库输出关系检查。随库只生成所选格式，不要求无关同名配套文件；项目比对可用 `--outputs`。二者不判断设计、美感、全部技术合规或目标软件行为。

所选直边区域/路径还可单独使用 [几何观测与定位](geometry-diagnostics.md)，取得有效性、短边、回折及精确重复的事实、候选和覆盖信息。空输入、未支持对象及缺失范围不会获得整体通过结论；是否进一步查看或使用其他检查由任务决定。

开放库回读、转换回转、在 AutoCAD/Rhino/SketchUp 中实际打开继续编辑分别记录。未做商业软件验收时如实说明；不能从扩展名推断已通过。用户再次提供修改后的文件时，以新版本为依据接续工作。

技术依据：[rhino3dm](https://github.com/mcneel/rhino3dm)、[BRep API](https://mcneel.github.io/rhino3dm/python/api/Brep.html)、[CadQuery交换](https://cadquery.readthedocs.io/en/latest/importexport.html)、[glTF单位与坐标](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#coordinate-system-and-units)。原生商业应用控制、SKP 写入和 IFC 未提供随库适配；DWG/3DM 文件适配仍可独立使用。未捆绑、未维护与当前机器不可用是不同状态，任务可选择其他实际可用的工具。
