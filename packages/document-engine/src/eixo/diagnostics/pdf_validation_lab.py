from __future__ import annotations

import json
import traceback
import zlib
from datetime import UTC, datetime
from hashlib import sha256
from importlib import import_module
import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from uuid import uuid4
from typing import Any, Protocol

from eixo.artifacts import ArtifactStore
from eixo.core import ArtifactReference, DocumentSource, ParseRequest
from eixo.core.serialization import to_jsonable


class PDFValidationDocumentState(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class PDFManualDimensionEvaluation:
    text: str = "not_applicable"
    geometry: str = "not_applicable"
    fonts: str = "not_applicable"
    images: str = "not_applicable"
    vectors: str = "not_applicable"
    clipping: str = "not_applicable"
    visual_order: str = "not_applicable"
    resources: str = "not_applicable"
    provenance: str = "not_applicable"
    overall_fidelity: str = "not_applicable"


@dataclass(frozen=True, slots=True)
class PDFManualEvaluationTemplate:
    status: str = "needs_investigation"
    dimensions: PDFManualDimensionEvaluation = field(
        default_factory=PDFManualDimensionEvaluation
    )
    notes: str = ""


@dataclass(frozen=True, slots=True)
class PDFValidationDocumentResult:
    document_path: str
    document_id: str | None
    state: PDFValidationDocumentState
    output_directory: Path
    diagnostic_run_id: str
    started_at: str
    finished_at: str
    source_hash: str | None = None
    page_count: int = 0
    processed_pages: int = 0
    current_stage: str = "completed"
    progress: float = 1.0
    elapsed_seconds: float = 0.0
    warning_count: int = 0
    limitation_count: int = 0
    finding_count: int = 0
    error: str | None = None
    report_path: Path | None = None
    html_report_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_path": self.document_path,
            "document_id": self.document_id,
            "state": self.state.value,
            "output_directory": str(self.output_directory),
            "diagnostic_run_id": self.diagnostic_run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "source_hash": self.source_hash,
            "page_count": self.page_count,
            "processed_pages": self.processed_pages,
            "current_stage": self.current_stage,
            "progress": self.progress,
            "elapsed_seconds": self.elapsed_seconds,
            "warning_count": self.warning_count,
            "limitation_count": self.limitation_count,
            "finding_count": self.finding_count,
            "error": self.error,
            "report_path": str(self.report_path) if self.report_path else None,
            "html_report_path": (
                str(self.html_report_path) if self.html_report_path else None
            ),
        }


@dataclass(frozen=True, slots=True)
class PDFValidationBatchResult:
    input_path: Path
    output_directory: Path
    profile: str
    page_selection: tuple[int, ...] | None
    documents: tuple[PDFValidationDocumentResult, ...]
    elapsed_seconds: float
    consolidated_report_path: Path

    def to_dict(self) -> dict[str, Any]:
        states = [document.state for document in self.documents]
        return {
            "input_path": str(self.input_path),
            "output_directory": str(self.output_directory),
            "profile": self.profile,
            "page_selection": list(self.page_selection) if self.page_selection else None,
            "elapsed_seconds": self.elapsed_seconds,
            "document_count": len(self.documents),
            "documents_processed": len(self.documents),
            "documents_approved": 0,
            "documents_with_limitations": 0,
            "documents_failed": sum(
                1 for state in states if state is PDFValidationDocumentState.FAILED
            ),
            "documents_completed": sum(
                1
                for state in states
                if state
                in {
                    PDFValidationDocumentState.COMPLETED,
                    PDFValidationDocumentState.COMPLETED_WITH_WARNINGS,
                }
            ),
            "pages_processed": sum(item.processed_pages for item in self.documents),
            "warning_count": sum(item.warning_count for item in self.documents),
            "limitation_count": sum(item.limitation_count for item in self.documents),
            "finding_count": sum(item.finding_count for item in self.documents),
            "warnings_by_category": {},
            "limitations_by_category": {},
            "failed_checks": sum(item.finding_count for item in self.documents),
            "problematic_documents": [
                item.document_path
                for item in sorted(
                    self.documents,
                    key=lambda document: (
                        document.finding_count
                        + document.warning_count
                        + document.limitation_count
                    ),
                    reverse=True,
                )[:5]
            ],
            "consolidated_report_path": str(self.consolidated_report_path),
            "documents": [item.to_dict() for item in self.documents],
        }


class PDFValidationEngine(Protocol):
    artifact_store: ArtifactStore

    async def parse(self, request_or_source: ParseRequest) -> Any:
        ...


async def validate_pdf_batch(
    engine: PDFValidationEngine,
    input_path: str | Path,
    *,
    output_directory: str | Path,
    profile: str = "visual",
    page_selection: tuple[int, ...] | None = None,
    password: str | None = None,
    diagnostic_preview: bool = False,
    temporary_mode: bool = False,
) -> PDFValidationBatchResult:
    started = time.perf_counter()
    source = Path(input_path)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    documents = tuple(_discover_inputs(source))
    results: list[PDFValidationDocumentResult] = []
    for document in documents:
        if document.suffix.lower() != ".pdf":
            results.append(_unsupported_document(document, output))
        else:
            results.append(
                await _validate_document(
                    engine,
                    document,
                    output,
                    profile=profile.replace("-", "_"),
                    page_selection=page_selection,
                    password=password,
                    diagnostic_preview=diagnostic_preview,
                    temporary_mode=temporary_mode,
                )
            )
    consolidated = PDFValidationBatchResult(
        input_path=source,
        output_directory=output,
        profile=profile.replace("-", "_"),
        page_selection=page_selection,
        documents=tuple(results),
        elapsed_seconds=round(time.perf_counter() - started, 6),
        consolidated_report_path=output / "summary.json",
    )
    _write_json(consolidated.consolidated_report_path, consolidated.to_dict())
    _write_json(output / "batch-report.json", consolidated.to_dict())
    _write_history(output / "history.json", consolidated)
    _write_html(
        output / "index.html",
        "PDF validation batch",
        _batch_html(consolidated.to_dict()),
    )
    _write_html(
        output / "batch-report.html",
        "PDF validation batch",
        _batch_html(consolidated.to_dict()),
    )
    return consolidated


async def _validate_document(
    engine: PDFValidationEngine,
    document: Path,
    output: Path,
    *,
    profile: str,
    page_selection: tuple[int, ...] | None,
    password: str | None,
    diagnostic_preview: bool,
    temporary_mode: bool,
) -> PDFValidationDocumentResult:
    started = time.perf_counter()
    started_at = _now_iso()
    diagnostic_run_id = _diagnostic_run_id()
    source_hash = _source_hash(document)
    document_root = _document_root(output, document, temporary_mode=temporary_mode)
    document_dir = _document_run_directory(
        document_root,
        diagnostic_run_id,
        temporary_mode=temporary_mode,
    )
    pages_dir = document_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    try:
        request = ParseRequest(
            source=DocumentSource.from_path(document),
            profile=profile,
            page_selection=page_selection,
            options={"password": password} if password is not None else {},
        )
        result = await engine.parse(request)
        native_scene = await _read_scene_artifact(
            engine.artifact_store,
            result.scene_artifact_reference or result.artifact_reference,
        )
        diagnostic_context = _diagnostic_context(
            await _read_supporting_artifacts(engine.artifact_store, result.artifacts)
        )
        report = _document_report(
            document,
            result,
            native_scene,
            diagnostic_run_id=diagnostic_run_id,
            source_hash=source_hash,
            started_at=started_at,
        )
        findings = _structural_findings(report, native_scene)
        report["findings"] = findings
        report["finding_count"] = len(findings)
        artifact_summary = _scene_summary(native_scene)
        comparison = _comparison_from_history(output / "history.json", report)
        _write_json(document_dir / "native-scene-summary.json", artifact_summary)
        _write_json(document_dir / "artifact-summary.json", artifact_summary)
        _write_json(document_dir / "findings.json", findings)
        _write_json(document_dir / "comparison.json", comparison)
        _write_json(document_dir / "warnings.json", report["warnings"])
        _write_json(document_dir / "limitations.json", report["limitations"])
        _write_json(document_dir / "manual-evaluation.json", _manual_template())
        if native_scene is not None:
            _write_json(document_dir / "inspection.json", native_scene.get("inspection"))
            _write_pages(
                pages_dir,
                native_scene,
                document=document,
                password=password,
                diagnostic_preview=diagnostic_preview,
                diagnostic_context=diagnostic_context,
            )
        state = (
            PDFValidationDocumentState.COMPLETED_WITH_WARNINGS
            if report["warning_count"] or report["limitation_count"]
            or report["finding_count"]
            else PDFValidationDocumentState.COMPLETED
        )
        finished_at = _now_iso()
        report["state"] = state.value
        report["status"] = state.value
        report["finished_at"] = finished_at
        report["processing_summary"]["finished_at"] = finished_at
        report["processing_summary"]["duration_seconds"] = round(
            time.perf_counter() - started,
            6,
        )
        _write_json(document_root / "document.json", _document_index(report))
        _write_json(document_dir / "report.json", report)
        _write_json(document_dir / "assessment.json", _assessment_template(report))
        html_path = document_dir / "report.html"
        lab_data = _lab_data(
            report,
            native_scene,
            diagnostic_context,
            temporary_mode=temporary_mode,
        )
        _write_html(
            html_path,
            f"PDF validation lab: {document.name}",
            _document_lab_html(report, lab_data),
        )
        return PDFValidationDocumentResult(
            document_path=str(document),
            document_id=str(result.document_id),
            state=state,
            output_directory=document_dir,
            diagnostic_run_id=diagnostic_run_id,
            started_at=started_at,
            finished_at=finished_at,
            source_hash=source_hash,
            page_count=int(result.page_count or report["page_count"]),
            processed_pages=int(result.page_count or report["page_count"]),
            elapsed_seconds=round(time.perf_counter() - started, 6),
            warning_count=report["warning_count"],
            limitation_count=report["limitation_count"],
            finding_count=report["finding_count"],
            report_path=document_dir / "report.json",
            html_report_path=html_path,
        )
    except Exception as exc:
        finished_at = _now_iso()
        report = {
            "document": str(document),
            "filename": document.name,
            "diagnostic_run_id": diagnostic_run_id,
            "source_hash": source_hash,
            "started_at": started_at,
            "finished_at": finished_at,
            "state": PDFValidationDocumentState.FAILED.value,
            "error": _safe_error(exc),
            "error_trace": traceback.format_exc(),
            "findings": [],
            "warnings": [],
            "limitations": [],
            "manual_evaluation": _manual_template(),
        }
        _write_json(document_dir / "report.json", report)
        _write_json(document_dir / "findings.json", [])
        _write_json(document_dir / "warnings.json", [])
        _write_json(document_dir / "limitations.json", [])
        _write_json(document_dir / "assessment.json", _assessment_template(report))
        _write_html(
            document_dir / "report.html",
            f"PDF validation failed: {document.name}",
            f"<p>{_html_escape(report['error'])}</p>",
        )
        return PDFValidationDocumentResult(
            document_path=str(document),
            document_id=None,
            state=PDFValidationDocumentState.FAILED,
            output_directory=document_dir,
            diagnostic_run_id=diagnostic_run_id,
            started_at=started_at,
            finished_at=finished_at,
            source_hash=source_hash,
            current_stage="failed",
            elapsed_seconds=round(time.perf_counter() - started, 6),
            error=report["error"],
            report_path=document_dir / "report.json",
            html_report_path=document_dir / "report.html",
        )


