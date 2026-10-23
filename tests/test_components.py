"""Technical geometry contracts; no private drawings or design-layout fixtures."""
import math

import ezdxf
import pytest
from ezarch.frames import transform_points
from ezarch.furniture import chair_symbol, desk_symbol, furniture_symbol, shelf_symbol
from ezarch.symbols import Symbol, color_style, door_symbol, linework_style, place_symbol, window_symbol
from ezdxf.lldxf.tagwriter import TagCollector
from ezdxf.math import Vec3


def geometry_tags(entity):
    entity = entity.copy()
    if entity.dxf.get("extrusion", (0, 0, 1)) == Vec3(0, 0, 1):
        entity.dxf.discard("extrusion")
    return [(t.code, t.value) for t in TagCollector.dxftags(entity)
            if t.code not in (5, 330, 8, 62, 420, 370, 6) and not (t.code == 38 and t.value == 0)]


CASES = [
    ("bed", 1700, 2250, {"mattress": (1550, 2000), "pillows": 2}),
    ("sofa", 2400, 950, {"seats": 3, "arm_width": 140}),
    ("lounge", 850, 950, {"seats": 1}),
    ("bench", 1400, 450, {"seats": 3}),
    ("dining_chair", 510, 570, {}), ("task_chair", 620, 640, {}),
    ("table", 1700, 900, {}), ("coffee", 950, 650, {}),
    ("side_table", 450, 450, {}), ("nightstand", 550, 430, {}),
    ("wardrobe", 2100, 620, {"modules": 4}),
    ("cabinet", 1300, 530, {"modules": 2, "mirror": True}),
    ("counter", 2700, 680, {"modules": 3, "fittings": [
        ("sink", (30, 30, 730, 630)), ("hob", (800, 30, 1500, 630)),
        ("dishwasher", (1800, 20, 2500, 650))]}),
    ("tv", 1800, 450, {"modules": 3, "screen_width": 1400}),
    ("fridge", 750, 710, {}), ("desk", 1300, 650, {}),
    ("washer", 620, 650, {}), ("vanity", 800, 560, {}),
    ("wc", 440, 720, {}), ("bathtub", 1750, 800, {}),
    ("shower", 1000, 1100, {"opening": (100, 900)}),
]


@pytest.mark.parametrize("kind,width,depth,details", CASES)
@pytest.mark.parametrize("mirror", [False, True])
def test_same_curves_in_color_and_pure_linework_roundtrip(tmp_path, kind, width, depth, details, mirror):
    symbol = furniture_symbol(kind, width, depth, **details)
    previous = [geometry_tags(p.entity) for p in symbol.parts]
    doc = ezdxf.new("R2010")
    color = doc.blocks.new("Color")
    mono = doc.blocks.new("Mono")
    args = {"unit_mm": 1000, "origin": (17, -23), "rotation_deg": 37, "mirror_x": mirror}
    colored = place_symbol(symbol, color, style=color_style(), **args)
    black = place_symbol(symbol, mono, style=linework_style(), **args)
    assert not any(e.dxftype() == "HATCH" for e in black.entities)
    assert all(e.dxf.true_color == 0 for e in black.entities)
    assert [geometry_tags(e) for e in colored.entities if e.dxftype() != "HATCH"] == [
        geometry_tags(e) for e in black.entities]
    assert colored.anchors == black.anchors
    assert colored.nominal_envelope == black.nominal_envelope
    assert previous == [geometry_tags(p.entity) for p in symbol.parts]
    path = tmp_path / "components.dxf"
    doc.saveas(path)
    saved = ezdxf.readfile(path)
    assert not saved.audit().has_errors
    assert [geometry_tags(e) for e in saved.blocks.get("Mono")] == [geometry_tags(e) for e in black.entities]
    # Native edits remain independent from the reusable source.
    black.entities[0].translate(1, 2, 0)
    assert previous == [geometry_tags(p.entity) for p in symbol.parts]


@pytest.mark.parametrize("angle", [-135, -90, 0, 63, 180])
@pytest.mark.parametrize("mirror", [False, True])
def test_door_anchors_arc_and_leaf_transform_together(angle, mirror):
    symbol = door_symbol(840, leaf_thickness=32, frame_width=45, frame_depth=205,
                         opening_angle_deg=angle)
    doc = ezdxf.new()
    placed = place_symbol(symbol, doc.modelspace(), style=linework_style(), unit_mm=1000,
                          origin=(7, -4), rotation_deg=29, mirror_x=mirror)
    assert placed.anchors["hinge"] == (7, -4)
    expected = transform_points([(840*math.cos(math.radians(angle)),
                                  840*math.sin(math.radians(angle)))], placed.transform)[0]
    assert placed.anchors["leaf_end"] == pytest.approx(expected)
    arcs = [e for e in placed.entities if e.dxftype() == "ARC"]
    if angle:
        assert len(arcs) == 1
        tips = [arcs[0].start_point, arcs[0].end_point]
        assert any(p.isclose(Vec3(*expected)) for p in tips)
        assert any(p.isclose(Vec3(*placed.anchors["closed_end"])) for p in tips)
    else:
        assert not arcs


