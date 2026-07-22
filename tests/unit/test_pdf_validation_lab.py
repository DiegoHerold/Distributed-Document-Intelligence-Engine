from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from eixo import DocumentId, ParseRequest, ParseResult
from eixo.artifacts import LocalArtifactStore
from eixo.core import ArtifactReference, ResultStatus
from eixo.diagnostics.pdf_validation_lab import (
    PDFValidationDocumentState,
    validate_pdf_batch,
)


def test_pdf_validation_lab_processes_batch_independently(tmp_path: Path) -> None:
    async def run() -> None:
        source_dir = tmp_path / "pdfs"
        source_dir.mkdir()
        good = source_dir / "good.pdf"
        bad = source_dir / "bad.pdf"
        good.write_bytes(b"%PDF-1.7\n")
        bad.write_bytes(b"%PDF-1.7\n")
        output = tmp_path / "diagnostics"

        result = await validate_pdf_batch(
            FakeValidationEngine(tmp_path),
            source_dir,
            output_directory=output,
            profile="visual",
            diagnostic_preview=True,
        )

        states = {Path(item.document_path).name: item.state for item in result.documents}
        assert states["good.pdf"] is PDFValidationDocumentState.COMPLETED_WITH_WARNINGS
        assert states["bad.pdf"] is PDFValidationDocumentState.FAILED
        assert (output / "summary.json").exists()
        assert (output / "batch-report.json").exists()
        assert (output / "index.html").exists()
        assert (output / "history.json").exists()
        good_run = next(
            (output / "documents" / "good" / "runs").iterdir(),
        )
        bad_run = next(
            (output / "documents" / "bad" / "runs").iterdir(),
        )
        assert (good_run / "report.json").exists()
        assert (good_run / "artifact-summary.json").exists()
        assert (good_run / "findings.json").exists()
        assert (good_run / "assessment.json").exists()
        assert (good_run / "manual-evaluation.json").exists()
        assert (good_run / "pages" / "page-001-original.png").exists()
        assert (good_run / "pages" / "page-001-overlay.png").exists()
        assert (good_run / "pages" / "page-001-elements.json").exists()
        html = (good_run / "report.html").read_text(encoding="utf-8")
        assert "lab-data" in html
        assert "data-kind=\"text\"" in html
        assert "Texto" in html
        assert "Imagens" in html
        assert "Vetores" in html
        assert "Recursos" in html
        assert "Salvar avaliacao local" in html
        assert "localStorage" in html
        assert (bad_run / "report.json").exists()
        batch = json.loads((output / "batch-report.json").read_text(encoding="utf-8"))
        assert batch["documents_failed"] == 1
        assert batch["documents_completed"] == 1
        assert batch["finding_count"] == 1

    import asyncio

    asyncio.run(run())


@dataclass(slots=True)
class FakeValidationEngine:
    base: Path
    artifact_store: LocalArtifactStore = field(init=False)

    def __post_init__(self) -> None:
        self.artifact_store = LocalArtifactStore(self.base / "store")

    async def parse(self, request: ParseRequest) -> ParseResult:
        if request.source.filename == "bad.pdf":
            raise RuntimeError("parse failed")
        reference = await self._store_scene()
        return ParseResult(
            document_id=DocumentId("doc_good"),
            status=ResultStatus.SUCCESS,
            format="pdf",
            profile=request.profile,
            scene_artifact_reference=reference,
            page_count=1,
            statistics={
                "page_count": 1,
                "element_count": 1,
                "text_element_count": 1,
            },
        )

    async def _store_scene(self) -> ArtifactReference:
        from io import BytesIO

        from eixo.core import ArtifactType, ArtifactWriteRequest, ContentHash

        payload = json.dumps(_native_scene()).encode("utf-8")
        digest = ContentHash("sha256", hashlib.sha256(payload).hexdigest())
        return await self.artifact_store.put(
            ArtifactWriteRequest(
                stream=BytesIO(payload),
                artifact_type=ArtifactType.DERIVED,
                content_hash=digest,
                size_bytes=len(payload),
                media_type="application/vnd.eixo+json",
                original_filename="native-scene.json",
            )
        )


def _native_scene() -> dict[str, object]:
    return {
        "artifact_id": "art_native_pdf_scene_doc_good",
        "artifact_type": "native_pdf_scene",
        "inspection": {"page_summary": {"total_pages": 1}},
        "statistics": {
            "page_count": 1,
            "element_count": 1,
            "text_element_count": 1,
        },
        "fidelity_summary": {"overall_level": "native_normalized"},
        "editability_summary": {"overall_status": "partially_editable"},
        "warnings": [],
        "limitations": [],
        "pages": [
            {
                "page_id": "pdfpage:0",
                "page_index": 0,
                "element_count": 1,
                "text_count": 1,
                "image_count": 0,
                "vector_count": 0,
                "interactive_count": 0,
            }
        ],
        "scenes": [
            {
                "page_id": "pdfpage:0",
                "page_index": 0,
                "geometry": {"size": {"width": 100, "height": 80}},
                "elements": [
                    {
                        "element_id": "sceneelement:text-span",
                        "element_type": "text_span",
                        "bounding_box": {
                            "x_min": 10,
                            "y_min": 10,
                            "x_max": 40,
                            "y_max": 20,
                        },
                        "scene_order": 0,
                        "visibility": "visible",
                    }
                ],
            }
        ],
    }
