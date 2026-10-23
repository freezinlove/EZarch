"""Version-bound inventories and bounded queries. Full geometry stays in its native file."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from .cad import check_source, sha256
from .project import write_json


def serial(value):
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, dict):
        return {str(k): serial(v) for k, v in value.items()}
    try:
        return [serial(x) for x in value]
    except TypeError:
        return str(value)


def digest(value):
    return hashlib.sha256(json.dumps(serial(value), sort_keys=True).encode()).hexdigest()


def dxf_inventory(doc, base):
    from ezdxf import bbox
    from ezdxf.lldxf.tagwriter import TagCollector
    objects, warnings, dependencies = [], [], []
    spaces = [(s.name, s) for s in doc.layouts]
    spaces += [(f'block:{b.name}', b) for b in doc.blocks if not b.name.startswith('*Model_Space') and not b.name.startswith('*Paper_Space')]
    for name, space in spaces:
        for entity in space:
            data = serial(entity.dxf.all_existing_dxf_attribs())
            record = {'id': entity.dxf.handle, 'type': entity.dxftype(), 'layer': entity.dxf.layer,
                      'space': name, 'attributes': data}
            try:
                box = bbox.extents([entity], fast=False)
                record['bounds'] = [*box.extmin, *box.extmax] if box.has_data else None
            except (ValueError, TypeError, AttributeError, RecursionError) as error:
                record['bounds'] = None
                warnings.append(f'{record["id"]}: bounds unavailable ({type(error).__name__})')
            if entity.dxftype() in {'TEXT', 'MTEXT', 'ATTRIB', 'ATTDEF'}:
                record['text'] = entity.plain_text()
            if entity.dxftype() == 'LWPOLYLINE':
                record.update(closed=entity.closed, vertices=len(entity), has_arc=entity.has_arc)
            if entity.dxftype() == 'INSERT':
                record.update(block=entity.dxf.name, array=[entity.dxf.row_count, entity.dxf.column_count],
                              transform=list(entity.matrix44()), attributes_text=[a.dxf.text for a in entity.attribs])
            try:
                record['content_hash'] = digest([(t.code, t.value) for t in TagCollector.dxftags(entity)])
            except (ValueError, TypeError, AttributeError) as error:
                record['content_hash'] = None
                warnings.append(f'{record["id"]}: entity serialization incomplete ({type(error).__name__})')
            if entity.dxftype() in {'ACAD_PROXY_ENTITY', 'ACAD_TABLE', '3DSOLID', 'BODY', 'REGION', 'OLE2FRAME'}:
                warnings.append(f'{record["id"]} {entity.dxftype()}: inventory is not proof of visual/semantic support')
            objects.append(record)
    for block in doc.blocks:
        path = block.block.dxf.get('xref_path', '')
        if path:
            dependencies.append({'kind': 'xref', 'path': path, 'exists_relative_to_source': (base / path).exists()})
    for entity in doc.objects:
        if entity.dxftype() in {'IMAGEDEF', 'PDFDEFINITION', 'DWFDEFINITION', 'DGNDEFINITION'}:
            path = entity.dxf.get('filename', '')
            dependencies.append({'kind': entity.dxftype(), 'path': path, 'exists_relative_to_source': (base / path).exists()})
    warnings.extend(f'Missing {d["kind"]}: {d["path"]}' for d in dependencies if not d['exists_relative_to_source'])
    return {'units': doc.units, 'dxf_version': doc.dxfversion, 'objects': objects,
            'layouts': [{'name': s.name, 'entities': len(s)} for s in doc.layouts],
            'layers': [{'name': layer.dxf.name, 'off': layer.is_off(), 'frozen': layer.is_frozen(),
                        'locked': layer.is_locked(), 'color': layer.dxf.color} for layer in doc.layers],
            'fonts': [{'style': s.dxf.name, 'font': s.dxf.font, 'bigfont': s.dxf.bigfont} for s in doc.styles],
            'dependencies': dependencies, 'warnings': warnings,
            'coverage': 'Layout entities plus block definitions; INSERT bounds include transforms. Definitions are not extra placed objects. Unknown extents are null, not zero.'}


def rhino_inventory(source):
    import rhino3dm as r
    doc = r.File3dm.Read(str(source))
    if doc is None:
        raise ValueError('Unreadable 3DM')
    objects = []

    def world_bounds(geometry, transforms=(), ancestry=()):
        if isinstance(geometry, r.InstanceReference):
            key = str(geometry.ParentIdefId)
            if key in ancestry:
                return None
            definition = doc.InstanceDefinitions.FindId(geometry.ParentIdefId)
            if definition is None:
                return None
            children = [doc.Objects.FindId(uid) for uid in definition.GetObjectIds()]
            boxes = [world_bounds(child.Geometry, (geometry.Xform,) + transforms, ancestry + (key,)) for child in children if child]
            boxes = [box for box in boxes if box]
            return [min(box[i] for box in boxes) for i in range(3)] + [max(box[i] for box in boxes) for i in range(3, 6)] if boxes else None
        geometry = geometry.Duplicate()
        for transform in transforms:
            geometry.Transform(transform)
        box = geometry.GetBoundingBox()
        return [box.Min.X, box.Min.Y, box.Min.Z, box.Max.X, box.Max.Y, box.Max.Z] if box.IsValid else None

    for obj in doc.Objects:
        g, a = obj.Geometry, obj.Attributes
        item = {'id': str(a.Id), 'name': a.Name, 'type': type(g).__name__,
                'layer': a.LayerIndex, 'bounds': world_bounds(g),
                'visible': a.Visible, 'definition_object': a.IsInstanceDefinitionObject,
                'content_hash': digest([g.Encode(), a.Encode()]), 'valid': g.IsValid}
        if isinstance(g, r.Brep):
            item.update(solid=g.IsSolid, faces=len(g.Faces), edges=len(g.Edges))
        if isinstance(g, r.Extrusion):
            item.update(solid=g.IsSolid, profiles=g.ProfileCount)
        if isinstance(g, r.Mesh):
            item.update(vertices=len(g.Vertices), faces=len(g.Faces))
        if isinstance(g, r.InstanceReference):
            item.update(definition=str(g.ParentIdefId), transform=[[getattr(g.Xform, f'M{i}{j}') for j in range(4)] for i in range(4)])
        objects.append(item)
    return {'units': str(doc.Settings.ModelUnitSystem), 'tolerance': doc.Settings.ModelAbsoluteTolerance,
            'objects': objects, 'layers': [{'id': layer.Index, 'name': layer.Name, 'parent': str(layer.ParentLayerId),
                                          'visible': layer.Visible, 'locked': layer.Locked} for layer in doc.Layers],
            'warnings': ['BRep bounds/IDs do not expose all trim topology. Wire previews are not shaded or hidden-line views.'],
            'coverage': 'Native geometry and attributes retained; instance definitions are not separate placed objects'}


def svg_inventory(source):
    import xml.etree.ElementTree as ET
    root = ET.parse(source).getroot()
    objects = []
    for i, node in enumerate(root.iter()):
        objects.append({'id': node.get('id') or f'index:{i}', 'type': node.tag.rsplit('}', 1)[-1],
                        'attributes': dict(node.attrib), 'text': (node.text or '').strip(),
                        'content_hash': digest([node.tag, dict(node.attrib), node.text, node.tail,
                                                [(child.tag, child.get('id')) for child in node]])})
    return {'units': 'viewBox/user units; physical width/height separate', 'root': dict(root.attrib),
            'objects': objects, 'warnings': ['DOM attributes are not computed CSS or world bounds; inspect rendering for inherited styles, transforms, use/clip/mask and external assets.']}


def inspect(source, out, preview=False, scale=None, layout_name='Model', region=None, handles=None):
    from .storage import output_path
    source, out = Path(source).resolve(), output_path(out)
    out.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix.lower()
    report = {'source': str(source), 'sha256': sha256(source), 'format': suffix[1:], 'objects': []}
    if suffix in {'.dwg', '.dxf'}:
        from .cad import plot, read
        doc, working = read(source, out / 'working')
        report.update(dxf_inventory(doc, source.parent), working_file=str(working), working_sha256=sha256(working))
        if preview:
            report['preview'] = plot(doc, out / 'view', scale, layout_name, handles, region)
    elif suffix == '.3dm':
        report.update(rhino_inventory(source))
        if preview:
            from .rhino import preview as rhino_preview
            report['preview'] = rhino_preview(source, out / 'view', handles=handles)
    elif suffix in {'.step', '.stp'}:
        import cadquery as cq

        from .geometry import bounds
        shape = cq.importers.importStep(str(source)).val()
        solids = shape.Solids() or [shape]
        report.update(units='mm (OCCT import normalization)', objects=[
            {'id': f'solid:{i}', 'type': s.ShapeType(), 'bounds': bounds(s),
             'valid': s.isValid(), 'volume': s.Volume(), 'area': s.Area(),
             'faces': len(s.Faces()), 'edges': len(s.Edges())} for i, s in enumerate(solids)],
            warnings=['solid:N IDs belong to this file version. Assembly names/styles are not loaded by this shape reader.'])
        if preview:
            target = out / 'view.svg'
            cq.exporters.export(shape, str(target), opt={'showAxes': False, 'showHidden': True})
            report['preview'] = raster_svg(target)
    elif suffix in {'.glb', '.gltf', '.dae', '.obj', '.stl', '.ply'}:
        import trimesh
        scene = trimesh.load(source, force='scene')
        objects = []
        for name in scene.graph.nodes_geometry:
            transform, key = scene.graph.get(name)
            geo = scene.geometry[key]
            points = trimesh.transform_points(geo.vertices, transform)
            objects.append({'id': name, 'geometry': key, 'type': 'mesh', 'vertices': len(geo.vertices),
                            'faces': len(geo.faces), 'transform': transform.tolist(),
                            'bounds': [*points.min(0), *points.max(0)]})
        report.update(objects=objects, units=scene.units, metadata=serial(scene.metadata),
                      warnings=['Scene graph transforms applied to bounds. Verify file-specific units/up axis and material/external dependencies; mesh is not exact BRep.'])
        if suffix in {'.glb', '.gltf'}:
            report['units'] = 'm; glTF +Y up'
        if suffix == '.dae':
            import collada
            doc = collada.Collada(str(source))
            report['units'] = {'unitmeter': doc.assetInfo.unitmeter, 'up_axis': doc.assetInfo.upaxis}
        if preview:
            report['warnings'].append('For mesh views use Blender import/render with chosen camera; inventory does not render materials.')
    elif suffix == '.blend':
        from .render import inspect_blend
        report.update(inspect_blend(source, out))
    elif suffix == '.svg':
        report.update(svg_inventory(source))
        if preview:
            report['preview'] = raster_svg(source, out / 'view.png')
    elif suffix == '.pdf':
        import pymupdf as fitz
        with fitz.open(source) as doc:
            report['pages'] = []
            for n, page in enumerate(doc):
                report['pages'].append({'page': n + 1, 'bounds_pt': list(page.rect),
                                        'text': page.get_text(), 'vector_paths': len(page.get_drawings())})
                if preview:
                    clip = fitz.Rect(region) if region else None
                    page.get_pixmap(dpi=150, clip=clip, alpha=False).save(out / f'page-{n + 1}.png')
            report['warnings'] = report.get('warnings', []) + ['PDF/SVG coordinates describe the sheet, not building units. Raster/scanned content may need OCR; perspective photos do not have a uniform measured scale.']
    else:
        from PIL import Image
        with Image.open(source) as im:
            report.update(pixels=list(im.size), mode=im.mode, units='pixels')
            if preview:
                if region:
                    im = im.crop(tuple(region))
                im.thumbnail((2400, 2400))
                im.convert('RGB').save(out / 'view.png')
    report['object_count'] = len(report['objects'])
    report['types'] = dict(Counter(o.get('type') for o in report['objects']))
    write_json(out / 'inspection.json', serial(report))
    summary = {k: report[k] for k in ('source', 'sha256', 'format', 'units', 'object_count', 'types', 'working_file', 'preview') if k in report}
    summary['counts'] = {k: len(report[k]) for k in ('pages', 'layers', 'fonts', 'instances', 'dependencies') if k in report}
    summary['warnings'] = report.get('warnings', [])[:12]
    summary['warning_count'] = len(report.get('warnings', []))
    if 'preview' in summary and len(summary['preview'].get('skipped', [])) > 12:
        summary['preview'] = dict(summary['preview'], skipped_count=len(summary['preview']['skipped']), skipped=summary['preview']['skipped'][:12])
    summary['report'] = str(out / 'inspection.json')
    return summary


def query(index, source=None, ids=None, layer=None, kind=None, space=None, contains=None, region=None, offset=0, limit=40, section="objects"):
    report = json.loads(Path(index).read_text(encoding='utf-8'))
    check_source(source or report['source'], report['sha256'])
    if report.get('working_sha256'):
        check_source(report['working_file'], report['working_sha256'])
    if offset < 0 or not 1 <= limit <= 500:
        raise ValueError('Use offset >= 0 and limit 1..500')
    rows = report.get(section, [])
    if not isinstance(rows, list):
        raise ValueError('Query section must be a list')
    rows = [dict(row, id=row.get('id', f'{section}:{i}')) for i, row in enumerate(rows)]
    if ids:
        rows = [r for r in rows if r['id'] in ids]
    if layer is not None:
        rows = [r for r in rows if str(r.get('layer')) == str(layer)]
    if kind:
        rows = [r for r in rows if r.get('type') == kind]
    if space:
        rows = [r for r in rows if r.get('space') == space]
    if contains:
        rows = [r for r in rows if contains.casefold() in json.dumps(r, ensure_ascii=False).casefold()]
    if region:
        rows = [r for r in rows if r.get('bounds') and r['bounds'][0] <= region[2]
                and r['bounds'][3] >= region[0] and r['bounds'][1] <= region[3] and r['bounds'][4] >= region[1]]
    return {'source_sha256': report['sha256'], 'matched': len(rows), 'offset': offset,
            'next_offset': offset + limit if offset + limit < len(rows) else None, 'objects': rows[offset:offset + limit]}


def compare(before, after):
    reports = [json.loads(Path(p).read_text(encoding='utf-8')) for p in (before, after)]
    for r in reports:
        check_source(r['source'], r['sha256'])
    a, b = [{o['id']: o for o in r['objects']} for r in reports]
    shared = a.keys() & b.keys()
    return {'before_sha256': reports[0]['sha256'], 'after_sha256': reports[1]['sha256'],
            'added': sorted(b.keys() - a.keys()), 'removed': sorted(a.keys() - b.keys()),
            'changed': sorted(k for k in shared if a[k] != b[k]),
            'scope': 'Stable IDs and inventoried properties; inspect changed IDs, regenerated IDs, document settings and visual results separately'}


def raster_svg(source, output=None):
    import resvg_py

    from .project import skill_root
    source = Path(source)
    target = Path(output) if output else source.with_suffix('.png')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(resvg_py.svg_to_bytes(svg_path=str(source), width=2400, dpi=96,
                       resources_dir=str(source.parent),
                       font_dirs=[str(skill_root() / 'assets/fonts')], background='white'))
    return {'svg': str(source), 'png': str(target), 'renderer': 'resvg',
            'scope': 'Static SVG preview; verify fonts/external assets and use a browser for unsupported web features'}
