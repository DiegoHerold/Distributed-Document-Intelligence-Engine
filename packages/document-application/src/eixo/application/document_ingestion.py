from __future__ import annotations

from dataclasses import dataclass, replace

from eixo.application.document_lifecycle import (
    DocumentLifecycle,
    DocumentRepository,
    LocalDocumentRepository,
    new_document_record,
)
from eixo.application.ingestion import (
    ContentIdentityService,
    LocalSourceResolver,
    SourceResolver,
)
from eixo.artifacts import ArtifactStore, LocalArtifactStore
from eixo.core import (
    ArtifactType,
    ArtifactWriteRequest,
    DocumentIngestionResult,
    DocumentSource,
    DocumentStatus,
)


@dataclass(frozen=True, slots=True)
class IngestDocument:
    source_resolver: SourceResolver
    content_identifier: ContentIdentityService
    artifact_store: ArtifactStore
    document_repository: DocumentRepository
    lifecycle: DocumentLifecycle

    @classmethod
    def local(cls, data_directory) -> "IngestDocument":
        return cls(
            source_resolver=LocalSourceResolver(),
            content_identifier=ContentIdentityService(),
            artifact_store=LocalArtifactStore(data_directory),
            document_repository=LocalDocumentRepository(data_directory),
            lifecycle=DocumentLifecycle.default(),
        )

    async def execute(self, source: DocumentSource) -> DocumentIngestionResult:
        async with self.source_resolver.resolve(source) as resolved:
            identified = await self.content_identifier.identify(resolved)
            source_metadata = dict(resolved.source_metadata or {})
            if resolved.filename is not None:
                source_metadata.setdefault("filename", resolved.filename)
            if resolved.declared_mime is not None:
                source_metadata.setdefault("declared_mime", resolved.declared_mime)
            record, received_transition = new_document_record(
                identity=identified.identity,
                detected_format=identified.identity.detected_format,
                source_metadata=source_metadata,
                warnings=identified.identity.detected_format.warnings,
            )
            await self.document_repository.create(record)
            await self.document_repository.append_transition(received_transition)

            validated, validated_transition = self.lifecycle.transition(
                record,
                to_status=DocumentStatus.VALIDATED,
                reason="content_identity_validated",
                actor="eixo.ingestion",
            )
            await self.document_repository.update(
                validated,
                expected_version=record.version,
            )
            await self.document_repository.append_transition(validated_transition)

            resolved.rewind()
            artifact_reference = await self.artifact_store.put(
                ArtifactWriteRequest(
                    stream=resolved.stream,
                    artifact_type=ArtifactType.ORIGINAL_DOCUMENT,
                    content_hash=identified.identity.content_hash,
                    size_bytes=identified.identity.size_bytes,
                    media_type=identified.identity.detected_format.canonical_mime,
                    original_filename=resolved.filename,
                    producer="eixo.ingestion",
                    source=resolved.source_kind,
                    metadata={
                        "document_id": str(record.document_id),
                        "identity_version": identified.identity.identity_version,
                    },
                )
            )
            with_artifact = replace(validated, original_artifact=artifact_reference)
            stored, stored_transition = self.lifecycle.transition(
                with_artifact,
                to_status=DocumentStatus.STORED,
                reason="original_artifact_persisted",
                actor="eixo.ingestion",
                metadata={"artifact_id": str(artifact_reference.artifact_id)},
            )
            await self.document_repository.update(
                stored,
                expected_version=validated.version,
            )
            await self.document_repository.append_transition(stored_transition)
            return DocumentIngestionResult(
                document_id=stored.document_id,
                status=stored.status,
                identity=identified.identity,
                original_artifact=artifact_reference,
                detected_format=identified.identity.detected_format,
                size_bytes=identified.identity.size_bytes,
                warnings=identified.identity.detected_format.warnings,
                transitions=(
                    received_transition,
                    validated_transition,
                    stored_transition,
                ),
            )


__all__ = ["IngestDocument"]
