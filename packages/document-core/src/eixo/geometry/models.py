from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from eixo.core.serialization import Serializable
from eixo.geometry.errors import GeometryValidationError, NonInvertibleTransformError

DEFAULT_ABSOLUTE_TOLERANCE = 1e-9
DEFAULT_RELATIVE_TOLERANCE = 1e-9
SINGULAR_MATRIX_TOLERANCE = 1e-12
POINTS_PER_INCH = 72.0
MILLIMETERS_PER_INCH = 25.4


def _validate_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise GeometryValidationError(f"{name} must be finite")


def _validate_non_negative_finite(name: str, value: float) -> None:
    _validate_finite(name, value)
    if value < 0.0:
        raise GeometryValidationError(f"{name} cannot be negative")


def _validate_positive_finite(name: str, value: float) -> None:
    _validate_finite(name, value)
    if value <= 0.0:
        raise GeometryValidationError(f"{name} must be positive")


class CoordinateUnit(StrEnum):
    POINT = "point"
    INCH = "inch"
    MILLIMETER = "millimeter"
    PIXEL = "pixel"


class CoordinateSpace(StrEnum):
    NATIVE = "native"
    CANONICAL = "canonical"
    NORMALIZED = "normalized"
    PIXEL = "pixel"
    OBJECT_LOCAL = "object_local"