def test_separable_door_parts_and_explicit_window_geometry():
    door = door_symbol(1100, leaf_thickness=40, frame_width=50, frame_depth=260,
                       frame=False, swing=False)
    assert len(door.parts) == 1
    window = window_symbol(2130, frame_depth=110, end_inset=30, rail_inset=20,
                           mullions=(700, 1400), mullion_width=40,
                           inner_offsets=(-20, 20), sill_offsets=(-170, 150))
    assert len(window.parts) == 12
    assert window.anchors["end"] == (2130, 0)
    assert window.geometry_bounds() == (0, -170, 2130, 150)
    assert window.nominal_bounds == (0, -55, 2130, 55)


@pytest.mark.parametrize("make", [
    lambda: furniture_symbol("bed", 1600, 2200, mattress=(1500, 2000)),
    lambda: furniture_symbol("bed", 1600, 2200, mattress=(1700, 2000), pillows=2),
    lambda: furniture_symbol("sofa", 1000, 900, seats=20),
    lambda: furniture_symbol("cabinet", 900, 500, modules=20),
    lambda: furniture_symbol("tv", 1200, 500, modules=2, screen_width=1300),
    lambda: furniture_symbol("shower", 900, 900, opening=(-30, 850)),
    lambda: furniture_symbol("cabinet", 900, 500, modules=2, fittings=[("unknown", (0, 0, 200, 200))]),
    lambda: furniture_symbol("counter", 1800, 600, modules=3, fittings=[("hob", (800, 200, 830, 230))]),
    lambda: furniture_symbol("table", 900, 500, seats=4),
    lambda: furniture_symbol("wc", float("nan"), 700),
    lambda: furniture_symbol("bathtub", 50, 50),
    lambda: shelf_symbol(1000, 500, divisions=3, axis="auto"),
    lambda: window_symbol(1500, frame_depth=70, end_inset=25, rail_inset=25,
                           mullions=(500, 510), mullion_width=40),
    lambda: door_symbol(900, leaf_thickness=30, frame_width=40, frame_depth=200, opening_angle_deg=270),
])
def test_invalid_inputs_are_not_silently_guessed_or_clamped(make):
    with pytest.raises(ValueError):
        make()


def test_school_resources_do_not_add_unrequested_chairs_or_choose_divisions():
    plain = desk_symbol(650, 480)
    computer = desk_symbol(650, 480, computer=True)
    assert len(plain.parts) == 2  # One outline and its optional fill, no chair.
    assert len(computer.parts) == 4
    chair = chair_symbol(420, 420, back_inset=55)
    assert len(chair.parts) == 3
    shelf = shelf_symbol(500, 2000, divisions=5, axis="x")
    assert len(shelf.parts) == 7  # X chosen explicitly even though Y is longer.


@pytest.mark.parametrize("target", ["model", "paper", "block"])
def test_target_resources_and_existing_objects_preserved(target):
    doc = ezdxf.new()
    doc.layers.new("Kept", dxfattribs={"color": 4, "lineweight": 50})
    doc.layers.get("Kept").freeze()
    layout = {"model": doc.modelspace, "paper": doc.paperspace,
              "block": lambda: doc.blocks.new("Target")}[target]()
    existing = layout.add_circle((12, 18), 7)
    before = list(TagCollector.dxftags(existing)), list(TagCollector.dxftags(doc.layers.get("Kept")))
    symbol = Symbol(anchors={"given": (3, 4)})
    circle = symbol.ellipse((3, 4), 20, 20, role="custom")
    style = linework_style()
    style.strokes["custom"] = ("#112233", .25)
    placed = place_symbol(symbol, layout, style=style, unit_mm=1, layer="Kept")
    assert len(placed.entities) == 1 and circle is not placed.entities[0]
    assert placed.entities[0].dxf.true_color == 0x112233
    assert placed.entities[0].dxf.lineweight == 25
    assert before == (list(TagCollector.dxftags(existing)), list(TagCollector.dxftags(doc.layers.get("Kept"))))


@pytest.mark.parametrize("failure", ["width", "role", "fill", "unit", "layer", "origin", "version"])
def test_failed_placement_does_not_write_partial_geometry(failure):
    doc = ezdxf.new("R2000" if failure == "version" else "R2010")
    ms = doc.modelspace()
    ms.add_line((1, 2), (3, 4))
    before = len(doc.entitydb), list(ms)
    symbol = furniture_symbol("bed", 1700, 2250, mattress=(1550, 2000), pillows=2)
    style = color_style()
    args = {"unit_mm": 1}
    if failure == "width":
        style.strokes["seam"] = ("#000000", .123)
    if failure == "role":
        del style.strokes["seam"]
    if failure == "fill":
        del style.fills["bedding"]
    if failure == "unit":
        args["unit_mm"] = 0
    if failure == "layer":
        args["layer"] = "Missing"
    if failure == "origin":
        args["origin"] = (float("inf"), 0)
    with pytest.raises((ValueError, KeyError)):
        place_symbol(symbol, ms, style=style, **args)
    assert before == (len(doc.entitydb), list(ms))
