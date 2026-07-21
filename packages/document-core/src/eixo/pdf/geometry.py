from __future__ import annotations

from dataclasses import dataclass

from eixo.geometry import (
    AffineMatrix,
    BoundingBox,
    GeometryValidationError,
    PageBoxPolicy,
    PageGeometry,
    Rotation,
    Size,
)

PDFBoxTuple = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class PDFNativePageGeometry:
    media_box: BoundingBox
    crop_box: BoundingBox | None
    rotation: Rotation
    user_unit: float = 1.0
    box_policy: PageBoxPolicy = PageBoxPolicy.CROP_BOX_THEN_MEDIA_BOX

    @property
    def visual_box(self) -> BoundingBox:
        if self.box_policy == PageBoxPolicy.MEDIA_BOX:
            return self.media_box
        if self.box_policy == PageBoxPolicy.CROP_BOX:
            if self.crop_box is None:
                raise GeometryValidationError("CropBox is required by page box policy")
            return self.crop_box
        return self.crop_box or self.media_box

    def to_canonical(self) -> PageGeometry:
        if self.user_unit <= 0.0:
            raise GeometryValidationError("user_unit must be positive")
        box = self.visual_box
        native_to_unrotated = AffineMatrix(
            self.user_unit,
            0.0,
            0.0,
            -self.user_unit,
            -box.x_min * self.user_unit,
            box.y_max * self.user_unit,
        )
        width = box.width * self.user_unit
        height = box.height * self.user_unit
        page_rotation = self.rotation.quarter_turns
        if page_rotation is None:
            raise GeometryValidationError("PDF page rotation must be orthogonal")
        rotation_matrix, size = _page_rotation_to_canonical(page_rotation, width, height)
        native_to_canonical = rotation_matrix @ native_to_unrotated
        return PageGeometry(
            size=size,
            rotation=self.rotation,
            visual_box=box,
            media_box=self.media_box,
            crop_box=self.crop_box,
            box_policy=self.box_policy,
            user_unit=self.user_unit,
            native_to_canonical=native_to_canonical,
            canonical_to_native=native_to_canonical.inverse(),
        )


def canonical_pdf_page_geometry(
    *,
    media_box: PDFBoxTuple | BoundingBox | None,
    crop_box: PDFBoxTuple | BoundingBox | None = None,
    rotation_degrees: float = 0.0,
    user_unit: float = 1.0,
    box_policy: PageBoxPolicy = PageBoxPolicy.CROP_BOX_THEN_MEDIA_BOX,
) -> PageGeometry:
    if media_box is None:
        raise GeometryValidationError("MediaBox is required for PDF page geometry")
    native = PDFNativePageGeometry(
        media_box=pdf_box(media_box),
        crop_box=pdf_box(crop_box) if crop_box is not None else None,
        rotation=Rotation(rotation_degrees),
        user_unit=user_unit,
        box_policy=box_policy,
    )
    return native.to_canonical()


def pdf_box(value: PDFBoxTuple | BoundingBox) -> BoundingBox:
    if isinstance(value, BoundingBox):
        return value
    x0, y0, x1, y1 = value
    return BoundingBox(float(x0), float(y0), float(x1), float(y1))


def box_tuple(box: BoundingBox | None) -> PDFBoxTuple | None:
    if box is None:
        return None
    return (box.x_min, box.y_min, box.x_max, box.y_max)


def _page_rotation_to_canonical(
    quarter_turns: int,
    width: float,
    height: float,
) -> tuple[AffineMatrix, Size]:
    if quarter_turns == 0:
        return AffineMatrix.identity(), Size(width, height)
    if quarter_turns == 1:
        return AffineMatrix(0.0, 1.0, -1.0, 0.0, height, 0.0), Size(height, width)
    if quarter_turns == 2:
        return AffineMatrix(-1.0, 0.0, 0.0, -1.0, width, height), Size(width, height)
    if quarter_turns == 3:
        return AffineMatrix(0.0, -1.0, 1.0, 0.0, 0.0, width), Size(height, width)
    raise GeometryValidationError("unsupported PDF page rotation")


__all__ = [
    "PDFBoxTuple",
    "PDFNativePageGeometry",
    "box_tuple",
    "canonical_pdf_page_geometry",
    "pdf_box",
]
