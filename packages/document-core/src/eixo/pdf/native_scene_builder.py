from __future__ import annotations

from collections.abc import Iterable

from eixo.core import ArtifactReference, DocumentId, EixoWarning
from eixo.core.enums import Severity
from eixo.core.versions import ContractVersion, SchemaVersion
from eixo.pdf.images import PDFNativeImageArtifact
from eixo.pdf.inspection import PDFInspectionState, PDFTechnicalInspection
from eixo.pdf.interactive import PDFInteractiveArtifact
from eixo.pdf.models import ProviderLimitation
from eixo.pdf.native_scene import (
    NativePDFSceneArtifact,
    NativePDFScenePageSummary,
    NativePDFSceneProvenance,
    NativePDFSceneSourceArtifactReference,
    NativePDFSceneStatistics,
    PDFArtifactLimitation,
    PDFArtifactLimitationCategory,
    PDFConsolidatedWarning,
    PDFEditabilitySummary,
    PDFFidelityDimension,
    PDFFidelitySummary,
    PDFNativeSceneEditabilityStatus,
    editability_counts,
    fidelity_counts,
    native_pdf_scene_artifact_id,
)
from eixo.pdf.native_text import PDFNativeTextArtifact
from eixo.pdf.scene import PDFPageScenesArtifact, PDFSceneEditabilityHint, PDFSceneFidelity
from eixo.pdf.structure import PDFInternalStructureArtifact
from eixo.pdf.typography import PDFTypographyArtifact, PDFFontEmbeddedStatus
from eixo.pdf.vectors import PDFNativeVectorArtifact


class NativePDFSceneArtifactBuilder:
    def build(
        self,
        *,
        page_scenes_artifact: PDFPageScenesArtifact,
        structure_artifact: PDFInternalStructureArtifact,
        inspection: PDFTechnicalInspection | None = None,
        typography_artifact: PDFTypographyArtifact | None = None,
        text_artifact: PDFNativeTextArtifact | None = None,
        image_artifact: PDFNativeImageArtifact | None = None,
        vector_artifact: PDFNativeVectorArtifact | None = None,
        interactive_artifact: PDFInteractiveArtifact | None = None,
        source_document_reference: ArtifactReference | None = None,
        source_hash: str | None = None,
        processing_profile: str | None = None,
        runtime: str | None = None,
        job_id: str | None = None,
    ) -> NativePDFSceneArtifact:
        source_hash_value = source_hash or _source_hash(
            source_document_reference,
            inspection,
            structure_artifact,
        )
        compatibility_warnings = _compatibility_warnings(
            structure_artifact.document_id,
            source_hash_value,
            inspection,
            typography_artifact,
            text_artifact,
            image_artifact,
            vector_artifact,
            interactive_artifact,
            page_scenes_artifact,
        )
        source_artifacts = _source_artifacts(
            inspection,
            structure_artifact,
            typography_artifact,
            text_artifact,
            image_artifact,
            vector_artifact,
            interactive_artifact,
            page_scenes_artifact,
        )
        provider_summary = _provider_summary(source_artifacts)
        limitations = _limitations(
            inspection,
            structure_artifact,
            typography_artifact,
            text_artifact,
            image_artifact,
            vector_artifact,
            interactive_artifact,
            page_scenes_artifact,
        )
        warnings = _warnings(
            compatibility_warnings,
            inspection,
            structure_artifact,
            typography_artifact,
            text_artifact,
            image_artifact,
            vector_artifact,
            interactive_artifact,
            page_scenes_artifact,
        )
        pages = tuple(
            _page_summary(scene)
            for scene in sorted(
                page_scenes_artifact.pages,
                key=lambda page: (page.page_index, page.page_id),
            )
        )
        fidelity_summary = _fidelity_summary(
            page_scenes_artifact,
            inspection,
            typography_artifact,
            text_artifact,
            image_artifact,
            vector_artifact,
            interactive_artifact,
            limitations,
        )
        editability_summary = _editability_summary(page_scenes_artifact)
        statistics = _statistics(
            pages,
            page_scenes_artifact,
            image_artifact,
            vector_artifact,
            interactive_artifact,
            warnings,
            limitations,
            fidelity_summary,
        )
        provenance = NativePDFSceneProvenance(
            provider=provider_summary[0] if provider_summary else None,
            provider_version=_provider_version(source_artifacts),
            artifact_versions={
                item.source_artifact_type: str(item.artifact_version)
                for item in source_artifacts
                if item.artifact_version is not None
            },
            input_document=source_document_reference.artifact_id.value
            if source_document_reference
            else None,
            input_hash=source_hash_value,
            configurations={
                "processing_profile": processing_profile
                or "native_pdf_scene_consolidation"
            },
            processing_profile=processing_profile,
            job_id=job_id,
            runtime=runtime,
            source_artifacts=source_artifacts,
            transformations=("artifact_consolidation",),
        )
        return NativePDFSceneArtifact(
            artifact_id=native_pdf_scene_artifact_id(
                structure_artifact.document_id,
                source_hash_value,
            ),
            artifact_type="native_pdf_scene",
            artifact_version=ContractVersion("1.0.0"),
            schema_version=SchemaVersion("1.0.0"),
            document_id=structure_artifact.document_id,
            source_document_reference=source_document_reference,
            source_hash=source_hash_value,
            provider_summary=provider_summary,
            inspection=inspection,
            resource_catalog_reference="PDFInternalStructureArtifact.resource_catalog",
            page_scene_references=tuple(page.scene_reference for page in pages),
            pages=pages,
            scenes=page_scenes_artifact.pages,
            font_catalog_reference="PDFTypographyArtifact.font_catalog"
            if typography_artifact is not None
            else None,
            text_artifact_reference=_source_by_type(source_artifacts, "PDFNativeTextArtifact"),
            image_artifact_reference=_source_by_type(source_artifacts, "PDFNativeImageArtifact"),
            vector_artifact_reference=_source_by_type(source_artifacts, "PDFNativeVectorArtifact"),
            interactive_artifact_reference=_source_by_type(
                source_artifacts,
                "PDFInteractiveArtifact",
            ),
            source_artifacts=source_artifacts,
            fidelity_summary=fidelity_summary,
            editability_summary=editability_summary,
            statistics=statistics,
            warnings=warnings,
            limitations=limitations,
            provenance=provenance,
        )


