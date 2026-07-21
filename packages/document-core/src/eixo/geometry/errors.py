from __future__ import annotations

from eixo.core.errors import ValidationError


class GeometryError(ValidationError):
    code = "geometry.error"


class GeometryValidationError(GeometryError):
    code = "geometry.validation"


class NonInvertibleTransformError(GeometryError):
    code = "geometry.non_invertible_transform"


__all__ = [
    "GeometryError",
    "GeometryValidationError",
    "NonInvertibleTransformError",
]
