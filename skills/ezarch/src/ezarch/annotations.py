"""Convert measured text bounds into geometry."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from shapely.geometry import Polygon

from .frames import transform_geometry


@dataclass(frozen=True)
class Footprint:
    """Geometry with its measurement basis and unavailable-data reason."""

    geometry: object
    basis: str
    source: object = None
    unavailable_reason: str | None = None
    limitations: tuple[str, ...] = ()


def text_footprint(measurement, *, kind, transform=None):
    """Adapt measure_text's rotated corners in mm, including missing-glyph gaps.

    kind explicitly selects 'ink' or 'metrics'; both are envelopes, not glyph
    outlines. An optional affine maps mm to the caller's coordinate system.
    No renderer-specific layout or font substitution is inferred.
    """
    if kind not in {"ink", "metrics"}:
        raise ValueError("kind must select ink or metrics")
    source = deepcopy({key: measurement[key] for key in
                       ("text", "faces", "size_mm", "size_mode", "origin_mm", "rotation", "align", "valign", "method")})
    source["transform"] = deepcopy(transform)
    limitations = tuple(measurement["not_checked"]) + ("Envelope, not individual glyph ink",)
    if not measurement["glyph_coverage_complete"]:
        reason = "Missing glyphs: " + repr(measurement["missing_characters"])
        return Footprint(None, kind + "_envelope", source, reason, limitations)
    envelope = measurement[kind]
    if envelope is None:
        return Footprint(None, kind + "_envelope", source, "No envelope for this text and kind", limitations)
    geometry = Polygon(envelope["corners_mm"])
    if transform is not None:
        geometry = transform_geometry(geometry, transform)
    return Footprint(geometry, kind + "_envelope", source, limitations=limitations)