def _source_hash(
    reference: ArtifactReference | None,
    inspection: PDFTechnicalInspection | None,
    structure_artifact: PDFInternalStructureArtifact,
) -> str | None:
    if reference is not None and reference.content_hash:
        return reference.content_hash
    if inspection is not None:
        identity_hash = inspection.source.content_hash
        if identity_hash is not None:
            return identity_hash
    source_artifact = structure_artifact.source_artifact
    return source_artifact.content_hash if source_artifact is not None else None


def _source_artifacts(
    inspection: PDFTechnicalInspection | None,
    *artifacts: object | None,
) -> tuple[NativePDFSceneSourceArtifactReference, ...]:
    references: list[NativePDFSceneSourceArtifactReference] = []
    if inspection is not None:
        references.append(
            NativePDFSceneSourceArtifactReference(
                source_artifact_id="PDFTechnicalInspection",
                source_artifact_type="PDFTechnicalInspection",
                schema_version=SchemaVersion(str(inspection.schema_version)),
                provider=str(inspection.provider.provider_id),
                provider_version=str(inspection.provider.provider_version),
                content_hash=inspection.source.content_hash,
            )
        )
    for artifact in artifacts:
        if artifact is None:
            continue
        artifact_type = artifact.__class__.__name__
        provider = getattr(artifact, "provider", None)
        version = getattr(artifact, "artifact_version", None)
        references.append(
            NativePDFSceneSourceArtifactReference(
                source_artifact_id=artifact_type,
                source_artifact_type=artifact_type,
                artifact_version=version if isinstance(version, ContractVersion) else None,
                provider=str(provider.provider_id) if provider is not None else None,
                provider_version=str(provider.provider_version)
                if provider is not None
                else None,
            )
        )
    return tuple(references)


