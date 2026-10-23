"""Independent marks and geometry contracts; no standard core/layout recipes."""
import ezdxf
import pytest
from ezarch.frames import transform_points
from ezarch.symbols import linework_style, place_symbol
from ezarch.vertical_symbols import direction_symbol, lift_symbol, stair_break_symbol, stair_flight_symbol
from ezdxf.lldxf.tagwriter import TagCollector
from ezdxf.math import Vec3


def lift(**changes):
    params = {"width": 2700, "depth": 2300, "wall_thickness": 180, "car_bounds": (320, 300, 2350, 1950),
                  "entrance_side": "bottom", "entrance_span": (700, 1650), "panel_count": 3,
                  "panel_depth": 50, "panel_inset": 60}
    return lift_symbol(**(params | changes))


def test_stair_uses_explicit_positions_and_does_not_insert_landings_or_break_gaps():
    symbol = stair_flight_symbol(1250, 2400, treads=(0, 330, 690, 2400),
                                 overhead_treads=(1100, 1800), side_edges=True)
    assert len(symbol.parts) == 8
    assert [p.entity.dxf.start.y for p in symbol.parts[:6]] == [0, 330, 690, 2400, 1100, 1800]
    assert [p.role for p in symbol.parts[:6]] == ["outline"]*4+["overhead"]*2
    assert symbol.anchors == {"start": (625, 0), "end": (625, 2400)}
    assert stair_flight_symbol(1250, 2400, treads=()).parts == []


def test_break_and_direction_use_requested_geometry():
    mark = stair_break_symbol(1300, amplitude=90, notch_width=240)
    assert [tuple(p[:2]) for p in mark.parts[0].entity.get_points()] == [
        (0, -90), (530, 90), (770, -90), (1300, 90)]
    direction = direction_symbol([(0, 0), (0, 300), (400, 600)], head_length=100, head_width=60)
    assert len(direction.parts) == 3
    tip = Vec3(400, 600)
    assert all(p.entity.dxf.start == tip for p in direction.parts[1:])
    ends = [p.entity.dxf.end for p in direction.parts[1:]]
    assert (ends[0]+ends[1])/2 == Vec3(320, 540)
    assert ends[0].distance(ends[1]) == pytest.approx(60)


@pytest.mark.parametrize("side,expected", [("bottom", (1175, 0)), ("top", (1175, 2300)),
                                          ("left", (0, 1175)), ("right", (2700, 1175))])
@pytest.mark.parametrize("mirror", [False, True])
def test_nonsquare_lift_native_components_rotate_mirror_and_roundtrip(tmp_path, side, expected, mirror):
    symbol = lift(entrance_side=side)
    assert symbol.anchors["entrance_center"] == expected
    # One opened shaft boundary, one car, three explicitly requested equal panels.
    assert len(symbol.parts) == 5
    assert all(p.entity.dxftype() == "LWPOLYLINE" for p in symbol.parts)
    panel = symbol.parts[-1].entity
    xs, ys = zip(*[(p[0], p[1]) for p in panel.get_points()])
    assert (max(ys)-min(ys) if side in ("bottom", "top") else max(xs)-min(xs)) == 50
    doc = ezdxf.new()
    placed = place_symbol(symbol, doc.modelspace(), style=linework_style(), unit_mm=1000,
                          origin=(11, -3), rotation_deg=47, mirror_x=mirror)
    assert placed.anchors["entrance_center"] == pytest.approx(transform_points([expected], placed.transform)[0])
    path = tmp_path / "lift.dxf"
    doc.saveas(path)
    restored = ezdxf.readfile(path)
    assert not restored.audit().has_errors
    assert len(restored.modelspace()) == 5
    original = list(symbol.parts[0].entity.get_points())
    placed.entities[0].translate(1, 2, 0)
    assert original == list(symbol.parts[0].entity.get_points())


def test_lift_parts_can_be_requested_separately():
    assert len(lift(shaft=False, doors=False).parts) == 1
    assert len(lift(car=False, doors=False).parts) == 1
    assert len(lift(car=False, shaft=False, panel_count=5).parts) == 5
    assert not lift(shaft=False, car=False, doors=False).parts


def test_role_placement_keeps_native_resources_and_missing_mapping_is_atomic(tmp_path):
    symbol = stair_flight_symbol(1400, 2500, treads=(300,), overhead_treads=(900,))
    style = linework_style()
    style.strokes["overhead"] = ("#112233", .13)
    doc = ezdxf.new()
    doc.layers.new("Upper", dxfattribs={"color": 4})
    doc.layers.get("Upper").freeze()
    doc.linetypes.new("UpperDash", dxfattribs={"pattern": [1000, 600, -400]})
    doc.header["$LTSCALE"] = 2
    before = [list(TagCollector.dxftags(resource)) for resource in
              (doc.layers.get("Upper"), doc.linetypes.get("UpperDash"))]
    with pytest.raises(ValueError):
        place_symbol(symbol, doc.modelspace(), style=style, unit_mm=1,
                     role_linetypes={"overhead": "MISSING"})
    assert len(doc.modelspace()) == 0
    placed = place_symbol(symbol, doc.modelspace(), style=style, unit_mm=1,
                          role_layers={"overhead": "Upper"}, role_linetypes={"overhead": "UpperDash"})
    assert placed.roles == ("outline", "overhead")
    upper = placed.entities[1]
    assert (upper.dxf.layer, upper.dxf.linetype, upper.dxf.true_color, upper.dxf.lineweight) == (
        "Upper", "UpperDash", 0x112233, 13)
    assert before == [list(TagCollector.dxftags(resource)) for resource in
                      (doc.layers.get("Upper"), doc.linetypes.get("UpperDash"))]
    path = tmp_path / "roles.dxf"
    doc.saveas(path)
    restored = ezdxf.readfile(path)
    assert restored.header["$LTSCALE"] == 2
    assert list(restored.modelspace())[1].dxf.linetype == "UpperDash"
    assert restored.layers.get("Upper").is_frozen()


@pytest.mark.parametrize("make", [
    lambda: stair_flight_symbol(1000, 2000, treads=(300, 300)),
    lambda: stair_flight_symbol(1000, 2000, treads=(300,), overhead_treads=(300,)),
    lambda: stair_flight_symbol(1000, 2000, treads=(2100,)),
    lambda: stair_flight_symbol(1000, 2000, treads=(float("nan"),)),
    lambda: stair_break_symbol(1000, amplitude=90, notch_width=1000),
    lambda: direction_symbol([(0, 0), (0, 0)], head_length=100, head_width=60),
    lambda: direction_symbol([(0, 0), (1, 1)], head_length=0, head_width=60),
    lambda: lift(entrance_side="north"), lambda: lift(wall_thickness=1200),
    lambda: lift(car_bounds=(100, 300, 2350, 1950)), lambda: lift(entrance_span=(0, 900)),
    lambda: lift(panel_inset=150), lambda: lift(panel_count=0), lambda: lift(panel_count=True),
    lambda: lift(panel_depth=float("inf")),
])
def test_invalid_geometry_is_not_replaced_by_project_defaults(make):
    with pytest.raises((TypeError, ValueError)):
        make()
