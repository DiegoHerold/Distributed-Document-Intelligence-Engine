from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from eixo.artifacts import ArtifactStore
from eixo.core import (
    ArtifactId,
    ArtifactReference,
    ArtifactType,
    ArtifactWriteRequest,
    CapabilityId,
    CapabilityStatus,
    CapabilityVersion,
    ContentHash,
    DocumentId,
    DocumentSource,
    EixoWarning,
    ErrorResult,
    InspectionRequest,
    InspectionResult,
    JobId,
    ParseRequest,
    ParseResult,
    ProcessingRequest,
    ProcessingResult,
    ProcessingStatus,
    ProviderId,
    ProviderVersion,
    ResultStatus,
    ValidationError,
)
from eixo.core.serialization import to_jsonable
from eixo.plugins import CapabilityDescriptor, ExecutionContext, ProviderDescriptor
from eixo.pdf import (
    NativePDFSceneArtifact,
    NativePDFSceneArtifactBuilder,
    PDFImageExtractionOptions,
    PDFInspectionOptions,
    PDFInternalMappingOptions,
    PDFInteractiveExtractionOptions,
    PDFNativeTextExtractionOptions,
    PDFNativeVectorOptions,
    PDFOpenOptions,
    PDFPageSceneBuilder,
    PDFPageSceneOptions,
    PDFPageScenesArtifact,
    PDFParseOptions,
    PDFParseProfile,
    PDFProviderRegistry,
    PDFTechnicalInspection,
    PDFTypographyOptions,
)

PUBLIC_PDF_PROVIDER_ID = ProviderId("prov_eixo_pdf_public")
PDF_INSPECT_CAPABILITY_ID = CapabilityId("cap_pdf_public_inspect")
PDF_PARSE_CAPABILITY_ID = CapabilityId("cap_pdf_public_parse")
PDF_PROCESS_CAPABILITY_ID = CapabilityId("cap_pdf_public_process")


def public_pdf_provider_descriptor() -> ProviderDescriptor:
    return ProviderDescriptor(
        provider_id=PUBLIC_PDF_PROVIDER_ID,
        name="Eixo public PDF integration",
        version=ProviderVersion("0.1.0"),
        status=CapabilityStatus.ACTIVE,
        capabilities=(
            PDF_INSPECT_CAPABILITY_ID,
            PDF_PARSE_CAPABILITY_ID,
            PDF_PROCESS_CAPABILITY_ID,
        ),
    )


@dataclass(slots=True)
class PDFInspectionCapability:
    pdf_provider_registry: PDFProviderRegistry
    artifact_store: ArtifactStore
    preferred_provider: ProviderId | None = None

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return _descriptor(
            capability_id=PDF_INSPECT_CAPABILITY_ID,
            name="pdf.inspect.public",
            input_contract="InspectionRequest",
            output_contract="InspectionResult",
        )

    async def execute(
        self,
        request: InspectionRequest,
        context: ExecutionContext,
    ) -> InspectionResult:
        options = PDFParseOptions.from_public_options(options=request.options)
        provider = self.pdf_provider_registry.resolve(
            preferred_provider=self.preferred_provider
        )
        async with await provider.open(
        request.source,
        PDFOpenOptions(
            password=options.password,
            timeout_seconds=options.timeout,
        ),
        ) as document:
            inspection = await _inspect_open_document(document, options)
        reference = await _store_json_artifact(
            self.artifact_store,
            inspection,
            artifact_kind="pdf_inspection",
            producer="eixo.pdf.public.inspect",
            source=request.source,
            document_id=_document_id_from_source(request.source),
        )
        return _inspection_result_from_pdf(
            request.source,
            inspection,
            artifact_reference=reference,
        )


@dataclass(slots=True)
class PDFParseCapability:
    pdf_provider_registry: PDFProviderRegistry
    artifact_store: ArtifactStore
    preferred_provider: ProviderId | None = None

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return _descriptor(
            capability_id=PDF_PARSE_CAPABILITY_ID,
            name="pdf.parse.public",
            input_contract="ParseRequest",
            output_contract="ParseResult",
        )

    async def execute(
        self,
        request: ParseRequest,
        context: ExecutionContext,
    ) -> ParseResult:
        options = PDFParseOptions.from_public_options(
            profile=request.profile or request.processing_profile,
            page_selection=request.page_selection,
            options=request.options,
        )
        return await parse_pdf_public(
            request.source,
            options=options,
            artifact_store=self.artifact_store,
            pdf_provider_registry=self.pdf_provider_registry,
            preferred_provider=self.preferred_provider,
        )


