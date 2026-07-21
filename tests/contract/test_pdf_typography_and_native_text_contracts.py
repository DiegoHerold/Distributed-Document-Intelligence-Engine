from __future__ import annotations

import pytest

from eixo import (
    BoundingBox,
    NativeGlyph,
    NativeTextSpan,
    NativeWord,
    PDFFontCatalog,
    PDFFontEmbeddedStatus,
    PDFFontResource,
    PDFFontResourceDescriptor,
    PDFFontType,
    PDFGlyphMapping,
    PDFGlyphMappingMethod,
    PDFMappingStatus,
    PDFNativeTextArtifact,
    PDFNativeTextExtractionOptions,
    PDFNativeTextGroupingMethod,
    PDFNativeTextLayer,
    PDFNativeTextRelation,
    PDFNativeTextRelationType,
    PDFNativeTextStatistics,
    PDFNativeTextVisibility,
    PDFObjectReference,
    PDFPageNativeTextLayer,
    PDFPageReference,
    PDFProviderCapabilities,
    PDFProviderDescriptor,
    PDFResourceReference,
    PDFResourceScope,
    PDFResourceType,
    PDFSupportLevel,
    PDFTextColor,
    PDFTextStyle,
    PDFTypographyArtifact,
    Quad,
    font_type_from_provider,
    native_glyph_id,
    normalize_font_family,
    split_subset_font_name,
    typography_style_id,
)
from eixo.core import ContractVersion, ProviderId, ProviderVersion


def test_font_subset_and_family_normalization_are_conservative() -> None:
    prefix, name = split_subset_font_name("ABCDEE+Arial-BoldMT")
    family, method, confidence = normalize_font_family(name)

    assert prefix == "ABCDEE"
    assert name == "Arial-BoldMT"
    assert family == "Arial"
    assert method.value == "heuristic"
    assert confidence < 1.0
    assert font_type_from_provider("CIDFontType2") == PDFFontType.CID_FONT_TYPE2


def test_font_resource_separates_resource_program_and_style() -> None:
    page = PDFPageReference(page_index=0, page_number=1)
    object_reference = PDFObjectReference(object_number=8, xref=8)
    resource = PDFResourceReference(
        resource_id="pdffont:pdfobj:8:0",
        resource_type=PDFResourceType.FONT,
        scope=PDFResourceScope.PAGE,
        resource_name="F1",
        page_reference=page,
        object_reference=object_reference,
    )
    descriptor = PDFFontResourceDescriptor(
        reference=resource,
        status=PDFMappingStatus.RESOLVED,
        object_reference=object_reference,
        pages_using_resource=(page,),
        font_subtype="Type1",
        base_font="ABCDEE+Arial-BoldMT",
        dictionary_summary={"provider_tuple": "8|n/a|Type1|ABCDEE+Arial-BoldMT|F1|WinAnsiEncoding"},
    )

    font = PDFFontResource.from_descriptor(descriptor)
    style = PDFTextStyle(
        style_id=typography_style_id(font.font_id, 12.0, "0", 0),
        font_id=font.font_id,
        font_size=12.0,
        fill_color=PDFTextColor(
            original_value="0",
            color_space="DeviceRGB",
            normalized_rgb=(0.0, 0.0, 0.0),
        ),
    )

    assert font.font_id == resource.resource_id
    assert font.subset is True
    assert font.subset_prefix == "ABCDEE"
    assert font.normalized_family == "Arial"
    assert font.encoding is not None
    assert font.encoding.name == "WinAnsiEncoding"
    assert font.embedded == PDFFontEmbeddedStatus.EXTRACTION_UNAVAILABLE
    assert style.font_size == 12.0
    assert "font_size" not in font.to_dict()


