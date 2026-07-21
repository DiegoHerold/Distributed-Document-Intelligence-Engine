from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import pytest

from eixo.geometry import (
    AffineMatrix,
    BoundingBox,
    GeometryValidationError,
    NonInvertibleTransformError,
    NormalizedBoundingBox,
    NormalizedPoint,
    Point,
    Polygon,
    Quad,
    Rotation,
    Size,
    SizeOrientation,
    Vector,
    inches_to_points,
    millimeters_to_points,
    pixels_to_points,
    points_to_inches,
    points_to_millimeters,
    points_to_pixels,
)


def test_point_operations_validation_and_immutability() -> None:
    point = Point(1.0, -2.0)

    assert point.translate(3.0, 4.0) == Point(4.0, 2.0)
    assert point.offset(Vector(2.0, 3.0)) == Point(3.0, 1.0)
    assert point.distance_to(Point(4.0, 2.0)) == 5.0
    assert point.transform(AffineMatrix.translation(1.0, 1.0)) == Point(2.0, -1.0)
    assert point.almost_equals(Point(1.0 + 1e-10, -2.0))

    with pytest.raises(GeometryValidationError):
        Point(math.nan, 0.0)
    with pytest.raises(FrozenInstanceError):
        point.x = 2.0  # type: ignore[misc]


def test_size_operations_orientation_and_units() -> None:
    assert Size(10.0, 20.0).area == 200.0
    assert Size(10.0, 20.0).orientation() == SizeOrientation.PORTRAIT
    assert Size(20.0, 10.0).orientation() == SizeOrientation.LANDSCAPE
    assert Size(10.0, 10.0).orientation() == SizeOrientation.SQUARE
    assert Size(0.0, 10.0).orientation() == SizeOrientation.DEGENERATE
    assert Size(10.0, 20.0).scale(2.0) == Size(20.0, 40.0)
    assert Size(10.0, 0.0).aspect_ratio() is None

    with pytest.raises(GeometryValidationError):
        Size(-1.0, 1.0)
    with pytest.raises(GeometryValidationError):
        Size(math.inf, 1.0)


def test_bounding_box_operations_normalization_and_clipping() -> None:
    box = BoundingBox(10.0, 20.0, 30.0, 50.0)
    other = BoundingBox(20.0, 10.0, 40.0, 40.0)

    assert box.width == 20.0
    assert box.height == 30.0
    assert box.area == 600.0
    assert box.center == Point(20.0, 35.0)
    assert box.contains_point(Point(10.0, 20.0))
    assert box.contains_box(BoundingBox(11.0, 21.0, 29.0, 49.0))
    assert box.intersection(other) == BoundingBox(20.0, 20.0, 30.0, 40.0)
    assert box.union(other) == BoundingBox(10.0, 10.0, 40.0, 50.0)
    assert box.iou(other) == pytest.approx(200.0 / 1000.0)
    assert box.translate(1.0, -2.0) == BoundingBox(11.0, 18.0, 31.0, 48.0)
    assert box.expand(2.0) == BoundingBox(8.0, 18.0, 32.0, 52.0)
    assert box.clip_to(BoundingBox(0.0, 0.0, 25.0, 25.0)) == BoundingBox(
        10.0,
        20.0,
        25.0,
        25.0,
    )

    normalized = box.normalize(Size(100.0, 100.0))
    assert normalized == NormalizedBoundingBox(0.1, 0.2, 0.3, 0.5)
    assert normalized.denormalize(Size(100.0, 100.0)) == box
    assert BoundingBox(-10.0, 0.0, 20.0, 120.0).normalize(
        Size(100.0, 100.0),
        clamp=True,
    ) == NormalizedBoundingBox(0.0, 0.0, 0.2, 1.0)

    with pytest.raises(GeometryValidationError):
        BoundingBox(1.0, 0.0, 0.0, 1.0)
    with pytest.raises(GeometryValidationError):
        BoundingBox(-10.0, 0.0, 20.0, 120.0).normalize(Size(100.0, 100.0))