def _compatibility_warnings(
    document_id: DocumentId | None,
    source_hash: str | None,
    *artifacts: object | None,
) -> tuple[EixoWarning, ...]:
    warnings: list[EixoWarning] = []
    for artifact in artifacts:
        if artifact is None:
            continue
        artifact_document_id = getattr(artifact, "document_id", None)
        if (
            document_id is not None
            and artifact_document_id is not None
            and artifact_document_id != document_id
        ):
            warnings.append(
                EixoWarning(
                    code="native_scene_document_mismatch",
                    message="Source artifact document_id differs from the root artifact.",
                    severity=Severity.ERROR,
                    scope=artifact.__class__.__name__,
                )
            )
        artifact_hash = getattr(artifact, "source_hash", None)
        if source_hash is not None and artifact_hash not in {None, source_hash}:
            warnings.append(
                EixoWarning(
                    code="native_scene_source_hash_mismatch",
                    message="Source artifact hash differs from the root artifact.",
                    severity=Severity.ERROR,
                    scope=artifact.__class__.__name__,
                )
            )
    if not getattr(artifacts[-1], "pages", ()):
        warnings.append(
            EixoWarning(
                code="native_scene_source_missing",
                message="No page scenes were available for consolidation.",
                severity=Severity.ERROR,
                scope="PDFPageScenesArtifact",
            )
        )
    return tuple(warnings)


def _warnings(
    compatibility: tuple[EixoWarning, ...],
    *artifacts: object | None,
) -> tuple[PDFConsolidatedWarning, ...]:
    raw: list[tuple[str, EixoWarning, str | None]] = []
    raw.extend(("compatibility", warning, None) for warning in compatibility)
    for artifact in artifacts:
        if artifact is None:
            continue
        source = artifact.__class__.__name__
        for warning in getattr(artifact, "warnings", ()):
            raw.append((source, warning, _provider_id(artifact)))
        for page in getattr(artifact, "pages", ()):
            for warning in getattr(page, "warnings", ()):
                raw.append((source, warning, _provider_id(artifact)))
    result: list[PDFConsolidatedWarning] = []
    seen: set[tuple[str, str | None, str | None]] = set()
    for source, warning, provider in sorted(
        raw,
        key=lambda item: (
            item[0],
            item[1].code,
            item[1].scope or "",
            item[1].message,
        ),
    ):
        key = (warning.code, warning.scope, source)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            PDFConsolidatedWarning(
                warning_id=f"pdfwarning:{_slug(source)}:{_slug(warning.code)}:{len(result)}",
                code=warning.code,
                severity=warning.severity.value,
                message=warning.message,
                page_id=warning.scope if warning.scope and "page" in warning.scope else None,
                source_artifact_id=source,
                provider=provider,
                details={str(k): str(v) for k, v in warning.details.items()},
            )
        )
    return tuple(result)


def _limitations(*artifacts: object | None) -> tuple[PDFArtifactLimitation, ...]:
    result: list[PDFArtifactLimitation] = []
    seen: set[tuple[str, str | None, str | None]] = set()
    for artifact in artifacts:
        if artifact is None:
            continue
        source = artifact.__class__.__name__
        for limitation in getattr(artifact, "limitations", ()):
            item = _limitation(limitation, source)
            key = (item.code, item.scope, item.source)
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
    return tuple(sorted(result, key=lambda item: (item.source or "", item.code)))


def _limitation(
    limitation: ProviderLimitation,
    source: str,
) -> PDFArtifactLimitation:
    return PDFArtifactLimitation(
        code=limitation.code,
        category=_limitation_category(limitation),
        scope=limitation.scope,
        description=limitation.message,
        impact=_limitation_impact(limitation),
        fallback="Preserve references and continue with partial fidelity.",
        source=source,
    )


