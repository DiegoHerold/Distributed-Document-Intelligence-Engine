from __future__ import annotations

import pytest

from eixo.geometry import BoundingBox, GeometryValidationError, PageBoxPolicy, Point
from eixo.pdf import canonical_pdf_page_geometry


def test_pdf_native_to_canonical_geometry_without_rotation() -> None:
    geometry = canonical_pdf_page_geometry(media_box=(0.0, 0.0, 200.0, 100.0))

    assert geometry.size.width == 200.0
    assert geometry.size.height == 100.0
    assert geometry.native_to_canonical.apply_to_point(Point(0.0, 100.0)) == Point(0.0, 0.0)
    assert geometry.native_to_canonical.apply_to_point(Point(200.0, 0.0)) == Point(
        200.0,
        100.0,
    )
    assert geometry.canonical_to_native.apply_to_point(Point(0.0, 0.0)) == Point(
        0.0,
        100.0,
    )


@pytest.mark.parametrize(
    ("rotation", "expected_size", "native_corner", "canonical_corner"),
    (
        (0.0, (200.0, 100.0), Point(0.0, 100.0), Point(0.0, 0.0)),
        (90.0, (100.0, 200.0), Point(0.0, 0.0), Point(0.0, 0.0)),
        (180.0, (200.0, 100.0), Point(200.0, 0.0), Point(0.0, 0.0)),
        (270.0, (100.0, 200.0), Point(200.0, 100.0), Point(0.0, 0.0)),
    ),
)
def test_pdf_page_rotations_map_known_top_left(
    rotation: float,
    expected_size: tuple[float, float],
    native_corner: Point,
    canonical_corner: Point,
) -> None:
    geometry = canonical_pdf_page_geometry(
        media_box=(0.0, 0.0, 200.0, 100.0),
        rotation_degrees=rotation,
    )

    assert (geometry.width, geometry.height) == expected_size
    assert geometry.native_to_canonical.apply_to_point(native_corner).almost_equals(
        canonical_corner
    )
    restored = geometry.canonical_to_native.apply_to_point(canonical_corner)
    assert restored.almost_equals(native_corner)


def test_pdf_cropbox_shift_negative_coordinates_and_user_unit() -> None:
    geometry = canonical_pdf_page_geometry(
        media_box=(-10.0, -20.0, 210.0, 120.0),
        crop_box=(10.0, 20.0, 110.0, 70.0),
        user_unit=2.0,
    )

    assert geometry.visual_box == BoundingBox(10.0, 20.0, 110.0, 70.0)
    assert geometry.size.width == 200.0
    assert geometry.size.height == 100.0
    assert geometry.native_to_canonical.apply_to_point(Point(10.0, 70.0)) == Point(
        0.0,
        0.0,
    )
    assert geometry.native_to_canonical.apply_to_point(Point(110.0, 20.0)) == Point(
        200.0,
        100.0,
    )


def test_pdf_box_policy_and_invalid_rotation() -> None:
    geometry = canonical_pdf_page_geometry(
        media_box=(0.0, 0.0, 100.0, 100.0),
        crop_box=(10.0, 10.0, 20.0, 20.0),
        box_policy=PageBoxPolicy.MEDIA_BOX,
    )

    assert geometry.visual_box == BoundingBox(0.0, 0.0, 100.0, 100.0)
    with pytest.raises(GeometryValidationError):
        canonical_pdf_page_geometry(
            media_box=(0.0, 0.0, 100.0, 100.0),
            rotation_degrees=45.0,
        )