def test_font_catalog_and_typography_artifact_are_queryable_and_serializable() -> None:
    provider = PDFProviderDescriptor(
        provider_id=ProviderId("prov_typography_contract"),
        name="Typography Provider",
        provider_version=ProviderVersion("0.1.0"),
        backend_name="ContractPDF",
        backend_version="0.1.0",
        capabilities=PDFProviderCapabilities(supports_text_extraction=PDFSupportLevel.PARTIAL),
    )
    page = PDFPageReference(page_index=1, page_number=2)
    font = PDFFontResource(
        font_id="pdffont:demo",
        resource_name="F1",
        subtype=PDFFontType.TRUE_TYPE,
        pages_using_font=(page,),
        status=PDFMappingStatus.PARTIALLY_RECOVERED,
    )
    mapping = PDFGlyphMapping(
        mapping_id="map-1",
        font_id=font.font_id,
        glyph_id=10,
        unicode_text="fi",
        normalized_unicode_text="fi",
        mapping_method=PDFGlyphMappingMethod.PROVIDER_MAPPING,
        confidence=0.8,
    )
    catalog = PDFFontCatalog(fonts=(font,), glyph_mappings=(mapping,))
    artifact = PDFTypographyArtifact(
        artifact_version=ContractVersion("1.0.0"),
        provider=provider,
        font_catalog=catalog,
    )

    assert catalog.font_by_id(font.font_id) == font
    assert catalog.fonts_for_page(1) == (font,)
    assert catalog.fonts_without_unicode() == ()
    data = artifact.to_dict()
    assert data["font_catalog"]["glyph_mappings"][0]["unicode_text"] == "fi"
    assert "ContractPDF" in str(data)


def test_native_text_models_preserve_glyphs_without_unicode() -> None:
    page = PDFPageReference(page_index=0, page_number=1)
    glyph_id = native_glyph_id(0, 0, 0)
    box = BoundingBox(10, 20, 15, 32)
    glyph = NativeGlyph(
        glyph_id=glyph_id,
        page_id=page.stable_id,
        bounding_box=box,
        quad=Quad(box.top_left, box.top_right, box.bottom_right, box.bottom_left),
        unicode_text=None,
        normalized_unicode_text=None,
        visibility=PDFNativeTextVisibility.VISIBLE,
        mapping_confidence=0.0,
        geometry_confidence=0.9,
    )
    word = NativeWord(
        word_id="word-1",
        page_id=page.stable_id,
        glyph_ids=(glyph.glyph_id,),
        grouping_method=PDFNativeTextGroupingMethod.EIXO_CONSERVATIVE,
        confidence=0.6,
    )
    span = NativeTextSpan(
        span_id="span-1",
        page_id=page.stable_id,
        glyph_ids=(glyph.glyph_id,),
        word_ids=(word.word_id,),
    )

    layer = PDFPageNativeTextLayer(
        page_reference=page,
        glyphs=(glyph,),
        words=(word,),
        spans=(span,),
        relations=(
            PDFNativeTextRelation(
                source_id=glyph.glyph_id,
                target_id=word.word_id,
                relation_type=PDFNativeTextRelationType.GLYPH_BELONGS_TO_WORD,
            ),
        ),
    )
    artifact = PDFNativeTextArtifact(
        artifact_version=ContractVersion("1.0.0"),
        provider=PDFProviderDescriptor(
            provider_id=ProviderId("prov_text_contract"),
            name="Text Provider",
            provider_version=ProviderVersion("0.1.0"),
            backend_name="ContractPDF",
            backend_version="0.1.0",
            capabilities=PDFProviderCapabilities(),
        ),
        pages=(layer,),
        text_layer=PDFNativeTextLayer(page_text_layers=(layer,)),
        statistics=PDFNativeTextStatistics(
            glyph_count=1,
            word_count=1,
            span_count=1,
            unresolved_unicode_count=1,
        ),
    )

    assert artifact.statistics.unresolved_unicode_count == 1
    assert artifact.to_dict()["pages"][0]["glyphs"][0]["unicode_text"] is None


def test_text_options_validate_limits() -> None:
    with pytest.raises(ValueError):
        PDFNativeTextExtractionOptions(max_glyphs_per_page=0)
    with pytest.raises(ValueError):
        PDFNativeTextExtractionOptions(page_selection=(-1,))
