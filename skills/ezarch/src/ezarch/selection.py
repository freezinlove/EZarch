"""Native entity selection, temporary view styles and explicit replacement."""
from __future__ import annotations

import io
from dataclasses import dataclass

import ezdxf


@dataclass
class SelectedEntity:
    id: str
    source_handle: str
    instance_path: tuple[str, ...]
    entity: object


def clone_document(doc):
    stream = io.StringIO()
    doc.write(stream)
    stream.seek(0)
    return ezdxf.read(stream)


def select_entities(doc, predicate=None, *, layout_name='Model', nested=False):
    """predicate receives a world-coordinate entity and its instance/source identity."""
    from ezdxf.math import Matrix44
    from ezdxf.transform import copies
    selected, unsupported = [], []

    def visit(entity, matrix, path=(), ancestors=(), inherited_layer='0', inherited_color=7, hidden=False):
        handle = entity.dxf.handle or '?'
        identifier = '/'.join((*path, handle))
        layer = inherited_layer if entity.dxf.layer == '0' else entity.dxf.layer
        layer_record = doc.layers.get(layer)
        hidden = hidden or layer_record.is_off() or layer_record.is_frozen() or bool(entity.dxf.get('invisible', 0))
        color = entity.dxf.get('color', 256)
        color = inherited_color if color == 0 else color
        if entity.dxftype() == 'INSERT' and nested:
            name = entity.dxf.name
            if name in ancestors:
                unsupported.append({'id': identifier, 'reason': 'cyclic block reference'})
                return
            block = entity.block()
            if block is None or block.block.dxf.get('xref_path', ''):
                unsupported.append({'id': identifier, 'reason': 'unresolved/external block'})
                return
            instances = list(entity.multi_insert()) if entity.mcount > 1 else [entity]
            for n, instance in enumerate(instances):
                instance_path = (*path, handle + (f'[{n}]' if len(instances) > 1 else ''))
                for child in block:
                    visit(child, instance.matrix44() @ matrix, instance_path, (*ancestors, name), layer, color, hidden)
                for attribute in instance.attribs:
                    visit(attribute, matrix, instance_path, ancestors, layer, color, hidden)
            return
        errors, transformed = copies([entity], matrix)
        if errors:
            unsupported.extend({'id': identifier, 'reason': str(error)} for error in errors)
            return
        for n, transformed_entity in enumerate(transformed):
            if hidden:
                transformed_entity.dxf.invisible = 1
            transformed_entity.dxf.layer = layer
            transformed_entity.dxf.color = color
            row = SelectedEntity(identifier + (f':{n}' if len(transformed) > 1 else ''), handle, path, transformed_entity)
            if predicate is None or predicate(row):
                selected.append(row)
    for entity in doc.layouts.get(layout_name):
        visit(entity, Matrix44())
    return {'selected': selected, 'unsupported': unsupported, 'layout': layout_name,
            'scope': 'Nested affine geometry and source identity; no semantic classification. Override flattened BYBLOCK styles explicitly when needed.'}


def render_view(doc, output, *, selection=None, overrides=None, region=None, scale=None, formats=None):
    """Display copies only. Overrides map selected IDs to native DXF attributes."""
    from .cad import plot
    result = select_entities(doc) if selection is None else selection
    if not result['selected']:
        raise ValueError('No entities selected for this view')
    view = clone_document(doc)
    layout = view.modelspace()
    layout.delete_all_entities()
    overrides = overrides or {}
    ids = {row.id for row in result['selected']}
    if set(overrides) - ids:
        raise ValueError('Override ID is not in selection')
    for row in result['selected']:
        entity = row.entity.copy()
        style = overrides.get(row.id, {})
        if set(style) - {'color', 'true_color', 'lineweight', 'linetype', 'invisible', 'layer'}:
            raise ValueError('View overrides only change color, lineweight, linetype, visibility or layer')
        entity.update_dxf_attribs(style)
        layout.add_entity(entity)
    report = plot(view, output, region=region, scale=scale, formats=formats)
    return {**report, 'selected_ids': list(ids), 'unsupported': result['unsupported'], 'source_modified': False}


