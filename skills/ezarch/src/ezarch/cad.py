"""Whole-document CAD operations; source coordinates and object handles survive edits."""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def check_source(source, expected=None):
    actual = sha256(source)
    if expected and actual != expected:
        raise ValueError('Source changed since inspection; inspect the latest file before using old object selections')
    return actual


def destination(source, target):
    from .storage import output_path
    source, target = Path(source).resolve(), output_path(target)
    if source == target:
        raise ValueError('Choose a separate output file; this helper preserves the source')
    if target.exists():
        raise FileExistsError(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    return source, target


def find_oda():
    from .project import skill_root
    from .runtime import locations, registered_tool
    cache = locations()['tools'] / 'oda'
    candidates = [os.environ.get('EZARCH_ODA'), shutil.which('ODAFileConverter'),
                  cache / 'ODAFileConverter.app/Contents/MacOS/ODAFileConverter',
                  skill_root() / '.ezarch/tools/oda/ODAFileConverter.app/Contents/MacOS/ODAFileConverter',
                  registered_tool('oda')]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    # MSI extraction may create nested vendor directories, but only search the ODA cache.
    if cache.is_dir():
        for candidate in cache.glob('**/ODAFileConverter.exe'):
            if candidate.is_file():
                return str(candidate.resolve())
    # Do not recursively walk /Applications: Xcode bundles can contain hundreds of thousands
    # of files, and conversion calls this probe repeatedly. Custom locations use EZARCH_ODA.
    for root in (Path.home() / 'Applications', Path('/Applications')):
        for pattern in ('ODA*.app/Contents/MacOS/ODAFileConverter',
                        'ODA*/ODA*.app/Contents/MacOS/ODAFileConverter'):
            for candidate in root.glob(pattern):
                if candidate.is_file():
                    return str(candidate.resolve())
    if os.environ.get('ProgramFiles'):
        for candidate in (Path(os.environ['ProgramFiles']) / 'ODA').glob('**/ODAFileConverter.exe'):
            if candidate.is_file():
                return str(candidate.resolve())
    return None


def convert(source, target, version='ACAD2018', repair=False, timeout=180):
    """Isolate one file, never audit/repair silently, check the actual output signature."""
    source, target = destination(source, target)
    if source.suffix.lower() not in {'.dwg', '.dxf'} or target.suffix.lower() not in {'.dwg', '.dxf'}:
        raise ValueError('ODA adapter accepts DWG/DXF only')
    executable = find_oda()
    if not executable:
        raise RuntimeError('ODA File Converter missing. Run bootstrap.py --install-oda or set EZARCH_ODA; ezdxf alone cannot read DWG')
    from ezdxf.addons.odafc import VALID_VERSIONS, map_version
    version = map_version(version)
    if version not in VALID_VERSIONS:
        raise ValueError(f'Unsupported ODA version: {version}')
    with tempfile.TemporaryDirectory(prefix='ezarch-oda-') as tmp:
        root = Path(tmp)
        incoming, outgoing = root / 'in', root / 'out'
        incoming.mkdir()
        outgoing.mkdir()
        # A neutral isolated name also handles Unicode, glob characters and unrelated files.
        copied = incoming / ('source' + source.suffix.lower())
        shutil.copy2(source, copied)
        command = [executable, str(incoming), str(outgoing), version, target.suffix[1:].upper(),
                   '0', '1' if repair else '0', copied.name]
        startup = {'creationflags': subprocess.CREATE_NO_WINDOW} if platform.system() == 'Windows' else {}
        run = subprocess.run(command, capture_output=True, text=True, errors='replace', timeout=timeout, **startup)
        result = outgoing / ('source' + target.suffix.lower())
        if run.returncode or not result.is_file() or result.stat().st_size == 0:
            raise RuntimeError(f'ODA conversion failed ({run.returncode}): {(run.stderr or run.stdout)[-1800:]}')
        if target.suffix.lower() == '.dxf':
            import ezdxf
            ezdxf.readfile(result)  # Conversion success is not a completeness/compliance claim.
        elif not result.read_bytes()[:6].startswith(b'AC10'):
            raise ValueError('ODA result has no DWG signature')
        shutil.copy2(result, target)
    return {'source_sha256': sha256(source), 'output_sha256': sha256(target), 'file': str(target),
            'version': version, 'repair_requested': repair, 'converter': 'ODA File Converter',
            'scope': 'Conversion and parse/signature only; compare content and target application behavior'}


def read(source, cache=None):
    import ezdxf
    source = Path(source)
    if source.suffix.lower() == '.dxf':
        return ezdxf.readfile(source), source
    if source.suffix.lower() != '.dwg':
        raise ValueError('Expected DWG or DXF')
    if cache is None:
        raise ValueError('DWG reading needs a project-local conversion directory')
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / f'{source.stem}-{sha256(source)[:16]}.dxf'
    metadata = target.with_suffix('.conversion.json')
    if not target.exists():
        result = convert(source, target)
        metadata.write_text(json.dumps(result, indent=2), encoding='utf-8')
    elif metadata.exists():
        result = json.loads(metadata.read_text(encoding='utf-8'))
        if result['source_sha256'] != sha256(source) or result['output_sha256'] != sha256(target):
            raise ValueError('Converted working copy changed; choose it explicitly as the new source or use a fresh conversion directory')
    else:
        raise ValueError('Existing conversion has no version record; choose a fresh output directory')
    doc = ezdxf.readfile(target)
    doc.filename = str(source)  # Relative dependencies remain rooted at the supplied file.
    return doc, target


def render(doc, scale=None, layout_name='Model', handles=None, region=None, *,
           margin=10, background=True):
    """Render current native entities to in-memory vector PDF plus view metadata."""
    import ezdxf
    from ezdxf.addons.drawing import Frontend, RenderContext, layout, pymupdf
    from ezdxf.addons.drawing.config import BackgroundPolicy, Configuration
    from ezdxf.math import BoundingBox2d
    if scale is not None and (not math.isfinite(scale) or scale <= 0 or doc.units == 0):
        raise ValueError('Print scale needs positive scale and known source units')
    if not math.isfinite(margin) or margin < 0:
        raise ValueError('Margin must be finite and nonnegative')
    if region is not None and (len(region) != 4 or not all(math.isfinite(v) for v in region)
                               or region[2] <= region[0] or region[3] <= region[1]):
        raise ValueError('Region needs finite xmin, ymin, xmax, ymax with positive extent')
    class BatchedRenderer(pymupdf.PyMuPdfRenderBackend):
        def __init__(self, page, settings):
            import pymupdf as fitz
            super().__init__(page, settings)
            # ezdxf 1.4.4 truncates the paper size to whole PDF points.
            self.page_width_in_pt = page.width_in_mm * 72 / 25.4
            self.page_height_in_pt = page.height_in_mm * 72 / 25.4
            self.page.set_mediabox(fitz.Rect(0, 0, self.page_width_in_pt, self.page_height_in_pt))
            self.content_shape = self.page.new_shape()

        def draw_solid_lines(self, lines, properties):
            from itertools import islice
            iterator = iter(lines)
            while batch := list(islice(iterator, 500)):
                super().draw_solid_lines(batch, properties)

    class BatchedBackend(pymupdf.PyMuPdfBackend):
        @staticmethod
        def make_backend(page, settings):
            return BatchedRenderer(page, settings)

    backend = BatchedBackend()
    warnings = []

    class ReportingFrontend(Frontend):
        def skip_entity(self, entity, msg):
            warnings.append({'handle': entity.dxf.handle, 'type': entity.dxftype(), 'reason': msg})
            super().skip_entity(entity, msg)

    selected = set(handles or [])
    from ezdxf import bbox
    source_layout = doc.layouts.get(layout_name)
    candidates = [e for e in source_layout if not selected or e.dxf.handle in selected]
    estimate = BoundingBox2d([(region[0], region[1]), (region[2], region[3])]) if region else bbox.extents(candidates, fast=True)
    estimate_size = max(estimate.size) if estimate.has_data else 1
    paper_factor = ezdxf.units.conversion_factor(doc.units, ezdxf.units.MM) / scale if scale and doc.units else 270 / max(estimate_size, 1e-9)
    # Use explicit font files in this frontend only. ezdxf's global resolver
    # otherwise falls back for absolute paths and can cache that fallback.
    from ezdxf.addons.drawing.unified_text_renderer import UnifiedTextRenderer
    from ezdxf.fonts import font_manager, fonts
    font_overrides, file_fonts = {}, {}
    for style in doc.styles:
        font_path = Path(style.dxf.font)
        if font_path.suffix.lower() not in {'.ttf', '.otf'}:
            continue
        if not font_path.is_absolute() and doc.filename:
            base = Path(doc.filename).resolve().parent
            font_path = next((p for p in (base / font_path, base / 'fonts' / font_path)
                              if p.is_file()), font_path)
        if font_path.is_absolute() and font_path.is_file():
            face = font_manager.get_ttf_font_face(font_path)
            font_overrides[style.dxf.name.lower()] = fonts.FontFace(
                filename=str(font_path), family=face.family, style=face.style,
                weight=face.weight, width=face.width)
            file_fonts[str(font_path).lower()] = fonts.sideload_ttf(font_path, 1)

    class FileTextRenderer(UnifiedTextRenderer):
        def get_font(self, font_face):
            font = file_fonts.get(font_face.filename.lower())
            return font if font is not None else super().get_font(font_face)
    context = RenderContext(doc)
    context.fonts.update(font_overrides)
    frontend = ReportingFrontend(context, backend,
        config=Configuration(background_policy=BackgroundPolicy.WHITE if background else BackgroundPolicy.OFF,
                             max_flattening_distance=.02 / paper_factor,
                             min_dash_length=.05 / paper_factor,
                             min_hatch_line_distance=.05 / paper_factor))
    frontend.pipeline.text_engine = FileTextRenderer()
    frontend.draw_layout(doc.layouts.get(layout_name), filter_func=(lambda e: e.dxf.handle in selected) if selected else None)
    bounds = BoundingBox2d([(region[0], region[1]), (region[2], region[3])]) if region else backend.player().bbox()
    if not bounds.has_data:
        raise ValueError('Empty view; inspect layout, visibility and selected objects')
    if scale is not None:
        if scale <= 0 or doc.units == 0:
            raise ValueError('Print scale needs positive scale and known source units; do not guess unitless CAD')
        factor = ezdxf.units.conversion_factor(doc.units, ezdxf.units.MM) / scale
    else:
        factor = 270 / max(max(bounds.size), 1)  # Preview size only, not a claimed drawing scale.
    if min(bounds.size) <= 0:
        # A line is drawable. Give its zero-width axis a small finite page extent.
        lo, hi = list(bounds.extmin), list(bounds.extmax)
        for i in range(2):
            if hi[i] == lo[i]:
                lo[i] -= .05 / factor
                hi[i] += .05 / factor
        bounds = BoundingBox2d([lo, hi])
    width, height = [v * factor + margin * 2 for v in bounds.size]
    page = layout.Page(width, height, margins=layout.Margins.all(margin))
    settings = layout.Settings(scale=factor, fit_page=False,
                               output_coordinate_space=max(width, height) * 72 / 25.4)
    player = backend.player()
    matrix = layout.Layout(bounds, flip_y=True).get_placement_matrix(page, settings=settings, top_origin=True)
    player.transform(matrix)
    renderer = BatchedRenderer(page, settings)
    player.replay(renderer)
    content = renderer.get_pdf_bytes()
    renderer.doc.close()
    return content, {'layout': layout_name, 'width_mm': width, 'height_mm': height,
                     'source_region': [*bounds.extmin, *bounds.extmax], 'scale': scale,
                     'skipped': warnings, 'view_source': 'native_cad',
                     'display_tolerance_paper_mm': .02,
                     'minimum_dash_hatch_spacing_paper_mm': .05}


def plot(doc, output, scale=None, layout_name='Model', handles=None, region=None, dpi=150,
         *, margin=10, formats=None):
    """Save current CAD as PDF/PNG/SVG; CAD text is outlined in these views."""
    import re

    import pymupdf as fitz

    from .storage import output_path
    output = output_path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    formats = {'pdf', 'png'} if formats is None else set(formats)
    if not formats or formats - {'svg', 'pdf', 'png'}:
        raise ValueError('CAD view formats: svg, pdf, png')
    content, report = render(doc, scale, layout_name, handles, region, margin=margin)
    with fitz.open(stream=content, filetype='pdf') as rendered:
        page = rendered[0]
        if 'pdf' in formats:
            output.with_suffix('.pdf').write_bytes(content)
        if 'png' in formats:
            page.get_pixmap(dpi=dpi, alpha=False).save(output.with_suffix('.png'))
        if 'svg' in formats:
            svg = page.get_svg_image(text_as_path=True)
            svg = re.sub(r'width="[^"]+"', f'width="{report["width_mm"]}mm"', svg, count=1)
            svg = re.sub(r'height="[^"]+"', f'height="{report["height_mm"]}mm"', svg, count=1)
            output.with_suffix('.svg').write_text(svg, encoding='utf-8')
        report.update(vector_paths=len(page.get_drawings()), images=len(page.get_images()))
    report.update({kind: str(output.with_suffix('.' + kind)) for kind in formats})
    report['formats'] = sorted(formats)
    return report


def edit(source, target, handles, move=None, text=None, expected=None):
    """Small selection edit. Native ezdxf API remains available for arbitrary design changes."""
    source, target = destination(source, target)
    before = check_source(source, expected)
    if move is not None and (len(move) != 3 or not all(math.isfinite(v) for v in move)):
        raise ValueError('Translation needs three finite source-unit values')
    if target.suffix.lower() not in {'.dxf', '.dwg'}:
        raise ValueError('CAD output must be DWG or DXF')
    with tempfile.TemporaryDirectory(prefix='ezarch-edit-') as tmp:
        doc, _ = read(source, Path(tmp))
        entities = [doc.entitydb.get(h) for h in handles]
        if not entities or any(e is None or not e.is_alive for e in entities):
            raise ValueError('Selection contains missing handles')
        if text is not None and any(e.dxftype() not in {'TEXT', 'MTEXT'} for e in entities):
            raise ValueError('Text replacement requires TEXT/MTEXT entities')
        for entity in entities:
            if move is not None:
                entity.translate(*move)
            if text is not None:
                if entity.dxftype() == 'TEXT':
                    entity.dxf.text = text
                else:
                    entity.text = text
        intermediate = Path(tmp) / 'edited.dxf'
        doc.saveas(intermediate)
        if target.suffix.lower() == '.dwg':
            convert(intermediate, target, version=doc.dxfversion)
        else:
            shutil.copy2(intermediate, target)
    return {'source_sha256': before, 'output_sha256': sha256(target), 'handles': handles, 'file': str(target),
            'roundtrip_note': 'DWG conversion may normalize text extent caches, spline tolerances and numeric serialization; compare actual geometry, properties and views' if target.suffix.lower() == '.dwg' else None}