def _limitation_category(limitation: ProviderLimitation) -> PDFArtifactLimitationCategory:
    haystack = f"{limitation.code} {limitation.scope or ''}".lower()
    if "font" in haystack:
        return PDFArtifactLimitationCategory.FONT_LIMITATION
    if "image" in haystack or "mask" in haystack:
        return PDFArtifactLimitationCategory.IMAGE_LIMITATION
    if "vector" in haystack or "graphics" in haystack or "clip" in haystack:
        return PDFArtifactLimitationCategory.VECTOR_LIMITATION
    if "interactive" in haystack or "annotation" in haystack or "form" in haystack:
        return PDFArtifactLimitationCategory.INTERACTION_LIMITATION
    if "security" in haystack or "password" in haystack or "encrypted" in haystack:
        return PDFArtifactLimitationCategory.SECURITY_LIMITATION
    if "order" in haystack:
        return PDFArtifactLimitationCategory.PAINT_ORDER_LIMITATION
    if "resource" in haystack:
        return PDFArtifactLimitationCategory.UNRESOLVED_RESOURCE
    if "partial" in haystack:
        return PDFArtifactLimitationCategory.PARTIAL_EXTRACTION
    if "unsupported" in haystack:
        return PDFArtifactLimitationCategory.UNSUPPORTED_FEATURE
    return PDFArtifactLimitationCategory.PROVIDER_LIMITATION


def _limitation_impact(limitation: ProviderLimitation) -> str:
    if limitation.scope:
        return f"May reduce fidelity for {limitation.scope}."
    return "May reduce native PDF scene fidelity."


def _page_summary(scene) -> NativePDFScenePageSummary:
    fidelity = _dominant_fidelity(element.fidelity for element in scene.elements)
    editability = _dominant_editability(
        _editability_status(element.editability_hint) for element in scene.elements
    )
    return NativePDFScenePageSummary(
        page_id=scene.page_id,
        page_index=scene.page_index,
        scene_reference=scene.scene_id,
        element_count=scene.statistics.element_count,
        text_count=scene.statistics.text_element_count,
        image_count=scene.statistics.image_element_count,
        vector_count=scene.statistics.vector_element_count,
        interactive_count=(
            scene.statistics.link_count
            + scene.statistics.annotation_count
            + scene.statistics.form_widget_count
        ),
        warning_count=len(scene.warnings),
        fidelity=fidelity,
        editability=editability,
    )


def _fidelity_summary(
    scenes_artifact: PDFPageScenesArtifact,
    inspection: PDFTechnicalInspection | None,
    typography: PDFTypographyArtifact | None,
    text: PDFNativeTextArtifact | None,
    images: PDFNativeImageArtifact | None,
    vectors: PDFNativeVectorArtifact | None,
    interactive: PDFInteractiveArtifact | None,
    limitations: tuple[PDFArtifactLimitation, ...],
) -> PDFFidelitySummary:
    counts = fidelity_counts(scenes_artifact.pages)
    dimensions = (
        _dimension("geometry", _geometry_level(scenes_artifact)),
        _dimension("text", _level_present(text, "text artifact available")),
        _dimension("font", _font_level(typography)),
        _dimension("image", _level_present(images, "image artifact available")),
        _dimension("vector", _level_present(vectors, "vector artifact available")),
        _dimension("interaction", _interaction_level(interactive)),
        _dimension("paint_order", _paint_order_level(scenes_artifact)),
        _dimension("resource", _resource_level(typography, images, vectors)),
    )
    if inspection is not None:
        dimensions += (
            _dimension(
                "inspection",
                _inspection_level(inspection.fidelity_indicators.geometry_fidelity),
            ),
        )
    overall = _dominant_fidelity(tuple(item.level for item in dimensions))
    return PDFFidelitySummary(
        overall_level=overall,
        dimensions=dimensions,
        exact_element_count=counts[PDFSceneFidelity.NATIVE_EXACT],
        normalized_element_count=counts[PDFSceneFidelity.NATIVE_NORMALIZED],
        reconstructed_element_count=counts[PDFSceneFidelity.PROVIDER_RECONSTRUCTED],
        heuristic_element_count=counts[PDFSceneFidelity.HEURISTIC],
        raster_only_element_count=counts[PDFSceneFidelity.RASTER_ONLY],
        unsupported_element_count=counts[PDFSceneFidelity.UNSUPPORTED],
        unknown_element_count=counts[PDFSceneFidelity.UNKNOWN],
        critical_limitations=tuple(
            item.code
            for item in limitations
            if item.category
            in {
                PDFArtifactLimitationCategory.SECURITY_LIMITATION,
                PDFArtifactLimitationCategory.UNSUPPORTED_FEATURE,
            }
        ),
    )


