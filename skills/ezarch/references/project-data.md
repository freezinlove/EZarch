# Optional project.yml API

> 可选 project.yml 兼容接口：model/views/draft 所用的旧 CadQuery/OCCT 路线目前未继续维护，依赖独立 legacy-cad，默认安装不启用。该文档的构件、字段和材质范围仅适用于这些助手；可按任务选用，也可使用 [Blender 原生 API](blender-modeling.md)、独立二维工具或其他能力。

This is the input contract for the optional `model`, `views`, `brief` and `diagram` helpers, not a universal project schema. Use it only when invoking those helpers. Existing files, direct ezdxf/bpy/CadQuery calls, SVG, CSV, image coordinates and other project structures do not need to adopt it.

Within this API, lengths/positions are millimetres and colors are RGB components from 0 to 1. IDs are filename-safe; stable IDs help when using its cross-file comparisons. Fields below document the helper API; they do not prescribe a building or output style.

Top-level fields include name, units, materials, elements and optional rooms/views/cameras. Read the matching source type when calling a helper.

## Elements

| kind | Required geometric fields | Optional fields |
|---|---|---|
| box / slab | origin [x,y,z], size [dx,dy,dz] | rotation, fillet_mm |
| wall | start/end [x,y], thickness, height | z, openings |
| cylinder | origin [x,y,z], radius, height | category |
| extrusion | polygon [[x,y],...], height | z, rotation |
| stair | origin, steps, rise, run, width | rotation |
| step | file (relative STEP path) | origin, rotation |
| dxf_extrusion | file, layer, height | origin, rotation |

All helper elements require `id`, `material`; `category` controls drawing inclusion and render treatment. Useful categories include wall, slab, roof, frame, glass, door, furniture, finish, water, site. Openings support passage, window, glass_door or door, with offset/width/sill/height. Window panels, frame width/depth and materials are configurable. Door solids use a closed leaf; plans replace that leaf with an opening arc and open leaf. `swing_side: 1` opens to the left of the wall direction; `-1` reverses it.

Any element may specify `cuts`, a list of box or cylinder cutters for actual geometric openings. Cutters use the coordinates of the element shape after its primary placement, before optional final rotation. A surface color or diagrammatic patch does not alter the solid geometry.

This schema requires valid positive-area room polygons; `brief` additionally rejects same-level overlap for its net-area calculation. Overlapping analytical regions can use their own data/calculation instead. `type: courtyard` excludes that area from interior net area. Optional fields: plan_name (short plan label), label_at, label:false, fill, diagram_color, grid_mm.

Dimensions: `id`, `p1`, `p2`, `base`, `view` (kind or exact view ID). Built-in dimension annotations are horizontal/vertical; oblique/radial dimensions require an explicit ezdxf/vector adapter. Sections/elevations may set `levels: [0, 3400, 4620]` in mm. Annotations: `view`, `points` and/or `text`, `at`, `size`. Exact geometry also supports project-local scripts for custom forms, rather than growing a one-case-specific schema.

## Views, cameras and rendering

Views have ID/kind/title/scale; optional paper_mm, margin and exclude categories. Views contain no predefined footer. `font` selects a font file relative to the project YAML (or an absolute path); rich drafting views accept a `style` parameter dictionary. Plans set cut_z. Sections set axis x/y and at. Elevations/axons set normal/xdir. Curves are sampled with controlled geometric tolerance for polyline presentation; original exact shapes remain in STEP.

Cameras: position/target in mm, lens in mm, aspect, optional orthographic:true and ortho_scale in mm. `render` config supports sun_elevation/sun_rotation in degrees, sun_energy, sky_strength and exposure. Lighting is a visual study unless a location/time-based simulation is explicitly provided.

Landscape: `kind: tree`, position [x,y,z], height, crown_radius and stable seed. Trees are render decoration and symbolic plan canopies, not exact botanical CAD solids.

`brief` contains requirements/assumptions and optional `routes: [[[x,y],...],...]` for circulation diagrams. `sources` stores reference URLs, dimensions and confidence notes. None of these inputs should contain private absolute paths when intended for redistribution.

## External models and custom geometry

For a CAD model supplied as STEP, use a `kind: step` element with `file`, `material` and optional `origin`; the STEP file is resolved relative to the project YAML and hashed as a dependency. For 2D-to-3D use `kind: dxf_extrusion`, `file`, `layer`, `height`: it converts documented DXF units to mm and extrudes closed, straight XY LWPOLYLINE boundaries. Unitless, curved, overlapping, nested or nonplanar boundaries fail explicitly so the AI can resolve their semantics in a project script. Original files are never modified. For external meshes use Blender's supported importers or trimesh and explicitly resolve units. Existing DXF layers, entities and blocks can be inspected or edited with ezdxf. Extrusion heights may come from supplied dimensions or explicit design assumptions, as the task permits.

The optional Project schema is not a universal raw-file importer. Use the independent inspect/edit/convert tools for DWG and native 3DM; SKP and arbitrary curved-BRep conversion remain outside this schema. Generated exchange formats and target-app import are described in [exchange-verification.md](exchange-verification.md); they do not imply universal native object support. Native application control is not provided by this package; other available tools may be used as appropriate.


## Optional semantic and expression fields

Optional top-level `levels: [{id: L0, elevation_mm: 0}, ...]`, `site`, `assemblies`, `requirements` retain project-specific semantics without imposing a building type. When levels exist, every room and plan view names a known `level`; plan `floor_z` clips projected geometry below that storey and `cut_z` defines the cutting height. A floor is not selected merely by moving the cut plane. Room overlap checks compare only the same level. Element metadata may include level, assembly, type_code, provenance.

A view with `drafting: []` uses the richer Drawing adapter. Each command names an `op` and that method’s keyword parameters; see the Drawing API. `drawing_bounds` explicitly includes annotations; `exclude_ids` supports per-view omission. Commands are allow-listed, not arbitrary code. Custom forms and oblique dimensions remain accessible through project scripts and the full API.

PBR `materials.<name>.maps` accepts base_color/roughness/normal/metallic file paths relative to the project. texture_size_m is the physical repeat size. Generated meshes receive planar UVs in world metres; normal textures use tangent space. Imported public models preserve their authored UVs/materials.

`render.hdri` is a downloaded project image path; hdri_rotation is degrees. `render.lights` accepts AREA-light id, position/target in mm, size_mm [width,height], power_w and color. `render.asset_instances` accepts id, downloaded GLB/GLTF/BLEND file, source_url, position in mm, rotation_z in degrees and uniform scale. Origin is the asset footprint centre and bottom; default asset units are metres. Imported model sizes are saved in render-report.json. This importer packs supported image dependencies into BLEND. Its project fingerprint includes asset/PBR/HDRI files and local GLTF buffers/images, using portable relative dependency keys. It rejects remote GLTF URIs and expects downloaded dependencies; direct Blender workflows may manage assets differently.
