from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Awaitable

from eixo.core import (
    CorruptedPDFError,
    DocumentSource,
    EixoWarning,
    InvalidPDFPasswordError,
    PDFPasswordRequiredError,
    ProviderId,
)
from eixo.core.versions import ContractVersion
from eixo.pdf.contracts import PDFDocumentHandle, PDFProvider
from eixo.pdf.inspection import (
    PDFEditabilityHints,
    PDFFeatureInventory,
    PDFFeatureSignal,
    PDFFidelityIndicators,
    PDFInspectionCoverage,
    PDFInspectionEvidence,
    PDFInspectionOptions,
    PDFInspectionState,
    PDFInspectionTimings,
    PDFIntegrityInspection,
    PDFIntegrityStatus,
    PDFMetadataInspection,
    PDFMetadataValue,
    PDFPageInspection,
    PDFPageSummary,
    PDFPageTechnicalHints,
    PDFPermissionStatus,
    PDFPermissionsInspection,
    PDFResourceSummary,
    PDFSamplingStrategy,
    PDFSecurityInspection,
    PDFSecurityStatus,
    PDFTechnicalInspection,
    PDFTechnicalProfile,
    PDFTechnicalProfileInspection,
    PDFVersionInspection,
    source_identity,
    unsupported_signal,
)
from eixo.pdf.models import (
    PDFBasicInfo,
    PDFEncryptionState,
    PDFOpenOptions,
    PDFProbeOptions,
    PDFProbeResult,
    PDFProbeStatus,
    PDFProviderProvenance,
    PDFProviderDescriptor,
    PDFSupportLevel,
    ProviderLimitation,
)
from eixo.pdf.registry import PDFProviderRegistry

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DefaultPDFTechnicalInspector:
    provider_registry: PDFProviderRegistry

    async def inspect(
        self,
        source: DocumentSource,
        options: PDFInspectionOptions | None = None,
    ) -> PDFTechnicalInspection:
        opts = options or PDFInspectionOptions()
        provider = self.provider_registry.resolve(
            preferred_provider=opts.preferred_provider,
            required_capabilities=("supports_basic_info",),
        )
        return await self._inspect_with_provider(provider, source, opts)

    async def inspect_document(
        self,
        document: PDFDocumentHandle,
        options: PDFInspectionOptions | None = None,
    ) -> PDFTechnicalInspection:
        opts = options or PDFInspectionOptions()
        descriptor = _descriptor_from_document(document)
        started = time.perf_counter()
        info = await document.get_basic_info()
        pages_started = time.perf_counter()
        page_inspections = await _inspect_pages(document, info.page_count, opts)
        page_seconds = time.perf_counter() - pages_started
        return _build_inspection(
            source=document.source,
            provider=descriptor_provider(descriptor),
            descriptor=descriptor,
            probe=None,
            info=info,
            options=opts,
            page_inspections=page_inspections,
            timings=PDFInspectionTimings(
                page_inspection_seconds=page_seconds,
                total_seconds=time.perf_counter() - started,
            ),
        )

    async def _inspect_with_provider(
        self,
        provider: PDFProvider,
        source: DocumentSource,
        options: PDFInspectionOptions,
    ) -> PDFTechnicalInspection:
        started = time.perf_counter()
        _log("pdf.inspection.started")
        probe_started = time.perf_counter()
        probe = await provider.probe(source, _probe_options(options))
        probe_seconds = time.perf_counter() - probe_started
        if not probe.supported or probe.status == PDFProbeStatus.NOT_PDF:
            return _probe_only_inspection(
                source=source,
                provider=provider,
                probe=probe,
                options=options,
                timings=PDFInspectionTimings(
                    probe_seconds=probe_seconds,
                    total_seconds=time.perf_counter() - started,
                ),
            )
        if probe.encryption_state in {
            PDFEncryptionState.PASSWORD_REQUIRED,
            PDFEncryptionState.INVALID_PASSWORD,
        } and options.password is None:
            return _probe_only_inspection(
                source=source,
                provider=provider,
                probe=probe,
                options=options,
                timings=PDFInspectionTimings(
                    probe_seconds=probe_seconds,
                    total_seconds=time.perf_counter() - started,
                ),
            )
        open_started = time.perf_counter()
        try:
            document = await provider.open(source, _open_options(options))
        except (PDFPasswordRequiredError, InvalidPDFPasswordError, CorruptedPDFError) as exc:
            return _failed_open_inspection(
                source=source,
                provider=provider,
                probe=probe,
                error=exc,
                options=options,
                timings=PDFInspectionTimings(
                    probe_seconds=probe_seconds,
                    open_seconds=time.perf_counter() - open_started,
                    total_seconds=time.perf_counter() - started,
                ),
            )
        open_seconds = time.perf_counter() - open_started
        try:
            async with document:
                info = await document.get_basic_info()
                pages_started = time.perf_counter()
                page_inspections = await _inspect_pages(document, info.page_count, options)
                page_seconds = time.perf_counter() - pages_started
                return _build_inspection(
                    source=source,
                    provider=provider,
                    descriptor=provider.descriptor,
                    probe=probe,
                    info=info,
                    options=options,
                    page_inspections=page_inspections,
                    timings=PDFInspectionTimings(
                        probe_seconds=probe_seconds,
                        open_seconds=open_seconds,
                        page_inspection_seconds=page_seconds,
                        total_seconds=time.perf_counter() - started,
                    ),
                )
        finally:
            _log("pdf.inspection.completed")