def _dimension(name: str, level: PDFSceneFidelity) -> PDFFidelityDimension:
    return PDFFidelityDimension(
        dimension=name,
        level=level,
        method="derived_from_source_artifacts",
        reasons=(f"{name} fidelity consolidated from available artifacts.",),
    )


def _editability_summary(scenes_artifact: PDFPageScenesArtifact) -> PDFEditabilitySummary:
    counts = editability_counts(scenes_artifact.pages)
    text_status = _status_for_element_prefix(scenes_artifact, "text_")
    image_status = _status_for_type(scenes_artifact, "image")
    vector_status = _status_for_type(scenes_artifact, "vector")
    form_status = _status_for_type(scenes_artifact, "form_widget")
    overall = _dominant_editability(
        (text_status, image_status, vector_status, form_status)
    )
    return PDFEditabilitySummary(
        overall_status=overall,
        text_status=text_status,
        image_status=image_status,
        vector_status=vector_status,
        form_status=form_status,
        native_editable_count=counts[PDFSceneEditabilityHint.NATIVE_EDITABLE],
        partially_editable_count=counts[PDFSceneEditabilityHint.PARTIALLY_EDITABLE],
        reconstruction_required_count=counts[
            PDFSceneEditabilityHint.RECONSTRUCTION_REQUIRED
        ],
        raster_only_count=counts[PDFSceneEditabilityHint.RASTER_ONLY],
        unknown_count=counts[PDFSceneEditabilityHint.UNKNOWN],
        reasons=("Editability is a preliminary technical hint, not an editor guarantee.",),
    )


def _statistics(
    pages: tuple[NativePDFScenePageSummary, ...],
    scenes_artifact: PDFPageScenesArtifact,
    images: PDFNativeImageArtifact | None,
    vectors: PDFNativeVectorArtifact | None,
    interactive: PDFInteractiveArtifact | None,
    warnings: tuple[PDFConsolidatedWarning, ...],
    limitations: tuple[PDFArtifactLimitation, ...],
    fidelity: PDFFidelitySummary,
) -> NativePDFSceneStatistics:
    image_stats = images.statistics if images is not None else None
    vector_stats = vectors.statistics if vectors is not None else None
    interactive_stats = interactive.statistics if interactive is not None else None
    return NativePDFSceneStatistics(
        page_count=len(pages),
        scene_count=len(scenes_artifact.pages),
        element_count=sum(page.element_count for page in pages),
        text_element_count=sum(page.text_count for page in pages),
        image_resource_count=_image_resource_count(images, image_stats),
        image_occurrence_count=_image_occurrence_count(images, image_stats),
        vector_element_count=_vector_count(vectors, vector_stats),
        clipping_path_count=_clip_count(vectors, vector_stats),
        link_count=_link_count(interactive, interactive_stats),
        annotation_count=_annotation_count(interactive, interactive_stats),
        form_field_count=_field_count(interactive, interactive_stats),
        widget_count=_widget_count(interactive, interactive_stats),
        layer_count=_layer_count(interactive, interactive_stats),
        warning_count=len(warnings),
        limitation_count=len(limitations),
        unresolved_reference_count=scenes_artifact.statistics.unresolved_reference_count,
        native_exact_count=fidelity.exact_element_count,
        native_normalized_count=fidelity.normalized_element_count,
        provider_reconstructed_count=fidelity.reconstructed_element_count,
        heuristic_count=fidelity.heuristic_element_count,
        raster_only_count=fidelity.raster_only_element_count,
        unsupported_count=fidelity.unsupported_element_count,
    )


def _image_resource_count(images, image_stats) -> int:
    if images is None:
        return 0
    return image_stats.image_resource_count or len(images.image_catalog.resources)


def _image_occurrence_count(images, image_stats) -> int:
    if images is None:
        return 0
    return image_stats.image_occurrence_count or len(images.image_catalog.occurrences)


def _vector_count(vectors, vector_stats) -> int:
    if vectors is None:
        return 0
    return vector_stats.vector_path_count or len(vectors.vector_paths)


def _clip_count(vectors, vector_stats) -> int:
    if vectors is None:
        return 0
    return vector_stats.clipping_path_count or len(vectors.clipping_paths)