@dataclass(slots=True)
class PDFProcessingCapability:
    parse_capability: PDFParseCapability

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return _descriptor(
            capability_id=PDF_PROCESS_CAPABILITY_ID,
            name="pdf.process.public",
            input_contract="ProcessingRequest",
            output_contract="ProcessingResult",
        )

    async def execute(
        self,
        request: ProcessingRequest,
        context: ExecutionContext,
    ) -> ProcessingResult:
        profile = _processing_profile(request.profile)
        parse_result = await self.parse_capability.execute(
            ParseRequest(
                source=request.source,
                profile=profile.value,
                options=request.options,
                correlation_id=request.correlation_id,
                tenant_id=request.tenant_id,
            ),
            context,
        )
        return ProcessingResult(
            job_id=JobId.new(),
            document_id=parse_result.document_id,
            status=_processing_status(parse_result.status),
            data={
                "format": parse_result.format,
                "profile": parse_result.profile,
                "summary": parse_result.summary,
                "page_count": parse_result.page_count,
                "statistics": parse_result.statistics,
                "fidelity_summary": parse_result.fidelity_summary,
                "editability_summary": parse_result.editability_summary,
                "limitations": list(parse_result.limitations),
                "artifact_reference": to_jsonable(parse_result.artifact_reference),
                "scene_artifact_reference": to_jsonable(
                    parse_result.scene_artifact_reference
                ),
            },
            artifacts=parse_result.artifacts,
            warnings=parse_result.warnings,
            errors=parse_result.errors,
        )


async def parse_pdf_public(
    source: DocumentSource,
    *,
    options: PDFParseOptions,
    artifact_store: ArtifactStore,
    pdf_provider_registry: PDFProviderRegistry,
    preferred_provider: ProviderId | None = None,
) -> ParseResult:
    document_id = _document_id_from_source(source)
    source_reference = _source_artifact_reference(source)
    provider = pdf_provider_registry.resolve(preferred_provider=preferred_provider)
    stored: list[ArtifactReference] = []

    async with await provider.open(
        source,
        PDFOpenOptions(
            password=options.password,
            timeout_seconds=options.timeout,
        ),
    ) as document:
        inspection = await _inspect_open_document(document, options)
        if options.persist_artifacts:
            stored.append(
                await _store_json_artifact(
                    artifact_store,
                    inspection,
                    artifact_kind="pdf_inspection",
                    producer="eixo.pdf.public.parse",
                    source=source,
                    document_id=document_id,
                )
            )
        if options.profile is PDFParseProfile.BASIC:
            result = _parse_result(
                document_id=document_id,
                profile=options.profile,
                inspection=inspection,
                artifacts=tuple(stored),
            )
            return await _with_stored_result(result, artifact_store, source, options)

        structure = await document.get_internal_structure(_structure_options(options))
        if options.profile is PDFParseProfile.FULL_FIDELITY and options.persist_artifacts:
            stored.append(
                await _store_json_artifact(
                    artifact_store,
                    structure,
                    artifact_kind="pdf_internal_structure",
                    producer="eixo.pdf.public.parse",
                    source=source,
                    document_id=document_id,
                )
            )
        typography = await document.get_typography(
            _typography_options(options),
            source_structure_artifact=structure,
        )
        text = await document.get_native_text(
            _text_options(options),
            typography_artifact=typography,
            source_structure_artifact=structure,
        )
        if options.persist_artifacts:
            stored.append(
                await _store_json_artifact(
                    artifact_store,
                    typography,
                    artifact_kind="pdf_typography",
                    producer="eixo.pdf.public.parse",
                    source=source,
                    document_id=document_id,
                )
            )
            stored.append(
                await _store_json_artifact(
                    artifact_store,
                    text,
                    artifact_kind="pdf_native_text",
                    producer="eixo.pdf.public.parse",
                    source=source,
                    document_id=document_id,
                )
            )
        if options.profile is PDFParseProfile.TEXTUAL:
            result = _parse_result(
                document_id=document_id,
                profile=options.profile,
                inspection=inspection,
                artifacts=tuple(stored),
                primary_artifact=stored[-1] if stored else None,
                statistics=to_jsonable(text.statistics),
                provenance=_provider_provenance(text.provenance),
            )
            return await _with_stored_result(result, artifact_store, source, options)

        images = await document.get_native_images(
            _image_options(options),
            source_structure_artifact=structure,
        )
        vectors = await document.get_native_vectors(
            _vector_options(options),
            source_structure_artifact=structure,
        )
        interactive = await document.get_native_interactive(
            _interactive_options(options),
            source_structure_artifact=structure,
        )
        page_scenes = PDFPageSceneBuilder().build(
            structure_artifact=structure,
            page_geometries=_page_geometries(inspection),
            text_artifact=text,
            image_artifact=images,
            vector_artifact=vectors,
            interactive_artifact=interactive,
            options=_scene_options(options),
        )
        native_scene = NativePDFSceneArtifactBuilder().build(
            page_scenes_artifact=page_scenes,
            structure_artifact=structure,
            inspection=inspection,
            typography_artifact=typography,
            text_artifact=text,
            image_artifact=images,
            vector_artifact=vectors,
            interactive_artifact=interactive,
            source_document_reference=source_reference,
            source_hash=source.metadata.get("content_hash"),
            processing_profile=options.profile.value,
            runtime="local",
        )
        scene_reference = None
        if options.persist_artifacts:
            stored.extend(
                [
                    await _store_json_artifact(
                        artifact_store,
                        images,
                        artifact_kind="pdf_native_images",
                        producer="eixo.pdf.public.parse",
                        source=source,
                        document_id=document_id,
                    ),
                    await _store_json_artifact(
                        artifact_store,
                        vectors,
                        artifact_kind="pdf_native_vectors",
                        producer="eixo.pdf.public.parse",
                        source=source,
                        document_id=document_id,
                    ),
                    await _store_json_artifact(
                        artifact_store,
                        interactive,
                        artifact_kind="pdf_interactive",
                        producer="eixo.pdf.public.parse",
                        source=source,
                        document_id=document_id,
                    ),
                    await _store_json_artifact(
                        artifact_store,
                        page_scenes,
                        artifact_kind="pdf_page_scenes",
                        producer="eixo.pdf.public.parse",
                        source=source,
                        document_id=document_id,
                    ),
                ]
            )
            scene_reference = await _store_json_artifact(
                artifact_store,
                native_scene,
                artifact_kind="native_pdf_scene",
                producer="eixo.pdf.public.parse",
                source=source,
                document_id=document_id,
            )
            stored.append(scene_reference)
        result = _parse_result(
            document_id=document_id,
            profile=options.profile,
            inspection=inspection,
            artifacts=tuple(stored),
            primary_artifact=scene_reference,
            scene_artifact=scene_reference,
            native_scene=native_scene,
            page_scenes=page_scenes,
        )
        return await _with_stored_result(result, artifact_store, source, options)