async def _inspect_pages(
    document: PDFDocumentHandle,
    total_pages: int,
    options: PDFInspectionOptions,
) -> tuple[PDFPageInspection, ...]:
    indexes = _sample_page_indexes(total_pages, options)
    pages: list[PDFPageInspection] = []
    for index in indexes:
        page = await document.get_page(index)
        geometry = await page.get_basic_geometry()
        hints = await _page_hints(page)
        pages.append(
            PDFPageInspection(
                page_index=index,
                page_number=index + 1,
                width=geometry.width,
                height=geometry.height,
                rotation=geometry.rotation,
                media_box=geometry.media_box,
                crop_box=geometry.crop_box,
                canonical_geometry=geometry.canonical_geometry,
                has_text=_option_state(options.inspect_text, hints.has_text),
                has_images=_option_state(options.inspect_images, hints.has_images),
                has_vectors=_option_state(options.inspect_vectors, hints.has_vectors),
                has_links=_option_state(options.inspect_links, hints.has_links),
                has_annotations=_option_state(
                    options.inspect_annotations,
                    hints.has_annotations,
                ),
                has_forms=_option_state(options.inspect_forms, hints.has_forms),
                has_layers=_option_state(options.inspect_layers, PDFInspectionState.UNSUPPORTED),
                approximate_resource_count=_resource_count(hints),
                provenance=geometry.provenance,
            )
        )
    return tuple(pages)


async def _page_hints(page: object) -> PDFPageTechnicalHints:
    getter = getattr(page, "get_technical_hints", None)
    if getter is None:
        return PDFPageTechnicalHints(
            has_text=PDFInspectionState.UNSUPPORTED,
            has_images=PDFInspectionState.UNSUPPORTED,
            has_vectors=PDFInspectionState.UNSUPPORTED,
            has_links=PDFInspectionState.UNSUPPORTED,
            has_annotations=PDFInspectionState.UNSUPPORTED,
            has_forms=PDFInspectionState.UNSUPPORTED,
        )
    value = getter()
    if isinstance(value, Awaitable):
        value = await value
    if not isinstance(value, PDFPageTechnicalHints):
        return PDFPageTechnicalHints()
    return value


