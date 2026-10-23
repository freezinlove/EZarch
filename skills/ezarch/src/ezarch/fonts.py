"""Explicit font discovery and unshaped horizontal text measurements.

No installation, global registration, implicit substitute or export. Font paths
and collection indices remain visible; callers may use a shaping engine instead.
"""
from __future__ import annotations

import math
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTCollection, TTFont

from .frames import _finite


@dataclass(frozen=True)
class FontFace:
    path: Path
    index: int = 0


def _face(value):
    face = value if isinstance(value, FontFace) else FontFace(Path(value))
    if isinstance(face.index, bool) or not isinstance(face.index, int) or face.index < 0:
        raise ValueError("Font collection index must be a nonnegative integer")
    return FontFace(Path(face.path).expanduser().resolve(), face.index)


def _open(face):
    with face.path.open("rb") as stream:
        collection = stream.read(4) == b"ttcf"
    if not collection and face.index != 0:
        raise ValueError("A standalone font has only face index 0")
    return TTFont(face.path, fontNumber=face.index)


def font_info(font, *, text=""):
    """Read real face metadata and glyph availability; no filename heuristics."""
    face = _face(font)
    with _open(face) as data:
        names, cmap = data["name"], data.getBestCmap() or {}
        os2 = data.get("OS/2")
        return {"face": face, "family": names.getDebugName(16) or names.getDebugName(1),
                "subfamily": names.getDebugName(17) or names.getDebugName(2),
                "postscript_name": names.getDebugName(6),
                "weight": os2.usWeightClass if os2 is not None else None,
                "italic": bool(data["head"].macStyle & 2 or (os2 and os2.fsSelection & 1)),
                "units_per_em": data["head"].unitsPerEm, "glyph_count": len(cmap),
                "variable": "fvar" in data,
                "missing_characters": tuple(dict.fromkeys(c for c in text if ord(c) not in cmap)),
                "embedding_fsType": os2.fsType if os2 is not None else None}


def discover_fonts(paths, *, recursive=False, family=None, weight=None, italic=None, text=""):
    """Inspect only supplied files/directories; return all matching faces + errors.

    Family/weight/italic filters are exact; missing glyphs remain visible on each
    candidate. Empty candidates do not authorize an automatic nearest match.
    fsType is metadata, not a font distribution license determination.
    """
    candidates, errors, checked, files = [], [], [], set()
    for value in paths:
        path = Path(value).expanduser().resolve()
        if path.is_dir():
            files.update(p.resolve() for p in (path.rglob("*") if recursive else path.iterdir())
                         if p.is_file() and p.suffix.lower() in {".ttf", ".otf", ".ttc", ".otc"})
        else:
            files.add(path)
    for path in sorted(files):
        checked.append(str(path))
        try:
            with path.open("rb") as stream:
                is_collection = stream.read(4) == b"ttcf"
            if is_collection:
                with TTCollection(path, lazy=True) as collection:
                    count = len(collection.fonts)
            else:
                count = 1
        except Exception as error:
            errors.append({"path": str(path), "index": None, "error": str(error)})
            continue
        for index in range(count):
            try:
                info = font_info(FontFace(path, index), text=text)
                if ((family is None or (info["family"] or "").casefold() == family.casefold())
                        and (weight is None or info["weight"] == weight)
                        and (italic is None or info["italic"] == italic)):
                    candidates.append(info)
            except Exception as error:
                errors.append({"path": str(path), "index": index, "error": str(error)})
    return {"candidates": candidates, "errors": errors, "checked_paths": checked,
            "scope": "Supplied paths only; no system-wide search or automatic font substitution"}


def _bounds(data, name):
    glyphs = data.getGlyphSet()
    pen = BoundsPen(glyphs)
    glyphs[name].draw(pen)
    return pen.bounds


def _cap_metrics(data):
    cmap = data.getBestCmap() or {}
    if any(ord(c) not in cmap for c in "xA"):
        raise ValueError("Cap-height sizing requires x/A font metrics; use em sizing or another font")
    x, a = (_bounds(data, cmap[ord(c)]) for c in "xA")
    if x is None or a is None or a[3] <= x[1]:
        raise ValueError("Positive x/A outline cap height required")
    units = data["head"].unitsPerEm
    return (a[3]-x[1])/units, x[1]/units


def cap_metrics(font):
    """Return cap-height/em and x-outline baseline/em, shared with Canvas."""
    with _open(_face(font)) as data:
        return _cap_metrics(data)


