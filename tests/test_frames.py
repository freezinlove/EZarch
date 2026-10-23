"""Geometry invariants, independent of any project's layout or design choices."""
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from ezarch.frames import (
    affine_determinant,
    affine_from_axes,
    inverse_affine,
    paper_transform,
    transform_direction,
    transform_geometry,
    transform_points,
)
from shapely.geometry import GeometryCollection, LineString, Point, Polygon


@pytest.mark.parametrize("angle", [0, 31, 113, 247])
@pytest.mark.parametrize("scale", [0.001, 1, 1000])
@pytest.mark.parametrize("mirror", [-1, 1])
def test_changed_basis_and_units_round_trip(angle, scale, mirror):
    a = math.radians(angle)
    transform = affine_from_axes((191, -93), (scale*math.cos(a), scale*math.sin(a)),
                                 (-mirror*scale*math.sin(a), mirror*scale*math.cos(a)))
    points = [(-7, 2), (0, 0), (1.6, -5)]
    mapped = transform_points(points, transform)
    np.testing.assert_allclose(transform_points(mapped, inverse_affine(transform)), points, atol=1e-9)
    assert math.dist(*mapped[:2]) == pytest.approx(math.dist(*points[:2]) * scale)
    assert affine_determinant(transform) == pytest.approx(mirror*scale**2)
    assert points == [(-7, 2), (0, 0), (1.6, -5)]


def test_mirror_twice_and_direction_ignores_translation():
    reflection = affine_from_axes((24, 0), (-1, 0), (0, 1))
    pts = [(1, -4), (6, 9)]
    assert transform_points(transform_points(pts, reflection), reflection) == pts
    assert transform_direction((3, 2), reflection) == (-3, 2)
    assert transform_points([(3, 2)], reflection)[0] == (21, 2)


def test_shear_and_holes_keep_geometry_and_area():
    polygon = Polygon([(0, 0), (9, 0), (9, 7), (0, 7)],
                      holes=[[(1, 1), (1, 3), (3, 3), (3, 1)]])
    transform = (2, .5, 0, -3, 15, -8)
    mapped = transform_geometry(polygon, transform)
    assert len(mapped.interiors) == 1
    assert mapped.area == pytest.approx(polygon.area * abs(affine_determinant(transform)))
    assert transform_geometry(mapped, inverse_affine(transform)).equals_exact(polygon, 1e-10)
    collection = GeometryCollection([polygon, LineString([(0, 0), (3, 2)]), Point(4, 1)])
    result = transform_geometry(collection, transform)
    assert [g.geom_type for g in result.geoms] == [g.geom_type for g in collection.geoms]
    assert transform_geometry(Point(), transform).is_empty


@pytest.mark.parametrize("unit_mm,length", [(1, 10000), (1000, 10)])
def test_paper_length_and_orientation(unit_mm, length):
    transform = paper_transform((0, 0, length, length/2), 100, unit_mm=unit_mm, margin=12)
    pts = transform_points([(0, 0), (length, 0), (0, length/2)], transform)
    assert pts == [(12, 62), (112, 62), (12, 12)]
    assert math.dist(pts[0], pts[1]) == 100


def test_invalid_and_unsupported_inputs_do_not_silently_lose_data():
    with pytest.raises(ValueError, match="Singular"):
        inverse_affine((1, 2, 2, 4, 0, 0))
    with pytest.raises(ValueError, match="finite"):
        transform_points([(1, math.inf)], (1, 0, 0, 1, 0, 0))
    with pytest.raises(ValueError, match="2 finite"):
        transform_points([(1, 2, 3)], (1, 0, 0, 1, 0, 0))
    with pytest.raises(ValueError, match="2D"):
        transform_geometry(Point(1, 2, 3), (1, 0, 0, 1, 0, 0))
    with pytest.raises(TypeError, match="Shapely"):
        transform_geometry([(1, 2)], (1, 0, 0, 1, 0, 0))
    for args in [((0, 0, 0, 1), 100), ((0, 0, 1, 1), 0)]:
        with pytest.raises(ValueError):
            paper_transform(*args)


def test_point_calculation_import_is_independent_and_has_no_outputs(tmp_path):
    source = Path(__file__).resolve().parents[1] / "skills/ezarch/src"
    env = {**os.environ, "PYTHONPATH": str(source), "PYTHONDONTWRITEBYTECODE": "1"}
    script = """
import sys
from ezarch.frames import transform_points
assert transform_points([(1, 2)], (2, 0, 0, 2, 3, 4)) == [(5, 8)]
assert not {'shapely', 'ezdxf', 'pymupdf', 'numpy', 'bpy', 'cadquery'} & sys.modules.keys()
"""
    subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env=env, check=True)
    assert list(tmp_path.iterdir()) == []