def _descriptor(
    *,
    capability_id: CapabilityId,
    name: str,
    input_contract: str,
    output_contract: str,
) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability_id=capability_id,
        name=name,
        description=name,
        version=CapabilityVersion("0.1.0"),
        input_contract=input_contract,
        output_contract=output_contract,
        supported_formats=("pdf",),
        supported_media_types=("application/pdf",),
        supports_cancellation=True,
        supports_progress=True,
        provider_id=PUBLIC_PDF_PROVIDER_ID,
        provider_version=ProviderVersion("0.1.0"),
        priority=200,
        metadata={
            "profiles": [item.value for item in PDFParseProfile],
            "artifact_policy": "summary_response_with_artifact_references",
        },
    )


async def _inspect_open_document(
    document: Any,
    options: PDFParseOptions,
) -> PDFTechnicalInspection:
    from eixo.pdf import DefaultPDFTechnicalInspector

    inspector = DefaultPDFTechnicalInspector(PDFProviderRegistry())
    return await inspector.inspect_document(
        document,
        PDFInspectionOptions(
            password=options.password,
            inspect_all_pages=True,
            inspect_resources=True,
            inspect_text=True,
            inspect_images=True,
            inspect_vectors=True,
            inspect_links=True,
            inspect_annotations=True,
            inspect_forms=True,
            inspect_layers=True,
            timeout_seconds=options.timeout,
        ),
    )


def _structure_options(options: PDFParseOptions) -> PDFInternalMappingOptions:
    full = options.profile is PDFParseProfile.FULL_FIDELITY
    return PDFInternalMappingOptions(
        include_indirect_objects=full,
        include_content_streams=full,
        include_content_operations=full,
        include_resources=True,
        include_unknown_resources=full,
        include_raw_dictionary_summaries=full,
        timeout_seconds=options.timeout,
    )


def _typography_options(options: PDFParseOptions) -> PDFTypographyOptions:
    return PDFTypographyOptions(
        include_font_programs=options.profile is PDFParseProfile.FULL_FIDELITY,
        include_glyph_mappings=True,
        include_text_styles=True,
        page_selection=options.page_indexes,
        timeout_seconds=options.timeout,
    )


