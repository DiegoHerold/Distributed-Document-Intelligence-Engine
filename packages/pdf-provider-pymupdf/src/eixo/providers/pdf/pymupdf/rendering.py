from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from eixo.core import InvalidPDFPasswordError, PDFProviderUnavailableError


def render_pdf_page_png(
    path: str | Path,
    page_index: int,
    *,
    password: str | None = None,
    scale: float = 1.0,
) -> bytes:
    """Render one PDF page to PNG bytes through the PyMuPDF backend."""

    try:
        fitz = importlib.import_module("fitz")
    except ModuleNotFoundError as exc:
        raise PDFProviderUnavailableError(
            "PyMuPDF PDF provider is not available",
            public_context={"install": "Install eixo-pdf-provider-pymupdf[backend]."},
            cause=exc,
        ) from exc

    document: Any = fitz.open(Path(path))
    try:
        if document.needs_pass and not document.authenticate(password or ""):
            raise InvalidPDFPasswordError("PDF password is invalid")
        page = document.load_page(page_index)
        matrix = fitz.Matrix(scale, scale)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        return pixmap.tobytes("png")
    finally:
        document.close()


__all__ = ["render_pdf_page_png"]
