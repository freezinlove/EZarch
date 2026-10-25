"""Direction metadata follows actual component geometry; no room layout verdicts."""
import math

import ezdxf
import pytest
from ezarch.drafting import Drawing
from ezarch.furniture import chair_symbol, desk_symbol, furniture_symbol
from ezarch.graphics import Canvas
from ezarch.symbols import Symbol, color_style, linework_style, place_symbol
from ezdxf import bbox


def resource_with_back(kind):
    if kind == "simple_chair":
        symbol = chair_symbol(510, 570, back_inset=55)
        # Actual back line, rather than a point copied from direction metadata.
        index = next(i for i, p in enumerate(symbol.parts) if p.entity.dxftype() == "LINE")
    elif kind == "dining_chair":
        symbol = furniture_symbol(kind, 510, 570)
        index = next(i for i, p in enumerate(symbol.parts) if p.fill and p.role == "upholstery_dark")
    else:
        symbol = furniture_symbol("wc", 440, 720)
        index = 0  # First actual filled outline is the tank.
    return symbol, index


@pytest.mark.parametrize("kind", ["simple_chair", "dining_chair", "wc"])
@pytest.mark.parametrize("unit_mm", [1, 1000])
@pytest.mark.parametrize("mirror", [False, True])
@pytest.mark.parametrize("angle", [0, 37, 180])
def test_front_faces_away_from_actual_back_or_tank(kind, unit_mm, mirror, angle):
    symbol, back_index = resource_with_back(kind)
    before = dict(symbol.directions)
    doc = ezdxf.new()
    placed = place_symbol(symbol, doc.modelspace(), style=color_style(), unit_mm=unit_mm,
                          origin=(17, -23), rotation_deg=angle, mirror_x=mirror)
    back = bbox.extents([placed.entities[back_index]], fast=False).center
    center = placed.anchors["center"]
    front = placed.directions["front"]
    assert math.hypot(*front) == pytest.approx(1)
    assert sum((center[i]-back[i])*front[i] for i in range(2)) > 0
    assert placed.directions["back"] == pytest.approx(tuple(-v for v in front))
    assert symbol.directions == before


def test_both_chair_factories_can_face_the_same_target_without_changing_geometry():
    for kind in ("simple_chair", "dining_chair"):
        symbol, back_index = resource_with_back(kind)
        dx, dy = symbol.directions["front"]
        angle = -math.degrees(math.atan2(dy, dx))  # Explicit request: face +X.
        doc = ezdxf.new()
        placed = place_symbol(symbol, doc.modelspace(), style=color_style(), unit_mm=1,
                              rotation_deg=angle)
        back = bbox.extents([placed.entities[back_index]], fast=False).center
        assert placed.directions["front"] == pytest.approx((1, 0))
        assert back.x < placed.anchors["center"][0]


def test_custom_direction_reflection_includes_x_and_has_no_scale_or_translation():
    source = {"access": (3, 4)}
    symbol = Symbol(directions=source)
    symbol.segment((0, 0), (3, 4))
    source["access"] = (1, 0)
    doc = ezdxf.new()
    placed = place_symbol(symbol, doc.modelspace(), style=linework_style(), unit_mm=1000,
                          origin=(100, 200), rotation_deg=90, mirror_x=True)
    line = placed.entities[0]
    actual = line.dxf.end - line.dxf.start
    assert placed.directions["access"] == pytest.approx((-.8, -.6))
    assert placed.directions["access"] == pytest.approx((actual.x/actual.magnitude, actual.y/actual.magnitude))
    assert symbol.directions["access"] == (.6, .8)
    placed.directions["access"] = (0, 1)
    assert symbol.directions["access"] == (.6, .8)


def test_only_defined_relationships_are_reported():
    bed = furniture_symbol("bed", 1700, 2250, mattress=(1550, 2000), pillows=2)
    assert bed.directions == {"head": (0, 1), "foot": (0, -1)}
    assert furniture_symbol("shower", 1000, 1100, opening=(100, 900)).directions == {"opening": (0, 1)}
    assert desk_symbol(650, 480, computer=True).directions == {"use_side": (0, 1)}
    assert not desk_symbol(650, 480).directions
    assert not furniture_symbol("table", 1700, 900).directions


def test_drawing_and_canvas_return_metadata_without_drawing_direction_markers():
    symbol = furniture_symbol("wc", 440, 720)
    count = sum(not part.fill for part in symbol.parts)
    doc = ezdxf.new()
    drawing = Drawing.from_layout(doc.modelspace(), scale=50, unit_mm=1000)
    placed = drawing.symbol(symbol, style=linework_style(), origin=(8, 9), rotation_deg=90)
    canvas = Canvas(100, 100)
    shown = canvas.symbol(symbol, origin=(50, 50), scale=50,
                          style=linework_style(), rotation_deg=90)
    assert placed.directions["front"] == pytest.approx((-1, 0))
    assert shown.directions == placed.directions  # Internal CAD XY, not paper Y-down.
    assert len(placed.entities) == len(shown.entities) == len(doc.modelspace()) == count


@pytest.mark.parametrize("direction", [(0, 0), (float("nan"), 1), (1, float("inf")), (1, 2, 3)])
def test_bad_direction_metadata_does_not_leave_partial_entities(direction):
    with pytest.raises(ValueError):
        Symbol(directions={"front": direction})
    symbol = Symbol()
    symbol.segment((0, 0), (1, 0))
    symbol.directions["front"] = direction
    doc = ezdxf.new()
    existing = doc.modelspace().add_circle((0, 0), 10)
    with pytest.raises(ValueError):
        place_symbol(symbol, doc.modelspace(), style=linework_style(), unit_mm=1)
    assert list(doc.modelspace()) == [existing]