def _build_inspection(
    *,
    source: DocumentSource,
    provider: PDFProvider,
    descriptor: PDFProviderDescriptor,
    probe: PDFProbeResult | None,
    info: PDFBasicInfo,
    options: PDFInspectionOptions,
    page_inspections: tuple[PDFPageInspection, ...],
    timings: PDFInspectionTimings,
) -> PDFTechnicalInspection:
    page_summary = _page_summary(info.page_count, page_inspections)
    inventory = _feature_inventory(page_inspections, provider)
    coverage = _coverage(info.page_count, page_inspections, options)
    integrity = _integrity(probe, info, page_summary)
    security = _security(info, options)
    metadata = _metadata(info, options)
    profile = _technical_profile(inventory, page_summary)
    provenance = info.provenance or _fallback_provenance(descriptor, "inspect", source, options)
    return PDFTechnicalInspection(
        schema_version=ContractVersion("1.0.0"),
        document_identity=source_identity(source),
        source=source_identity(source),
        provider=descriptor,
        integrity=integrity,
        version=PDFVersionInspection(
            declared_version=info.declared_version,
            interpreted_version=info.interpreted_version,
            version_mismatch=(
                PDFInspectionState.PRESENT
                if info.declared_version
                and info.interpreted_version
                and info.declared_version != info.interpreted_version
                else PDFInspectionState.ABSENT
            ),
        ),
        page_summary=page_summary,
        metadata=metadata,
        security=security,
        permissions=_permissions(options),
        feature_inventory=inventory,
        resource_summary=_resource_summary(inventory),
        page_inspections=page_inspections,
        warnings=tuple((probe.warnings if probe else ()) + info.warnings),
        limitations=tuple(descriptor.limitations + info.limitations),
        coverage=coverage,
        technical_profile=profile,
        fidelity_indicators=_fidelity(inventory, metadata),
        editability_hints=_editability(inventory),
        processing_recommendations=_recommendations(inventory, security, integrity, coverage),
        evidences=integrity.evidences + profile.evidences,
        provenance=provenance,
        timings=timings,
    )


def _probe_only_inspection(
    *,
    source: DocumentSource,
    provider: PDFProvider,
    probe: PDFProbeResult,
    options: PDFInspectionOptions,
    timings: PDFInspectionTimings,
) -> PDFTechnicalInspection:
    descriptor = provider.descriptor
    security = _security_from_probe(probe, options)
    integrity = PDFIntegrityInspection(
        status=(
            PDFIntegrityStatus.INVALID
            if probe.status == PDFProbeStatus.NOT_PDF
            else PDFIntegrityStatus.INCONCLUSIVE
        ),
        header=(
            PDFInspectionState.ABSENT
            if probe.status == PDFProbeStatus.NOT_PDF
            else PDFInspectionState.PRESENT
        ),
        confidence=probe.confidence,
        evidences=(
            PDFInspectionEvidence(
                code=f"probe.{probe.status.value}",
                message="PDF probe did not authorize full inspection.",
                scope="document",
            ),
        ),
    )
    empty_summary = PDFPageSummary(total_pages=0, inspected_pages=0, not_inspected_pages=0)
    empty_inventory = _empty_inventory(PDFInspectionState.NOT_INSPECTED)
    return PDFTechnicalInspection(
        schema_version=ContractVersion("1.0.0"),
        document_identity=source_identity(source),
        source=source_identity(source),
        provider=descriptor,
        integrity=integrity,
        version=PDFVersionInspection(declared_version=probe.detected_version),
        page_summary=empty_summary,
        metadata=PDFMetadataInspection(status=PDFInspectionState.NOT_INSPECTED),
        security=security,
        permissions=PDFPermissionsInspection(
            technical_capability=PDFInspectionState.NOT_INSPECTED
        ),
        feature_inventory=empty_inventory,
        resource_summary=_resource_summary(empty_inventory),
        page_inspections=(),
        warnings=probe.warnings,
        limitations=descriptor.limitations + probe.limitations,
        coverage=PDFInspectionCoverage(
            total_pages=0,
            inspected_pages=0,
            sampled_page_indexes=(),
            inspection_complete=False,
            metadata_inspected=PDFInspectionState.NOT_INSPECTED,
            security_inspected=PDFInspectionState.PRESENT,
            permissions_inspected=PDFInspectionState.NOT_INSPECTED,
            resources_inspected=PDFInspectionState.NOT_INSPECTED,
            features_inspected=PDFInspectionState.NOT_INSPECTED,
            coverage_ratio=0.0,
        ),
        technical_profile=PDFTechnicalProfileInspection(
            profile=PDFTechnicalProfile.UNKNOWN,
            confidence=0.0,
            reasons=("Document was not opened for full inspection.",),
        ),
        provenance=probe.provenance,
        timings=timings,
    )


