from __future__ import annotations

import pytest

from eixo import (
    BoundingBox,
    PDFImageBinaryFidelity,
    PDFImageBinaryReference,
    PDFImageBinaryRepresentation,
    PDFImageCatalog,
    PDFImageExtractionMethod,
    PDFImageExtractionOptions,
    PDFImageKind,
    PDFImageMaskType,
    PDFImageOccurrence,
    PDFImageResource,
    PDFImageResourceDescriptor,
    PDFImageVisibility,
    PDFNativeImageArtifact,
    PDFNativeImageStatistics,
    PDFObjectReference,
    PDFPageImageLayer,
    PDFPageReference,
    PDFPaintOrder,
    PDFPaintOrderConfidence,
    PDFProviderCapabilities,
    PDFProviderDescriptor,
    PDFResourceReference,
    PDFResourceScope,
    PDFResourceType,
    PDFSupportLevel,
    Quad,
    image_binary_id,
    image_occurrence_id,
    image_resource_id,
    sha256_hex,
)
from eixo.core import ContractVersion, ProviderId, ProviderVersion


def test_image_ids_and_hashes_are_deterministic() -> None:
    reference = PDFObjectReference(object_number=53, xref=53)

    assert image_resource_id(reference) == "pdfimage:pdfobj:53:0"
    assert image_occurrence_id(0, 2, stream_index=1, operation_index=72) == (
        "pdfimageocc:page-0:stream-1:operation-72:occurrence-2"
    )
    assert sha256_hex(b"image") == sha256_hex(b"image")


def test_image_resource_separates_binary_metadata_from_occurrence() -> None:
    page = PDFPageReference(page_index=0, page_number=1)
    object_reference = PDFObjectReference(object_number=9, xref=9)
    mask_object = PDFObjectReference(object_number=12, xref=12)
    mask_reference = PDFResourceReference(
        resource_id="pdfmask:pdfobj:12:0",
        resource_type=PDFResourceType.MASK,
        scope=PDFResourceScope.PAGE,
        resource_name="Im0-smask",
        page_reference=page,
        object_reference=mask_object,
    )
    resource_reference = PDFResourceReference(
        resource_id="pdfimage:pdfobj:9:0",
        resource_type=PDFResourceType.IMAGE,
        scope=PDFResourceScope.PAGE,
        resource_name="Im0",
        page_reference=page,
        object_reference=object_reference,
    )
    binary = PDFImageBinaryReference(
        binary_id=image_binary_id(
            resource_reference.resource_id,
            PDFImageBinaryRepresentation.PROVIDER_EXTRACTED_ORIGINAL.value,
        ),
        content_hash=sha256_hex(b"encoded"),
        size_bytes=7,
        representation=PDFImageBinaryRepresentation.PROVIDER_EXTRACTED_ORIGINAL,
        media_type="image/jpeg",
        detected_format="jpeg",
        extraction_method=PDFImageExtractionMethod.PROVIDER_EXTRACT_IMAGE,
        fidelity=PDFImageBinaryFidelity.PROVIDER_RECONSTRUCTED,
    )
    descriptor = PDFImageResourceDescriptor(
        reference=resource_reference,
        object_reference=object_reference,
        pages_using_resource=(page,),
        width=64,
        height=32,
        bits_per_component=8,
        filter_chain=("DCTDecode",),
        soft_mask_reference=mask_reference,
        dictionary_summary={"color_space": "DeviceRGB"},
    )

    resource = PDFImageResource.from_descriptor(
        descriptor,
        encoded_artifact_reference=binary,
    )
    occurrence = PDFImageOccurrence(
        occurrence_id=image_occurrence_id(0, 0),
        image_resource_id=resource.image_resource_id,
        page_id=page.stable_id,
        bounding_box=BoundingBox(10, 20, 42, 36),
        quad=Quad(
            BoundingBox(10, 20, 42, 36).top_left,
            BoundingBox(10, 20, 42, 36).top_right,
            BoundingBox(10, 20, 42, 36).bottom_right,
            BoundingBox(10, 20, 42, 36).bottom_left,
        ),
        soft_mask_reference=resource.soft_mask_reference,
        visibility=PDFImageVisibility.VISIBLE,
        paint_order=PDFPaintOrder(
            global_paint_order=0,
            confidence=PDFPaintOrderConfidence.PROVIDER_APPROXIMATION,
        ),
        effective_dpi_x=144.0,
        effective_dpi_y=144.0,
        geometry_confidence=0.8,
    )

    assert resource.image_kind == PDFImageKind.IMAGE_XOBJECT
    assert resource.encoded_hash == sha256_hex(b"encoded")
    assert resource.soft_mask_reference is not None
    assert resource.soft_mask_reference.mask_type == PDFImageMaskType.SOFT_MASK
    assert occurrence.image_resource_id == resource.image_resource_id
    data = resource.encoded_artifact_reference.to_dict()
    assert data["content_hash"] == sha256_hex(b"encoded")
    assert "encoded" not in data.values()


def test_image_catalog_artifact_queries_and_statistics_are_serializable() -> None:
    provider = PDFProviderDescriptor(
        provider_id=ProviderId("prov_image_contract"),
        name="Image Provider",
        provider_version=ProviderVersion("0.1.0"),
        backend_name="ContractPDF",
        backend_version="0.1.0",
        capabilities=PDFProviderCapabilities(
            supports_image_extraction=PDFSupportLevel.PARTIAL
        ),
    )
    page = PDFPageReference(page_index=0, page_number=1)
    resource = PDFImageResource(
        image_resource_id="pdfimage:demo",
        width=100,
        height=50,
        image_kind=PDFImageKind.IMAGE_XOBJECT,
        pages_using_resource=(page,),
    )
    occurrence = PDFImageOccurrence(
        occurrence_id="pdfimageocc:demo",
        image_resource_id=resource.image_resource_id,
        page_id=page.stable_id,
        visibility=PDFImageVisibility.VISIBLE,
        geometry_confidence=0.5,
    )
    catalog = PDFImageCatalog(resources=(resource,), occurrences=(occurrence,))
    artifact = PDFNativeImageArtifact(
        artifact_version=ContractVersion("1.0.0"),
        provider=provider,
        image_catalog=catalog,
        pages=(
            PDFPageImageLayer(
                page_reference=page,
                occurrence_ids=(occurrence.occurrence_id,),
                ordered_occurrence_ids=(occurrence.occurrence_id,),
            ),
        ),
        statistics=PDFNativeImageStatistics(
            image_resource_count=1,
            image_occurrence_count=1,
        ),
    )

    assert catalog.resource_by_id(resource.image_resource_id) == resource
    assert catalog.occurrences_for_resource(resource.image_resource_id) == (occurrence,)
    assert catalog.occurrences_for_page(page.stable_id) == (occurrence,)
    assert catalog.resources_without_known_occurrence() == ()
    assert artifact.to_dict()["statistics"]["image_occurrence_count"] == 1


def test_image_options_validate_limits() -> None:
    with pytest.raises(ValueError):
        PDFImageExtractionOptions(max_image_resources=-1)
    with pytest.raises(ValueError):
        PDFImageExtractionOptions(page_selection=(-1,))
