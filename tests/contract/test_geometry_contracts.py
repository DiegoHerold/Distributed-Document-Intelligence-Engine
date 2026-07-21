from __future__ import annotations

from eixo.geometry import (
    AffineMatrix,
    BoundingBox,
    CoordinateSpace,
    CoordinateUnit,
    NormalizedBoundingBox,
    PageGeometry,
    Point,
    Polygon,
    Quad,
    Rotation,
    Size,
)


def test_geometry_golden_serialization_is_stable() -> None:
    assert Point(1.25, 2.5).to_dict() == {"x": 1.25, "y": 2.5}
    assert Size(612.0, 792.0).to_dict() == {
        "width": 612.0,
        "height": 792.0,
        "unit": "point",
    }
    assert BoundingBox(1.0, 2.0, 3.0, 4.0).to_dict() == {
        "x_min": 1.0,
        "y_min": 2.0,
        "x_max": 3.0,
        "y_max": 4.0,
    }
    assert NormalizedBoundingBox(0.0, 0.25, 0.5, 1.0).to_dict() == {
        "x_min": 0.0,
        "y_min": 0.25,
        "x_max": 0.5,
        "y_max": 1.0,
    }
    assert Rotation(-90.0).to_dict() == {"degrees": 270.0}
    assert AffineMatrix.translation(10.0, 20.0).to_dict() == {
        "a": 1.0,
        "b": 0.0,
        "c": 0.0,
        "d": 1.0,
        "e": 10.0,
        "f": 20.0,
    }


def test_geometry_shape_contracts_are_serializable_without_external_types() -> None:
    polygon = Polygon((Point(0.0, 0.0), Point(10.0, 0.0), Point(0.0, 10.0)))
    quad = Quad(Point(0.0, 0.0), Point(10.0, 0.0), Point(10.0, 5.0), Point(0.0, 5.0))
    page = PageGeometry(
        size=Size(10.0, 5.0),
        visual_box=BoundingBox(0.0, 0.0, 10.0, 5.0),
    )

    assert polygon.to_dict()["points"][0] == {"x": 0.0, "y": 0.0}
    assert quad.to_dict()["bottom_right"] == {"x": 10.0, "y": 5.0}
    assert page.to_dict()["coordinate_space"] == CoordinateSpace.CANONICAL.value
    assert page.to_dict()["unit"] == CoordinateUnit.POINT.value
