# 公开三维素材入口

skill 不捆绑大型模型/贴图库，也不依赖作者个人素材目录。用户已有素材及任务授权下可访问的其他来源都可按需选择；下面列出公开来源示例与下载助手，下载文件属于项目依赖。定制素材也可自行制作，不要求所有物体都使用素材库。

## 来源示例

这些网站不是白名单。可主动搜索其他模型、材质、HDRI 或官方 API，按访问条件、参考和任务选择；不要求先尝试表中来源。已有用户模型可直接使用。

资源访问以项目当时的元数据、许可与服务规则为准；列表不代表已经验证每个资源或插件在当前机器可用。

| 来源 | 用途 | 路径 |
|---|---|---|
| Poly Haven | HDRI、PBR、部分模型 | https://polyhaven.com/our-api 、https://api.polyhaven.com/ 、https://docs.polyhaven.com/en/faq |
| ambientCG | 建筑材质 | https://docs.ambientcg.com/api/ 、https://docs.ambientcg.com/license/ |
| Blendkit（原 BlenderKit） | 家具和软装等可选来源 | https://www.blendkit.com/docs/licenses/ 、https://github.com/BlenderKit/bk_client |

Poly Haven、ambientCG 素材采用 CC0；服务访问规则与素材许可分开。Blendkit 逐资源区分 CC0/Royalty Free，部分需要登录或付费。本库不将需账号资源作为默认运行依赖；其他来源按其实际访问条件、许可和用户授权处理。

## 可选 Poly Haven 下载器

```yaml
provider: polyhaven
id: dining_chair_02  # 仅展示字段；不是默认选用的椅子
kind: model
resolution: 1k
```

`asset <asset.yml> --out <project/dependencies/...>` 读取官方 `/files/{id}`，下载 GLTF 与贴图/缓冲区依赖并校验，保存来源与 SHA256 清单。kind 支持 model、texture、hdri；客户端纹理入口获取 Diffuse/Rough/nor_gl 三类图。没有对应字段或需要其他资源类型时，可调用原 API 或编写适配器，不受这个封装限制。

直接查询可用 `GET /assets?t=models|textures|hdris` 与 `GET /files/<id>`。API 要求唯一 User-Agent 和来源标识；文件地址来自元数据，无需猜测 CDN 路径。分辨率和格式可按任务选择。

## 导入操作知识

Blender 可集合实例化重复素材；`scripts/blender_scene.py` 的 import_asset 将 GLTF/GLB/BLEND 按包围盒底部中心归一化，使用统一 scale 和 rotation_z，不改变原始 UV。其他原点、非均匀缩放或造型需求可直接通过 bpy 处理。具体字段见 [接口](project-data.md)。

原始文件可能有不同单位、正面方向、法线、纹理色彩空间和依赖路径。原点在某个范围内不代表完整几何也在范围内；`oriented_footprint` 可计算保守占地，精确检查可使用实际几何。家具面向、植被与通路的关系可以按当前设计需要判断，无固定镜头数或检查表。

`Material.maps` 支持 base_color/roughness/normal/metallic；`texture_size_m` 表示物理重复尺度；render.hdri 接项目图像。公开模型文件按数据导入，随库 Blender 不启用自动执行下载文件中的脚本。

独立交付 BLEND 时可 pack 图像依赖；公开分发源素材时按其许可决定范围。是否另写资产表、采用随库 manifest 或沿用项目记录，可按交付需求选择。

插件、几何/材质节点组和自动化接入见 [Blender 社区能力](blender-ecosystem.md)。成熟资产可以与自行建模组合使用；AI 负责资源选择、尺度、朝向、依赖和画面适配，不要求所有细节从基本几何重新生成。
