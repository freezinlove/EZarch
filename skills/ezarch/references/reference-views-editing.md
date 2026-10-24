# 参考定位、临时视图与局部修改

接受现有文件、ezdxf 文档和本次选择，返回提取资料、临时视图或修改副本。`from ezarch import references, selection` 后调用对应模块的函数；源码见 [references.py](../src/ezarch/references.py) 和 [selection.py](../src/ezarch/selection.py)，运行方法见 [项目脚本接入](environment.md#命令与项目脚本)。

## 资料与 PDF

本节函数位于 `ezarch.references`。`catalog_sources(paths)` 返回文件摘要、格式、大小及可取得的 PDF 页数 / DXF 布局，同内容不同文件名会关联。读取失败单独返回，不按文件时间推断当前版本。

`extract_reference(source,out,pages=None,region=None,dpi=150)` 只处理选定 PDF 页。页码从 1 开始，region 是显示页面的 pt 坐标；输出 PNG、保留裁剪的 PDF/SVG、区域文字和原始路径记录。路径记录保留整张所选页的绘图/clip/group 指令，采用未旋转页坐标；报告给出显示坐标与源裁切坐标。SVG 中 PDF 文字转曲，原始文字另存；不进行 OCR 或建筑对象识别。CLI `reference` 支持 `--pages`、`--region`、`--dpi`。

`fit_reference_transform(source_points,target_points)` 用至少三个非共线控制点求二维仿射关系，返回六系数及每点残差，目标单位由调用者选择。残差不证明参考建筑内容准确。已有变换也可直接提供。

`map_reference_geometry(paths,layout,transform=...,indices=None,region=None,dxfattribs=None)` 将明确选中的线、三次曲线、矩形和四边形转换为可编辑折线/样条/填充，保留 source→target 对应。region 使用源页 pt；跨出范围的路径和受剪裁路径明确列入 skipped，不裁断后假装完整。复合非零环绕填充、透明混合、文字和图片没有完整 CAD 适配；需要原貌时使用提取的 SVG/PDF。原生 PDF 描边样式不自动解释为建筑线型，由 dxfattribs 或后续实体编辑控制。

## 选择与临时显示

本节及下节函数位于 `ezarch.selection`，doc 为现有 ezdxf 文档。`select_entities(doc,predicate=None,layout_name="Model",nested=False)` 返回含 selected 与 unsupported 的字典，可直接传给 render_view 的 selection。predicate 接收 SelectedEntity，含 id、源 handle、实例路径和已变换到世界坐标的原生 entity。nested=True 展开块实例，保留旋转/缩放和多重实例身份；循环块、外参及无法变换的对象明确列出。不会按 INSERT/HATCH 类型推断家具或墙。

`render_view(doc,output,selection=None,overrides=None,region=None,scale=None,formats=None)` 对副本设置显示属性，overrides 以 selected id 为键，支持颜色、线宽、线型、图层和可见性。原文件不被隐藏、删改或重建。扁平化后的复杂 BYBLOCK 表达可显式覆盖；不是所有外部代理对象都能渲染。图种、选层、高亮颜色及观察范围由 AI 决定。

## 选定对象替换与前后对照

`replace_selection(doc,handles,replacements,layout_name="Model")` 返回 `(文档副本, 变更记录)`，记录包含新增/删除 handle；只替换明确布局中的选择，其他实体、布局和资源保留。replacements 是 AI 自行构造的原生实体；需要的图层、线型和块应已在目标文档中定义。它不推断邻墙、门洞或尺寸关联。

`patch_document(source,target,handles,replacements,expected_sha256=...,layout_name="Model")` 将上述替换写到单独 DXF，源摘要不符时停止，避免把旧选择写到新版本。DWG 可另外转换。

`compare_documents(before,after)` 返回原生实体标签与所列图层/线型/文字/尺寸样式的差异，不判定设计对错；依赖稳定 ID，转换器重编号时需另行理解。`preview_changes(before,after,out,region=...,scale=...,formats=None)` 在同一范围和比例下生成前后图，用颜色标出原生变化，便于 AI 看图判断修改是否生效。标色表示变化，不能当作错误标记或合格结论。