class SizeOrientation(StrEnum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"
    SQUARE = "square"
    DEGENERATE = "degenerate"


class PageBoxPolicy(StrEnum):
    CROP_BOX_THEN_MEDIA_BOX = "crop_box_then_media_box"
    MEDIA_BOX = "media_box"
    CROP_BOX = "crop_box"


@dataclass(frozen=True, slots=True)
class GeometryTolerance(Serializable):
    absolute: float = DEFAULT_ABSOLUTE_TOLERANCE
    relative: float = DEFAULT_RELATIVE_TOLERANCE

    def __post_init__(self) -> None:
        _validate_non_negative_finite("absolute", self.absolute)
        _validate_non_negative_finite("relative", self.relative)

    def close(self, left: float, right: float) -> bool:
        return math.isclose(left, right, abs_tol=self.absolute, rel_tol=self.relative)


DEFAULT_TOLERANCE = GeometryTolerance()


@dataclass(frozen=True, slots=True)
class Vector(Serializable):
    dx: float
    dy: float

    def __post_init__(self) -> None:
        _validate_finite("dx", self.dx)
        _validate_finite("dy", self.dy)

    @property
    def length(self) -> float:
        return math.hypot(self.dx, self.dy)

    def scale(self, factor: float) -> "Vector":
        _validate_finite("factor", factor)
        return Vector(self.dx * factor, self.dy * factor)

    def almost_equals(
        self,
        other: "Vector",
        tolerance: GeometryTolerance = DEFAULT_TOLERANCE,
    ) -> bool:
        return tolerance.close(self.dx, other.dx) and tolerance.close(self.dy, other.dy)


@dataclass(frozen=True, slots=True)
class Point(Serializable):
    x: float
    y: float

    def __post_init__(self) -> None:
        _validate_finite("x", self.x)
        _validate_finite("y", self.y)

    def translate(self, dx: float, dy: float) -> "Point":
        _validate_finite("dx", dx)
        _validate_finite("dy", dy)
        return Point(self.x + dx, self.y + dy)

    def offset(self, vector: Vector) -> "Point":
        return self.translate(vector.dx, vector.dy)

    def vector_to(self, other: "Point") -> Vector:
        return Vector(other.x - self.x, other.y - self.y)

    def distance_to(self, other: "Point") -> float:
        return self.vector_to(other).length

    def transform(self, matrix: "AffineMatrix") -> "Point":
        return matrix.apply_to_point(self)

    def normalize(self, page_size: "Size", *, clamp: bool = False) -> "NormalizedPoint":
        _validate_positive_page_size(page_size)
        x = self.x / page_size.width
        y = self.y / page_size.height
        if clamp:
            x = _clamp_unit(x)
            y = _clamp_unit(y)
        return NormalizedPoint(x, y)

    def almost_equals(
        self,
        other: "Point",
        tolerance: GeometryTolerance = DEFAULT_TOLERANCE,
    ) -> bool:
        return tolerance.close(self.x, other.x) and tolerance.close(self.y, other.y)


@dataclass(frozen=True, slots=True)
class Size(Serializable):
    width: float
    height: float
    unit: CoordinateUnit = CoordinateUnit.POINT

    def __post_init__(self) -> None:
        _validate_non_negative_finite("width", self.width)
        _validate_non_negative_finite("height", self.height)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def has_positive_area(self) -> bool:
        return self.width > 0.0 and self.height > 0.0

    @property
    def is_degenerate(self) -> bool:
        return not self.has_positive_area

    def aspect_ratio(self) -> float | None:
        if self.height == 0.0:
            return None
        return self.width / self.height

    def orientation(
        self,
        tolerance: GeometryTolerance = DEFAULT_TOLERANCE,
    ) -> SizeOrientation:
        if self.is_degenerate:
            return SizeOrientation.DEGENERATE
        if tolerance.close(self.width, self.height):
            return SizeOrientation.SQUARE
        return (
            SizeOrientation.LANDSCAPE
            if self.width > self.height
            else SizeOrientation.PORTRAIT
        )

    def scale(self, sx: float, sy: float | None = None) -> "Size":
        _validate_finite("sx", sx)
        if sy is None:
            sy = sx
        _validate_finite("sy", sy)
        if sx < 0.0 or sy < 0.0:
            raise GeometryValidationError("scale factors for Size cannot be negative")
        return Size(self.width * sx, self.height * sy, self.unit)

    def almost_equals(
        self,
        other: "Size",
        tolerance: GeometryTolerance = DEFAULT_TOLERANCE,
    ) -> bool:
        return (
            self.unit == other.unit
            and tolerance.close(self.width, other.width)
            and tolerance.close(self.height, other.height)
        )


@dataclass(frozen=True, slots=True)
class Rotation(Serializable):
    degrees: float

    def __post_init__(self) -> None:
        _validate_finite("degrees", self.degrees)
        object.__setattr__(self, "degrees", self.degrees % 360.0)

    @property
    def radians(self) -> float:
        return math.radians(self.degrees)

    @property
    def is_orthogonal(self) -> bool:
        return self.almost_equals(Rotation(0)) or self.quarter_turns is not None

    @property
    def quarter_turns(self) -> int | None:
        value = round(self.degrees / 90.0)
        if math.isclose(self.degrees, value * 90.0, abs_tol=DEFAULT_ABSOLUTE_TOLERANCE):
            return value % 4
        return None

    def compose(self, other: "Rotation") -> "Rotation":
        return Rotation(self.degrees + other.degrees)

    def inverse(self) -> "Rotation":
        return Rotation(-self.degrees)

    def almost_equals(
        self,
        other: "Rotation",
        tolerance: GeometryTolerance = DEFAULT_TOLERANCE,
    ) -> bool:
        direct = abs(self.degrees - other.degrees)
        circular = min(direct, 360.0 - direct)
        return circular <= max(tolerance.absolute, tolerance.relative * 360.0)


@dataclass(frozen=True, slots=True)
class BoundingBox(Serializable):
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def __post_init__(self) -> None:
        _validate_finite("x_min", self.x_min)
        _validate_finite("y_min", self.y_min)
        _validate_finite("x_max", self.x_max)
        _validate_finite("y_max", self.y_max)
        if self.x_min > self.x_max:
            raise GeometryValidationError("x_min cannot be greater than x_max")
        if self.y_min > self.y_max:
            raise GeometryValidationError("y_min cannot be greater than y_max")

    @classmethod
    def from_xywh(cls, x: float, y: float, width: float, height: float) -> "BoundingBox":
        _validate_non_negative_finite("width", width)
        _validate_non_negative_finite("height", height)
        return cls(x, y, x + width, y + height)

    @classmethod
    def from_points(cls, points: Iterable[Point]) -> "BoundingBox":
        values = tuple(points)
        if not values:
            raise GeometryValidationError("at least one point is required")
        return cls(
            min(point.x for point in values),
            min(point.y for point in values),
            max(point.x for point in values),
            max(point.y for point in values),
        )

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min

    @property
    def size(self) -> Size:
        return Size(self.width, self.height)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> Point:
        return Point((self.x_min + self.x_max) / 2.0, (self.y_min + self.y_max) / 2.0)

    @property
    def top_left(self) -> Point:
        return Point(self.x_min, self.y_min)

    @property
    def top_right(self) -> Point:
        return Point(self.x_max, self.y_min)

    @property
    def bottom_right(self) -> Point:
        return Point(self.x_max, self.y_max)

    @property
    def bottom_left(self) -> Point:
        return Point(self.x_min, self.y_max)

    @property
    def corners(self) -> tuple[Point, Point, Point, Point]:
        return (self.top_left, self.top_right, self.bottom_right, self.bottom_left)

    @property
    def is_degenerate(self) -> bool:
        return self.width == 0.0 or self.height == 0.0

    @property
    def has_positive_area(self) -> bool:
        return self.width > 0.0 and self.height > 0.0

    def union(self, other: "BoundingBox") -> "BoundingBox":
        return BoundingBox(
            min(self.x_min, other.x_min),
            min(self.y_min, other.y_min),
            max(self.x_max, other.x_max),
            max(self.y_max, other.y_max),
        )

    def intersection(self, other: "BoundingBox") -> "BoundingBox | None":
        x_min = max(self.x_min, other.x_min)
        y_min = max(self.y_min, other.y_min)
        x_max = min(self.x_max, other.x_max)
        y_max = min(self.y_max, other.y_max)
        if x_min > x_max or y_min > y_max:
            return None
        return BoundingBox(x_min, y_min, x_max, y_max)

    def intersects(self, other: "BoundingBox") -> bool:
        return self.intersection(other) is not None

    def contains_point(self, point: Point) -> bool:
        return (
            self.x_min <= point.x <= self.x_max
            and self.y_min <= point.y <= self.y_max
        )

    def contains_box(self, other: "BoundingBox") -> bool:
        return self.contains_point(other.top_left) and self.contains_point(
            other.bottom_right
        )

    def iou(self, other: "BoundingBox") -> float:
        intersection = self.intersection(other)
        if intersection is None:
            return 0.0
        union_area = self.area + other.area - intersection.area
        if union_area == 0.0:
            return 1.0 if self.almost_equals(other) else 0.0
        return intersection.area / union_area

    def expand(self, amount: float) -> "BoundingBox":
        _validate_finite("amount", amount)
        return BoundingBox(
            self.x_min - amount,
            self.y_min - amount,
            self.x_max + amount,
            self.y_max + amount,
        )

    def shrink(self, amount: float) -> "BoundingBox":
        return self.expand(-amount)

    def translate(self, dx: float, dy: float) -> "BoundingBox":
        _validate_finite("dx", dx)
        _validate_finite("dy", dy)
        return BoundingBox(
            self.x_min + dx,
            self.y_min + dy,
            self.x_max + dx,
            self.y_max + dy,
        )

    def scale(self, sx: float, sy: float | None = None) -> "BoundingBox":
        _validate_finite("sx", sx)
        if sy is None:
            sy = sx
        _validate_finite("sy", sy)
        points = [Point(point.x * sx, point.y * sy) for point in self.corners]
        return BoundingBox.from_points(points)

    def transform(self, matrix: "AffineMatrix") -> "BoundingBox":
        return BoundingBox.from_points(matrix.apply_to_point(point) for point in self.corners)

    def clip_to(self, bounds: "BoundingBox") -> "BoundingBox | None":
        return self.intersection(bounds)

    def normalize(
        self,
        page_size: Size,
        *,
        clamp: bool = False,
    ) -> "NormalizedBoundingBox":
        _validate_positive_page_size(page_size)
        values = (
            self.x_min / page_size.width,
            self.y_min / page_size.height,
            self.x_max / page_size.width,
            self.y_max / page_size.height,
        )
        if clamp:
            values = tuple(_clamp_unit(value) for value in values)
        return NormalizedBoundingBox(*values)

    def to_polygon(self) -> "Polygon":
        return Polygon(self.corners)

    def almost_equals(
        self,
        other: "BoundingBox",
        tolerance: GeometryTolerance = DEFAULT_TOLERANCE,
    ) -> bool:
        return (
            tolerance.close(self.x_min, other.x_min)
            and tolerance.close(self.y_min, other.y_min)
            and tolerance.close(self.x_max, other.x_max)
            and tolerance.close(self.y_max, other.y_max)
        )


@dataclass(frozen=True, slots=True)
class NormalizedPoint(Serializable):
    x: float
    y: float

    def __post_init__(self) -> None:
        _validate_unit_interval("x", self.x)
        _validate_unit_interval("y", self.y)

    def denormalize(self, page_size: Size) -> Point:
        _validate_positive_page_size(page_size)
        return Point(self.x * page_size.width, self.y * page_size.height)


@dataclass(frozen=True, slots=True)
class NormalizedBoundingBox(Serializable):
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def __post_init__(self) -> None:
        _validate_unit_interval("x_min", self.x_min)
        _validate_unit_interval("y_min", self.y_min)
        _validate_unit_interval("x_max", self.x_max)
        _validate_unit_interval("y_max", self.y_max)
        if self.x_min > self.x_max:
            raise GeometryValidationError("x_min cannot be greater than x_max")
        if self.y_min > self.y_max:
            raise GeometryValidationError("y_min cannot be greater than y_max")

    def denormalize(self, page_size: Size) -> BoundingBox:
        _validate_positive_page_size(page_size)
        return BoundingBox(
            self.x_min * page_size.width,
            self.y_min * page_size.height,
            self.x_max * page_size.width,
            self.y_max * page_size.height,
        )


@dataclass(frozen=True, slots=True)
class Polygon(Serializable):
    points: tuple[Point, ...]

    def __post_init__(self) -> None:
        if len(self.points) < 3:
            raise GeometryValidationError("Polygon requires at least three points")

    @property
    def signed_area(self) -> float:
        total = 0.0
        for left, right in _closed_pairs(self.points):
            total += left.x * right.y - right.x * left.y
        return total / 2.0

    @property
    def area(self) -> float:
        return abs(self.signed_area)

    @property
    def is_clockwise(self) -> bool:
        return self.signed_area > 0.0

    @property
    def is_degenerate(self) -> bool:
        return math.isclose(self.area, 0.0, abs_tol=DEFAULT_ABSOLUTE_TOLERANCE)

    @property
    def bounding_box(self) -> BoundingBox:
        return BoundingBox.from_points(self.points)

    @property
    def centroid(self) -> Point:
        area_factor = self.signed_area * 6.0
        if math.isclose(area_factor, 0.0, abs_tol=DEFAULT_ABSOLUTE_TOLERANCE):
            box = self.bounding_box
            return box.center
        cx = 0.0
        cy = 0.0
        for left, right in _closed_pairs(self.points):
            cross = left.x * right.y - right.x * left.y
            cx += (left.x + right.x) * cross
            cy += (left.y + right.y) * cross
        return Point(cx / area_factor, cy / area_factor)

    @property
    def is_self_intersecting(self) -> bool:
        edges = list(_closed_pairs(self.points))
        for index, edge in enumerate(edges):
            for other_index, other in enumerate(edges):
                if abs(index - other_index) <= 1:
                    continue
                if {index, other_index} == {0, len(edges) - 1}:
                    continue
                if _segments_intersect(edge[0], edge[1], other[0], other[1]):
                    return True
        return False

    def transform(self, matrix: "AffineMatrix") -> "Polygon":
        return Polygon(tuple(matrix.apply_to_point(point) for point in self.points))

    def contains_point(self, point: Point) -> bool:
        inside = False
        vertices = self.points
        for left, right in _closed_pairs(vertices):
            if _point_on_segment(point, left, right):
                return True
            crosses = (left.y > point.y) != (right.y > point.y)
            if crosses:
                x_intersection = (right.x - left.x) * (point.y - left.y) / (
                    right.y - left.y
                ) + left.x
                if point.x < x_intersection:
                    inside = not inside
        return inside


@dataclass(frozen=True, slots=True)
class Quad(Serializable):
    top_left: Point
    top_right: Point
    bottom_right: Point
    bottom_left: Point

    @property
    def points(self) -> tuple[Point, Point, Point, Point]:
        return (self.top_left, self.top_right, self.bottom_right, self.bottom_left)

    @property
    def polygon(self) -> Polygon:
        return Polygon(self.points)

    @property
    def bounding_box(self) -> BoundingBox:
        return self.polygon.bounding_box

    @property
    def top_width(self) -> float:
        return self.top_left.distance_to(self.top_right)

    @property
    def bottom_width(self) -> float:
        return self.bottom_left.distance_to(self.bottom_right)

    @property
    def left_height(self) -> float:
        return self.top_left.distance_to(self.bottom_left)

    @property
    def right_height(self) -> float:
        return self.top_right.distance_to(self.bottom_right)

    @property
    def is_degenerate(self) -> bool:
        return self.polygon.is_degenerate

    @property
    def is_convex(self) -> bool:
        signs: list[float] = []
        points = self.points
        for index, point in enumerate(points):
            next_point = points[(index + 1) % len(points)]
            next_next = points[(index + 2) % len(points)]
            cross = _cross(point, next_point, next_next)
            if not math.isclose(cross, 0.0, abs_tol=DEFAULT_ABSOLUTE_TOLERANCE):
                signs.append(cross)
        return bool(signs) and (
            all(value > 0 for value in signs) or all(value < 0 for value in signs)
        )

    def transform(self, matrix: "AffineMatrix") -> "Quad":
        return Quad(*(matrix.apply_to_point(point) for point in self.points))

    def almost_equals(
        self,
        other: "Quad",
        tolerance: GeometryTolerance = DEFAULT_TOLERANCE,
    ) -> bool:
        return all(
            left.almost_equals(right, tolerance)
            for left, right in zip(self.points, other.points, strict=True)
        )


@dataclass(frozen=True, slots=True)
class AffineMatrix(Serializable):
    a: float
    b: float
    c: float
    d: float
    e: float
    f: float

    def __post_init__(self) -> None:
        for name in ("a", "b", "c", "d", "e", "f"):
            _validate_finite(name, getattr(self, name))

    @classmethod
    def identity(cls) -> "AffineMatrix":
        return cls(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

    @classmethod
    def translation(cls, tx: float, ty: float) -> "AffineMatrix":
        _validate_finite("tx", tx)
        _validate_finite("ty", ty)
        return cls(1.0, 0.0, 0.0, 1.0, tx, ty)

    @classmethod
    def scale(cls, sx: float, sy: float | None = None) -> "AffineMatrix":
        _validate_finite("sx", sx)
        if sy is None:
            sy = sx
        _validate_finite("sy", sy)
        return cls(sx, 0.0, 0.0, sy, 0.0, 0.0)

    @classmethod
    def rotation(cls, degrees: float, origin: Point | None = None) -> "AffineMatrix":
        radians = math.radians(degrees)
        cos_value = math.cos(radians)
        sin_value = math.sin(radians)
        matrix = cls(cos_value, sin_value, -sin_value, cos_value, 0.0, 0.0)
        if origin is None:
            return matrix
        return cls.translation(origin.x, origin.y) @ matrix @ cls.translation(
            -origin.x,
            -origin.y,
        )

    @classmethod
    def skew(cls, x_degrees: float = 0.0, y_degrees: float = 0.0) -> "AffineMatrix":
        return cls(
            1.0,
            math.tan(math.radians(y_degrees)),
            math.tan(math.radians(x_degrees)),
            1.0,
            0.0,
            0.0,
        )

    @property
    def determinant(self) -> float:
        return self.a * self.d - self.b * self.c

    @property
    def is_singular(self) -> bool:
        return abs(self.determinant) <= SINGULAR_MATRIX_TOLERANCE

    def inverse(self) -> "AffineMatrix":
        det = self.determinant
        if abs(det) <= SINGULAR_MATRIX_TOLERANCE:
            raise NonInvertibleTransformError(
                "Affine matrix is singular or too close to singular"
            )
        return AffineMatrix(
            self.d / det,
            -self.b / det,
            -self.c / det,
            self.a / det,
            (self.c * self.f - self.d * self.e) / det,
            (self.b * self.e - self.a * self.f) / det,
        )

    def __matmul__(self, other: "AffineMatrix") -> "AffineMatrix":
        return AffineMatrix(
            self.a * other.a + self.c * other.b,
            self.b * other.a + self.d * other.b,
            self.a * other.c + self.c * other.d,
            self.b * other.c + self.d * other.d,
            self.a * other.e + self.c * other.f + self.e,
            self.b * other.e + self.d * other.f + self.f,
        )

    def apply_to_point(self, point: Point) -> Point:
        return Point(
            self.a * point.x + self.c * point.y + self.e,
            self.b * point.x + self.d * point.y + self.f,
        )

    def apply_to_box(self, box: BoundingBox) -> BoundingBox:
        return box.transform(self)

    def apply_to_polygon(self, polygon: Polygon) -> Polygon:
        return polygon.transform(self)

    def apply_to_quad(self, quad: Quad) -> Quad:
        return quad.transform(self)

    def almost_equals(
        self,
        other: "AffineMatrix",
        tolerance: GeometryTolerance = DEFAULT_TOLERANCE,
    ) -> bool:
        return all(
            tolerance.close(getattr(self, name), getattr(other, name))
            for name in ("a", "b", "c", "d", "e", "f")
        )


def points_to_inches(points: float) -> float:
    _validate_finite("points", points)
    return points / POINTS_PER_INCH


def inches_to_points(inches: float) -> float:
    _validate_finite("inches", inches)
    return inches * POINTS_PER_INCH


def points_to_millimeters(points: float) -> float:
    return points_to_inches(points) * MILLIMETERS_PER_INCH


def millimeters_to_points(millimeters: float) -> float:
    _validate_finite("millimeters", millimeters)
    return inches_to_points(millimeters / MILLIMETERS_PER_INCH)


def points_to_pixels(points: float, dpi: float) -> float:
    _validate_positive_finite("dpi", dpi)
    return points * dpi / POINTS_PER_INCH


def pixels_to_points(pixels: float, dpi: float) -> float:
    _validate_finite("pixels", pixels)
    _validate_positive_finite("dpi", dpi)
    return pixels * POINTS_PER_INCH / dpi


def _validate_unit_interval(name: str, value: float) -> None:
    _validate_finite(name, value)
    if value < 0.0 or value > 1.0:
        raise GeometryValidationError(f"{name} must be between 0 and 1")


def _validate_positive_page_size(size: Size) -> None:
    if not size.has_positive_area:
        raise GeometryValidationError("page size must have positive area")


def _clamp_unit(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def _closed_pairs(points: tuple[Point, ...]) -> Iterable[tuple[Point, Point]]:
    for index, point in enumerate(points):
        yield point, points[(index + 1) % len(points)]


def _cross(origin: Point, left: Point, right: Point) -> float:
    return (left.x - origin.x) * (right.y - origin.y) - (
        left.y - origin.y
    ) * (right.x - origin.x)


def _point_on_segment(point: Point, left: Point, right: Point) -> bool:
    if not math.isclose(_cross(left, right, point), 0.0, abs_tol=DEFAULT_ABSOLUTE_TOLERANCE):
        return False
    return (
        min(left.x, right.x) <= point.x <= max(left.x, right.x)
        and min(left.y, right.y) <= point.y <= max(left.y, right.y)
    )


def _segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    def orientation(left: Point, right: Point, point: Point) -> float:
        return _cross(left, right, point)

    o1 = orientation(a, b, c)
    o2 = orientation(a, b, d)
    o3 = orientation(c, d, a)
    o4 = orientation(c, d, b)
    if (
        o1 * o2 < 0.0
        and o3 * o4 < 0.0
    ):
        return True
    return any(
        (
            math.isclose(o1, 0.0, abs_tol=DEFAULT_ABSOLUTE_TOLERANCE)
            and _point_on_segment(c, a, b),
            math.isclose(o2, 0.0, abs_tol=DEFAULT_ABSOLUTE_TOLERANCE)
            and _point_on_segment(d, a, b),
            math.isclose(o3, 0.0, abs_tol=DEFAULT_ABSOLUTE_TOLERANCE)
            and _point_on_segment(a, c, d),
            math.isclose(o4, 0.0, abs_tol=DEFAULT_ABSOLUTE_TOLERANCE)
            and _point_on_segment(b, c, d),
        )
    )


__all__ = [
    "AffineMatrix",
    "BoundingBox",
    "CoordinateSpace",
    "CoordinateUnit",
    "DEFAULT_ABSOLUTE_TOLERANCE",
    "DEFAULT_RELATIVE_TOLERANCE",
    "DEFAULT_TOLERANCE",
    "GeometryTolerance",
    "NormalizedBoundingBox",
    "NormalizedPoint",
    "PageBoxPolicy",
    "POINTS_PER_INCH",
    "Point",
    "Polygon",
    "Quad",
    "Rotation",
    "SINGULAR_MATRIX_TOLERANCE",
    "Size",
    "SizeOrientation",
    "Vector",
    "inches_to_points",
    "millimeters_to_points",
    "pixels_to_points",
    "points_to_inches",
    "points_to_millimeters",
    "points_to_pixels",
]
