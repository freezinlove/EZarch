"""Deterministic vector composition in physical millimetres, SVG + vector PDF."""
from __future__ import annotations

import base64
import html
import math
from functools import lru_cache
from pathlib import Path

import pymupdf as fitz

from ._drawing import css_color, dash_pattern, paper_width, points_2d, polygon_rings
from .project import skill_root, write_json

PT = 72 / 25.4


@lru_cache(maxsize=32)
def _cap_metrics(path):
    """Match CAD cap-height/baseline semantics using the selected font's outlines."""
    from .fonts import cap_metrics
    return cap_metrics(path)


def rgb(value):
    if value is None or value == "none":
        return None
    if isinstance(value, str):
        value = value.lstrip("#")
        return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return tuple(value)


class Canvas:
    """Page coordinates: x right, y down, sizes in mm; text y is the baseline."""

    def __init__(self, width, height, background="#ffffff", font=None, *, font_roles=None):
        self.width, self.height = float(width), float(height)
        self.custom_font = font is not None
        self.font_path = Path(font) if font is not None else skill_root() / "assets/fonts/EZarchFang.ttf"
        from .fonts import font_roles as resolve_roles
        self.font_roles = resolve_roles(font_roles or {})
        self.items = []
        self.rect(0, 0, width, height, fill=background, stroke=None)

    def poly(self, points, stroke="#30332f", width=0.18, fill=None, close=False, dash=None, tag="", *, holes=()):
        stroke, fill = css_color(stroke), css_color(fill)
        points, holes = polygon_rings(points, holes, close, fill)
        self.items.append(dict(kind="poly", points=points, holes=holes, stroke=stroke,
                               width=paper_width(width), fill=fill, close=close, dash=dash_pattern(dash), tag=tag))

    def line(self, x1, y1, x2, y2, **kwargs):
        self.poly([(x1, y1), (x2, y2)], **kwargs)

    def rect(self, x, y, w, h, **kwargs):
        self.poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], close=True, **kwargs)

    def circle(self, x, y, radius, stroke="#30332f", width=.18, fill=None, dash=None, tag=""):
        (x, y), = points_2d([(x, y)])
        if not math.isfinite(radius) or radius <= 0:
            raise ValueError("Circle radius must be positive and finite")
        self.items.append(dict(kind="circle", x=x, y=y, radius=radius, stroke=css_color(stroke),
                               width=paper_width(width), fill=css_color(fill), dash=dash_pattern(dash), tag=tag))

    def text(self, x, y, text, size=3.0, color="#30332f", align="left", bold=False, tag="", rotation=0,
             *, valign="baseline", size_mode="em", font=None, font_role=None, fallbacks=()):
        (x, y), = points_2d([(x, y)])
        if not math.isfinite(rotation) or not math.isfinite(size) or size <= 0:
            raise ValueError("Text rotation must be finite and size positive")
        if align not in {"left", "center", "right"} or valign not in {"baseline", "middle"}:
            raise ValueError("Text align: left/center/right; valign: baseline/middle")
        if font is not None and font_role is not None:
            raise ValueError("Choose font or font_role")
        if font_role is not None:
            font = self.font_roles[font_role]
        if size_mode not in {"em", "cap"} or (size_mode == "cap" and not (self.custom_font or font)):
            raise ValueError("Cap-height sizing requires an explicit Canvas font")
        color = css_color(color)
        if color is None:
            raise ValueError("Text requires a color")
        self.items.append(dict(kind="text", x=x, y=y, text=str(text), size=size, color=color,
                               align=align, bold=bold, tag=tag, rotation=rotation, valign=valign,
                               size_mode=size_mode, font=font, fallbacks=tuple(fallbacks)))

    def image(self, path, x, y, w, h):
        self.items.append(dict(kind="image", path=str(Path(path).resolve()), x=x, y=y, w=w, h=h))

    def cad(self, doc, *, origin, scale, layout_name="Model", handles=None, region=None, padding=1):
        """Place live CAD at a paper-mm origin, with native XY up and explicit scale."""
        (origin,) = points_2d([origin])
        if not math.isfinite(scale) or scale <= 0 or not doc.units:
            raise ValueError("CAD placement needs positive scale and declared document units")
        if not math.isfinite(padding) or padding < 0:
            raise ValueError("CAD padding must be finite and nonnegative paper mm")
        self.items.append(dict(kind="cad", doc=doc, origin=origin, scale=scale,
                               layout_name=layout_name, handles=handles, region=region, padding=padding))

    def symbol(self, symbol, *, origin, scale, style, rotation_deg=0, mirror_x=False):
        """Place component geometry in paper mm; returned entities remain editable."""
        import ezdxf

        from .symbols import place_symbol
        doc = ezdxf.new("R2010")
        doc.units = ezdxf.units.MM
        placed = place_symbol(symbol, doc.modelspace(), style=style, unit_mm=1,
                              rotation_deg=rotation_deg, mirror_x=mirror_x)
        self.cad(doc, origin=origin, scale=scale)
        return placed

    def text_box(self, x, y, w, h, text, size=3, leading=None, **kwargs):
        """Measured wrapping for mixed CJK/Latin text; reject overflow, never shrink."""
        leading = leading or size * 1.55
        from .fonts import font_bytes
        selected = kwargs.get("font") or self.font_roles.get(kwargs.get("font_role"))
        font = fitz.Font(fontbuffer=font_bytes(selected)) if selected else fitz.Font(fontfile=str(self.font_path))
        fallbacks = [fitz.Font(fontbuffer=font_bytes(face)) for face in kwargs.get("fallbacks", ())]
        latin = fitz.Font("hebo" if kwargs.get("bold") else "helv")
        def width(value):
            primary = font if selected or self.custom_font or any(ord(c) > 255 for c in value) else latin
            total = 0
            for char in value:
                candidates = [primary, *fallbacks] + ([] if selected else [latin])
                face = next((f for f in candidates if f.has_glyph(ord(char))), None)
                if face is None:
                    raise ValueError(f"No selected font glyph for {char!r}")
                total += face.text_length(char, fontsize=size)
            return total
        lines = []
        for paragraph in str(text).split("\n"):
            line = ""
            for char in paragraph:
                if width(line + char) > w and line:
                    # Prefer an existing Latin word boundary when possible.
                    split = line.rfind(" ")
                    if char.isascii() and char.isalnum() and split > len(line) / 2:
                        lines.append(line[:split])
                        line = line[split + 1:] + char
                    else:
                        lines.append(line.rstrip())
                        line = char.lstrip()
                else:
                    line += char
            lines.append(line)
        used = size + max(0, len(lines) - 1) * leading
        if used > h + .01 or any(width(line) > w + .01 for line in lines):
            raise ValueError(f"Text box overflow: {str(text)[:50]}")
        for i, line in enumerate(lines):
            self.text(x, y + size + i * leading, line, size=size, **kwargs)
        return {"lines": len(lines), "used_height_mm": used}

    def rich_text(self, x, y, w, h, markup, *, css="", fonts=None, scale_low=1):
        """Shaped HTML text via MuPDF Story; explicit fit range, PDF text remains text."""
        if min(w, h) <= 0 or not 0 < scale_low <= 1:
            raise ValueError("Positive box and 0 < scale_low <= 1 required")
        self.items.append(dict(kind="rich_text", x=x, y=y, w=w, h=h, markup=markup,
                               css=css, fonts=fonts or {}, scale_low=scale_low))

    def svg(self, path, x, y, w, h):
        """Import SVG as a vector PDF view; embedded text is outlined in composed SVG."""
        with fitz.open(path) as source:
            content = source.convert_to_pdf()
        self.items.append(dict(kind="pdf", content=content, x=x, y=y, w=w, h=h, page=0))

    def pdf(self, path, x, y, w, h, page=0):
        self.items.append(dict(kind="pdf", path=str(Path(path).resolve()), x=x, y=y, w=w, h=h,
                               page=page))

    def save(self, stem: Path, dpi=120, metadata=None, formats=None, *, svg_text="editable"):
        if svg_text not in {"editable", "outline"}:
            raise ValueError("svg_text: editable or outline")
        formats = set(["svg", "pdf", "png"] if formats is None else formats)
        if formats - {"svg", "pdf", "png"}:
            raise ValueError("Canvas formats: svg, pdf, png")
        from .storage import output_path
        stem = output_path(stem)
        stem.parent.mkdir(parents=True, exist_ok=True)
        font_path = self.font_path
        if not font_path.exists():
            raise FileNotFoundError(f"Bundled FangSong font missing: {font_path}")
        cjk_font = fitz.Font(fontfile=str(font_path))
        regular_font, bold_font = fitz.Font("helv"), fitz.Font("hebo")
        doc = fitz.open()
        page = doc.new_page(width=self.width * PT, height=self.height * PT)
        page.insert_font(fontname="FangSong", fontfile=str(font_path)) if font_path.exists() else None
        # Embed MuPDF's supplied Latin outlines too: PDF viewers otherwise choose
        # different system substitutes for the unembedded Base-14 fonts.
        page.insert_font(fontname="EZLatin", fontbuffer=regular_font.buffer)
        page.insert_font(fontname="EZBold", fontbuffer=bold_font.buffer)
        svg = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
               f'width="{self.width}mm" height="{self.height}mm" viewBox="0 0 {self.width} {self.height}">']
        if font_path.exists():
            encoded = base64.b64encode(font_path.read_bytes()).decode()
            mime = 'font/otf' if font_path.suffix.lower() == '.otf' else 'font/ttf'
            svg.append('<defs><style>@font-face{font-family:FandolFang;src:url(data:' + mime + ';base64,'
                       + encoded + ')}</style></defs>')
        registered_fonts = {}
        svg_families = {"FangSong": "FandolFang", "EZLatin": "EZLatin", "EZBold": "EZBold"}
        for name, builtin in (("EZLatin", regular_font), ("EZBold", bold_font)):
            encoded = base64.b64encode(builtin.buffer).decode()
            svg.append(f'<defs><style>@font-face{{font-family:{name};src:url(data:font/otf;base64,{encoded})}}</style></defs>')
        def register_face(value):
            from .fonts import _face, font_bytes
            face = _face(value)
            key = (str(face.path), face.index)
            if key not in registered_fonts:
                name = f"EZFace{len(registered_fonts)}"
                data = font_bytes(face)
                font = fitz.Font(fontbuffer=data)
                page.insert_font(fontname=name, fontbuffer=data)
                encoded = base64.b64encode(data).decode()
                svg.append(f'<defs><style>@font-face{{font-family:{name};src:url(data:font/otf;base64,{encoded})}}</style></defs>')
                svg_families[name] = name
                registered_fonts[key] = (font, name)
            return registered_fonts[key]
        overflow, geometry_overflow, rich_text_runs = [], [], []
        # Batch adjacent paths: committing each triangle makes MuPDF rescan growing page streams.
        # Flush at text/media boundaries to preserve painter order.
        path_batch = None
        cad_views = []
        for item in self.items:
            k = item["kind"]
            if k == "rich_text":
                from .fonts import font_bytes
                archive = fitz.Archive()
                css = item["css"]
                for index, (family, face) in enumerate(item["fonts"].items()):
                    if not family.replace("_", "").replace("-", "").isalnum():
                        raise ValueError("HTML font family keys must be simple identifiers")
                    name = f"face{index}.otf"
                    archive.add((font_bytes(face), name))
                    css += f"\n@font-face{{font-family:{family};src:url({name});}}"
                text_doc = fitz.open()
                text_page = text_doc.new_page(width=item["w"] * PT, height=item["h"] * PT)
                spare, actual_scale = text_page.insert_htmlbox(text_page.rect, item["markup"], css=css,
                                                               archive=archive, scale_low=item["scale_low"])
                if spare < 0:
                    text_doc.close()
                    raise ValueError("Rich text does not fit the supplied box and allowed scale")
                rich_text_runs.append({"box_mm": [item[key] for key in ("x", "y", "w", "h")], "scale": actual_scale})
                content = text_doc.tobytes()
                text_doc.close()
                item = dict(kind="pdf", content=content, page=0, **{key: item[key] for key in ("x", "y", "w", "h")})
                k = "pdf"
            if k == "cad":
                import ezdxf

                from .cad import render
                content, view = render(item["doc"], scale=item["scale"],
                                       layout_name=item["layout_name"], handles=item["handles"],
                                       region=item["region"], margin=item["padding"], background=False)
                cad_views.append(view)
                xmin, ymin, xmax, ymax = view["source_region"]
                factor = ezdxf.units.conversion_factor(item["doc"].units, ezdxf.units.MM) / item["scale"]
                item = dict(kind="pdf", content=content, page=0,
                            x=item["origin"][0] + xmin * factor - item["padding"],
                            y=item["origin"][1] - ymax * factor - item["padding"],
                            w=view["width_mm"], h=view["height_mm"])
                k = "pdf"
            if k not in {"poly", "circle"} and path_batch is not None:
                path_batch.commit()
                path_batch = None
            if k in {"poly", "circle"}:
                if item["stroke"] is None and item["fill"] is None:
                    continue
                if k == "poly":
                    points = item["points"]
                    if len(points) < 2:
                        continue
                else:
                    x, y, radius = item["x"], item["y"], item["radius"]
                    points = [(x-radius, y-radius), (x+radius, y+radius)]
                if any(x < -.1 or x > self.width + .1 or y < -.1 or y > self.height + .1 for x, y in points):
                    geometry_overflow.append({"bounds_mm": [min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points)]})
                if path_batch is None:
                    path_batch = page.new_shape()
                sh = path_batch
                if k == "circle":
                    # Same +X start and model-CCW direction as a native CAD circle.
                    sh.draw_sector(fitz.Point(x * PT, y * PT),
                                   fitz.Point((x + radius) * PT, y * PT), 360, fullSector=False)
                else:
                    for ring in [points, *item["holes"]]:
                        path = list(ring)
                        if item["close"] and path[-1] != path[0]:
                            path.append(path[0])
                        sh.draw_polyline([fitz.Point(x * PT, y * PT) for x, y in path])
                dashes = None if not item["dash"] else "[" + " ".join(str(v * PT) for v in item["dash"]) + "] 0"
                pdf_width = item["width"] * PT
                if pdf_width == 0 and item["stroke"] is not None:
                    # PyMuPDF finish(width=0) removes the stroke color instead of
                    # writing a PDF hairline. Set 0 w within this path's saved state;
                    # width=1 leaves that operator intact while retaining color.
                    sh.draw_cont = "0 w\n" + sh.draw_cont
                    pdf_width = 1
                sh.finish(color=rgb(item["stroke"]), fill=rgb(item["fill"]),
                          width=pdf_width, closePath=False, dashes=dashes, even_odd=True,
                          lineJoin=1)
                dash_attr = '' if not item["dash"] else f' stroke-dasharray="{",".join(map(str, item["dash"]))}"'
                # SVG has no device hairline: use one non-scaling pixel for width=0.
                width_attr = (f'stroke-width="{item["width"]}"' if item["width"] else
                              'stroke-width="1" vector-effect="non-scaling-stroke"')
                attrs = (f' fill="{item["fill"] or "none"}" stroke="{item["stroke"] or "none"}" '
                         f'{width_attr} stroke-linejoin="round"{dash_attr}')
                if k == "circle":
                    svg.append(f'<circle cx="{x}" cy="{y}" r="{radius}" '
                               f'transform="translate(0 {2*y}) scale(1 -1)"{attrs}/>')
                elif item["holes"]:
                    paths = []
                    for ring in [points, *item["holes"]]:
                        paths.append("M " + " L ".join(f"{x:.8g},{y:.8g}" for x, y in ring) + " Z")
                    svg.append(f'<path d="{" ".join(paths)}" fill-rule="evenodd"{attrs}/>')
                else:
                    tag = "polygon" if item["close"] else "polyline"
                    svg.append(f'<{tag} points="' + " ".join(f"{x:.8g},{y:.8g}" for x, y in points)
                               + f'"{attrs}/>')
            elif k == "text":
                text = item["text"]
                explicit_font = item.get("font")
                cjk = self.custom_font or any(ord(c) > 255 for c in text)
                font = cjk_font if cjk else bold_font if item["bold"] else regular_font
                fontname = "FangSong" if cjk else "EZBold" if item["bold"] else "EZLatin"
                if explicit_font is not None:
                    font, fontname = register_face(explicit_font)
                fallback_faces = [register_face(value) for value in item.get("fallbacks", ())]
                size = item["size"]
                cap, baseline = _cap_metrics(str(font_path)) if item["size_mode"] == "cap" else (1, 0)
                if item["size_mode"] == "cap":
                    if explicit_font is not None:
                        from .fonts import cap_metrics
                        cap, baseline = cap_metrics(explicit_font)
                    size /= cap
                runs = []
                for char in text:
                    candidates = [(font, fontname), *fallback_faces]
                    if explicit_font is None:
                        candidates.append((regular_font, "EZLatin"))
                    candidate = next(((f, n) for f, n in candidates if f.has_glyph(ord(char))), None)
                    if candidate is None:
                        raise ValueError(f"No selected font glyph for {char!r} (U+{ord(char):04X}); supply a fallback")
                    run_font, run_name = candidate
                    if runs and runs[-1][0] == run_name:
                        runs[-1][2] += char
                    else:
                        runs.append([run_name, run_font, char])
                length = sum(f.text_length(t, fontsize=size) for _, f, t in runs)
                angle = math.radians(item["rotation"])
                # Offset from the stated anchor in the rotated local down direction.
                dy = baseline * size
                if item["valign"] == "middle":
                    dy += item["size"] / 2
                anchor_x = item["x"] + dy * math.sin(angle)
                anchor_y = item["y"] + dy * math.cos(angle)
                offset = length / 2 if item["align"] == "center" else length if item["align"] == "right" else 0
                x, y = anchor_x - offset * math.cos(angle), anchor_y + offset * math.sin(angle)
                top = max(f.ascender for _, f, _ in runs) * size if runs else size
                bottom = -min(f.descender for _, f, _ in runs) * size if runs else 0
                corners = [(x + u * math.cos(angle) + v * math.sin(angle), y - u * math.sin(angle) + v * math.cos(angle)) for u in (0, length) for v in (-top, bottom)]
                bounds = [min(p[0] for p in corners), min(p[1] for p in corners), max(p[0] for p in corners), max(p[1] for p in corners)]
                if bounds[0] < -.1 or bounds[2] > self.width + .1 or bounds[3] > self.height + .1 or bounds[1] < -.1:
                    overflow.append({"text": text, "box_mm": bounds})
                advance = 0
                for run_name, run_font, run_text in runs:
                    page.insert_text(((x + advance * math.cos(angle)) * PT, (y - advance * math.sin(angle)) * PT),
                                     run_text, fontsize=size * PT, fontname=run_name,
                                     color=rgb(item["color"]),
                                     morph=(fitz.Point((x + advance * math.cos(angle)) * PT,
                                                      (y - advance * math.sin(angle)) * PT),
                                            fitz.Matrix(item["rotation"])))
                    advance += run_font.text_length(run_text, fontsize=size)
                anchor = {"left": "start", "center": "middle", "right": "end"}[item["align"]]
                spans = ''.join(f'<tspan font-family="{svg_families[name]}">{html.escape(value)}</tspan>' for name, _, value in runs)
                svg.append(f'<text x="{anchor_x}" y="{anchor_y}" transform="rotate({-item["rotation"]} {anchor_x} {anchor_y})" font-size="{size}" '
                           f'font-kerning="none" font-variant-ligatures="none" '
                           f'text-anchor="{anchor}" fill="{item["color"]}">{spans}</text>')
            elif k in ("image", "pdf"):
                rect = fitz.Rect(item["x"] * PT, item["y"] * PT,
                                 (item["x"] + item["w"]) * PT, (item["y"] + item["h"]) * PT)
                if k == "image":
                    page.insert_image(rect, filename=item["path"], keep_proportion=True)
                    encoded = base64.b64encode(Path(item["path"]).read_bytes()).decode()
                    mime = "image/jpeg" if Path(item["path"]).suffix.lower() in (".jpg", ".jpeg") else "image/png"
                    svg.append(f'<image x="{item["x"]}" y="{item["y"]}" width="{item["w"]}" '
                               f'height="{item["h"]}" preserveAspectRatio="xMidYMid meet" '
                               f'xlink:href="data:{mime};base64,{encoded}"/>')
                else:
                    with (fitz.open(stream=item["content"], filetype="pdf") if "content" in item
                          else fitz.open(item["path"])) as source:
                        source_page = source[item["page"]]
                        page.show_pdf_page(rect, source, pno=item["page"], keep_proportion=True)
                        raw_svg = source_page.get_svg_image(text_as_path=True)
                        # Nest the source SVG to preserve vector content and its own viewBox.
                        raw_svg = raw_svg.replace('<svg ', f'<svg x="{item["x"]}" y="{item["y"]}" ', 1)
                        import re
                        raw_svg = re.sub(r'width="[^"]+"', f'width="{item["w"]}"', raw_svg, count=1)
                        raw_svg = re.sub(r'height="[^"]+"', f'height="{item["h"]}"', raw_svg, count=1)
                        # Each imported PDF has its own IDs; namespace them across the board.
                        prefix = f"slot{len(svg)}_"
                        ids = re.findall(r'\bid="([^"]+)"', raw_svg)
                        for ident in sorted(set(ids), key=len, reverse=True):
                            raw_svg = raw_svg.replace(f'id="{ident}"', f'id="{prefix}{ident}"')
                            raw_svg = raw_svg.replace(f'#{ident}"', f'#{prefix}{ident}"').replace(f'#{ident})', f'#{prefix}{ident})')
                        svg.append(raw_svg)
        if path_batch is not None:
            path_batch.commit()
        svg.append("</svg>")
        if "svg" in formats:
            svg_content = "\n".join(svg)
            if svg_text == "outline":
                import re
                svg_content = page.get_svg_image(text_as_path=True)
                svg_content = re.sub(r'width="[^"]+"', f'width="{self.width}mm"', svg_content, count=1)
                svg_content = re.sub(r'height="[^"]+"', f'height="{self.height}mm"', svg_content, count=1)
            stem.with_suffix(".svg").write_text(svg_content, encoding="utf-8")
        doc.set_metadata({"title": (metadata or {}).get("title", stem.stem), "producer": "EZarch"})
        doc.subset_fonts()
        if "pdf" in formats:
            doc.save(str(stem.with_suffix(".pdf")), garbage=4, deflate=True)
        if "png" in formats:
            page.get_pixmap(dpi=dpi, alpha=False).save(str(stem.with_suffix(".png")))
        report = {"width_mm": self.width, "height_mm": self.height, "text_overflow": overflow,
                  "geometry_overflow": geometry_overflow,
                  "vector_paths": len(page.get_drawings()), "images": len(page.get_images()),
                  "metadata": metadata or {}, "formats": sorted(formats), "cad_views": cad_views,
                  "svg_text": svg_text, "font_faces": [{"path": key[0], "index": key[1]} for key in registered_fonts],
                  "rich_text": rich_text_runs}
        write_json(stem.with_suffix(".report.json"), report)
        doc.close()
        return report