def _text_options(options: PDFParseOptions) -> PDFNativeTextExtractionOptions:
    return PDFNativeTextExtractionOptions(
        include_glyphs=True,
        include_characters=True,
        include_words=True,
        include_native_lines=True,
        include_native_blocks=True,
        include_invisible_text=options.include_hidden_elements,
        preserve_raw_text=options.profile is PDFParseProfile.FULL_FIDELITY,
        page_selection=options.page_indexes,
        timeout_seconds=options.timeout,
    )


def _image_options(options: PDFParseOptions) -> PDFImageExtractionOptions:
    full = options.profile is PDFParseProfile.FULL_FIDELITY
    return PDFImageExtractionOptions(
        include_encoded_bytes=full,
        include_decoded_representation=full,
        generate_normalized_exports=full,
        include_invisible_images=options.include_hidden_elements,
        include_unused_resources=True,
        resolve_masks=True,
        page_selection=options.page_indexes,
        timeout_seconds=options.timeout,
    )


def _vector_options(options: PDFParseOptions) -> PDFNativeVectorOptions:
    return PDFNativeVectorOptions(
        include_invisible_vectors=options.include_hidden_elements,
        include_clipping_paths=True,
        resolve_graphics_state=True,
        page_selection=options.page_indexes,
        timeout_seconds=options.timeout,
    )


def _interactive_options(options: PDFParseOptions) -> PDFInteractiveExtractionOptions:
    return PDFInteractiveExtractionOptions(
        include_links=True,
        include_annotations=True,
        include_forms=True,
        include_layers=True,
        include_appearances=options.profile is PDFParseProfile.FULL_FIDELITY,
        page_selection=options.page_indexes,
        timeout_seconds=options.timeout,
    )


def _scene_options(options: PDFParseOptions) -> PDFPageSceneOptions:
    return PDFPageSceneOptions(
        page_selection=options.page_indexes,
        include_invisible_elements=options.include_hidden_elements,
        include_logical_interactive_elements=True,
        timeout_seconds=options.timeout,
    )


def _page_geometries(inspection: PDFTechnicalInspection) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for page in inspection.page_inspections:
        if page.canonical_geometry is not None:
            result[f"pdfpage:{page.page_index}"] = page.canonical_geometry
            result[f"pdf-page-{page.page_index}"] = page.canonical_geometry
    return result


def _inspection_result_from_pdf(
    source: DocumentSource,
    inspection: PDFTechnicalInspection,
    *,
    artifact_reference: ArtifactReference,
) -> InspectionResult:
    document_id = _document_id_from_source(source)
    return InspectionResult(
        document_id=document_id,
        detected_format="pdf",
        declared_media_type=source.declared_media_type,
        detected_media_type="application/pdf",
        size=source.size,
        status=ResultStatus.SUCCESS,
        metadata={
            "artifact_reference": to_jsonable(artifact_reference),
            "page_count": inspection.page_summary.total_pages,
            "pdf_version": inspection.version.interpreted_version
            or inspection.version.declared_version,
            "security": inspection.security.status.value,
            "features": {
                "text": inspection.feature_inventory.native_text.status.value,
                "images": inspection.feature_inventory.images.status.value,
                "vectors": inspection.feature_inventory.vectors.status.value,
                "forms": inspection.feature_inventory.forms.status.value,
            },
        },
        warnings=inspection.warnings,
    )


def _parse_result(
    *,
    document_id: DocumentId,
    profile: PDFParseProfile,
    inspection: PDFTechnicalInspection,
    artifacts: tuple[ArtifactReference, ...],
    primary_artifact: ArtifactReference | None = None,
    scene_artifact: ArtifactReference | None = None,
    native_scene: NativePDFSceneArtifact | None = None,
    page_scenes: PDFPageScenesArtifact | None = None,
    statistics: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
) -> ParseResult:
    warnings = inspection.warnings
    limitations = tuple(item.code for item in inspection.limitations)
    summary = {
        "pdf_version": inspection.version.interpreted_version
        or inspection.version.declared_version,
        "encrypted": inspection.security.status.value,
        "features": {
            "text": inspection.feature_inventory.native_text.status.value,
            "images": inspection.feature_inventory.images.status.value,
            "vectors": inspection.feature_inventory.vectors.status.value,
            "forms": inspection.feature_inventory.forms.status.value,
        },
    }
    if native_scene is not None:
        warnings = warnings + tuple(
            EixoWarning(
                code=item.code,
                message=item.message,
                scope=item.page_id or item.element_id or "pdf.native_scene",
            )
            for item in native_scene.warnings
        )
        limitations = limitations + tuple(item.code for item in native_scene.limitations)
    return ParseResult(
        document_id=document_id,
        status=ResultStatus.SUCCESS,
        format="pdf",
        profile=profile.value,
        artifact_reference=primary_artifact,
        scene_artifact_reference=scene_artifact,
        summary=summary,
        page_count=(
            page_scenes.statistics.page_count
            if page_scenes is not None
            else inspection.page_summary.total_pages
        ),
        statistics=statistics
        or (to_jsonable(native_scene.statistics) if native_scene is not None else {}),
        fidelity_summary=(
            to_jsonable(native_scene.fidelity_summary)
            if native_scene is not None
            else to_jsonable(inspection.fidelity_indicators)
        ),
        editability_summary=(
            to_jsonable(native_scene.editability_summary)
            if native_scene is not None
            else to_jsonable(inspection.editability_hints)
        ),
        limitations=tuple(dict.fromkeys(limitations)),
        provenance=provenance
        or (
            to_jsonable(native_scene.provenance)
            if native_scene is not None
            else _provider_provenance(inspection.provenance)
        ),
        artifacts=artifacts,
        warnings=warnings,
    )


