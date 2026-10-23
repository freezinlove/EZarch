"""Reference inspection and measured design briefs; no invented reconstruction claims."""
from pathlib import Path

from .project import Project, fingerprint, write_json


def brief(project: Project, out: Path):
    from shapely.geometry import Polygon

    from .measurements import measure_area
    areas = []
    for room in project.rooms:
        polygon = Polygon(room["polygon"])
        if not polygon.is_valid:
            raise ValueError(f"Invalid room boundary: {room.get('id')}")
        measured = measure_area(polygon, unit_mm=1)
        areas.append({"id": room.get("id"), "name": room.get("name"),
                      "area_m2": round(measured["area_m2"], 3),
                      "basis": "Supplied room polygon; no additional deductions", "unit_mm": 1,
                      "type": room.get("type", "interior"), "level": room.get("level")})
    report = {"project": project.name, "project_hash": fingerprint(project), "rooms": areas,
              "interior_net_area_m2": sum(a["area_m2"] for a in areas if a["type"] == "interior"),
              "courtyard_area_m2": sum(a["area_m2"] for a in areas if a["type"] == "courtyard"),
              "brief": project.brief, "sources": project.sources}
    report["interior_boundary_area_m2"] = report["interior_net_area_m2"]
    report["compatibility_fields"] = {
        "interior_net_area_m2": "Legacy alias for interior_boundary_area_m2; no net-area deductions implied"}
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "brief.json", report)
    lines = [f"# {project.name}", "", project.subtitle, "", "## Design constraints", ""]
    for key, value in project.brief.items():
        lines.append(f"- **{key}**: {value}")
    lines += ["", "## Supplied boundary areas", "", "| Space | Type | Area m² |", "|---|---|---:|"]
    lines += [f"| {a['name']} | {a['type']} | {a['area_m2']:.2f} |" for a in areas]
    lines += ["", f"Sum of interior boundary areas: {report['interior_boundary_area_m2']:.2f} m².",
              "Areas derive from supplied polygons without additional deductions; not certified net or gross area.", ""]
    (out / "brief.md").write_text("\n".join(lines), encoding="utf-8")
    return report


def reference(source: Path, out: Path, known_mm=None, pixel_distance=None, *, pages=None, region=None, dpi=150):
    if source.suffix.lower() == ".pdf" and (pages is not None or region is not None):
        from .references import extract_reference
        return extract_reference(source, out, pages=pages, region=region, dpi=dpi)
    import hashlib

    import pymupdf as fitz
    from PIL import Image
    out.mkdir(parents=True, exist_ok=True)
    report = {"source": source.name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "interpretation": "AI must inspect the generated previews; extracted paths are not BIM objects"}
    if source.suffix.lower() == ".pdf":
        pages = []
        with fitz.open(source) as doc:
            for i, page in enumerate(doc):
                name = f"page-{i + 1:03d}"
                page.get_pixmap(dpi=144, alpha=False).save(out / (name + ".png"))
                drawings = page.get_drawings()

                def serial(value):
                    if isinstance(value, (fitz.Point, fitz.Rect, fitz.Quad)):
                        return [serial(v) for v in value]
                    if isinstance(value, dict):
                        return {k: serial(v) for k, v in value.items()}
                    if isinstance(value, (list, tuple)):
                        return [serial(v) for v in value]
                    return value

                write_json(out / (name + "-paths.json"), serial(drawings))
                (out / (name + ".txt")).write_text(page.get_text(), encoding="utf-8")
                pages.append({"page": i + 1, "width_mm": page.rect.width * 25.4 / 72,
                              "height_mm": page.rect.height * 25.4 / 72,
                              "vector_paths": len(drawings), "preview": name + ".png"})
        report["pages"] = pages
    else:
        with Image.open(source) as im:
            report.update(width_px=im.width, height_px=im.height, image_mode=im.mode)
            im.thumbnail((2200, 2200))
            im.convert("RGB").save(out / "reference-preview.png")
        if known_mm is not None or pixel_distance is not None:
            if not known_mm or not pixel_distance or known_mm <= 0 or pixel_distance <= 0:
                raise ValueError("Calibration needs positive known-mm and pixel-distance")
            report["calibration"] = {"known_mm": known_mm, "source_pixel_distance": pixel_distance,
                                     "mm_per_source_pixel": known_mm / pixel_distance,
                                     "assumption": "isotropic orthographic image; does not correct perspective"}
    write_json(out / "reference-report.json", report)
    return report
