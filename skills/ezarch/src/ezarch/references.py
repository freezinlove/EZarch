"""Selected-page reference extraction and explicit vector coordinate mapping."""
from pathlib import Path

from .cad import sha256
from .storage import output_path


def catalog_sources(paths):
    """File identity and lightweight page/layout metadata; no implicit latest version."""
    result, known = [], {}
    for value in paths:
        path = Path(value).expanduser().resolve()
        row = {'path': str(path), 'format': path.suffix.lower()}
        try:
            row.update(sha256=sha256(path), bytes=path.stat().st_size)
            row['duplicate_of'] = known.get(row['sha256'])
            known.setdefault(row['sha256'], str(path))
            if path.suffix.lower() == '.pdf':
                import pymupdf
                with pymupdf.open(path) as doc:
                    row.update(pages=len(doc), encrypted=doc.needs_pass)
            elif path.suffix.lower() == '.dxf':
                import ezdxf
                doc = ezdxf.readfile(path)
                row.update(layouts=[s.name for s in doc.layouts], units=doc.units)
            row['state'] = 'listed'
        except Exception as error:
            row.update(state='unavailable', error=str(error))
        result.append(row)
    return result


def extract_reference(source, out, *, pages=None, region=None, dpi=150):
    """1-based PDF pages; region in displayed page points. Preserve a clipped vector view."""
    import pymupdf as fitz

    from .inspection import serial
    from .runtime import atomic_json
    source, out = Path(source).resolve(), output_path(out)
    with fitz.open(source) as doc:
        selected = list(range(1, len(doc) + 1)) if pages is None else list(pages)
        if len(selected) != len(set(selected)) or any(not isinstance(n, int) or not 1 <= n <= len(doc) for n in selected):
            raise ValueError('pages must be unique 1-based existing page numbers')
        if dpi <= 0:
            raise ValueError('dpi must be positive')
        out.mkdir(parents=True, exist_ok=True)
        report = {'source': str(source), 'sha256': sha256(source), 'pages': []}
        for number in selected:
            page = doc[number - 1]
            clip = fitz.Rect(region) if region else page.rect
            if clip.is_empty or clip.is_infinite or not page.rect.contains(clip):
                raise ValueError('region must lie inside the displayed page')
            # MuPDF extraction uses unrotated coordinates; rendering uses displayed coordinates.
            source_clip = clip * page.derotation_matrix
            stem = out / f'page-{number:03d}'
            page.get_pixmap(dpi=dpi, clip=clip, alpha=False).save(stem.with_suffix('.png'))
            view = fitz.open()
            target = view.new_page(width=clip.width, height=clip.height)
            target.show_pdf_page(target.rect, doc, number - 1, clip=source_clip, rotate=page.rotation)
            view.save(stem.with_suffix('.pdf'))
            stem.with_suffix('.svg').write_text(target.get_svg_image(text_as_path=True), encoding='utf-8')
            view.close()
            drawings = page.get_drawings(extended=True)
            atomic_json(stem.with_suffix('.paths.json'), serial(drawings))
            stem.with_suffix('.txt').write_text(page.get_text(clip=source_clip), encoding='utf-8')
            report['pages'].append({'page': number, 'rotation': page.rotation, 'display_region_pt': list(clip),
                                     'source_region_pt': list(source_clip), 'paths': len(drawings),
                                     'path_coordinates': 'unrotated page points, Y down; full page paths retain clipping records',
                                     'stem': str(stem)})
    atomic_json(out / 'reference.json', report)
    return report