def _failed_open_inspection(
    *,
    source: DocumentSource,
    provider: PDFProvider,
    probe: PDFProbeResult,
    error: Exception,
    options: PDFInspectionOptions,
    timings: PDFInspectionTimings,
) -> PDFTechnicalInspection:
    if isinstance(error, PDFPasswordRequiredError):
        security = PDFSecurityStatus.ENCRYPTED_PASSWORD_REQUIRED
        integrity_status = PDFIntegrityStatus.INCONCLUSIVE
    elif isinstance(error, InvalidPDFPasswordError):
        security = PDFSecurityStatus.ENCRYPTED_INVALID_PASSWORD
        integrity_status = PDFIntegrityStatus.INCONCLUSIVE
    else:
        security = PDFSecurityStatus.UNKNOWN
        integrity_status = PDFIntegrityStatus.CORRUPTED
    descriptor = provider.descriptor
    empty_inventory = _empty_inventory(PDFInspectionState.NOT_INSPECTED)
    return PDFTechnicalInspection(
        schema_version=ContractVersion("1.0.0"),
        document_identity=source_identity(source),
        source=source_identity(source),
        provider=descriptor,
        integrity=PDFIntegrityInspection(
            status=integrity_status,
            header=PDFInspectionState.PRESENT,
            malformed=PDFInspectionState.PRESENT
            if integrity_status == PDFIntegrityStatus.CORRUPTED
            else PDFInspectionState.UNKNOWN,
            confidence=probe.confidence,
            evidences=(
                PDFInspectionEvidence(
                    code=getattr(error, "code", error.__class__.__name__),
                    message="PDF open failed during technical inspection.",
                    scope="document",
                ),
            ),
        ),
        version=PDFVersionInspection(declared_version=probe.detected_version),
        page_summary=PDFPageSummary(total_pages=0, inspected_pages=0, not_inspected_pages=0),
        metadata=PDFMetadataInspection(status=PDFInspectionState.NOT_INSPECTED),
        security=PDFSecurityInspection(
            status=security,
            encryption_state=probe.encryption_state,
            password_provided=options.password is not None,
            authenticated=PDFInspectionState.ABSENT
            if isinstance(error, InvalidPDFPasswordError)
            else PDFInspectionState.UNKNOWN,
        ),
        permissions=PDFPermissionsInspection(
            technical_capability=PDFInspectionState.NOT_INSPECTED
        ),
        feature_inventory=empty_inventory,
        resource_summary=_resource_summary(empty_inventory),
        page_inspections=(),
        warnings=probe.warnings,
        limitations=descriptor.limitations + probe.limitations,
        coverage=PDFInspectionCoverage(
            total_pages=0,
            inspected_pages=0,
            sampled_page_indexes=(),
            inspection_complete=False,
            metadata_inspected=PDFInspectionState.NOT_INSPECTED,
            security_inspected=PDFInspectionState.PRESENT,
            permissions_inspected=PDFInspectionState.NOT_INSPECTED,
            resources_inspected=PDFInspectionState.NOT_INSPECTED,
            features_inspected=PDFInspectionState.NOT_INSPECTED,
            coverage_ratio=0.0,
        ),
        technical_profile=PDFTechnicalProfileInspection(
            profile=PDFTechnicalProfile.UNKNOWN,
            confidence=0.0,
            reasons=("Document could not be opened.",),
        ),
        provenance=probe.provenance,
        timings=timings,
    )


def _probe_options(options: PDFInspectionOptions) -> PDFProbeOptions:
    return PDFProbeOptions(
        password=options.password,
        max_pages=options.max_pages_to_inspect,
        strict_validation=options.strict_validation,
        tolerate_partial_corruption=options.tolerate_partial_corruption,
        timeout_seconds=options.timeout_seconds,
    )


def _open_options(options: PDFInspectionOptions) -> PDFOpenOptions:
    return PDFOpenOptions(
        password=options.password,
        max_pages=options.max_pages_to_inspect,
        strict_validation=options.strict_validation,
        tolerate_partial_corruption=options.tolerate_partial_corruption,
        timeout_seconds=options.timeout_seconds,
    )


