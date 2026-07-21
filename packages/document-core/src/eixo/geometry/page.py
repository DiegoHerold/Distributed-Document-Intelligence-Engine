from __future__ import annotations

from dataclasses import dataclass, field

from eixo.core import EixoWarning
from eixo.core.serialization import Serializable
from eixo.geometry.models import (
    AffineMatrix,
    BoundingBox,
    CoordinateSpace,
    CoordinateUnit,
    PageBoxPolicy,
    Rotation,
    Size,
)


@dataclass(frozen=True, slots=True)
class PageGeometry(Serializable):
    size: Size
    rotation: Rotation = field(default_factory=lambda: Rotation(0.0))
    coordinate_space: CoordinateSpace = CoordinateSpace.CANONICAL
    unit: CoordinateUnit = CoordinateUnit.POINT
    visual_box: BoundingBox | None = None
    media_box: BoundingBox | None = None
    crop_box: BoundingBox | None = None
    box_policy: PageBoxPolicy = PageBoxPolicy.CROP_BOX_THEN_MEDIA_BOX
    user_unit: float = 1.0
    native_to_canonical: AffineMatrix = field(default_factory=AffineMatrix.identity)
    canonical_to_native: AffineMatrix = field(default_factory=AffineMatrix.identity)
    warnings: tuple[EixoWarning, ...] = ()

    def __post_init__(self) -> None:
        if self.unit != CoordinateUnit.POINT:
            raise ValueError("canonical page geometry must use point units")
        if not self.size.has_positive_area:
            raise ValueError("page size must have positive area")
        if self.user_unit <= 0:
            raise ValueError("user_unit must be positive")

    @property
    def width(self) -> float:
        return self.size.width

    @property
    def height(self) -> float:
        return self.size.height

    @property
    def page_box(self) -> BoundingBox:
        return BoundingBox(0.0, 0.0, self.width, self.height)

    def normalize_box(self, box: BoundingBox, *, clamp: bool = False):
        return box.normalize(self.size, clamp=clamp)

    def denormalize_box(self, box):
        return box.denormalize(self.size)


__all__ = ["PageGeometry"]