def _discover_inputs(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(item for item in path.rglob("*") if item.is_file())
    return []


def _unsupported_document(document: Path, output: Path) -> PDFValidationDocumentResult:
    started_at = _now_iso()
    finished_at = _now_iso()
    diagnostic_run_id = _diagnostic_run_id()
    document_dir = output / "documents" / _slug(document.stem) / "runs" / diagnostic_run_id
    message = f"Unsupported input format: {document.suffix or 'unknown'}"
    report = {
        "document": str(document),
        "filename": document.name,
        "diagnostic_run_id": diagnostic_run_id,
        "source_hash": _source_hash(document),
        "state": PDFValidationDocumentState.FAILED.value,
        "status": PDFValidationDocumentState.FAILED.value,
        "current_stage": "unsupported_format",
        "started_at": started_at,
        "finished_at": finished_at,
        "error": message,
        "warnings": [],
        "limitations": [],
        "findings": [
            {
                "code": "diagnostics.unsupported_format",
                "severity": "error",
                "scope": "document",
                "message": message,
            }
        ],
        "manual_evaluation": _manual_template(),
    }
    _write_json(document_dir / "report.json", report)
    _write_json(document_dir / "findings.json", report["findings"])
    _write_json(document_dir / "warnings.json", [])
    _write_json(document_dir / "limitations.json", [])
    _write_html(document_dir / "report.html", "Unsupported document", f"<p>{message}</p>")
    return PDFValidationDocumentResult(
        document_path=str(document),
        document_id=None,
        state=PDFValidationDocumentState.FAILED,
        output_directory=document_dir,
        diagnostic_run_id=diagnostic_run_id,
        started_at=started_at,
        finished_at=finished_at,
        source_hash=report["source_hash"],
        current_stage="unsupported_format",
        warning_count=0,
        limitation_count=0,
        finding_count=1,
        error=message,
        report_path=document_dir / "report.json",
        html_report_path=document_dir / "report.html",
    )


async def _read_scene_artifact(
    artifact_store: ArtifactStore,
    reference: ArtifactReference | None,
) -> dict[str, Any] | None:
    if reference is None:
        return None
    async with artifact_store.open(reference) as reader:
        return json.loads(reader.stream.read().decode("utf-8"))


async def _read_supporting_artifacts(
    artifact_store: ArtifactStore,
    references: tuple[ArtifactReference, ...],
) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for reference in references:
        try:
            async with artifact_store.open(reference) as reader:
                value = json.loads(reader.stream.read().decode("utf-8"))
        except Exception:
            continue
        if isinstance(value, dict):
            artifacts.append(value)
    return artifacts


def _diagnostic_context(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "text_by_source_id": _text_index(artifacts),
    }


def _text_index(artifacts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    text_artifact = next((_ for _ in artifacts if _is_text_artifact(_)), None)
    if text_artifact is None:
        return index
    for page in text_artifact.get("pages", []):
        _index_text_collection(
            index,
            page.get("blocks", []),
            id_field="block_id",
            level="block",
            value_fields=("raw_text",),
        )
        _index_text_collection(
            index,
            page.get("lines", []),
            id_field="line_id",
            level="line",
            value_fields=("raw_text",),
        )
        _index_text_collection(
            index,
            page.get("spans", []),
            id_field="span_id",
            level="span",
            value_fields=("raw_text", "normalized_text"),
        )
        _index_text_collection(
            index,
            page.get("words", []),
            id_field="word_id",
            level="word",
            value_fields=("text", "normalized_text"),
        )
        _index_text_collection(
            index,
            page.get("glyphs", []),
            id_field="glyph_id",
            level="glyph",
            value_fields=("unicode_text", "normalized_unicode_text"),
        )
    return index


def _is_text_artifact(value: dict[str, Any]) -> bool:
    return "text_layer" in value or any(
        "words" in page or "spans" in page or "blocks" in page
        for page in value.get("pages", [])
        if isinstance(page, dict)
    )


def _index_text_collection(
    index: dict[str, dict[str, Any]],
    items: list[dict[str, Any]],
    *,
    id_field: str,
    level: str,
    value_fields: tuple[str, ...],
) -> None:
    for item in items:
        item_id = item.get(id_field)
        if not item_id:
            continue
        value = _first_text_value(item, value_fields)
        index[str(item_id)] = {
            "text_level": level,
            "raw_text": item.get("raw_text") or item.get("text") or item.get("unicode_text"),
            "display_text": value,
            "normalized_text": item.get("normalized_text")
            or item.get("normalized_unicode_text"),
            "font_reference": item.get("font_id"),
            "style_reference": item.get("style_id"),
            "baseline_reference": item.get("baseline_reference")
            or item.get("baseline_id"),
            "direction": item.get("direction"),
            "writing_mode": item.get("writing_mode"),
            "source_order": item.get("source_order"),
            "provider_order": item.get("provider_order"),
            "glyph_ids": item.get("glyph_ids", []),
            "word_ids": item.get("word_ids", []),
            "span_ids": item.get("span_ids", []),
            "line_ids": item.get("line_ids", []),
            "character_ids": item.get("character_ids", []),
            "warnings": item.get("warnings", []),
        }


def _first_text_value(item: dict[str, Any], fields: tuple[str, ...]) -> str | None:
    for field_name in fields:
        value = item.get(field_name)
        if isinstance(value, str) and value:
            return value
    return None


def _document_report(
    document: Path,
    result: Any,
    native_scene: dict[str, Any] | None,
    *,
    diagnostic_run_id: str,
    source_hash: str,
    started_at: str,
) -> dict[str, Any]:
    statistics = dict(result.statistics or {})
    warnings = [to_jsonable(item) for item in result.warnings]
    limitations = [to_jsonable(item) for item in result.limitations]
    pages = native_scene.get("pages", []) if native_scene else []
    scenes = native_scene.get("scenes", []) if native_scene else []
    element_count = int(statistics.get("element_count", 0))
    return {
        "document": str(document),
        "filename": document.name,
        "document_id": str(result.document_id),
        "diagnostic_run_id": diagnostic_run_id,
        "source_hash": source_hash,
        "state": "completed",
        "status": "completed",
        "current_stage": "completed",
        "started_at": started_at,
        "finished_at": None,
        "profile": result.profile,
        "page_count": int(result.page_count or len(pages)),
        "element_count": element_count,
        "text_count": int(statistics.get("text_element_count", 0)),
        "image_count": int(statistics.get("image_occurrence_count", 0)),
        "vector_count": int(statistics.get("vector_element_count", 0)),
        "link_count": int(statistics.get("link_count", 0)),
        "annotation_count": int(statistics.get("annotation_count", 0)),
        "widget_count": int(statistics.get("widget_count", 0)),
        "layer_count": int(statistics.get("layer_count", 0)),
        "text_elements": int(statistics.get("text_element_count", 0)),
        "image_resources": int(statistics.get("image_resource_count", 0)),
        "image_occurrences": int(statistics.get("image_occurrence_count", 0)),
        "vector_elements": int(statistics.get("vector_element_count", 0)),
        "clipping_paths": int(statistics.get("clipping_path_count", 0)),
        "links": int(statistics.get("link_count", 0)),
        "annotations": int(statistics.get("annotation_count", 0)),
        "fields": int(statistics.get("form_field_count", 0)),
        "widgets": int(statistics.get("widget_count", 0)),
        "layers": int(statistics.get("layer_count", 0)),
        "unresolved_resources": int(statistics.get("unresolved_reference_count", 0)),
        "elements_without_geometry": _elements_without_geometry(scenes),
        "elements_without_order": _elements_without_order(scenes),
        "partial_failures": len(warnings) + len(limitations),
        "warnings": warnings,
        "limitations": limitations,
        "warning_count": len(warnings),
        "limitation_count": len(limitations),
        "finding_count": 0,
        "fidelity": to_jsonable(result.fidelity_summary),
        "fidelity_summary": to_jsonable(result.fidelity_summary),
        "editability": to_jsonable(result.editability_summary),
        "editability_summary": to_jsonable(result.editability_summary),
        "processing_summary": {
            "started_at": started_at,
            "finished_at": None,
            "duration_seconds": None,
            "profile": result.profile,
            "page_selection": None,
        },
        "manual_evaluation": _manual_template(),
    }


def _scene_summary(native_scene: dict[str, Any] | None) -> dict[str, Any]:
    if native_scene is None:
        return {"available": False}
    return {
        "available": True,
        "artifact_id": native_scene.get("artifact_id"),
        "artifact_type": native_scene.get("artifact_type"),
        "statistics": native_scene.get("statistics", {}),
        "fidelity_summary": native_scene.get("fidelity_summary", {}),
        "editability_summary": native_scene.get("editability_summary", {}),
        "pages": native_scene.get("pages", []),
    }


def _write_pages(
    pages_dir: Path,
    native_scene: dict[str, Any],
    *,
    document: Path,
    password: str | None,
    diagnostic_preview: bool,
    diagnostic_context: dict[str, Any],
) -> None:
    for scene in native_scene.get("scenes", []):
        zero_based_index = int(scene.get("page_index", 0))
        page_index = zero_based_index + 1
        prefix = f"page-{page_index:03d}"
        _write_json(pages_dir / f"{prefix}-scene.json", scene)
        _write_json(
            pages_dir / f"{prefix}-elements.json",
            _page_elements(scene, diagnostic_context),
        )
        width, height = _scene_dimensions(scene)
        preview_scales = {"standard": 1.0, "high": 2.0, "ultra": 3.0}
        preview_paths: dict[str, bytes] = {}
        for quality, scale in preview_scales.items():
            original_png = _render_original_png(
                document,
                zero_based_index,
                password,
                scale=scale,
            )
            if original_png is None:
                original_png = _blank_png(
                    max(1, int(width * scale)),
                    max(1, int(height * scale)),
                )
            preview_paths[quality] = original_png
            _write_bytes(pages_dir / f"{prefix}-original-{quality}.png", original_png)
        _write_bytes(pages_dir / f"{prefix}-original.png", preview_paths["high"])
        if diagnostic_preview:
            overlay_png = _overlay_png(scene, width, height)
            _write_bytes(pages_dir / f"{prefix}-overlay.png", overlay_png)
        elif not (pages_dir / f"{prefix}-overlay.png").exists():
            _write_bytes(pages_dir / f"{prefix}-overlay.png", _blank_png(width, height))


def _render_original_png(
    document: Path,
    page_index: int,
    password: str | None,
    *,
    scale: float = 1.0,
) -> bytes | None:
    try:
        rendering = import_module("eixo.providers.pdf.pymupdf.rendering")
        return rendering.render_pdf_page_png(
            document,
            page_index,
            password=password,
            scale=scale,
        )
    except Exception:
        return None


def _scene_dimensions(scene: dict[str, Any]) -> tuple[int, int]:
    geometry = scene.get("geometry", {})
    size = geometry.get("size", {})
    width = size.get("width", geometry.get("width", 612))
    height = size.get("height", geometry.get("height", 792))
    return max(1, int(round(float(width)))), max(1, int(round(float(height))))


def _overlay_png(scene: dict[str, Any], width: int, height: int) -> bytes:
    canvas = _Canvas(width, height)
    for element in scene.get("elements", []):
        bbox = element.get("bounding_box")
        if not isinstance(bbox, dict):
            continue
        color = _color_for_element(element)
        canvas.rectangle(
            int(round(float(bbox["x_min"]))),
            int(round(float(bbox["y_min"]))),
            int(round(float(bbox["x_max"]))),
            int(round(float(bbox["y_max"]))),
            color,
            marker=True,
        )
    return _encode_png(width, height, canvas.bytes())


def _blank_png(width: int, height: int) -> bytes:
    return _encode_png(width, height, bytes([255, 255, 255] * width * height))


class _Canvas:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self._pixels = bytearray([255, 255, 255] * width * height)

    def bytes(self) -> bytes:
        return bytes(self._pixels)

    def rectangle(
        self,
        x_min: int,
        y_min: int,
        x_max: int,
        y_max: int,
        color: tuple[int, int, int],
        *,
        marker: bool = False,
    ) -> None:
        left = max(0, min(self.width - 1, x_min))
        right = max(0, min(self.width - 1, x_max))
        top = max(0, min(self.height - 1, y_min))
        bottom = max(0, min(self.height - 1, y_max))
        for x in range(left, right + 1):
            self._set(x, top, color)
            self._set(x, bottom, color)
        for y in range(top, bottom + 1):
            self._set(left, y, color)
            self._set(right, y, color)
        if marker:
            self._set(left, top, color)
            if left + 1 <= right:
                self._set(left + 1, top, color)
            if top + 1 <= bottom:
                self._set(left, top + 1, color)

    def _set(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        index = (y * self.width + x) * 3
        self._pixels[index : index + 3] = bytes(color)


def _encode_png(width: int, height: int, rgb: bytes) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        import struct

        payload = kind + data
        crc = zlib.crc32(payload) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + payload + struct.pack(">I", crc)

    import struct

    raw = b"".join(
        b"\x00" + rgb[row * width * 3 : (row + 1) * width * 3]
        for row in range(height)
    )
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _color_for_element(element: dict[str, Any]) -> tuple[int, int, int]:
    if element.get("visibility") not in {None, "visible"}:
        return (120, 120, 120)
    element_type = element.get("element_type")
    if str(element_type).startswith("text_"):
        return (0, 96, 192)
    if element_type == "image":
        return (200, 80, 0)
    if element_type == "vector":
        return (0, 150, 70)
    if element_type in {"link", "annotation", "form_widget"}:
        return (120, 60, 200)
    return (0, 0, 0)


def _elements_without_geometry(scenes: list[dict[str, Any]]) -> int:
    return sum(
        1
        for scene in scenes
        for element in scene.get("elements", [])
        if element.get("bounding_box") is None
    )


def _elements_without_order(scenes: list[dict[str, Any]]) -> int:
    return sum(
        1
        for scene in scenes
        for element in scene.get("elements", [])
        if element.get("scene_order") is None
    )


def _page_elements(
    scene: dict[str, Any],
    diagnostic_context: dict[str, Any],
) -> dict[str, Any]:
    elements = [
        _diagnostic_element(item, diagnostic_context) for item in scene.get("elements", [])
    ]
    return {
        "page_id": scene.get("page_id"),
        "page_index": scene.get("page_index"),
        "geometry": scene.get("geometry", {}),
        "elements": elements,
        "relations": scene.get("relations", []),
        "warnings": scene.get("warnings", []),
        "limitations": scene.get("limitations", []),
        "statistics": {
            "element_count": len(elements),
            "text_count": sum(1 for item in elements if item["kind"] == "text"),
            "image_count": sum(1 for item in elements if item["kind"] == "image"),
            "vector_count": sum(1 for item in elements if item["kind"] == "vector"),
            "without_geometry": sum(1 for item in elements if item["bounding_box"] is None),
            "without_order": sum(1 for item in elements if item["scene_order"] is None),
        },
    }


def _diagnostic_element(
    element: dict[str, Any],
    diagnostic_context: dict[str, Any],
) -> dict[str, Any]:
    keys = (
        "element_id",
        "element_type",
        "page_id",
        "bounding_box",
        "quad",
        "polygon",
        "path",
        "local_transform",
        "effective_transform",
        "paint_order",
        "scene_order",
        "order_method",
        "order_confidence",
        "visibility",
        "opacity",
        "blend_mode",
        "clip_reference",
        "layer_reference",
        "parent_reference",
        "resource_references",
        "source_references",
        "fidelity",
        "editability",
        "editability_hint",
        "warnings",
        "limitations",
        "provenance",
        "text",
        "raw_text",
        "display_text",
        "normalized_text",
        "unicode_text",
        "font_reference",
        "style_reference",
        "baseline_reference",
        "direction",
        "writing_mode",
        "image_resource_id",
        "occurrence_id",
        "vector_path_id",
    )
    diagnostic = {key: element.get(key) for key in keys if key in element}
    diagnostic.setdefault("element_id", "not_available")
    diagnostic.setdefault("element_type", "unknown")
    diagnostic.setdefault("bounding_box", None)
    diagnostic.setdefault("scene_order", None)
    diagnostic.setdefault("visibility", "unknown")
    diagnostic["kind"] = _element_kind(diagnostic.get("element_type"))
    diagnostic["resources"] = _element_resources(diagnostic)
    _enrich_element_from_context(diagnostic, diagnostic_context)
    diagnostic["text_level"] = _text_level(diagnostic.get("element_type"))
    diagnostic["selection_priority"] = _selection_priority(diagnostic)
    diagnostic["display_label"] = _display_label(diagnostic)
    diagnostic["short_id"] = _short_id(str(diagnostic["element_id"]))
    diagnostic["search_text"] = _search_text(diagnostic)
    return diagnostic


def _enrich_element_from_context(
    element: dict[str, Any],
    diagnostic_context: dict[str, Any],
) -> None:
    if element.get("kind") != "text":
        return
    text_index = diagnostic_context.get("text_by_source_id", {})
    source_ids = [
        str(source.get("source_element_id"))
        for source in element.get("source_references", [])
        if isinstance(source, dict) and source.get("source_element_id")
    ]
    text_data = next((text_index[item] for item in source_ids if item in text_index), None)
    if text_data is None:
        return
    element.update({key: value for key, value in text_data.items() if value is not None})
    value = text_data.get("display_text")
    if value:
        element["display_text"] = value
        element["text"] = value


def _text_level(element_type: object) -> str | None:
    value = str(element_type or "")
    if value.startswith("text_"):
        return value.removeprefix("text_")
    if value in {"glyph", "word", "span", "line", "block"}:
        return value
    return None


def _selection_priority(element: dict[str, Any]) -> int:
    element_type = str(element.get("element_type") or "")
    priorities = {
        "text_word": 90,
        "text_span": 80,
        "text_line": 70,
        "text_block": 60,
        "image": 55,
        "vector": 50,
        "clipping_path": 45,
        "link": 85,
        "annotation": 84,
        "form_widget": 83,
        "text_glyph": 20,
    }
    return priorities.get(element_type, 10)


def _display_label(element: dict[str, Any]) -> str:
    kind = str(element.get("kind"))
    if kind == "text":
        value = _compact_text(element.get("display_text") or element.get("text"))
        level = element.get("text_level") or "text"
        return f'"{value}" | {level}' if value else f"{level} | {_short_id(element['element_id'])}"
    if kind == "image":
        resource = next(iter(element.get("resources", [])), None)
        suffix = f" | {resource}" if resource else ""
        return f"Imagem{suffix}"
    if kind == "vector":
        resource = next(iter(element.get("resources", [])), None)
        suffix = f" | {resource}" if resource else ""
        return f"Vetor{suffix}"
    return f"{element.get('element_type', 'element')} | {_short_id(element['element_id'])}"


def _compact_text(value: object, *, limit: int = 80) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _short_id(value: object) -> str:
    text = str(value)
    if len(text) <= 32:
        return text
    return f"{text[:14]}...{text[-14:]}"


def _search_text(element: dict[str, Any]) -> str:
    parts = [
        element.get("element_id"),
        element.get("element_type"),
        element.get("kind"),
        element.get("display_text"),
        element.get("normalized_text"),
        element.get("font_reference"),
        element.get("style_reference"),
        " ".join(str(item) for item in element.get("resources", [])),
    ]
    return " ".join(str(part) for part in parts if part).lower()


def _element_kind(element_type: object) -> str:
    value = str(element_type or "")
    if value.startswith("text") or value in {"glyph", "word", "span", "line", "block"}:
        return "text"
    if "image" in value:
        return "image"
    if value in {"vector", "path", "shape"} or "vector" in value:
        return "vector"
    if value in {"link", "annotation", "widget", "form_widget"}:
        return "interactive"
    if "clip" in value:
        return "clipping"
    return "other"


def _element_resources(element: dict[str, Any]) -> list[str]:
    resources: list[str] = []
    raw = element.get("resource_references")
    if isinstance(raw, list):
        resources.extend(str(item) for item in raw)
    for key in ("font_reference", "image_resource_id", "resource_id"):
        value = element.get(key)
        if value is not None:
            resources.append(str(value))
    return sorted(set(resources))


def _structural_findings(
    report: dict[str, Any],
    native_scene: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not report.get("document_id"):
        findings.append(_finding("diagnostics.document_id_missing", "error"))
    if not report.get("source_hash"):
        findings.append(_finding("diagnostics.source_hash_missing", "error"))
    if native_scene is None:
        findings.append(_finding("diagnostics.native_scene_missing", "error"))
        return findings
    element_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    missing_provenance = 0
    for scene in native_scene.get("scenes", []):
        for element in scene.get("elements", []):
            element_id = str(element.get("element_id", ""))
            if not element_id:
                findings.append(_finding("diagnostics.element_id_missing", "error"))
            elif element_id in element_ids:
                duplicate_ids.add(element_id)
            else:
                element_ids.add(element_id)
            if element.get("provenance") is None and element.get("source_references") is None:
                missing_provenance += 1
    if duplicate_ids:
        findings.append(
            _finding(
                "diagnostics.duplicate_element_ids",
                "error",
                message=f"{len(duplicate_ids)} duplicate element id(s)",
            )
        )
    if report.get("elements_without_geometry"):
        findings.append(_finding("diagnostics.elements_without_geometry", "warning"))
    if report.get("elements_without_order"):
        findings.append(_finding("diagnostics.elements_without_order", "warning"))
    if missing_provenance:
        findings.append(
            _finding(
                "diagnostics.elements_without_provenance",
                "warning",
                message=f"{missing_provenance} element(s) without explicit provenance",
            )
        )
    return findings


def _finding(
    code: str,
    severity: str,
    *,
    message: str | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "scope": "document",
        "message": message or code,
    }


def _assessment_template(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "diagnostic_run_id": report.get("diagnostic_run_id"),
        "document_id": report.get("document_id"),
        "source_hash": report.get("source_hash"),
        "artifact_version": "not_available",
        "producer_version": "not_available",
        "status": "needs_investigation",
        "dimensions": _manual_template()["dimensions"],
        "page_assessments": [],
        "element_assessments": [],
        "finding_assessments": [],
        "warning_assessments": [],
        "notes": "",
        "reviewer": "",
        "created_at": None,
    }


def _document_index(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "document_id": report.get("document_id"),
        "filename": report.get("filename"),
        "source_hash": report.get("source_hash"),
        "latest_run_id": report.get("diagnostic_run_id"),
        "latest_status": report.get("state"),
    }


def _comparison_from_history(
    history_path: Path,
    report: dict[str, Any],
) -> dict[str, Any]:
    history = _read_json(history_path, {"runs": []})
    current_hash = report.get("source_hash")
    previous = next(
        (
            item
            for item in reversed(history.get("runs", []))
            if item.get("source_hash") == current_hash
        ),
        None,
    )
    fields = (
        "page_count",
        "element_count",
        "text_count",
        "image_count",
        "vector_count",
        "warning_count",
        "limitation_count",
        "finding_count",
    )
    if previous is None:
        return {"baseline": None, "differences": []}
    differences = []
    for field_name in fields:
        before = previous.get(field_name)
        after = report.get(field_name)
        if before != after:
            differences.append({"field": field_name, "before": before, "after": after})
    return {
        "baseline": previous.get("diagnostic_run_id"),
        "current": report.get("diagnostic_run_id"),
        "differences": differences,
    }


def _write_history(path: Path, result: PDFValidationBatchResult) -> None:
    history = _read_json(path, {"runs": []})
    runs = list(history.get("runs", []))
    for document in result.documents:
        item = document.to_dict()
        item["profile"] = result.profile
        runs.append(item)
    _write_json(path, {"runs": runs})


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _source_hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _diagnostic_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    return f"run_{stamp}_{uuid4().hex[:8]}"


def _document_root(
    output: Path,
    document: Path,
    *,
    temporary_mode: bool,
) -> Path:
    if not temporary_mode:
        return output / "documents" / _slug(document.stem)
    slug = _slug(document.stem)
    digest = sha256(str(document).encode("utf-8")).hexdigest()[:8]
    return output / "d" / f"{slug[:12]}-{digest}"


def _document_run_directory(
    document_root: Path,
    diagnostic_run_id: str,
    *,
    temporary_mode: bool,
) -> Path:
    if not temporary_mode:
        return document_root / "runs" / diagnostic_run_id
    return document_root / "r" / diagnostic_run_id.rsplit("_", maxsplit=1)[-1]


def _manual_template() -> dict[str, Any]:
    return to_jsonable(PDFManualEvaluationTemplate())


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(to_jsonable(value), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)


def _write_html(path: Path, title: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    style = """
:root {
  color-scheme: light;
  --bg: #f4f6f8;
  --surface: #fff;
  --surface-alt: #f9fafb;
  --line: #d8dee7;
  --line-soft: #e7ebf0;
  --text: #17212b;
  --muted: #617283;
  --accent: #087f8c;
  --accent-strong: #066773;
  --danger: #c83232;
  --warn: #b06b00;
  --focus: #1f6fb2;
  --shadow: 0 1px 2px rgba(16, 24, 40, .08);
}
* {
  box-sizing: border-box;
}
body {
  font-family: Inter, Segoe UI, Arial, sans-serif;
  margin: 0;
  color: var(--text);
  background: var(--bg);
  font-size: 14px;
  line-height: 1.45;
}
h1 {
  margin: 0;
  padding: 14px 20px 10px;
  font-size: 18px;
  font-weight: 700;
  background: #101820;
  color: #fff;
  border-bottom: 1px solid #243241;
  letter-spacing: 0;
}
h2 {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 700;
  color: #26323f;
}
table {
  border-collapse: collapse;
  width: 100%;
  font-size: 13px;
}
td,
th {
  border: 1px solid var(--line);
  padding: 7px 8px;
  text-align: left;
  vertical-align: top;
}
th {
  background: var(--surface-alt);
  color: #26323f;
  font-weight: 700;
}
code {
  background: #eef2f7;
  border: 1px solid #dde5ef;
  border-radius: 5px;
  padding: 1px 4px;
}
button,
select,
input,
textarea {
  font: inherit;
  color: var(--text);
}
button {
  border: 1px solid #b8c4d0;
  background: linear-gradient(#fff, #f5f7fa);
  padding: 7px 10px;
  border-radius: 6px;
  cursor: pointer;
  box-shadow: var(--shadow);
}
button:hover {
  border-color: #8394a6;
  background: #fff;
}
button:active {
  transform: translateY(1px);
}
button:focus-visible,
select:focus-visible,
input:focus-visible,
textarea:focus-visible {
  outline: 2px solid var(--focus);
  outline-offset: 1px;
}
select,
input,
textarea {
  border: 1px solid #b8c4d0;
  background: #fff;
  border-radius: 6px;
  padding: 7px 8px;
  min-height: 32px;
}
textarea {
  display: block;
  width: 100%;
  resize: vertical;
}
input[type="checkbox"] {
  min-height: 0;
  width: 14px;
  height: 14px;
  margin-right: 6px;
  vertical-align: -2px;
}
input[type="range"] {
  padding: 0;
  min-height: 0;
  vertical-align: middle;
}
label {
  display: block;
  margin: 7px 0;
  color: #344252;
}
label select,
label input:not([type="checkbox"]) {
  width: 100%;
  margin-top: 4px;
}
.top {
  padding: 12px 20px 14px;
  border-bottom: 1px solid #cfd7e2;
  background: #fff;
  box-shadow: 0 1px 3px rgba(16, 24, 40, .06);
  position: sticky;
  top: 0;
  z-index: 20;
}
.top strong {
  font-size: 15px;
}
.layout {
  display: grid;
  grid-template-columns: 280px minmax(480px, 1fr) 380px;
  min-height: calc(100vh - 92px);
}
.pane {
  height: calc(100vh - 92px);
  overflow: auto;
  border-right: 1px solid var(--line);
  background: #fff;
}
.pane:last-child {
  border-right: 0;
  border-left: 1px solid var(--line);
}
.section {
  padding: 14px 16px;
  border-bottom: 1px solid var(--line-soft);
}
.section:empty {
  display: none;
}
.viewer {
  padding: 14px;
  display: grid;
  gap: 12px;
  background: #edf1f5;
}
.viewer > .section {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: var(--shadow);
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.viewer > .section label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: 0;
}
.viewer > .section label select,
.viewer > .section label input {
  width: auto;
  margin-top: 0;
}
.layout.left-collapsed {
  grid-template-columns: 0 minmax(480px, 1fr) 380px;
}
.layout.right-collapsed {
  grid-template-columns: 280px minmax(480px, 1fr) 0;
}
.layout.left-collapsed.right-collapsed {
  grid-template-columns: 0 minmax(480px, 1fr) 0;
}
.layout.left-collapsed > aside:first-child,
.layout.right-collapsed > aside:last-child {
  overflow: hidden;
  padding: 0;
  border: 0;
}
.view {
  background: #fff;
  border: 1px solid #c9d2dd;
  border-radius: 8px;
  min-height: 240px;
  overflow: auto;
  box-shadow: var(--shadow);
}
.stage {
  position: relative;
  display: inline-block;
  line-height: 0;
  background: #fff;
}
.stage img {
  display: block;
  max-width: none;
}
.stage svg {
  position: absolute;
  left: 0;
  top: 0;
}
.pdf-page-preview {
  position: relative;
  z-index: 1;
  image-rendering: auto;
}
.interactive-elements-layer {
  z-index: 2;
  pointer-events: none;
}
.hover-layer {
  z-index: 3;
  pointer-events: none;
}
.selection-layer {
  z-index: 4;
  pointer-events: none;
}
.temporary-labels-layer {
  z-index: 5;
  pointer-events: none;
}
.hit-layer {
  z-index: 6;
  cursor: crosshair;
  pointer-events: all;
}
.hidden {
  display: none;
}
.list button {
  display: block;
  width: 100%;
  text-align: left;
  margin: 0;
  padding: 8px 10px;
  border: 0;
  border-bottom: 1px solid var(--line-soft);
  border-radius: 0;
  background: #fff;
  box-shadow: none;
  min-height: 40px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.list button:hover {
  background: #f3f7fa;
  border-color: var(--line-soft);
}
.list button.selected {
  background: #e8f6f7;
  border-left: 4px solid var(--accent);
  padding-left: 6px;
}
.list-scroll {
  height: 300px;
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
  box-shadow: inset 0 1px 2px rgba(16, 24, 40, .04);
}
.row {
  height: 48px;
  box-sizing: border-box;
  overflow: hidden;
}
.selected {
  outline: 2px solid var(--danger);
  outline-offset: 1px;
}
.muted {
  color: var(--muted);
  font-size: 12px;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}
.chip {
  border: 1px solid #c8d1dc;
  border-radius: 999px;
  padding: 4px 8px;
  background: #f9fbfd;
  font-size: 12px;
  color: #2f3b48;
}
.candidate {
  border-color: #e2a2a2;
  background: #fff6f2;
}
.value-box {
  font-size: 18px;
  line-height: 1.35;
  background: #eefaf9;
  border: 1px solid #afd7d7;
  border-left: 4px solid var(--accent);
  border-radius: 8px;
  padding: 12px;
  white-space: pre-wrap;
  word-break: break-word;
}
.toolbar-group {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  padding: 4px;
  border: 1px solid var(--line-soft);
  border-radius: 8px;
  background: #f8fafc;
}
.button-subtle {
  box-shadow: none;
  background: #fff;
}
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 1px solid #c8d1dc;
  border-radius: 999px;
  padding: 4px 8px;
  color: #2f3b48;
  background: #fff;
  font-size: 12px;
}
.tabs {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
  margin-bottom: 10px;
  border-bottom: 1px solid var(--line);
}
.tabs button {
  box-shadow: none;
  border: 0;
  border-bottom: 2px solid transparent;
  border-radius: 0;
  background: transparent;
  padding: 7px 8px;
  color: #465668;
}
.tabs button[aria-selected="true"] {
  background: transparent;
  color: var(--accent-strong);
  border-bottom-color: var(--accent);
  font-weight: 700;
}
.tab-panel {
  display: none;
}
.tab-panel.active {
  display: block;
}
pre {
  white-space: pre-wrap;
  background: #111827;
  color: #e8eef7;
  padding: 12px;
  border-radius: 8px;
  overflow: auto;
  font-size: 12px;
  line-height: 1.5;
}
#candidate-panel {
  border-color: #e6c48b;
  background: #fffaf0;
}
#candidate-panel strong {
  color: #6d4500;
}
#visible-count {
  font-weight: 700;
  color: var(--accent-strong);
}
#resource-panel button,
#finding-panel button {
  font-size: 12px;
}
@media (max-width: 1100px) {
  .layout {
    grid-template-columns: 1fr;
  }
  .pane {
    height: auto;
  }
  .top {
    position: static;
  }
}
"""
    path.write_text(
        (
            "<!doctype html><html><head><meta charset=\"utf-8\">"
            f"<title>{_html_escape(title)}</title>"
            f"<style>{style}</style></head><body>"
            f"<h1>{_html_escape(title)}</h1>{body}</body></html>"
        ),
        encoding="utf-8",
    )


def _lab_data(
    report: dict[str, Any],
    native_scene: dict[str, Any] | None,
    diagnostic_context: dict[str, Any],
    *,
    temporary_mode: bool = False,
) -> dict[str, Any]:
    pages = []
    resources: dict[str, list[str]] = {}
    for scene in (native_scene or {}).get("scenes", []):
        page_number = int(scene.get("page_index", 0)) + 1
        prefix = f"page-{page_number:03d}"
        elements = [
            _diagnostic_element(item, diagnostic_context)
            for item in scene.get("elements", [])
        ]
        for element in elements:
            for resource in element.get("resources", []):
                resources.setdefault(resource, []).append(str(element["element_id"]))
        pages.append(
            {
                "page_id": scene.get("page_id"),
                "page_index": scene.get("page_index"),
                "geometry": scene.get("geometry", {}),
                "original": f"pages/{prefix}-original.png",
                "previews": {
                    "standard": f"pages/{prefix}-original-standard.png",
                    "high": f"pages/{prefix}-original-high.png",
                    "ultra": f"pages/{prefix}-original-ultra.png",
                },
                "overlay": f"pages/{prefix}-overlay.png",
                "elements_json": f"pages/{prefix}-elements.json",
                "elements": elements,
                "warnings": scene.get("warnings", []),
                "limitations": scene.get("limitations", []),
            }
        )
    return {
        "report": {
            key: value
            for key, value in report.items()
            if key not in {"warnings", "limitations", "findings"}
        }
        | {"temporary_mode": temporary_mode},
        "warnings": report.get("warnings", []),
        "limitations": report.get("limitations", []),
        "findings": report.get("findings", []),
        "pages": pages,
        "resources": resources,
        "manual_template": _assessment_template(report),
    }


def _document_lab_html(report: dict[str, Any], lab_data: dict[str, Any]) -> str:
    data = json.dumps(lab_data, ensure_ascii=False).replace("</", "<\\/")
    summary = _summary_cards(report)
    return f"""
<div class="top">
  <div><strong>{_html_escape(str(report.get("filename", "document")))}</strong></div>
  <div class="muted">Run: {report.get("diagnostic_run_id")} | Status: {report.get("state")}</div>
  <div class="chips">{summary}</div>
</div>
<div class="layout">
  <aside class="pane">
    <div class="section">
      <label>Pagina <select id="page-select"></select></label>
    </div>
    <div class="section">
      <div class="muted">Filtros</div>
      <label>Buscar <input id="search-input" placeholder="texto, ID, recurso"></label><br>
      <label>Granularidade textual
        <select id="text-granularity">
          <option value="block">bloco</option>
          <option value="line">linha</option>
          <option value="span">span</option>
          <option value="word" selected>palavra</option>
          <option value="glyph">glifo</option>
          <option value="all">todos</option>
        </select>
      </label><br>
      <label><input type="checkbox" data-kind="text" checked> texto</label><br>
      <label><input type="checkbox" data-kind="image" checked> imagens</label><br>
      <label><input type="checkbox" data-kind="vector" checked> vetores</label><br>
      <label><input type="checkbox" data-kind="interactive" checked> interativos</label><br>
      <label><input type="checkbox" data-kind="clipping" checked> clipping</label><br>
      <label><input type="checkbox" data-kind="other" checked> outros</label><br>
      <div class="muted">Niveis de texto</div>
      <label><input type="checkbox" data-text-level="block" checked> blocos</label><br>
      <label><input type="checkbox" data-text-level="line" checked> linhas</label><br>
      <label><input type="checkbox" data-text-level="span" checked> spans</label><br>
      <label><input type="checkbox" data-text-level="word" checked> palavras</label><br>
      <label><input type="checkbox" data-text-level="glyph"> glifos</label><br>
      <label><input id="visible-only" type="checkbox" checked> apenas visiveis</label><br>
      <label><input id="show-warnings" type="checkbox"> warnings</label><br>
      <label><input id="show-limitations" type="checkbox"> limitacoes</label><br>
      <label>ID <input id="id-filter" placeholder="elemento ou recurso"></label>
    </div>
    <div class="section">
      <div><strong>Elementos visiveis</strong> <span id="visible-count"></span></div>
      <div id="element-list" class="list list-scroll"></div>
      <div id="virtual-status" class="muted"></div>
    </div>
  </aside>
  <main class="pane viewer">
    <div class="section">
      <div class="toolbar-group">
        <button id="toggle-left" class="button-subtle">Navegacao</button>
        <button id="toggle-right" class="button-subtle">Painel</button>
      </div>
      <div class="toolbar-group">
        <button id="previous-page">Pagina anterior</button>
        <button id="next-page">Proxima pagina</button>
      </div>
      <label>Exibicao
        <select id="layer-mode">
          <option value="clean" selected>limpo</option>
          <option value="selection">selecao</option>
          <option value="light">diagnostico leve</option>
          <option value="full">diagnostico completo</option>
        </select>
      </label>
      <label>Labels
        <select id="label-mode">
          <option value="never">nunca</option>
          <option value="hover">somente hover</option>
          <option value="selection" selected>somente selecao</option>
          <option value="always">sempre</option>
        </select>
      </label>
      <label>Selecionar por
        <select id="selection-mode">
          <option value="auto" selected>automatico</option>
          <option value="block">bloco</option>
          <option value="line">linha</option>
          <option value="span">span</option>
          <option value="word">palavra</option>
          <option value="entity">entidade candidata</option>
          <option value="manual">multisselecao manual</option>
        </select>
      </label>
      <label>Qualidade
        <select id="preview-quality">
          <option value="standard">standard</option>
          <option value="high" selected>high</option>
          <option value="ultra">ultra</option>
        </select>
      </label>
      <button id="zoom-out">-</button>
      <label>Zoom <input id="zoom" type="range" min="40" max="200" value="100"></label>
      <button id="zoom-in">+</button>
      <button id="zoom-100">100%</button>
      <button id="fit-width">Ajustar largura</button>
      <button id="fit-page">Ajustar pagina</button>
      <button id="center-selection">Centralizar</button>
      <button id="expand-line">Expandir linha</button>
      <button id="clear-selection">Limpar selecao</button>
      <button id="undo-composite">Desfazer item</button>
      <label>Intensidade
        <input id="layer-intensity" type="range" min="0" max="100" value="28">
      </label>
      <span id="preview-quality-status" class="status-pill">preview: high</span>
    </div>
    <div id="candidate-panel" class="section hidden"></div>
    <div class="view" id="page-view">
      <div id="original-stage" class="stage pdf-page-viewport"></div>
    </div>
  </main>
  <aside class="pane">
    <div class="section">
      <h2>Valor extraido</h2>
      <div id="value-panel" class="value-box">Selecione um elemento.</div>
      <button id="copy-value">Copiar valor</button>
      <button id="copy-id">Copiar ID</button>
    </div>
    <div class="section">
      <h2>Inspecao</h2>
      <div class="tabs" id="property-tabs">
        <button data-tab="summary" aria-selected="true">Resumo</button>
        <button data-tab="geometry">Geometria</button>
        <button data-tab="style">Estilo</button>
        <button data-tab="resources">Recursos</button>
        <button data-tab="origin">Origem</button>
        <button data-tab="warnings">Warnings</button>
        <button data-tab="json">JSON</button>
      </div>
      <div id="tab-summary" class="tab-panel active"></div>
      <div id="tab-geometry" class="tab-panel"></div>
      <div id="tab-style" class="tab-panel"></div>
      <div id="tab-resources" class="tab-panel"></div>
      <div id="tab-origin" class="tab-panel"></div>
      <div id="tab-warnings" class="tab-panel"></div>
      <pre id="tab-json" class="tab-panel">Selecione um elemento.</pre>
    </div>
    <div class="section">
      <h2>Texto</h2>
      <div id="text-panel" class="list list-scroll"></div>
    </div>
    <div class="section">
      <h2>Imagens</h2>
      <div id="image-panel" class="list list-scroll"></div>
    </div>
    <div class="section">
      <h2>Vetores</h2>
      <div id="vector-panel" class="list list-scroll"></div>
    </div>
    <div class="section">
      <h2>Recursos</h2>
      <div id="resource-panel" class="list"></div>
    </div>
    <div class="section">
      <h2>Warnings e achados</h2>
      <div id="finding-panel" class="list"></div>
    </div>
    <div class="section">
      <h2>Avaliacao manual</h2>
      <label>Status <select id="assessment-status">
        <option>approved</option>
        <option>approved_with_limitations</option>
        <option selected>needs_investigation</option>
        <option>failed</option>
      </select></label>
      <textarea id="assessment-notes" rows="4" placeholder="Comentario"></textarea>
      <input id="assessment-reviewer" placeholder="Responsavel">
      <button id="save-assessment">Salvar avaliacao local</button>
      <pre id="assessment-history"></pre>
    </div>
  </aside>
</div>
<script id="lab-data" type="application/json">{data}</script>
<script>{_lab_script()}</script>
"""


def _summary_cards(report: dict[str, Any]) -> str:
    fields = (
        ("pages", "page_count"),
        ("elements", "element_count"),
        ("text", "text_count"),
        ("images", "image_count"),
        ("vectors", "vector_count"),
        ("warnings", "warning_count"),
        ("limitations", "limitation_count"),
        ("findings", "finding_count"),
    )
    return "".join(
        f"<span class=\"chip\">{label}: {_html_escape(str(report.get(key, 0)))}</span>"
        for label, key in fields
    )


def _lab_script() -> str:
    return r"""
const data = JSON.parse(document.getElementById("lab-data").textContent);
const state = {
  pageIndex: 0,
  selectedId: null,
  selectedIds: [],
  hoverId: null,
  visibleElements: [],
  candidates: [],
  candidateIndex: 0,
  lastHitKey: "",
  previewCache: {},
  previewToken: 0,
};
const $ = (id) => document.getElementById(id);
const kindChecks = () => [...document.querySelectorAll("[data-kind]")];
const textLevelChecks = () => [...document.querySelectorAll("[data-text-level]")];
const html = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;");
const compact = (value, limit = 90) => {
  const text = String(value ?? "").replace(/\s+/g, " ").trim();
  return text.length > limit ? text.slice(0, limit - 3) + "..." : text;
};
const fillSelect = () => {
  $("page-select").innerHTML = data.pages.map((p, i) =>
    `<option value="${i}">Pagina ${i + 1}</option>`).join("");
};
const bboxStyle = (el) => {
  const colors = {text:"#0b66c3", image:"#c75400", vector:"#008f56",
    interactive:"#764abc", clipping:"#52616f", other:"#111827"};
  return colors[el.kind] || colors.other;
};
const currentPage = () => data.pages[state.pageIndex] || {elements: [], geometry: {}};
const pageSize = (page) => {
  const size = (page.geometry && page.geometry.size) || page.geometry || {};
  return {width: Math.round(size.width || 612), height: Math.round(size.height || 792)};
};
const previewPath = (page, quality) => {
  const previews = page.previews || {};
  return previews[quality] || page.original;
};
class PreviewRenderManager {
  resolveQuality(page, zoom) {
    const selected = $("preview-quality").value;
    if (zoom >= 1.6) return "ultra";
    if (zoom >= 1.15 && selected === "standard") return "high";
    return selected;
  }
  apply(img, page, zoom) {
    const quality = this.resolveQuality(page, zoom);
    const path = previewPath(page, quality);
    const cacheKey = `${state.pageIndex}:${quality}`;
    const token = ++state.previewToken;
    $("preview-quality-status").textContent = `preview: ${quality}`;
    img.dataset.quality = quality;
    if (state.previewCache[cacheKey]) {
      img.src = path;
      return;
    }
    const loader = new Image();
    loader.onload = () => {
      state.previewCache[cacheKey] = true;
      if (token === state.previewToken) img.src = path;
    };
    loader.src = path;
    img.src = path;
  }
}
const previewRenderManager = new PreviewRenderManager();
const textLevel = (el) => el.text_level || String(el.element_type || "").replace("text_", "");
const elementArea = (el) => {
  const b = el.bounding_box;
  if (!b) return Number.MAX_SAFE_INTEGER;
  return Math.max(1, b.x_max - b.x_min) * Math.max(1, b.y_max - b.y_min);
};
class PageViewportTransform {
  constructor(page, stage) {
    this.page = page;
    this.stage = stage;
    this.size = pageSize(page);
  }
  pointerToCanonical(event) {
    const rect = this.stage.getBoundingClientRect();
    const x = (event.clientX - rect.left) * this.size.width / rect.width;
    const y = (event.clientY - rect.top) * this.size.height / rect.height;
    return this.applyRotation(x, y);
  }
  minimumHitPadding() {
    const rect = this.stage.getBoundingClientRect();
    const xPad = 8 * this.size.width / Math.max(1, rect.width);
    const yPad = 8 * this.size.height / Math.max(1, rect.height);
    return {x: xPad, y: yPad};
  }
  applyRotation(x, y) {
    const raw = this.page.geometry?.rotation?.degrees || 0;
    const rotation = ((Math.round(raw) % 360) + 360) % 360;
    if (rotation === 90) return {x: y, y: this.size.width - x};
    if (rotation === 180) return {x: this.size.width - x, y: this.size.height - y};
    if (rotation === 270) return {x: this.size.height - y, y: x};
    return {x, y};
  }
}
const DiagnosticViewportTransform = PageViewportTransform;
class DiagnosticHitTestEngine {
  hitTest(point, elements, transform) {
    const pad = transform.minimumHitPadding();
    const candidates = elements.filter(el => this.contains(el, point, pad));
    candidates.sort((a, b) => {
      const priority = (b.selection_priority || 0) - (a.selection_priority || 0);
      if (priority !== 0) return priority;
      const area = elementArea(a) - elementArea(b);
      if (area !== 0) return area;
      return (b.scene_order || 0) - (a.scene_order || 0);
    });
    return {
      point,
      candidate_element_ids: candidates.map(el => el.element_id),
      selected_element_id: candidates[0]?.element_id || null,
      selection_reason: candidates.length ? "filtered_hit_test" : "no_candidate",
      candidates,
    };
  }
  contains(el, point, pad) {
    const b = el.bounding_box;
    if (!b) return false;
    return point.x >= b.x_min - pad.x && point.x <= b.x_max + pad.x
      && point.y >= b.y_min - pad.y && point.y <= b.y_max + pad.y;
  }
}
class DiagnosticSelectionStore {
  select(id, candidates = []) {
    state.selectedId = id;
    state.selectedIds = id ? [id] : [];
    state.candidates = candidates;
    state.candidateIndex = Math.max(0, candidates.findIndex(el => el.element_id === id));
  }
  clear() {
    state.selectedId = null;
    state.selectedIds = [];
    state.candidates = [];
    state.candidateIndex = 0;
    render();
    renderInspector(null);
  }
  cycle(delta) {
    if (!state.candidates.length) return;
    const size = state.candidates.length;
    state.candidateIndex = (state.candidateIndex + delta + size) % size;
    selectElement(state.candidates[state.candidateIndex].element_id, {center: false});
  }
}
const hitTestEngine = new DiagnosticHitTestEngine();
const selectionStore = new DiagnosticSelectionStore();
const filterElements = () => {
  const enabled = new Set(kindChecks().filter(c => c.checked).map(c => c.dataset.kind));
  const enabledTextLevels = new Set(
    textLevelChecks().filter(c => c.checked).map(c => c.dataset.textLevel)
  );
  const idNeedle = $("id-filter").value.trim().toLowerCase();
  const query = $("search-input").value.trim().toLowerCase();
  const granularity = $("text-granularity").value;
  const visibleOnly = $("visible-only").checked;
  state.visibleElements = currentPage().elements.filter(el => {
    if (!enabled.has(el.kind)) return false;
    if (visibleOnly && el.visibility !== "visible") return false;
    if (el.kind === "text" && !enabledTextLevels.has(textLevel(el))) return false;
    if (el.kind === "text" && granularity !== "all" && textLevel(el) !== granularity) {
      return false;
    }
    if (idNeedle && !String(el.search_text || JSON.stringify(el)).includes(idNeedle)) {
      return false;
    }
    if (query && !String(el.search_text || JSON.stringify(el)).includes(query)) {
      return false;
    }
    return true;
  });
  if (!state.visibleElements.some(el => el.element_id === state.hoverId)) {
    state.hoverId = null;
  }
};
const layerMode = () => $("layer-mode").value;
const layerIntensity = () => Number($("layer-intensity").value) / 100;
const renderStage = (stageId) => {
  const page = currentPage();
  const size = pageSize(page);
  const zoom = Number($("zoom").value) / 100;
  const stage = $(stageId);
  const mode = layerMode();
  stage.innerHTML = "";
  stage.style.width = `${size.width * zoom}px`;
  stage.style.height = `${size.height * zoom}px`;
  const image = document.createElement("img");
  image.className = "pdf-page-preview";
  image.width = size.width * zoom;
  image.alt = `Pagina ${state.pageIndex + 1}`;
  previewRenderManager.apply(image, page, zoom);
  stage.appendChild(image);
  const visual = svgLayer("interactive-elements-layer", size, zoom);
  const hover = svgLayer("hover-layer", size, zoom);
  const selection = svgLayer("selection-layer", size, zoom);
  const labels = svgLayer("temporary-labels-layer", size, zoom);
  const hit = svgLayer("hit-layer", size, zoom);
  if (mode === "light" || mode === "full") {
    state.visibleElements.forEach(el => {
      if (!el.bounding_box) return;
      visual.appendChild(elementShape(el, false));
      appendLabel(labels, el, "always");
    });
  }
  const hovered = hoverElement();
  if (hovered?.bounding_box) {
    hover.appendChild(hoverShape(hovered));
    appendLabel(labels, hovered, "hover");
  }
  const selected = selectedElement();
  compositeElements().forEach(el => {
    if (el?.bounding_box) selection.appendChild(selectionShape(el));
  });
  if (selected?.bounding_box) {
    selection.appendChild(selectionShape(selected));
    appendLabel(labels, selected, "selection");
  }
  const hitRect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  hitRect.setAttribute("x", 0);
  hitRect.setAttribute("y", 0);
  hitRect.setAttribute("width", size.width);
  hitRect.setAttribute("height", size.height);
  hitRect.setAttribute("fill", "transparent");
  hitRect.setAttribute("pointer-events", "all");
  hitRect.addEventListener("click", event => handlePageClick(event, stage));
  hitRect.addEventListener("mousemove", event => handlePageHover(event, stage));
  hitRect.addEventListener("mouseleave", () => {
    if (!state.hoverId) return;
    state.hoverId = null;
    renderViews();
  });
  hit.appendChild(hitRect);
  stage.appendChild(visual);
  stage.appendChild(hover);
  stage.appendChild(selection);
  stage.appendChild(labels);
  stage.appendChild(hit);
};
const svgLayer = (className, size, zoom) => {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", className);
  svg.setAttribute("width", size.width * zoom);
  svg.setAttribute("height", size.height * zoom);
  svg.setAttribute("viewBox", `0 0 ${size.width} ${size.height}`);
  return svg;
};
const elementShape = (el, selected) => {
  const b = el.bounding_box;
  const mode = layerMode();
  const intensity = selected ? 1 : layerIntensity();
  const r = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  r.setAttribute("x", b.x_min);
  r.setAttribute("y", b.y_min);
  r.setAttribute("width", Math.max(1, b.x_max - b.x_min));
  r.setAttribute("height", Math.max(1, b.y_max - b.y_min));
  const fillAlpha = mode === "full" ? Math.min(.22, intensity * .28)
    : mode === "light" ? Math.min(.10, intensity * .14)
    : 0;
  r.setAttribute("fill", selected ? "#d12b2b" : bboxStyle(el));
  r.setAttribute("fill-opacity", selected ? ".16" : String(fillAlpha));
  r.setAttribute("stroke", selected ? "#d12b2b" : bboxStyle(el));
  r.setAttribute("stroke-width", selected ? "2" : ".65");
  r.setAttribute("stroke-opacity", selected ? "1" : String(Math.max(.15, intensity)));
  r.setAttribute("pointer-events", "none");
  return r;
};
const selectionShape = (el) => elementShape(el, true);
const hoverShape = (el) => {
  const r = elementShape(el, true);
  r.setAttribute("stroke", "#f59e0b");
  r.setAttribute("fill", "#f59e0b");
  r.setAttribute("fill-opacity", ".10");
  return r;
};
const selectionLabel = (el) => {
  const b = el.bounding_box;
  const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
  text.setAttribute("x", b.x_min);
  text.setAttribute("y", Math.max(10, b.y_min - 4));
  text.setAttribute("font-size", "9");
  text.setAttribute("fill", "#d12b2b");
  text.textContent = compact(el.display_value || el.display_text || el.short_id, 42);
  return text;
};
const appendLabel = (layer, el, reason) => {
  const mode = $("label-mode").value;
  if (mode === "never") return;
  if (mode === "hover" && reason !== "hover") return;
  if (mode === "selection" && reason !== "selection") return;
  if (mode === "always" && layer.children.length > 200) return;
  layer.appendChild(selectionLabel(el));
};
const renderViews = () => {
  renderStage("original-stage");
};
const renderLists = () => {
  $("visible-count").textContent = `(${state.visibleElements.length})`;
  renderVirtualList($("element-list"), state.visibleElements, "element");
  panel("text-panel", currentPage().elements.filter(el => el.kind === "text"), "text");
  panel("image-panel", currentPage().elements.filter(el => el.kind === "image"), "image");
  panel("vector-panel", currentPage().elements.filter(el => el.kind === "vector"), "vector");
  renderResources();
  const findings = [...data.warnings, ...data.limitations, ...data.findings];
  $("finding-panel").innerHTML = findings.map((f, i) =>
    `<button data-i="${i}">${f.code || f.message || f}</button>`
  ).join("") || "<span class='muted'>vazio</span>";
};
const rowHtml = (el) => {
  const selectedClass = state.selectedIds.includes(el.element_id) ? "selected" : "";
  const value = html(el.display_label || el.display_text || el.short_id);
  const meta = html(`${el.element_type} | pagina ${state.pageIndex + 1}`);
  return `<button class="row ${selectedClass}" data-id="${html(el.element_id)}">`
    + `<strong>${value}</strong><br><span class="muted">${meta}</span></button>`;
};
const renderVirtualList = (container, items) => {
  const rowHeight = 48;
  const viewportRows = Math.ceil(Math.max(1, container.clientHeight) / rowHeight) + 8;
  const start = Math.max(0, Math.floor(container.scrollTop / rowHeight) - 4);
  const end = Math.min(items.length, start + viewportRows);
  const top = start * rowHeight;
  const bottom = Math.max(0, (items.length - end) * rowHeight);
  container.innerHTML = `<div style="height:${top}px"></div>`
    + items.slice(start, end).map(rowHtml).join("")
    + `<div style="height:${bottom}px"></div>`;
  container.querySelectorAll("button[data-id]").forEach(btn =>
    btn.addEventListener("click", event => {
      if (event.ctrlKey || event.metaKey || $("selection-mode").value === "manual") {
        toggleCompositeSelection(btn.dataset.id);
        return;
      }
      selectElement(btn.dataset.id, {center: true});
    }));
  if (container.id === "element-list") {
    $("virtual-status").textContent = items.length
      ? `Mostrando ${start + 1}-${end} de ${items.length}`
      : "Nenhum elemento visivel";
  }
};
const panel = (id, items, kind) => {
  const filtered = items.filter(el => kind !== "text" || $("text-granularity").value === "all"
    || textLevel(el) === $("text-granularity").value);
  renderVirtualList($(id), filtered);
};
const renderResources = () => {
  $("resource-panel").innerHTML = Object.entries(data.resources).map(([id, els]) =>
    `<button data-resource="${id}">${id} (${els.length})</button>`
  ).join("") || "<span class='muted'>vazio</span>";
  $("resource-panel").querySelectorAll("button").forEach(btn => {
    btn.addEventListener("click", () => {$("id-filter").value = btn.dataset.resource; render();});
  });
};
const handlePageClick = (event, stage) => {
  const transform = new DiagnosticViewportTransform(currentPage(), stage);
  const hit = hitTestEngine.hitTest(
    transform.pointerToCanonical(event),
    state.visibleElements,
    transform,
  );
  if (!hit.selected_element_id) return;
  const key = hit.candidate_element_ids.join("|");
  let selected = selectCandidateForMode(hit.candidates)?.element_id || hit.selected_element_id;
  if (key === state.lastHitKey && hit.candidates.length > 1) {
    const next = (state.candidateIndex + 1) % hit.candidates.length;
    selected = hit.candidates[next].element_id;
  }
  state.lastHitKey = key;
  if (event.ctrlKey || event.metaKey || $("selection-mode").value === "manual") {
    toggleCompositeSelection(selected, {candidates: hit.candidates});
    return;
  }
  selectElement(selected, {candidates: hit.candidates, center: false});
};
const selectCandidateForMode = (candidates) => {
  const mode = $("selection-mode").value;
  if (mode === "auto" || mode === "manual") return candidates[0];
  if (mode === "entity") {
    return candidates.find(el => String(el.element_type || "").includes("candidate"))
      || candidates[0];
  }
  return candidates.find(el => el.kind === "text" && textLevel(el) === mode)
    || candidates.find(el => String(el.element_type || "").includes(mode))
    || candidates[0];
};
const handlePageHover = (event, stage) => {
  const transform = new PageViewportTransform(currentPage(), stage);
  const hit = hitTestEngine.hitTest(
    transform.pointerToCanonical(event),
    state.visibleElements,
    transform,
  );
  const next = hit.selected_element_id;
  if (next === state.hoverId) return;
  state.hoverId = next;
  renderViews();
};
const selectElement = (id, options = {}) => {
  let page = currentPage();
  let el = page.elements.find(item => item.element_id === id);
  if (!el) {
    const foundPage = data.pages.findIndex(p => p.elements.some(item => item.element_id === id));
    if (foundPage >= 0) {
      state.pageIndex = foundPage;
      $("page-select").value = String(foundPage);
      page = currentPage();
      el = page.elements.find(item => item.element_id === id);
    }
  }
  if (!el) return;
  selectionStore.select(id, options.candidates || state.candidates);
  renderInspector(el);
  renderCandidatePanel(options.candidates || state.candidates);
  renderViews();
  renderLists();
  scrollListToSelection();
  if (options.center !== false) centerElement(el);
};
const toggleCompositeSelection = (id, options = {}) => {
  if (!id) return;
  const exists = state.selectedIds.includes(id);
  state.selectedIds = exists
    ? state.selectedIds.filter(item => item !== id)
    : [...state.selectedIds, id];
  state.selectedId = state.selectedIds[state.selectedIds.length - 1] || null;
  state.candidates = options.candidates || state.candidates;
  renderInspector(selectedElement());
  renderCandidatePanel(state.candidates);
  renderViews();
  renderLists();
  scrollListToSelection();
};
const sourceIds = (el) => [
  ...(el.source_references || [])
    .map(source => source.source_element_id)
    .filter(Boolean),
  ...(el.line_ids || []),
  ...(el.word_ids || []),
];
const lineKey = (el) => {
  const ids = sourceIds(el).map(String);
  const directLine = ids.find(id => id.startsWith("pdfline:"));
  if (directLine) return directLine;
  const word = ids.find(id => id.startsWith("pdfword:"));
  const match = word?.match(/^pdfword:(.+):word-\d+$/);
  return match ? `pdfline:${match[1]}` : null;
};
const expandSelectionToLine = () => {
  const items = compositeElements();
  const anchor = selectedElement() || items[items.length - 1];
  const key = anchor ? lineKey(anchor) : null;
  if (!key) return;
  const lineItems = currentPage().elements
    .filter(el => el.kind === "text" && lineKey(el) === key)
    .filter(el => ["word", "span"].includes(textLevel(el)))
    .sort((a, b) => (a.bounding_box?.y_min || 0) - (b.bounding_box?.y_min || 0)
      || (a.bounding_box?.x_min || 0) - (b.bounding_box?.x_min || 0));
  const wordItems = lineItems.filter(el => textLevel(el) === "word");
  const selected = wordItems.length ? wordItems : lineItems;
  if (!selected.length) return;
  state.selectedIds = selected.map(el => el.element_id);
  state.selectedId = state.selectedIds[state.selectedIds.length - 1] || null;
  renderInspector(selectedElement());
  renderViews();
  renderLists();
  centerCurrentSelection();
};
const fillMissing = (el) => {
  const keys = ["element_id","element_type","page_id","bounding_box","quad","polygon",
    "path","local_transform","effective_transform","paint_order","scene_order",
    "order_method","order_confidence","visibility","opacity","blend_mode",
    "text_level","display_text","normalized_text","font_reference","style_reference",
    "clip_reference","layer_reference","parent_reference","resource_references",
    "source_references","fidelity","editability","warnings","limitations","provenance"];
  const out = {};
  keys.forEach(k => {
    out[k] = el[k] === undefined || el[k] === null ? "not_available" : el[k];
  });
  return out;
};
const selectedElement = () => currentPage().elements.find(el => el.element_id === state.selectedId);
const hoverElement = () => currentPage().elements.find(el => el.element_id === state.hoverId);
const compositeElements = () => state.selectedIds
  .map(id => currentPage().elements.find(el => el.element_id === id))
  .filter(Boolean)
  .sort((a, b) => (a.bounding_box?.y_min || 0) - (b.bounding_box?.y_min || 0)
    || (a.bounding_box?.x_min || 0) - (b.bounding_box?.x_min || 0)
    || (a.scene_order || 0) - (b.scene_order || 0));
const compositeSelection = () => {
  const items = compositeElements();
  const boxes = items.map(el => el.bounding_box).filter(Boolean);
  const joined = items.map(el => el.display_text || el.text || el.normalized_text || "")
    .filter(Boolean).join(" ").replace(/\s+([,.;:/-])/g, "$1");
  return {
    selection_id: `selection_${state.pageIndex}_${items.map(el => el.element_id).join("_")}`,
    selected_element_ids: items.map(el => el.element_id),
    selection_type: items.length > 1 ? "composite" : "single",
    joined_text: joined,
    bounding_box: boxes.length ? {
      x_min: Math.min(...boxes.map(b => b.x_min)),
      y_min: Math.min(...boxes.map(b => b.y_min)),
      x_max: Math.max(...boxes.map(b => b.x_max)),
      y_max: Math.max(...boxes.map(b => b.y_max)),
    } : null,
    page_id: currentPage().page_id,
    created_by: "pdf_validation_lab",
    creation_method: items.length > 1 ? "manual_ctrl_selection" : "single_click",
    items,
  };
};
const renderCandidatePanel = (candidates) => {
  const panel = $("candidate-panel");
  panel.classList.toggle("hidden", !candidates || candidates.length <= 1);
  if (!candidates || candidates.length <= 1) return;
  panel.innerHTML = `<strong>${candidates.length} elementos nesta posicao</strong>`
    + candidates.map((el, i) =>
      `<button class="candidate" data-id="${html(el.element_id)}">${i + 1}. `
      + `${html(el.display_label || el.short_id)}</button>`).join("");
  panel.querySelectorAll("button[data-id]").forEach(btn =>
    btn.addEventListener("click", () => selectElement(btn.dataset.id, {
      candidates,
      center: false,
    })));
};
const renderInspector = (el) => {
  if (!el) {
    $("value-panel").textContent = "Selecione um elemento.";
    $("tab-summary").innerHTML = "";
    $("tab-geometry").innerHTML = "";
    $("tab-style").innerHTML = "";
    $("tab-resources").innerHTML = "";
    $("tab-origin").innerHTML = "";
    $("tab-warnings").innerHTML = "";
    $("tab-json").textContent = "Selecione um elemento.";
    return;
  }
  if (state.selectedIds.length > 1) {
    const composite = compositeSelection();
    $("value-panel").textContent = composite.joined_text || "Selecao composta";
    $("tab-summary").innerHTML = detailsTable({
      tipo: composite.selection_type,
      valor: composite.joined_text || "not_available",
      itens: composite.items.length,
      metodo: composite.creation_method,
      pagina: state.pageIndex + 1,
    });
    $("tab-geometry").innerHTML = detailsTable({
      bounding_box: JSON.stringify(composite.bounding_box || "not_available"),
      item_count: composite.items.length,
    });
    $("tab-style").innerHTML = "<span class='muted'>Selecao composta temporaria.</span>";
    $("tab-resources").innerHTML = composite.items.map(item =>
      `<button data-id="${html(item.element_id)}">`
      + `${html(item.display_label || item.short_id)}</button>`
    ).join("");
    const selectedJson = JSON.stringify(composite.selected_element_ids, null, 2);
    $("tab-origin").innerHTML = `<pre>${html(selectedJson)}</pre>`;
    $("tab-warnings").innerHTML = "<span class='muted'>Sem warnings na selecao composta.</span>";
    $("tab-json").textContent = JSON.stringify({
      selection_id: composite.selection_id,
      selected_element_ids: composite.selected_element_ids,
      selection_type: composite.selection_type,
      joined_text: composite.joined_text,
      bounding_box: composite.bounding_box,
      page_id: composite.page_id,
      created_by: composite.created_by,
      creation_method: composite.creation_method,
    }, null, 2);
    return;
  }
  const value = el.display_text || el.text || el.normalized_text || "";
  $("value-panel").textContent = value || el.display_label || el.short_id;
  $("tab-summary").innerHTML = detailsTable({
    tipo: el.element_type,
    valor: value || "not_available",
    pagina: state.pageIndex + 1,
    id: el.element_id,
    visibilidade: el.visibility,
    fidelidade: el.fidelity,
    editabilidade: el.editability || el.editability_hint,
  });
  $("tab-geometry").innerHTML = detailsTable({
    bounding_box: JSON.stringify(el.bounding_box || "not_available"),
    quad: JSON.stringify(el.quad || "not_available"),
    path: JSON.stringify(el.path || el.path_reference || "not_available"),
    local_transform: JSON.stringify(el.local_transform || "not_available"),
    effective_transform: JSON.stringify(el.effective_transform || "not_available"),
    scene_order: el.scene_order,
  });
  $("tab-style").innerHTML = detailsTable({
    fonte: el.font_reference || "not_available",
    estilo: el.style_reference || "not_available",
    opacidade: el.opacity || "not_available",
    blend_mode: el.blend_mode || "not_available",
  });
  $("tab-resources").innerHTML = resourceLinks(el);
  const originJson = JSON.stringify(el.source_references || [], null, 2);
  const warningJson = JSON.stringify(el.warnings || [], null, 2);
  $("tab-origin").innerHTML = `<pre>${html(originJson)}</pre>`;
  $("tab-warnings").innerHTML = `<pre>${html(warningJson)}</pre>`;
  $("tab-json").textContent = JSON.stringify(fillMissing(el), null, 2);
};
const detailsTable = (rows) => "<table>" + Object.entries(rows)
  .map(([k, v]) => `<tr><th>${html(k)}</th><td>${html(v)}</td></tr>`).join("")
  + "</table>";
const resourceLinks = (el) => {
  const resources = el.resources || el.resource_references || [];
  if (!resources.length) return "<span class='muted'>not_available</span>";
  return resources.map(resource =>
    `<button data-resource="${html(resource)}">${html(resource)}</button>`).join("");
};
const centerElement = (el) => {
  if (!el?.bounding_box) return;
  const zoom = Number($("zoom").value) / 100;
  const b = el.bounding_box;
  const x = ((b.x_min + b.x_max) / 2) * zoom;
  const y = ((b.y_min + b.y_max) / 2) * zoom;
  const view = $("page-view");
  view.scrollLeft = Math.max(0, x - view.clientWidth / 2);
  view.scrollTop = Math.max(0, y - view.clientHeight / 2);
};
const centerCurrentSelection = () => {
  const composite = compositeSelection();
  if (composite.bounding_box) {
    centerElement({bounding_box: composite.bounding_box});
    return;
  }
  centerElement(selectedElement());
};
const scrollListToSelection = () => {
  const index = state.visibleElements.findIndex(el => el.element_id === state.selectedId);
  if (index < 0) return;
  $("element-list").scrollTop = Math.max(0, index * 48 - 96);
  renderVirtualList($("element-list"), state.visibleElements);
};
const temporaryMode = data.report.temporary_mode === true;
const transientAssessments = [];
const historyKey = `eixo.pdf.lab.assessments.${data.report.source_hash}`;
const saveAssessment = () => {
  const entries = temporaryMode
    ? transientAssessments
    : JSON.parse(localStorage.getItem(historyKey) || "[]");
  const el = selectedElement();
  entries.push({
    diagnostic_run_id: data.report.diagnostic_run_id,
    status: $("assessment-status").value,
    notes: $("assessment-notes").value,
    reviewer: $("assessment-reviewer").value,
    selected_element_id: state.selectedId,
    selected_value: el?.display_text || el?.text || null,
    created_at: new Date().toISOString()
  });
  if (!temporaryMode) localStorage.setItem(historyKey, JSON.stringify(entries));
  renderAssessmentHistory();
};
const renderAssessmentHistory = () => {
  if (temporaryMode) {
    $("assessment-history").textContent =
      "Historico desativado no modo temporario.\\n" +
      JSON.stringify(transientAssessments, null, 2);
    return;
  }
  $("assessment-history").textContent =
    JSON.stringify(JSON.parse(localStorage.getItem(historyKey) || "[]"), null, 2);
};
const render = () => { filterElements(); renderViews(); renderLists(); };
fillSelect();
["page-select","layer-mode","label-mode","selection-mode","preview-quality","zoom",
  "layer-intensity","id-filter","search-input","text-granularity","visible-only"].forEach(id =>
  $(id).addEventListener("input", () => {
    if (id === "page-select") state.pageIndex = Number($(id).value);
    render();
  }));
[...kindChecks(), ...textLevelChecks()].forEach(check =>
  check.addEventListener("change", render));
$("previous-page").addEventListener("click", () => {
  state.pageIndex = Math.max(0, state.pageIndex - 1);
  $("page-select").value = String(state.pageIndex);
  render();
});
$("next-page").addEventListener("click", () => {
  state.pageIndex = Math.min(data.pages.length - 1, state.pageIndex + 1);
  $("page-select").value = String(state.pageIndex);
  render();
});
$("zoom-out").addEventListener("click", () => {
  $("zoom").value = Math.max(40, Number($("zoom").value) - 10);
  render();
});
$("zoom-in").addEventListener("click", () => {
  $("zoom").value = Math.min(200, Number($("zoom").value) + 10);
  render();
});
$("zoom-100").addEventListener("click", () => {$("zoom").value = 100; render();});
$("fit-width").addEventListener("click", () => {
  const size = pageSize(currentPage());
  const zoom = Math.floor(($("page-view").clientWidth - 24) * 100 / size.width);
  $("zoom").value = Math.max(40, Math.min(200, zoom));
  render();
});
$("fit-page").addEventListener("click", () => {
  const size = pageSize(currentPage());
  const x = ($("page-view").clientWidth - 24) * 100 / size.width;
  const y = ($("page-view").clientHeight - 24) * 100 / size.height;
  $("zoom").value = Math.max(40, Math.min(200, Math.floor(Math.min(x, y))));
  render();
});
$("center-selection").addEventListener("click", () => {
  centerCurrentSelection();
});
$("expand-line").addEventListener("click", expandSelectionToLine);
$("clear-selection").addEventListener("click", () => selectionStore.clear());
$("undo-composite").addEventListener("click", () => {
  state.selectedIds.pop();
  state.selectedId = state.selectedIds[state.selectedIds.length - 1] || null;
  renderInspector(selectedElement());
  render();
});
$("save-assessment").addEventListener("click", saveAssessment);
$("copy-value").addEventListener("click", () => {
  const value = state.selectedIds.length > 1
    ? compositeSelection().joined_text
    : $("value-panel").textContent || "";
  navigator.clipboard?.writeText(value || "");
});
$("copy-id").addEventListener("click", () => {
  const value = state.selectedIds.length > 1
    ? state.selectedIds.join("\n")
    : state.selectedId || "";
  navigator.clipboard?.writeText(value);
});
$("element-list").addEventListener("scroll", () => {
  renderVirtualList($("element-list"), state.visibleElements);
});
document.querySelectorAll("#property-tabs button").forEach(button => {
  button.addEventListener("click", () => {
    document.querySelectorAll("#property-tabs button").forEach(item =>
      item.setAttribute("aria-selected", String(item === button)));
    document.querySelectorAll(".tab-panel").forEach(panel =>
      panel.classList.toggle("active", panel.id === `tab-${button.dataset.tab}`));
  });
});
document.addEventListener("keydown", event => {
  if (event.key === "Escape") selectionStore.clear();
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
    event.preventDefault();
    state.selectedIds.pop();
    state.selectedId = state.selectedIds[state.selectedIds.length - 1] || null;
    renderInspector(selectedElement());
    render();
  }
  if (event.key === "ArrowDown") selectionStore.cycle(1);
  if (event.key === "ArrowUp") selectionStore.cycle(-1);
  if (event.key === "Enter" && state.selectedId) centerCurrentSelection();
});
renderAssessmentHistory();
render();
"""


def _document_html(report: dict[str, Any]) -> str:
    rows = "".join(
        f"<tr><th>{_html_escape(key)}</th><td>{_html_escape(str(value))}</td></tr>"
        for key, value in report.items()
        if key not in {"warnings", "limitations", "fidelity", "editability"}
    )
    return f"<table>{rows}</table>"
    return f"<table>{rows}</table>"


def _batch_html(report: dict[str, Any]) -> str:
    rows = "".join(
        "<tr>"
        f"<td><a href=\"{_relative_html_link(item['html_report_path'])}\">"
        f"{_html_escape(Path(item['document_path']).name)}</a></td>"
        f"<td>{_html_escape(item['state'])}</td>"
        f"<td>{item['page_count']}</td>"
        f"<td>{item['warning_count']}</td>"
        f"<td>{item['limitation_count']}</td>"
        f"<td>{item.get('finding_count', 0)}</td>"
        f"<td><code>{_html_escape(str(item.get('diagnostic_run_id')))}</code></td>"
        "</tr>"
        for item in report["documents"]
    )
    return (
        f"<div class=\"top\"><strong>Documents: {report['document_count']}</strong></div>"
        "<table><tr><th>Document</th><th>State</th><th>Pages</th>"
        "<th>Warnings</th><th>Limitations</th><th>Findings</th>"
        f"<th>Run</th></tr>{rows}</table>"
    )


def _relative_html_link(value: object) -> str:
    text = str(value or "")
    marker = "documents"
    index = text.find(marker)
    return text[index:].replace("\\", "/") if index >= 0 else _html_escape(text)


def _safe_error(exc: Exception) -> str:
    code = getattr(exc, "code", exc.__class__.__name__)
    return str(code)


def _html_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _slug(value: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    return "-".join(part for part in safe.split("-") if part) or "document"


__all__ = [
    "PDFManualDimensionEvaluation",
    "PDFManualEvaluationTemplate",
    "PDFValidationBatchResult",
    "PDFValidationDocumentResult",
    "PDFValidationDocumentState",
    "validate_pdf_batch",
]
