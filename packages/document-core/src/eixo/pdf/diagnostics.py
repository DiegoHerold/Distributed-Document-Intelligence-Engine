from __future__ import annotations

import hashlib
import struct
import zlib
from dataclasses import dataclass, field
from typing import Any

from eixo.core.serialization import Serializable
from eixo.pdf.scene import (
    PDFPageScene,
    PDFSceneElementType,
    PDFSceneVisibility,
    PDFVisualElement,
)


@dataclass(frozen=True, slots=True)
class PDFDiagnosticPreviewConfig(Serializable):
    show_glyphs: bool = True
    show_words: bool = True
    show_spans: bool = True
    show_lines: bool = True
    show_blocks: bool = True
    show_images: bool = True
    show_vectors: bool = True
    show_clipping: bool = True
    show_links: bool = True
    show_annotations: bool = True
    show_widgets: bool = True
    show_element_ids: bool = True
    show_paint_order: bool = True
    show_baselines: bool = True
    show_invisible_elements: bool = True
    scale: float = 1.0

    def __post_init__(self) -> None:
        if self.scale <= 0:
            raise ValueError("scale must be positive")


@dataclass(frozen=True, slots=True)
class PDFDiagnosticOverlay(Serializable):
    element_id: str
    element_type: str
    page_id: str
    bounding_box: dict[str, float] | None = None
    paint_order: int | None = None
    scene_order: int | None = None
    order_confidence: str | None = None
    visibility: str | None = None
    clip_path_reference: str | None = None
    resource_references: tuple[str, ...] = ()
    marker: str | None = None


@dataclass(frozen=True, slots=True)
class PDFDiagnosticPreviewArtifact(Serializable):
    preview_id: str
    page_id: str
    page_index: int
    width: int
    height: int
    media_type: str = "image/png"
    png_bytes: bytes = field(default=b"", repr=False, compare=False)
    png_sha256: str = ""
    base_render_source: str = "diagnostic_blank_page"
    overlays: tuple[PDFDiagnosticOverlay, ...] = ()
    legend: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def metadata_dict(self) -> dict[str, Any]:
        data = self.to_dict()
        data.pop("png_bytes", None)
        return data


class PDFDiagnosticPreviewGenerator:
    def generate(
        self,
        scene: PDFPageScene,
        config: PDFDiagnosticPreviewConfig | None = None,
    ) -> PDFDiagnosticPreviewArtifact:
        config = config or PDFDiagnosticPreviewConfig()
        width = max(1, int(round(scene.geometry.width * config.scale)))
        height = max(1, int(round(scene.geometry.height * config.scale)))
        canvas = _Canvas(width, height)
        overlays: list[PDFDiagnosticOverlay] = []

        for element in scene.elements:
            if not _should_show(element, config):
                continue
            overlay = _overlay_for(element)
            overlays.append(overlay)
            _draw_element(canvas, element, config)

        legend = _legend(scene, overlays, config)
        warnings = tuple(warning.code for warning in scene.warnings)
        limitations = tuple(item.code for item in scene.limitations)
        if not overlays:
            warnings = warnings + ("diagnostic_preview.empty_overlay",)
        limitations = limitations + ("diagnostic_preview.no_official_pdf_renderer",)
        png = _encode_png(width, height, canvas.bytes())
        digest = hashlib.sha256(png).hexdigest()
        return PDFDiagnosticPreviewArtifact(
            preview_id=f"pdfdiag:{scene.scene_id}",
            page_id=scene.page_id,
            page_index=scene.page_index,
            width=width,
            height=height,
            png_bytes=png,
            png_sha256=digest,
            overlays=tuple(overlays),
            legend=legend,
            warnings=warnings,
            limitations=limitations,
        )