def _sample_page_indexes(total_pages: int, options: PDFInspectionOptions) -> tuple[int, ...]:
    if total_pages <= 0:
        return ()
    limit = options.max_pages_to_inspect or total_pages
    limit = min(limit, total_pages)
    if options.inspect_all_pages and limit == total_pages:
        return tuple(range(total_pages))
    if options.sampling_strategy == PDFSamplingStrategy.FIRST:
        return tuple(range(limit))
    if options.sampling_strategy == PDFSamplingStrategy.FIRST_MIDDLE_LAST:
        candidates = {0, total_pages // 2, total_pages - 1}
        return tuple(sorted(candidates))[:limit]
    if options.sampling_strategy == PDFSamplingStrategy.UNIFORM and limit > 1:
        step = (total_pages - 1) / (limit - 1)
        return tuple(sorted({round(index * step) for index in range(limit)}))
    return tuple(range(limit))


def _page_summary(
    total_pages: int,
    pages: tuple[PDFPageInspection, ...],
) -> PDFPageSummary:
    widths = [page.width for page in pages]
    heights = [page.height for page in pages]
    orientations = sorted(
        {
            "landscape" if page.width > page.height else "portrait"
            for page in pages
            if page.width or page.height
        }
    )
    return PDFPageSummary(
        total_pages=total_pages,
        inspected_pages=len(pages),
        not_inspected_pages=max(total_pages - len(pages), 0),
        pages_with_errors=sum(
            1 for page in pages if page.inspection_status == PDFInspectionState.INCONCLUSIVE
        ),
        pages_empty=sum(
            1
            for page in pages
            if page.has_text == page.has_images == page.has_vectors == PDFInspectionState.ABSENT
        ),
        pages_with_text=_count_pages(pages, "has_text"),
        pages_with_images=_count_pages(pages, "has_images"),
        pages_with_vectors=_count_pages(pages, "has_vectors"),
        pages_with_annotations=_count_pages(pages, "has_annotations"),
        pages_with_forms=_count_pages(pages, "has_forms"),
        pages_with_rotation=sum(1 for page in pages if page.rotation % 360 != 0),
        min_width=min(widths) if widths else None,
        max_width=max(widths) if widths else None,
        min_height=min(heights) if heights else None,
        max_height=max(heights) if heights else None,
        orientations=tuple(orientations),
        sampled_page_indexes=tuple(page.page_index for page in pages),
    )


def _feature_inventory(
    pages: tuple[PDFPageInspection, ...],
    provider: PDFProvider,
) -> PDFFeatureInventory:
    return PDFFeatureInventory(
        native_text=_signal_from_pages(pages, "has_text"),
        images=_signal_from_pages(pages, "has_images"),
        image_masks=_unsupported_or_unknown(provider, "supports_image_extraction"),
        vectors=_signal_from_pages(pages, "has_vectors"),
        clipping=_unsupported_or_unknown(provider, "supports_clipping"),
        transparency=_unsupported_or_unknown(provider, "supports_vector_extraction"),
        embedded_fonts=_unsupported_or_unknown(provider, "supports_embedded_fonts"),
        non_embedded_fonts=_unsupported_or_unknown(provider, "supports_embedded_fonts"),
        xobjects=_unsupported_or_unknown(provider, "supports_object_references"),
        form_xobjects=_unsupported_or_unknown(provider, "supports_object_references"),
        links=_signal_from_pages(pages, "has_links"),
        annotations=_signal_from_pages(pages, "has_annotations"),
        forms=_signal_from_pages(pages, "has_forms"),
        signatures=_signal_from_pages(pages, "has_forms"),
        layers=_signal_from_pages(pages, "has_layers"),
        attachments=_unsupported_or_unknown(provider, "supports_object_references"),
        javascript=_unsupported_or_unknown(provider, "supports_object_references"),
        tagged_pdf=_unsupported_or_unknown(provider, "supports_object_references"),
        logical_structure=_unsupported_or_unknown(provider, "supports_object_references"),
        incremental_updates=_unsupported_or_unknown(provider, "supports_object_references"),
    )


def _resource_summary(inventory: PDFFeatureInventory) -> PDFResourceSummary:
    return PDFResourceSummary(
        fonts=inventory.embedded_fonts,
        images=inventory.images,
        vectors=inventory.vectors,
        annotations=inventory.annotations,
        forms=inventory.forms,
        layers=inventory.layers,
        unsupported_resource_types=tuple(
            name
            for name, signal in {
                "fonts": inventory.embedded_fonts,
                "images": inventory.images,
                "vectors": inventory.vectors,
                "annotations": inventory.annotations,
                "forms": inventory.forms,
                "layers": inventory.layers,
            }.items()
            if signal.status == PDFInspectionState.UNSUPPORTED
        ),
    )


def _coverage(
    total_pages: int,
    pages: tuple[PDFPageInspection, ...],
    options: PDFInspectionOptions,
) -> PDFInspectionCoverage:
    inspected = len(pages)
    return PDFInspectionCoverage(
        total_pages=total_pages,
        inspected_pages=inspected,
        sampled_page_indexes=tuple(page.page_index for page in pages),
        inspection_complete=inspected == total_pages and total_pages > 0,
        metadata_inspected=_bool_state(options.inspect_metadata),
        security_inspected=_bool_state(options.inspect_security),
        permissions_inspected=_bool_state(options.inspect_permissions),
        resources_inspected=_bool_state(options.inspect_resources),
        features_inspected=PDFInspectionState.PRESENT
        if inspected
        else PDFInspectionState.NOT_INSPECTED,
        coverage_ratio=inspected / total_pages if total_pages else 0.0,
    )


def _integrity(
    probe: PDFProbeResult | None,
    info: PDFBasicInfo,
    summary: PDFPageSummary,
) -> PDFIntegrityInspection:
    if summary.total_pages == 0:
        status = PDFIntegrityStatus.INVALID
    elif probe is not None and probe.warnings:
        status = PDFIntegrityStatus.VALID_WITH_WARNINGS
    else:
        status = PDFIntegrityStatus.VALID
    return PDFIntegrityInspection(
        status=status,
        header=PDFInspectionState.PRESENT,
        page_tree=PDFInspectionState.PRESENT if summary.total_pages else PDFInspectionState.ABSENT,
        repaired=PDFInspectionState.UNKNOWN,
        empty_document=PDFInspectionState.PRESENT
        if summary.total_pages == 0
        else PDFInspectionState.ABSENT,
        confidence=probe.confidence if probe is not None else 0.8,
        evidences=(
            PDFInspectionEvidence(
                code="provider.opened",
                message="Provider opened the PDF and returned basic information.",
                scope="document",
            ),
        ),
    )


def _security(info: PDFBasicInfo, options: PDFInspectionOptions) -> PDFSecurityInspection:
    status_by_state = {
        PDFEncryptionState.NOT_ENCRYPTED: PDFSecurityStatus.NOT_ENCRYPTED,
        PDFEncryptionState.ENCRYPTED_UNLOCKED: PDFSecurityStatus.ENCRYPTED_UNLOCKED,
        PDFEncryptionState.PASSWORD_REQUIRED: PDFSecurityStatus.ENCRYPTED_PASSWORD_REQUIRED,
        PDFEncryptionState.INVALID_PASSWORD: PDFSecurityStatus.ENCRYPTED_INVALID_PASSWORD,
        PDFEncryptionState.UNSUPPORTED_ENCRYPTION: PDFSecurityStatus.ENCRYPTED_UNSUPPORTED,
        PDFEncryptionState.UNKNOWN: PDFSecurityStatus.UNKNOWN,
    }
    return PDFSecurityInspection(
        status=status_by_state[info.encryption_state],
        encryption_state=info.encryption_state,
        password_provided=options.password is not None,
        authenticated=PDFInspectionState.PRESENT
        if info.encryption_state == PDFEncryptionState.ENCRYPTED_UNLOCKED
        else PDFInspectionState.NOT_APPLICABLE
        if info.encryption_state == PDFEncryptionState.NOT_ENCRYPTED
        else PDFInspectionState.UNKNOWN,
        details_supported=PDFSupportLevel.UNSUPPORTED,
    )


def _security_from_probe(
    probe: PDFProbeResult,
    options: PDFInspectionOptions,
) -> PDFSecurityInspection:
    if probe.encryption_state == PDFEncryptionState.PASSWORD_REQUIRED:
        status = PDFSecurityStatus.ENCRYPTED_PASSWORD_REQUIRED
    elif probe.encryption_state == PDFEncryptionState.INVALID_PASSWORD:
        status = PDFSecurityStatus.ENCRYPTED_INVALID_PASSWORD
    elif probe.encryption_state == PDFEncryptionState.NOT_ENCRYPTED:
        status = PDFSecurityStatus.NOT_ENCRYPTED
    else:
        status = PDFSecurityStatus.UNKNOWN
    return PDFSecurityInspection(
        status=status,
        encryption_state=probe.encryption_state,
        password_provided=options.password is not None,
        authenticated=PDFInspectionState.UNKNOWN,
    )


def _metadata(info: PDFBasicInfo, options: PDFInspectionOptions) -> PDFMetadataInspection:
    if not options.inspect_metadata:
        return PDFMetadataInspection(status=PDFInspectionState.NOT_INSPECTED)
    fields: dict[str, PDFMetadataValue] = {}
    for key in sorted(info.metadata):
        value = info.metadata[key]
        if value.strip():
            fields[key] = PDFMetadataValue(
                normalized=value,
                sources=("provider_metadata",),
                confidence=0.8,
            )
    return PDFMetadataInspection(
        status=PDFInspectionState.PRESENT if fields else PDFInspectionState.ABSENT,
        fields=fields,
        info_dictionary=PDFInspectionState.PRESENT if fields else PDFInspectionState.ABSENT,
        xmp_metadata=PDFInspectionState.UNSUPPORTED,
    )


def _permissions(options: PDFInspectionOptions) -> PDFPermissionsInspection:
    if not options.inspect_permissions:
        return PDFPermissionsInspection(technical_capability=PDFInspectionState.NOT_INSPECTED)
    return PDFPermissionsInspection(technical_capability=PDFInspectionState.UNSUPPORTED)


def _technical_profile(
    inventory: PDFFeatureInventory,
    summary: PDFPageSummary,
) -> PDFTechnicalProfileInspection:
    reasons: list[str] = []
    if inventory.forms.status == PDFInspectionState.PRESENT:
        profile = PDFTechnicalProfile.FORM_DOCUMENT
        reasons.append("Form fields were detected.")
    elif (
        inventory.links.status == PDFInspectionState.PRESENT
        or inventory.annotations.status == PDFInspectionState.PRESENT
    ):
        profile = PDFTechnicalProfile.INTERACTIVE
        reasons.append("Interactive elements were detected.")
    elif (
        inventory.native_text.status == PDFInspectionState.PRESENT
        and inventory.images.status == PDFInspectionState.PRESENT
    ):
        profile = PDFTechnicalProfile.MIXED
        reasons.append("Native text and images were detected.")
    elif inventory.native_text.status == PDFInspectionState.PRESENT:
        profile = PDFTechnicalProfile.DIGITAL_TEXT
        reasons.append("Native text was detected.")
    elif inventory.images.status == PDFInspectionState.PRESENT:
        profile = PDFTechnicalProfile.IMAGE_BASED
        reasons.append("Images were detected and native text was not confirmed.")
    elif inventory.vectors.status == PDFInspectionState.PRESENT:
        profile = PDFTechnicalProfile.VECTOR_DOMINANT
        reasons.append("Vector content was detected.")
    else:
        profile = PDFTechnicalProfile.UNKNOWN
        reasons.append("Provider did not expose enough feature information.")
    confidence = min(summary.inspected_pages / max(summary.total_pages, 1), 1.0)
    return PDFTechnicalProfileInspection(
        profile=profile,
        confidence=confidence,
        reasons=tuple(reasons),
    )


def _fidelity(
    inventory: PDFFeatureInventory,
    metadata: PDFMetadataInspection,
) -> PDFFidelityIndicators:
    return PDFFidelityIndicators(
        native_text_fidelity=inventory.native_text.status,
        image_fidelity=inventory.images.status,
        vector_fidelity=inventory.vectors.status,
        metadata_fidelity=metadata.status,
        geometry_fidelity=PDFInspectionState.PARTIAL,
    )


def _editability(inventory: PDFFeatureInventory) -> PDFEditabilityHints:
    return PDFEditabilityHints(
        text_editability=inventory.native_text.status,
        image_editability=inventory.images.status,
        vector_editability=inventory.vectors.status,
        font_availability=inventory.embedded_fonts.status,
        reconstruction_required=PDFInspectionState.UNKNOWN,
    )


def _recommendations(
    inventory: PDFFeatureInventory,
    security: PDFSecurityInspection,
    integrity: PDFIntegrityInspection,
    coverage: PDFInspectionCoverage,
) -> tuple[str, ...]:
    values: list[str] = []
    if security.status == PDFSecurityStatus.ENCRYPTED_PASSWORD_REQUIRED:
        values.append("Provide a PDF password before parsing.")
    if integrity.status not in {PDFIntegrityStatus.VALID, PDFIntegrityStatus.VALID_WITH_WARNINGS}:
        values.append("Avoid heavy parsing until PDF integrity is resolved.")
    if coverage.coverage_ratio < 1.0:
        values.append("Inspection is partial; avoid global assumptions about all pages.")
    if inventory.native_text.status == PDFInspectionState.UNSUPPORTED:
        values.append("Use a provider phase with text presence support before routing OCR.")
    return tuple(values)


def _empty_inventory(state: PDFInspectionState) -> PDFFeatureInventory:
    signal = PDFFeatureSignal(status=state, confidence=1.0)
    return PDFFeatureInventory(
        native_text=signal,
        images=signal,
        image_masks=signal,
        vectors=signal,
        clipping=signal,
        transparency=signal,
        embedded_fonts=signal,
        non_embedded_fonts=signal,
        xobjects=signal,
        form_xobjects=signal,
        links=signal,
        annotations=signal,
        forms=signal,
        signatures=signal,
        layers=signal,
        attachments=signal,
        javascript=signal,
        tagged_pdf=signal,
        logical_structure=signal,
        incremental_updates=signal,
    )


def _unsupported_or_unknown(provider: PDFProvider, capability_name: str) -> PDFFeatureSignal:
    support = provider.capabilities.support_for(capability_name)
    return (
        unsupported_signal()
        if support == PDFSupportLevel.UNSUPPORTED
        else PDFFeatureSignal(status=PDFInspectionState.UNKNOWN, confidence=0.0)
    )


def _signal_from_pages(
    pages: tuple[PDFPageInspection, ...],
    attribute: str,
) -> PDFFeatureSignal:
    present_pages = tuple(
        page.page_index
        for page in pages
        if getattr(page, attribute) == PDFInspectionState.PRESENT
    )
    if present_pages:
        return PDFFeatureSignal(
            status=PDFInspectionState.PRESENT,
            approximate_count=len(present_pages),
            pages=present_pages,
            confidence=1.0,
        )
    values = {getattr(page, attribute) for page in pages}
    if PDFInspectionState.UNSUPPORTED in values:
        return unsupported_signal()
    if PDFInspectionState.UNKNOWN in values:
        return PDFFeatureSignal(status=PDFInspectionState.UNKNOWN, confidence=0.0)
    return PDFFeatureSignal(status=PDFInspectionState.ABSENT, approximate_count=0, confidence=1.0)


def _count_pages(pages: tuple[PDFPageInspection, ...], attribute: str) -> int:
    return sum(1 for page in pages if getattr(page, attribute) == PDFInspectionState.PRESENT)


def _resource_count(hints: PDFPageTechnicalHints) -> int | None:
    values = (
        hints.approximate_text_count,
        hints.approximate_image_count,
        hints.approximate_vector_count,
        hints.approximate_link_count,
        hints.approximate_annotation_count,
        hints.approximate_form_count,
    )
    known = [value for value in values if value is not None]
    return sum(known) if known else None


def _option_state(enabled: bool, state: PDFInspectionState) -> PDFInspectionState:
    return state if enabled else PDFInspectionState.NOT_INSPECTED


def _bool_state(enabled: bool) -> PDFInspectionState:
    return PDFInspectionState.PRESENT if enabled else PDFInspectionState.NOT_INSPECTED


def _fallback_provenance(
    descriptor,
    operation: str,
    source: DocumentSource,
    options: PDFInspectionOptions,
) -> PDFProviderProvenance:
    return PDFProviderProvenance(
        provider_id=descriptor.provider_id,
        provider_version=descriptor.provider_version,
        backend_name=descriptor.backend_name,
        backend_version=descriptor.backend_version,
        operation=operation,
        source_reference=source.origin_reference,
        source_hash=source.metadata.get("content_hash"),
        options=options.safe_options(),
    )


def _descriptor_from_document(document: PDFDocumentHandle) -> PDFProviderDescriptor:
    info_provider = getattr(document, "descriptor", None)
    if info_provider is None:
        raise ValueError("document handle does not expose a PDF provider descriptor")
    return info_provider


def descriptor_provider(descriptor: PDFProviderDescriptor) -> object:
    class _ProviderAdapter:
        def __init__(self, value):
            self.descriptor = value
            self.capabilities = value.capabilities

    return _ProviderAdapter(descriptor)


def _log(event: str, **fields: str) -> None:
    logger.info(event, extra={"event": event, **fields})


__all__ = ["DefaultPDFTechnicalInspector"]
