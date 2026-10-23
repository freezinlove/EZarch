# Changelog

## Unreleased

- Add editable route/direction, road-boundary and canopy primitives. Add per-text/role fonts, TTC face export, shaped HTML text boxes, SVG composition and explicit editable/outlined SVG text.

- Add selected PDF page/crop exports, explicit vector-to-CAD mapping with unsupported clipping reported, affine control-point fitting, nested entity selection, temporary view styles, version-bound replacement and same-extent change previews.

- Add release manifests, cached nonblocking update notices, optional background preparation, explicit safe activation/reload, local-change protection, rollback and interrupted-transaction recovery. Add tagged release packaging workflow.

- Add user-selected shared runtime locations, dependency reuse, isolated caches, capability probes and recoverable preparation. Keep old environments and make system font registration explicit.
- Protect normal output entry points from accidental writes into tool code; provide opt-in staged/push Git boundary checks without changing existing hooks.

- Reorganize the entry into a short capability index and focused operation references. Replace the general design-judgment expansion with concise visual guidance linked to actual drawings, model views and edits.
- Remove `audit`, `review`, wall diagnostics, annotation-conflict and reachability modules, issue/coverage reporting, and `check_clearances`. Retain direct geometry measurements, input errors and native file validity handling. These removed APIs have no success-returning compatibility stubs.
- Render new Drawing exports from current CAD entities by default, including native edits and placed components. CAD text remains editable in DXF; SVG/PDF views use outlines. Explicit `view_source="canvas"` retains recorded Canvas exports, including editable text; it does not track native CAD changes. Legacy project view generation retains this recorded mode.
- Connect the existing component geometry to `Drawing.symbol` and `Canvas.symbol`; `Canvas.cad` refreshes embedded CAD during saving. Extend CAD plotting to SVG and preserve exact physical page dimensions and explicitly selected TTF/OTF fonts.
- Remove automatic overlap rejection from board composition and the legacy area brief; allow page cropping and impose an image PPI floor only when explicitly supplied.
- Retain colors, lineweights, dash patterns, polygon holes, text positioning, coordinate transforms, measurements and native Drawing binding. Correct outdated interface descriptions and release manifests; dependency installation and update mechanisms are unchanged.

## 0.6.0

- Make native Blender Python the primary 3D route, with optional script execution, evaluated mesh extraction, GLB/3DM/DAE exchange and mesh-based sections/hidden-line projections.
- Keep full .blend editing independent of project.yml, preserve source scenes, and verify exchange units against evaluated geometry.
- Add focused modeling and community-plugin/node-asset guidance; expand material, render-pass and compositing guidance without prescribing designs or task sequences.
- Remove CadQuery/OCCT/VTK from default installation profiles; retain old project helpers behind a legacy-cad extra for existing projects only. Precise STEP is deferred.
- Retain modular CAD/SVG/PDF tools, proposal confirmation, design/precision expectations, and public-project separation.

## 0.5.0

- Accept raw-file workflows: version-bound inspection, bounded object queries, CAD/3DM/SVG selection edits and inventory comparison, independent of Project YAML.
- Add optional official ODA setup and isolated DWG/DXF round trips; keep full documents and report missing dependencies.
- Add native 3DM geometry writing and exact prismatic BRep export with holes; unsupported geometry fails instead of silently becoming a mesh.
- Inspect Blender evaluated geometry, instances and dependencies without embedded script execution.
- Use resvg for static SVG previews, with clip/transform/CSS/physical-size regression coverage.
- Add conditional architectural design reasoning, standards applicability and multi-source understanding references; preserve model/user discretion.
- Remove demonstration scripts/configurations and preset drawing footers. Update packaging and regression tests.


## 0.4.1

- Package the skill from an explicit file list; reject selected symlinks/junctions and invalid paths.
- Restrict wheel inputs to individual source/resource files and validate them before packaging.
- Upgrade CadQuery to 2.8.0, OCP to 7.9.3.1.1 and VTK to 9.6.2, removing the vulnerable VTK 9.3.1 dependency.
- Retain Intel Mac binary installation with a platform-specific Numba constraint; require wheels for native dependencies.
- Document the existing macOS 14 minimum of the model environment's rhino3dm wheel.

## 0.4.0

- Preserve existing BLEND render settings by default; support Chinese camera names without renaming objects.
- Make drawing footers opt-in; expose font, angle, symbol parameters and selected output formats.
- Correct GLB Z-up to glTF Y-up conversion and compare readback in source coordinates.
- Default model output to STEP; allow selected scene/mesh exports and independent file checks.
- Retain legacy evidence review only for maintenance compatibility, outside normal skill guidance.
- Add executable native ezdxf, CadQuery, bpy and SVG editing examples with coordinate/editing notes.
- Explicitly keep resource search and tool selection open; rename spatial design guidance to spatial measurement.

## 0.3.0

- Recast the skill as optional tool guidance: user requirements, references and model judgement drive the work.
- Remove mandatory task files, staged design sequences, universal audit routines and fixed deliverable packages.
- Scope geometry schemas, units, fonts and drawing rules to the tools and tasks where they apply.
- Document direct SVG/native API routes and helper limitations without requiring a justification for bypassing helpers.
- Keep modular bootstrap, public asset access, exchange utilities and technical drafting references.
- Allow optional evidence review with task-selected criteria and free/omitted categories; preserve stale-evidence detection and legacy record compatibility.
- Align repository guidance and mark historical workflow documents as superseded.

## 0.2.0

- Route create/develop/reconstruct tasks by selected modules and project-specific acceptance conditions.
- Add lightweight Chinese drafting helpers, 2D furniture, independently editable DXF and matching PDF/SVG output.
- Add floor scope, real asset footprints, door operation notation and metadata for coordinated drawings/models.
- Download public Poly Haven resources with dependencies, provenance, checksums and retries; no bundled 3D library.
- Add physical PBR scale, HDRI/area lights and reusable Blender collection instances with packed dependencies.
- Add explicit route/door clearance and solar helpers, with limited analytical scope.
- Separate technical integrity from standards/completeness/design/presentation review with current-file evidence.
- Strengthen board text fitting, slot overlap and scale checks; batch vector paths without changing painter order.
- Bind independently refined drawing/camera sources and inspect packed BLEND images and asset instances on readback.
- Keep north/index symbols on annotation layers so CAD editing and model-projection checks remain separate.
- Keep project validation outside the skill repository. Native commercial application control and IFC remain deferred.