def font_bytes(font):
    """Standalone selected face bytes, including a face from TTC/OTC. No installation."""
    import io
    face = _face(font)
    with _open(face) as data:
        output = io.BytesIO()
        data.save(output)
        return output.getvalue()


def font_roles(mapping):
    """Resolve arbitrary caller-named roles to real faces; no automatic role taxonomy."""
    result = {str(name): _face(value) for name, value in mapping.items()}
    for face in result.values():
        font_info(face)
    return result


def measure_text(text, font, *, size_mm, fallbacks=(), origin=(0, 0), rotation=0,
                 align="left", valign="baseline", size_mode="em"):
    """Measure one unshaped horizontal line, in mm and Y-up coordinates.

    advance_mm includes spaces; ink is actual glyph outlines, metrics is a line
    box using each used face's hhea ascender/descender. Both return rotated
    corners and an axis-aligned bbox. Missing glyphs suppress aggregate bounds.
    No kerning, ligatures, bidi, multiline layout or renderer equivalence claim.
    Variable fonts use their default axes. Fallbacks are explicit and ordered.
    """
    if not isinstance(text, str) or any(c in text for c in "\n\r\t"):
        raise ValueError("A single text line without tabs/newlines is required")
    size_mm, rotation = _finite((size_mm, rotation), 2, "text parameters")
    origin = _finite(origin, 2, "origin")
    if size_mm <= 0 or align not in {"left", "center", "right"}:
        raise ValueError("Positive size and left/center/right alignment required")
    if valign not in {"baseline", "middle"} or size_mode not in {"em", "cap"}:
        raise ValueError("valign: baseline/middle; size_mode: em/cap")
    faces = [_face(font), *(_face(face) for face in fallbacks)]
    with ExitStack() as stack:
        fonts = [stack.enter_context(_open(face)) for face in faces]
        cmaps = [data.getBestCmap() or {} for data in fonts]
        cap, baseline = _cap_metrics(fonts[0]) if size_mode == "cap" else (1, 0)
        em = size_mm/cap
        advance, ink_boxes, metric_boxes, glyphs, missing = 0.0, [], [], [], []
        for char in text:
            index = next((i for i, cmap in enumerate(cmaps) if ord(char) in cmap), None)
            if index is None:
                missing.append(char)
                continue
            data, face, name = fonts[index], faces[index], cmaps[index][ord(char)]
            factor = em/data["head"].unitsPerEm
            width = data["hmtx"].metrics[name][0]*factor
            box = _bounds(data, name)
            if box is not None:
                ink_boxes.append((advance+box[0]*factor, box[1]*factor,
                                  advance+box[2]*factor, box[3]*factor))
            metric_boxes.append((advance, data["hhea"].descent*factor,
                                 advance+width, data["hhea"].ascent*factor))
            glyphs.append({"character": char, "face": face, "glyph": name, "advance_mm": width})
            advance += width
        offset = advance * {"left": 0, "center": .5, "right": 1}[align]
        dy = baseline*em + (size_mm/2 if valign == "middle" else 0)
        theta = math.radians(rotation)

        def envelope(boxes):
            if not boxes or missing:
                return None
            left, bottom = min(b[0] for b in boxes)-offset, min(b[1] for b in boxes)-dy
            right, top = max(b[2] for b in boxes)-offset, max(b[3] for b in boxes)-dy
            corners = [(origin[0]+x*math.cos(theta)-y*math.sin(theta),
                        origin[1]+x*math.sin(theta)+y*math.cos(theta))
                       for x, y in ((left, bottom), (right, bottom), (right, top), (left, top))]
            if not all(math.isfinite(v) for p in corners for v in p):
                raise ValueError("Text measurement exceeds representable range")
            return {"corners_mm": corners, "bbox_mm": (min(p[0] for p in corners), min(p[1] for p in corners),
                                                       max(p[0] for p in corners), max(p[1] for p in corners))}

        if not math.isfinite(advance):
            raise ValueError("Text advance exceeds representable range")
        return {"text": text, "faces": faces, "size_mm": size_mm, "size_mode": size_mode,
                "origin_mm": origin, "rotation": rotation, "align": align, "valign": valign,
                "advance_mm": None if missing else advance, "ink": envelope(ink_boxes),
                "metrics": envelope(metric_boxes), "glyphs": glyphs,
                "missing_characters": tuple(dict.fromkeys(missing)), "glyph_coverage_complete": not missing,
                "method": "unshaped horizontal glyph advances and outlines; variable fonts at default axes",
                "not_checked": ["kerning, ligatures, bidi and complex-script shaping",
                                "target renderer substitutions or layout", "overlap with other objects"]}