async def _with_stored_result(
    result: ParseResult,
    artifact_store: ArtifactStore,
    source: DocumentSource,
    options: PDFParseOptions,
) -> ParseResult:
    if not options.persist_artifacts:
        return result
    reference = await _store_json_artifact(
        artifact_store,
        result,
        artifact_kind="parse_result",
        producer="eixo.pdf.public.parse",
        source=source,
        document_id=result.document_id,
        artifact_type=ArtifactType.RESULT,
    )
    return ParseResult(
        document_id=result.document_id,
        status=result.status,
        format=result.format,
        profile=result.profile,
        artifact_reference=result.artifact_reference or reference,
        scene_artifact_reference=result.scene_artifact_reference,
        summary=result.summary,
        page_count=result.page_count,
        statistics=result.statistics,
        fidelity_summary=result.fidelity_summary,
        editability_summary=result.editability_summary,
        limitations=result.limitations,
        provenance=result.provenance,
        artifacts=result.artifacts + (reference,),
        warnings=result.warnings,
        errors=result.errors,
        execution_metadata=result.execution_metadata,
    )


async def _store_json_artifact(
    artifact_store: ArtifactStore,
    value: Any,
    *,
    artifact_kind: str,
    producer: str,
    source: DocumentSource,
    document_id: DocumentId,
    artifact_type: ArtifactType = ArtifactType.DERIVED,
) -> ArtifactReference:
    payload = json.dumps(to_jsonable(value), sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    digest = hashlib.sha256(payload).hexdigest()
    return await artifact_store.put(
        ArtifactWriteRequest(
            stream=BytesIO(payload),
            artifact_type=artifact_type,
            content_hash=ContentHash("sha256", digest),
            size_bytes=len(payload),
            media_type="application/vnd.eixo+json",
            original_filename=source.filename,
            producer=producer,
            source=source.source_type,
            metadata={
                "artifact_kind": artifact_kind,
                "document_id": str(document_id),
                "source_artifact_id": source.metadata.get("artifact_id", ""),
                "profile": str(getattr(value, "profile", "")),
            },
        )
    )


def _source_artifact_reference(source: DocumentSource) -> ArtifactReference | None:
    artifact_id = source.metadata.get("artifact_id")
    if not artifact_id:
        return None
    return ArtifactReference(
        artifact_id=ArtifactId.parse(artifact_id),
        kind=ArtifactType.ORIGINAL_DOCUMENT.value,
        media_type="application/pdf",
        content_hash=(
            f"sha256:{source.metadata['content_hash']}"
            if source.metadata.get("content_hash")
            else None
        ),
        size_bytes=source.size,
        original_filename=source.filename,
    )


def _document_id_from_source(source: DocumentSource) -> DocumentId:
    value = source.metadata.get("document_id")
    return DocumentId.parse(value) if value else DocumentId.new()


def _provider_provenance(value: Any) -> dict[str, Any]:
    return to_jsonable(value) if value is not None else {}


def _processing_profile(value: str) -> PDFParseProfile:
    try:
        return PDFParseProfile.parse(value)
    except ValidationError:
        return PDFParseProfile.VISUAL


def _processing_status(status: ResultStatus) -> ProcessingStatus:
    if status is ResultStatus.FAILED:
        return ProcessingStatus.FAILED
    if status is ResultStatus.REVIEW_REQUIRED:
        return ProcessingStatus.REVIEW_REQUIRED
    return ProcessingStatus.COMPLETED


__all__ = [
    "PDFInspectionCapability",
    "PDFParseCapability",
    "PDFProcessingCapability",
    "public_pdf_provider_descriptor",
]
