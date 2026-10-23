# Blender 建模、理解与连续编辑

Blender 的 bpy、BMesh、曲线、修改器与 Geometry Nodes 操作知识，以及运行脚本和提取几何的助手。渲染见 [rendering](rendering.md)，扩展见 [ecosystem](blender-ecosystem.md)。

## 运行与续改

已有 Blender 可直接 `blender --background --disable-autoexec --python-exit-code 1 --python <script.py>`。脚本使用 Blender 自带 Python；外部 ezdxf/rhino3dm 环境可以通过文件或进程交换数据，不必往 Blender Python 安装整套 CAD 依赖。

可选 `blender run <script.py> --out <log-dir> [--source <existing.blend>] [--save <result.blend>] [--timeout 1800] [-- <script-arguments>]`，在 `scripts/run.py` 后调用。无 source 时启动空场景；有 source 时先读整个工程。脚本执行成功后才执行可选保存。自定义参数位于 `sys.argv` 的 `--` 后；输出、日志和资源使用项目目录。可直接绕过该助手运行自己的 Blender 命令。

读取已有工程可用 `inspect <source.blend> --out <dir>`，再用 `query` 定位对象。返回的名称只对当前文件版本有效。对象/顶点统计不能代替看模型；根据需求渲染合适的整体、局部、正交或剖切视图，结合资料理解空间与对象关系。现有相机可直接用 `render`；需要其他视图时脚本创建临时相机或保存工程副本。

场景查询支持 `query <inspection.json> --section objects|instances|collections|cameras|materials|node_groups|libraries|dependencies`，结合 `--contains`、`--ids` 和分页；节点组结果列出可调接口的实际 identifier。详细拓扑和完整节点结构留在原文件，需要时再用 bpy 局部读取。

修改时保留本次任务未涉及的模型、材质、灯光、相机和设置；需要调整的部分按用户要求处理。共享的 mesh/material/node group 在需要独立修改时复制 datablock；父子约束和实例关系不能仅看 location。用户新文件优先于旧生成脚本。

## 几何操作选择

- `bpy.data`、`Mesh.from_pydata` 与 BMesh 适合直接构造/修改拓扑。`bpy.ops` 的部分操作依赖选择、模式和窗口上下文；导入、保存等可以用 operator，复杂操作先核实实际上下文。
- 曲线、布尔、阵列、倒角、细分等修改器支持可继续调整的几何；选择顺序和尺度影响结果。Geometry Nodes 适合重复构件、参数关系和散布，但并非每个物体都要写节点网络。
- 渲染与检查实际变形结果使用 `evaluated_get(depsgraph)`、`to_mesh()` 和 `depsgraph.object_instances`；实例使用其 `matrix_world`。临时 mesh 用完 `to_mesh_clear()`。导出副本的求值网格不能覆盖有参数历史的源对象。
- 区分 viewport/render 的修改器、集合可见性与实例设置；数值检查对象应对应实际出图对象。

建模方法服务于空间和造型。按本次用途解决结构支承、层间关系、洞口、交接、家具尺度/朝向/使用空间和构造细节；适用规范与设计判断见对应模块。视觉上有意义的细节可深化；物体数量和高面数不是质量指标。

## 精度与规模

建议新建筑场景以米为内部单位、近原点建模，并记录 CAD 毫米或场地坐标的转换；已有工程保留其已确认单位。Unit Scale 不是自动缩放所有几何。世界矩阵、父级缩放、实例和镜像都影响测量。对实际尺寸和控制点检查，不只看总包围盒。

圆弧和曲面网格化按当前图纸/镜头精度选误差；保留来源精确曲线或设计参数。大地坐标可保存在变换记录中，避免巨大坐标引起浮点精度损失。网格几何精确到指定尺寸，不等于可无损恢复任意 NURBS/BRep。

重复构件和素材可用 linked data/集合实例，按视图范围或任务选择相关几何；仅在交换边界按需实现实例。高面数树木或纹理不必进入建筑技术剖切。根据实际耗时、内存和画面调整密度，不套用固定质量预设。

## 可选几何与交换入口

`blender extract <source.blend> --out <dir>` 输出世界坐标毫米网格快照。可加 `--objects <names...>`、`--collections <names...>`；集合筛选为对象直接所属集合。实例根据其放置对象筛选。未声明单位时用已知尺寸决定 `--unit-scale-m`，不能猜。快照是内部传递格式，不要求用户维护它。

`blender export <source.blend> --formats glb 3dm dae --out <dir>` 按所选格式导出；同样支持筛选和单位参数。GLB 使用 Blender 原生导出器保留适用 UV/PBR，3DM/DAE 为求值网格和基本颜色。未支持的几何出现在 omitted 中，不能忽略它后声称完整交换。完整着色器/参数历史继续保存在 .blend。见 [交换范围](exchange-verification.md)。

二维 CAD 可直接提取已确认轮廓并在 bpy 中生成几何；模型出图使用 [剖切和投影](geometry-drawings.md)。是否共享参数、保留 CAD 轮廓或从模型派生图纸，由任务决定。

## 官方依据

[Python API](https://docs.blender.org/api/4.5/)、[BMesh](https://docs.blender.org/api/4.5/bmesh.html)、[依赖图](https://docs.blender.org/api/4.5/bpy.types.Depsgraph.html)、[操作上下文](https://docs.blender.org/api/4.5/info_gotchas_operators.html)、[精度限制](https://docs.blender.org/manual/en/4.5/advanced/limits.html)。按实际 Blender 版本查接口，列表之外的原生功能和适用插件也可使用。