class _Canvas:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.pixels = bytearray([255, 255, 255] * width * height)

    def set_pixel(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return
        offset = (y * self.width + x) * 3
        self.pixels[offset : offset + 3] = bytes(color)

    def rectangle(
        self,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        color: tuple[int, int, int],
        *,
        marker: bool = False,
    ) -> None:
        left, right = sorted((max(0, x0), min(self.width - 1, x1)))
        top, bottom = sorted((max(0, y0), min(self.height - 1, y1)))
        for x in range(left, right + 1):
            self.set_pixel(x, top, color)
            self.set_pixel(x, bottom, color)
        for y in range(top, bottom + 1):
            self.set_pixel(left, y, color)
            self.set_pixel(right, y, color)
        if marker:
            for y in range(top, min(top + 4, self.height)):
                for x in range(left, min(left + 4, self.width)):
                    self.set_pixel(x, y, color)

    def baseline(
        self,
        x0: int,
        y: int,
        x1: int,
        color: tuple[int, int, int],
    ) -> None:
        for x in range(max(0, x0), min(self.width, x1 + 1)):
            self.set_pixel(x, y, color)

    def bytes(self) -> bytes:
        return bytes(self.pixels)


def _should_show(element: PDFVisualElement, config: PDFDiagnosticPreviewConfig) -> bool:
    if (
        element.visibility != PDFSceneVisibility.VISIBLE
        and not config.show_invisible_elements
    ):
        return False
    mapping = {
        PDFSceneElementType.TEXT_GLYPH: config.show_glyphs,
        PDFSceneElementType.TEXT_WORD: config.show_words,
        PDFSceneElementType.TEXT_SPAN: config.show_spans,
        PDFSceneElementType.TEXT_LINE: config.show_lines,
        PDFSceneElementType.TEXT_BLOCK: config.show_blocks,
        PDFSceneElementType.IMAGE: config.show_images,
        PDFSceneElementType.VECTOR: config.show_vectors,
        PDFSceneElementType.CLIPPING_PATH: config.show_clipping,
        PDFSceneElementType.LINK: config.show_links,
        PDFSceneElementType.ANNOTATION: config.show_annotations,
        PDFSceneElementType.FORM_WIDGET: config.show_widgets,
    }
    return mapping.get(element.element_type, True)


def _overlay_for(element: PDFVisualElement) -> PDFDiagnosticOverlay:
    bbox = element.bounding_box.to_dict() if element.bounding_box is not None else None
    paint_order = (
        element.paint_order.global_paint_order
        if element.paint_order is not None
        else element.native_order
    )
    return PDFDiagnosticOverlay(
        element_id=element.element_id,
        element_type=element.element_type.value,
        page_id=element.page_id,
        bounding_box=bbox,
        paint_order=paint_order,
        scene_order=element.scene_order,
        order_confidence=element.order_confidence.value,
        visibility=element.visibility.value,
        clip_path_reference=element.clip_path_reference,
        resource_references=element.resource_references,
        marker=_short_marker(element.element_id),
    )


def _draw_element(
    canvas: _Canvas,
    element: PDFVisualElement,
    config: PDFDiagnosticPreviewConfig,
) -> None:
    if element.bounding_box is None:
        return
    bbox = element.bounding_box
    x0 = int(round(bbox.x_min * config.scale))
    y0 = int(round(bbox.y_min * config.scale))
    x1 = int(round(bbox.x_max * config.scale))
    y1 = int(round(bbox.y_max * config.scale))
    color = _color_for(element)
    canvas.rectangle(x0, y0, x1, y1, color, marker=config.show_element_ids)
    if config.show_baselines and element.element_type.value.startswith("text_"):
        canvas.baseline(x0, y1, x1, color)
    if config.show_paint_order and element.paint_order is not None:
        canvas.rectangle(x0 + 2, y0 + 2, x0 + 6, y0 + 6, color, marker=True)


def _color_for(element: PDFVisualElement) -> tuple[int, int, int]:
    if element.visibility != PDFSceneVisibility.VISIBLE:
        return (120, 120, 120)
    return {
        PDFSceneElementType.TEXT_GLYPH: (0, 96, 192),
        PDFSceneElementType.TEXT_WORD: (0, 128, 160),
        PDFSceneElementType.TEXT_SPAN: (0, 72, 200),
        PDFSceneElementType.TEXT_LINE: (0, 120, 220),
        PDFSceneElementType.TEXT_BLOCK: (0, 150, 220),
        PDFSceneElementType.IMAGE: (200, 80, 0),
        PDFSceneElementType.VECTOR: (0, 150, 70),
        PDFSceneElementType.CLIPPING_PATH: (180, 0, 160),
        PDFSceneElementType.LINK: (120, 60, 200),
        PDFSceneElementType.ANNOTATION: (220, 180, 0),
        PDFSceneElementType.FORM_WIDGET: (200, 0, 80),
    }.get(element.element_type, (0, 0, 0))


def _legend(
    scene: PDFPageScene,
    overlays: list[PDFDiagnosticOverlay],
    config: PDFDiagnosticPreviewConfig,
) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for overlay in overlays:
        counts[overlay.element_type] = counts.get(overlay.element_type, 0) + 1
    return {
        "page_id": scene.page_id,
        "overlay_counts": dict(sorted(counts.items())),
        "show_element_ids": config.show_element_ids,
        "show_paint_order": config.show_paint_order,
        "order_note": "provider or partial order is marked through order_confidence",
        "colors": {
            "text": "blue",
            "image": "orange",
            "vector": "green",
            "clipping": "magenta",
            "interactive": "purple/red",
            "invisible": "gray",
        },
    }


def _short_marker(element_id: str) -> str:
    return hashlib.sha1(element_id.encode("utf-8")).hexdigest()[:6]


def _encode_png(width: int, height: int, rgb: bytes) -> bytes:
    rows = []
    stride = width * 3
    for y in range(height):
        rows.append(b"\x00" + rgb[y * stride : (y + 1) * stride])
    raw = b"".join(rows)
    chunks = [
        _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
        _png_chunk(b"IDAT", zlib.compress(raw, level=9)),
        _png_chunk(b"IEND", b""),
    ]
    return b"\x89PNG\r\n\x1a\n" + b"".join(chunks)


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)


__all__ = [
    "PDFDiagnosticOverlay",
    "PDFDiagnosticPreviewArtifact",
    "PDFDiagnosticPreviewConfig",
    "PDFDiagnosticPreviewGenerator",
]