def _link_count(interactive, interactive_stats) -> int:
    if interactive is None:
        return 0
    return interactive_stats.link_count or len(interactive.links)


def _annotation_count(interactive, interactive_stats) -> int:
    if interactive is None:
        return 0
    return interactive_stats.annotation_count or len(interactive.annotations)


def _field_count(interactive, interactive_stats) -> int:
    if interactive is None:
        return 0
    return interactive_stats.form_field_count or len(interactive.fields)


def _widget_count(interactive, interactive_stats) -> int:
    if interactive is None:
        return 0
    return interactive_stats.widget_count or len(interactive.widgets)


def _layer_count(interactive, interactive_stats) -> int:
    if interactive is None:
        return 0
    return interactive_stats.layer_count or len(interactive.layers)


def _geometry_level(scenes_artifact: PDFPageScenesArtifact) -> PDFSceneFidelity:
    if not scenes_artifact.pages:
        return PDFSceneFidelity.UNKNOWN
    if all(scene.geometry is not None for scene in scenes_artifact.pages):
        return PDFSceneFidelity.NATIVE_NORMALIZED
    return PDFSceneFidelity.UNKNOWN


def _font_level(typography: PDFTypographyArtifact | None) -> PDFSceneFidelity:
    if typography is None:
        return PDFSceneFidelity.UNKNOWN
    if typography.font_catalog.unresolved_fonts:
        return PDFSceneFidelity.PROVIDER_RECONSTRUCTED
    if any(
        font.embedded == PDFFontEmbeddedStatus.EXTRACTION_UNAVAILABLE
        for font in typography.font_catalog.fonts
    ):
        return PDFSceneFidelity.PROVIDER_RECONSTRUCTED
    return PDFSceneFidelity.NATIVE_NORMALIZED


def _interaction_level(interactive: PDFInteractiveArtifact | None) -> PDFSceneFidelity:
    if interactive is None:
        return PDFSceneFidelity.UNKNOWN
    if interactive.limitations:
        return PDFSceneFidelity.PROVIDER_RECONSTRUCTED
    return PDFSceneFidelity.NATIVE_NORMALIZED


def _paint_order_level(scenes_artifact: PDFPageScenesArtifact) -> PDFSceneFidelity:
    unordered = sum(page.statistics.unordered_element_count for page in scenes_artifact.pages)
    if unordered == 0:
        return PDFSceneFidelity.NATIVE_NORMALIZED
    if unordered < sum(page.statistics.element_count for page in scenes_artifact.pages):
        return PDFSceneFidelity.EIXO_DERIVED
    return PDFSceneFidelity.UNKNOWN


def _resource_level(
    typography: PDFTypographyArtifact | None,
    images: PDFNativeImageArtifact | None,
    vectors: PDFNativeVectorArtifact | None,
) -> PDFSceneFidelity:
    if any(item is not None for item in (typography, images, vectors)):
        return PDFSceneFidelity.NATIVE_NORMALIZED
    return PDFSceneFidelity.UNKNOWN


def _level_present(artifact: object | None, _reason: str) -> PDFSceneFidelity:
    return PDFSceneFidelity.NATIVE_NORMALIZED if artifact is not None else PDFSceneFidelity.UNKNOWN


def _inspection_level(state: PDFInspectionState) -> PDFSceneFidelity:
    if state == PDFInspectionState.PRESENT:
        return PDFSceneFidelity.NATIVE_NORMALIZED
    if state == PDFInspectionState.PARTIAL:
        return PDFSceneFidelity.PROVIDER_RECONSTRUCTED
    if state == PDFInspectionState.UNSUPPORTED:
        return PDFSceneFidelity.UNSUPPORTED
    return PDFSceneFidelity.UNKNOWN