def fit_reference_transform(source_points, target_points):
    import numpy as np
    source, target = np.asarray(source_points, dtype=float), np.asarray(target_points, dtype=float)
    if source.shape != target.shape or source.ndim != 2 or source.shape[1] != 2 or len(source) < 3:
        raise ValueError('At least three corresponding 2D points required')
    if not np.isfinite(source).all() or not np.isfinite(target).all():
        raise ValueError('Control points must be finite')
    matrix = np.column_stack((source, np.ones(len(source))))
    coefficients, _, rank, _ = np.linalg.lstsq(matrix, target, rcond=None)
    if rank < 3:
        raise ValueError('Collinear control points cannot define an affine mapping')
    residual = np.linalg.norm(matrix @ coefficients - target, axis=1)
    return {'transform': [float(coefficients[0, 0]), float(coefficients[1, 0]), float(coefficients[0, 1]),
                           float(coefficients[1, 1]), float(coefficients[2, 0]), float(coefficients[2, 1])],
            'residuals_target_units': residual.tolist(), 'max_residual': float(residual.max())}


def map_reference_geometry(paths, layout, *, transform, indices=None, region=None, dxfattribs=None):
    """Map explicitly selected PDF paths to lines/cubic splines/hatches; no OCR or object inference."""
    import pymupdf as fitz
    from ezdxf import colors
    from ezdxf.path import Path as CadPath
    from ezdxf.path import render_hatches

    from .frames import transform_points
    selected = set(range(len(paths))) if indices is None else set(indices)
    if not selected <= set(range(len(paths))):
        raise ValueError('Path index missing')
    entities, skipped, clipped = [], [], []
    def point(value):
        return transform_points([tuple(value)], transform)[0]
    for index, item in enumerate(paths):
        level = item.get('level', 0)
        clipped = [n for n in clipped if n < level]
        if item['type'] == 'clip':
            clipped.append(level)
            continue
        if index not in selected or item['type'] == 'group':
            continue
        if clipped or (region is not None and not fitz.Rect(region).contains(fitz.Rect(item['rect']))):
            skipped.append({'index': index, 'reason': 'clipped path: use extracted SVG/PDF to retain clipping'})
            continue
        if any(segment[0] not in {'l', 'c', 're', 'qu'} for segment in item['items']):
            skipped.append({'index': index, 'reason': 'unsupported path command'})
            continue
        contours, current = [], None
        for segment in item['items']:
            kind = segment[0]
            if kind in {'re', 'qu'}:
                if current:
                    contours.append(current)
                    current = None
                shape = segment[1]
                if kind == 're':
                    rect = fitz.Rect(shape)
                    pts = [rect.tl, rect.tr, rect.br, rect.bl]
                else:
                    quad = fitz.Quad(shape)
                    pts = [quad.ul, quad.ur, quad.lr, quad.ll]
                polygon = CadPath(point(pts[0]))
                for p in pts[1:]:
                    polygon.line_to(point(p))
                polygon.close()
                contours.append(polygon)
            else:
                first = point(segment[1])
                if current is None or not current.end.isclose(first):
                    if current:
                        contours.append(current)
                    current = CadPath(first)
                if kind == 'l':
                    current.line_to(point(segment[2]))
                else:
                    current.curve4_to(point(segment[4]), point(segment[2]), point(segment[3]))
        if current:
            if item.get('closePath'):
                current.close()
            contours.append(current)
        attributes = dict(dxfattribs or {})
        if item.get('fill') is not None:
            if len(contours) > 1 and not item.get('even_odd'):
                skipped.append({'index': index, 'reason': 'nonzero-winding compound fill not adapted'})
            else:
                fill_attributes = {**attributes, 'true_color': colors.rgb2int(tuple(round(c * 255) for c in item['fill']))}
                entities.extend(render_hatches(layout, contours, dxfattribs=fill_attributes))
        if item.get('color') is not None:
            from ezdxf.path import render_splines_and_polylines
            stroke = {**attributes, 'true_color': colors.rgb2int(tuple(round(c * 255) for c in item['color']))}
            entities.extend(render_splines_and_polylines(layout, contours, dxfattribs=stroke))
    return {'entities': entities, 'skipped': skipped, 'transform': tuple(transform),
            'scope': 'Selected vector paths only; text/images/transparency are not architectural objects; stroke style supplied by caller'}