def test_polygon_quad_and_rotation() -> None:
    polygon = Polygon(
        (
            Point(0.0, 0.0),
            Point(10.0, 0.0),
            Point(10.0, 10.0),
            Point(0.0, 10.0),
        )
    )
    concave = Polygon(
        (
            Point(0.0, 0.0),
            Point(10.0, 0.0),
            Point(5.0, 5.0),
            Point(10.0, 10.0),
            Point(0.0, 10.0),
        )
    )
    crossing = Polygon(
        (
            Point(0.0, 0.0),
            Point(10.0, 10.0),
            Point(0.0, 10.0),
            Point(10.0, 0.0),
        )
    )

    assert polygon.area == 100.0
    assert polygon.is_clockwise is True
    assert polygon.bounding_box == BoundingBox(0.0, 0.0, 10.0, 10.0)
    assert polygon.contains_point(Point(5.0, 5.0))
    assert concave.contains_point(Point(2.0, 5.0))
    assert crossing.is_self_intersecting is True

    quad = Quad(Point(0.0, 0.0), Point(10.0, 0.0), Point(10.0, 10.0), Point(0.0, 10.0))
    assert quad.top_width == 10.0
    assert quad.left_height == 10.0
    assert quad.is_convex is True
    assert quad.transform(AffineMatrix.translation(1.0, 2.0)).top_left == Point(1.0, 2.0)

    assert Rotation(450.0).degrees == 90.0
    assert Rotation(-90.0).degrees == 270.0
    assert Rotation(90.0).radians == pytest.approx(math.pi / 2.0)
    assert Rotation(90.0).quarter_turns == 1
    assert Rotation(45.0).quarter_turns is None
    assert Rotation(350.0).compose(Rotation(20.0)).degrees == 10.0
    assert Rotation(90.0).inverse().degrees == 270.0


def test_affine_matrix_composition_inverse_and_singularity() -> None:
    point = Point(2.0, 3.0)
    translation = AffineMatrix.translation(10.0, 0.0)
    scale = AffineMatrix.scale(2.0, 3.0)
    combined = translation @ scale

    assert combined.apply_to_point(point) == Point(14.0, 9.0)
    assert combined.apply_to_point(point) == translation.apply_to_point(
        scale.apply_to_point(point)
    )
    assert combined.inverse().apply_to_point(combined.apply_to_point(point)).almost_equals(
        point
    )
    assert AffineMatrix.rotation(90.0).apply_to_point(Point(1.0, 0.0)).almost_equals(
        Point(0.0, 1.0)
    )
    assert AffineMatrix.skew(x_degrees=45.0).apply_to_point(Point(0.0, 1.0)).x == pytest.approx(1.0)
    assert AffineMatrix.scale(0.0, 1.0).is_singular is True

    with pytest.raises(NonInvertibleTransformError):
        AffineMatrix.scale(0.0, 1.0).inverse()


def test_normalized_coordinates_and_units() -> None:
    page_size = Size(200.0, 100.0)

    assert NormalizedPoint(0.5, 0.5).denormalize(page_size) == Point(100.0, 50.0)
    assert Point(100.0, 50.0).normalize(page_size) == NormalizedPoint(0.5, 0.5)
    assert BoundingBox(0.0, 0.0, 200.0, 100.0).normalize(page_size) == (
        NormalizedBoundingBox(0.0, 0.0, 1.0, 1.0)
    )
    assert inches_to_points(1.0) == 72.0
    assert points_to_inches(72.0) == 1.0
    assert points_to_millimeters(72.0) == pytest.approx(25.4)
    assert millimeters_to_points(25.4) == pytest.approx(72.0)
    assert points_to_pixels(72.0, 144.0) == 144.0
    assert pixels_to_points(144.0, 144.0) == 72.0

    with pytest.raises(GeometryValidationError):
        NormalizedPoint(1.1, 0.0)
    with pytest.raises(GeometryValidationError):
        points_to_pixels(10.0, 0.0)


def test_property_like_geometry_invariants() -> None:
    points = (
        Point(-10.5, 2.0),
        Point(0.0, 0.0),
        Point(10.0, 20.0),
        Point(1234.5, -987.25),
    )
    matrices = (
        AffineMatrix.identity(),
        AffineMatrix.translation(10.0, -3.0),
        AffineMatrix.scale(2.0, 0.5),
        AffineMatrix.rotation(30.0),
        AffineMatrix.translation(3.0, 4.0) @ AffineMatrix.scale(1.5),
    )

    for matrix in matrices:
        for point in points:
            assert matrix.inverse().apply_to_point(matrix.apply_to_point(point)).almost_equals(
                point
            )
            assert (matrix @ AffineMatrix.identity()).apply_to_point(point).almost_equals(
                matrix.apply_to_point(point)
            )

    boxes = (
        BoundingBox(0.0, 0.0, 10.0, 10.0),
        BoundingBox(-5.0, -5.0, 5.0, 5.0),
        BoundingBox(1.0, 2.0, 1.0, 9.0),
    )
    for left in boxes:
        for right in boxes:
            union = left.union(right)
            assert union.contains_box(left)
            assert union.contains_box(right)
            intersection = left.intersection(right)
            if intersection is not None:
                assert left.contains_box(intersection)
                assert right.contains_box(intersection)

    page_size = Size(612.0, 792.0)
    for point in (Point(0.0, 0.0), Point(306.0, 396.0), Point(612.0, 792.0)):
        assert point.normalize(page_size).denormalize(page_size).almost_equals(point)
