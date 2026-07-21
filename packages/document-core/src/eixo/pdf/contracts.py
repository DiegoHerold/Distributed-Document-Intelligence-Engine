from __future__ import annotations

from typing import Protocol, runtime_checkable

from eixo.core import DocumentSource
from eixo.pdf.inspection import PDFInspectionOptions, PDFTechnicalInspection
from eixo.pdf.native_text import PDFNativeTextArtifact, PDFNativeTextExtractionOptions
from eixo.pdf.structure import PDFInternalMappingOptions, PDFInternalStructureArtifact
from eixo.pdf.typography import PDFTypographyArtifact, PDFTypographyOptions
from eixo.pdf.models import (
    PDFBasicInfo,
    PDFOpenOptions,
    PDFPageGeometry,
    PDFProbeOptions,
    PDFProbeResult,
    PDFProviderCapabilities,
    PDFProviderDescriptor,
)


@runtime_checkable
class PDFPageHandle(Protocol):
    @property
    def index(self) -> int:
        ...

    @property
    def page_number(self) -> int:
        ...

    @property
    def stable_id(self) -> str:
        ...

    async def get_basic_geometry(self) -> PDFPageGeometry:
        ...


@runtime_checkable
class PDFDocumentHandle(Protocol):
    @property
    def provider_id(self) -> str:
        ...

    @property
    def source(self) -> DocumentSource:
        ...

    @property
    def closed(self) -> bool:
        ...

    async def get_basic_info(self) -> PDFBasicInfo:
        ...

    async def get_page_count(self) -> int:
        ...

    async def get_page(self, index: int) -> PDFPageHandle:
        ...

    async def close(self) -> None:
        ...

    async def __aenter__(self) -> "PDFDocumentHandle":
        ...

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        ...


@runtime_checkable
class PDFProvider(Protocol):
    @property
    def descriptor(self) -> PDFProviderDescriptor:
        ...

    @property
    def capabilities(self) -> PDFProviderCapabilities:
        ...

    async def probe(
        self,
        source: DocumentSource,
        options: PDFProbeOptions | None = None,
    ) -> PDFProbeResult:
        ...

    async def open(
        self,
        source: DocumentSource,
        options: PDFOpenOptions | None = None,
    ) -> PDFDocumentHandle:
        ...


@runtime_checkable
class PDFTechnicalInspector(Protocol):
    async def inspect(
        self,
        source: DocumentSource,
        options: PDFInspectionOptions | None = None,
    ) -> PDFTechnicalInspection:
        ...

    async def inspect_document(
        self,
        document: PDFDocumentHandle,
        options: PDFInspectionOptions | None = None,
    ) -> PDFTechnicalInspection:
        ...


@runtime_checkable
class PDFInternalStructureMapper(Protocol):
    async def map(
        self,
        source: DocumentSource,
        options: PDFInternalMappingOptions | None = None,
    ) -> PDFInternalStructureArtifact:
        ...

    async def map_document(
        self,
        document: PDFDocumentHandle,
        options: PDFInternalMappingOptions | None = None,
    ) -> PDFInternalStructureArtifact:
        ...


@runtime_checkable
class PDFTypographyResolver(Protocol):
    async def resolve(
        self,
        source: DocumentSource,
        options: PDFTypographyOptions | None = None,
    ) -> PDFTypographyArtifact:
        ...

    async def resolve_document(
        self,
        document: PDFDocumentHandle,
        options: PDFTypographyOptions | None = None,
    ) -> PDFTypographyArtifact:
        ...


@runtime_checkable
class PDFNativeTextExtractor(Protocol):
    async def extract(
        self,
        source: DocumentSource,
        options: PDFNativeTextExtractionOptions | None = None,
    ) -> PDFNativeTextArtifact:
        ...

    async def extract_document(
        self,
        document: PDFDocumentHandle,
        options: PDFNativeTextExtractionOptions | None = None,
    ) -> PDFNativeTextArtifact:
        ...


__all__ = [
    "PDFDocumentHandle",
    "PDFInternalStructureMapper",
    "PDFNativeTextExtractor",
    "PDFPageHandle",
    "PDFProvider",
    "PDFTechnicalInspector",
    "PDFTypographyResolver",
]