def replace_selection(doc, handles, replacements, *, layout_name='Model'):
    """Return a modified document copy. Does not infer selection, joins or dependencies."""
    handles, replacements = list(handles), list(replacements)
    if len(handles) != len(set(handles)) or not handles:
        raise ValueError('Explicit unique handles required')
    layout = doc.layouts.get(layout_name)
    available = {e.dxf.handle for e in layout}
    if not set(handles) <= available:
        raise ValueError('Selection includes a missing handle or another layout')
    for entity in replacements:
        if entity.dxf.layer not in doc.layers or entity.dxf.get('linetype', 'BYLAYER') not in doc.linetypes:
            raise ValueError('Replacement uses undefined layer/linetype; add resources explicitly')
        if entity.dxftype() == 'INSERT' and entity.dxf.name not in doc.blocks:
            raise ValueError('Replacement references an undefined block')
    result = clone_document(doc)
    target = result.layouts.get(layout_name)
    for handle in handles:
        target.delete_entity(result.entitydb[handle])
    added = []
    for entity in replacements:
        copy = entity.copy()
        target.add_entity(copy)
        added.append(copy.dxf.handle)
    return result, {'removed': handles, 'added': added, 'layout': layout_name}


def compare_documents(before, after):
    """Describe native serialized differences, without approval or visual conclusions."""
    from ezdxf.lldxf.tagwriter import TagCollector

    from .inspection import digest, serial
    def inventory(doc):
        result = {}
        for layout in [*doc.layouts, *doc.blocks]:
            for entity in layout:
                result[entity.dxf.handle] = digest(serial([(t.code, t.value) for t in TagCollector.dxftags(entity)]))
        return result
    a, b = inventory(before), inventory(after)
    tables = {}
    for name in ('layers', 'linetypes', 'styles', 'dimstyles'):
        def values(doc, name=name):
            return {e.dxf.name: serial(e.dxf.all_existing_dxf_attribs()) for e in getattr(doc, name)}
        if values(before) != values(after):
            tables[name] = {'before': values(before), 'after': values(after)}
    return {'added': sorted(b.keys() - a.keys()), 'removed': sorted(a.keys() - b.keys()),
            'changed': sorted(k for k in a.keys() & b.keys() if a[k] != b[k]), 'tables': tables,
            'units': [before.units, after.units], 'layouts': [[s.name for s in doc.layouts] for doc in (before, after)],
            'scope': 'Native entity tags and listed tables; IDs must be stable. Visual/semantic equivalence is not inferred.'}


def preview_changes(before, after, out, *, region, scale, formats=None):
    """Same extent/scale previews; colored changes are navigation aids, not error labels."""
    from .storage import output_path
    out = output_path(out)
    diff = compare_documents(before, after)
    result = {'differences': diff}
    for name, doc, affected, color in [('before', before, diff['removed'] + diff['changed'], 0xC54242),
                                      ('after', after, diff['added'] + diff['changed'], 0x217B9C)]:
        selection = select_entities(doc)
        overrides = {row.id: {'true_color': color} for row in selection['selected'] if row.source_handle in affected}
        result[name] = render_view(doc, out / name, selection=selection, overrides=overrides,
                                   region=region, scale=scale, formats=formats)
    return result


def patch_document(source, target, handles, replacements, *, expected_sha256, layout_name='Model'):
    """Version-bound native replacement to a separate DXF; caller creates replacement geometry."""
    from .cad import check_source, destination, read, sha256
    source, target = destination(source, target)
    if target.suffix.lower() != '.dxf':
        raise ValueError('Save the native patch as DXF; DWG conversion is a separate operation')
    if not expected_sha256:
        raise ValueError("expected_sha256 is required for a version-bound patch")
    actual = check_source(source, expected_sha256)
    doc, _ = read(source)
    result, change = replace_selection(doc, handles, replacements, layout_name=layout_name)
    result.saveas(target)
    return {**change, 'source_sha256': actual, 'output_sha256': sha256(target), 'file': str(target)}