def _dominant_fidelity(levels: Iterable[PDFSceneFidelity]) -> PDFSceneFidelity:
    priority = {
        PDFSceneFidelity.UNSUPPORTED: 0,
        PDFSceneFidelity.UNKNOWN: 1,
        PDFSceneFidelity.RASTER_ONLY: 2,
        PDFSceneFidelity.HEURISTIC: 3,
        PDFSceneFidelity.PROVIDER_RECONSTRUCTED: 4,
        PDFSceneFidelity.EIXO_DERIVED: 5,
        PDFSceneFidelity.NATIVE_NORMALIZED: 6,
        PDFSceneFidelity.NATIVE_EXACT: 7,
    }
    values = tuple(levels)
    if not values:
        return PDFSceneFidelity.UNKNOWN
    return min(values, key=lambda level: priority[level])


def _status_for_element_prefix(
    scenes_artifact: PDFPageScenesArtifact,
    prefix: str,
) -> PDFNativeSceneEditabilityStatus:
    statuses = (
        _editability_status(element.editability_hint)
        for scene in scenes_artifact.pages
        for element in scene.elements
        if element.element_type.value.startswith(prefix)
    )
    return _dominant_editability(statuses)


def _status_for_type(
    scenes_artifact: PDFPageScenesArtifact,
    value: str,
) -> PDFNativeSceneEditabilityStatus:
    statuses = (
        _editability_status(element.editability_hint)
        for scene in scenes_artifact.pages
        for element in scene.elements
        if element.element_type.value == value
    )
    return _dominant_editability(statuses)


def _editability_status(
    hint: PDFSceneEditabilityHint,
) -> PDFNativeSceneEditabilityStatus:
    mapping = {
        PDFSceneEditabilityHint.NATIVE_EDITABLE: (
            PDFNativeSceneEditabilityStatus.NATIVE_EDITABLE
        ),
        PDFSceneEditabilityHint.PARTIALLY_EDITABLE: (
            PDFNativeSceneEditabilityStatus.PARTIALLY_EDITABLE
        ),
        PDFSceneEditabilityHint.RECONSTRUCTION_REQUIRED: (
            PDFNativeSceneEditabilityStatus.RECONSTRUCTION_REQUIRED
        ),
        PDFSceneEditabilityHint.RASTER_ONLY: PDFNativeSceneEditabilityStatus.RASTER_ONLY,
        PDFSceneEditabilityHint.UNKNOWN: PDFNativeSceneEditabilityStatus.UNKNOWN,
    }
    return mapping[hint]


def _dominant_editability(
    statuses: Iterable[PDFNativeSceneEditabilityStatus],
) -> PDFNativeSceneEditabilityStatus:
    priority = {
        PDFNativeSceneEditabilityStatus.NOT_EDITABLE: 0,
        PDFNativeSceneEditabilityStatus.UNKNOWN: 1,
        PDFNativeSceneEditabilityStatus.RASTER_ONLY: 2,
        PDFNativeSceneEditabilityStatus.RECONSTRUCTION_REQUIRED: 3,
        PDFNativeSceneEditabilityStatus.PARTIALLY_EDITABLE: 4,
        PDFNativeSceneEditabilityStatus.NATIVE_EDITABLE: 5,
    }
    values = tuple(statuses)
    if not values:
        return PDFNativeSceneEditabilityStatus.UNKNOWN
    return min(values, key=lambda status: priority[status])


def _provider_summary(
    source_artifacts: tuple[NativePDFSceneSourceArtifactReference, ...],
) -> tuple[str, ...]:
    return tuple(
        sorted({item.provider for item in source_artifacts if item.provider is not None})
    )


def _provider_version(
    source_artifacts: tuple[NativePDFSceneSourceArtifactReference, ...],
) -> str | None:
    versions = tuple(
        sorted(
            {
                item.provider_version
                for item in source_artifacts
                if item.provider_version is not None
            }
        )
    )
    return versions[0] if len(versions) == 1 else None


def _source_by_type(
    source_artifacts: tuple[NativePDFSceneSourceArtifactReference, ...],
    artifact_type: str,
) -> NativePDFSceneSourceArtifactReference | None:
    return next(
        (item for item in source_artifacts if item.source_artifact_type == artifact_type),
        None,
    )


def _provider_id(artifact: object) -> str | None:
    provider = getattr(artifact, "provider", None)
    return str(provider.provider_id) if provider is not None else None


def _slug(value: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    return "-".join(part for part in safe.split("-") if part) or "unknown"


__all__ = ["NativePDFSceneArtifactBuilder"]
