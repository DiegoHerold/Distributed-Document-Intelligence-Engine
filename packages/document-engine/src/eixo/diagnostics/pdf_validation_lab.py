from __future__ import annotations

import json
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
) -> PDFValidationDocumentResult:
    started = time.perf_counter()
    started_at = _now_iso()
    diagnostic_run_id = _diagnostic_run_id()
    source_hash = _source_hash(document)
    document_root = output / "documents" / _slug(document.stem)
    document_dir = document_root / "runs" / diagnostic_run_id
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
        lab_data = _lab_data(report, native_scene)
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
) -> None:
    for scene in native_scene.get("scenes", []):
        zero_based_index = int(scene.get("page_index", 0))
        page_index = zero_based_index + 1
        prefix = f"page-{page_index:03d}"
        _write_json(pages_dir / f"{prefix}-scene.json", scene)
        _write_json(pages_dir / f"{prefix}-elements.json", _page_elements(scene))
        width, height = _scene_dimensions(scene)
        original_png = _render_original_png(document, zero_based_index, password)
        if original_png is None:
            original_png = _blank_png(width, height)
        (pages_dir / f"{prefix}-original.png").write_bytes(original_png)
        if diagnostic_preview:
            overlay_png = _overlay_png(scene, width, height)
            (pages_dir / f"{prefix}-overlay.png").write_bytes(overlay_png)
        elif not (pages_dir / f"{prefix}-overlay.png").exists():
            (pages_dir / f"{prefix}-overlay.png").write_bytes(_blank_png(width, height))


def _render_original_png(
    document: Path,
    page_index: int,
    password: str | None,
) -> bytes | None:
    try:
        rendering = import_module("eixo.providers.pdf.pymupdf.rendering")
        return rendering.render_pdf_page_png(document, page_index, password=password)
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


def _page_elements(scene: dict[str, Any]) -> dict[str, Any]:
    elements = [_diagnostic_element(item) for item in scene.get("elements", [])]
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


def _diagnostic_element(element: dict[str, Any]) -> dict[str, Any]:
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
        "display_text",
        "font_reference",
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
    return diagnostic


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


def _manual_template() -> dict[str, Any]:
    return to_jsonable(PDFManualEvaluationTemplate())


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(to_jsonable(value), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_html(path: Path, title: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        (
            "<!doctype html><html><head><meta charset=\"utf-8\">"
            f"<title>{_html_escape(title)}</title>"
            "<style>body{font-family:Arial,sans-serif;margin:0;color:#1f2933;}"
            "table{border-collapse:collapse;width:100%;}"
            "td,th{border:1px solid #d7dde5;padding:6px;text-align:left;}"
            "code{background:#eef2f7;padding:2px 4px;}"
            "button,select,input,textarea{font:inherit;}"
            "button{border:1px solid #a9b4c2;background:#fff;padding:6px 8px;}"
            ".top{padding:16px 20px;border-bottom:1px solid #d7dde5;}"
            ".layout{display:grid;grid-template-columns:240px minmax(360px,1fr) 340px;}"
            ".pane{height:calc(100vh - 82px);overflow:auto;border-right:1px solid #d7dde5;}"
            ".pane:last-child{border-right:0;border-left:1px solid #d7dde5;}"
            ".section{padding:12px;border-bottom:1px solid #e3e8ef;}"
            ".viewer{padding:12px;display:grid;gap:12px;background:#f8fafc;}"
            ".views{display:grid;grid-template-columns:1fr 1fr;gap:12px;align-items:start;}"
            ".view{background:#fff;border:1px solid #d7dde5;min-height:120px;overflow:auto;}"
            ".stage{position:relative;display:inline-block;line-height:0;}"
            ".stage img{display:block;max-width:none;}"
            ".stage svg{position:absolute;left:0;top:0;}"
            ".hidden{display:none;}"
            ".list button{display:block;width:100%;text-align:left;margin:2px 0;}"
            ".selected{outline:2px solid #d12b2b;outline-offset:1px;}"
            ".muted{color:#66788a;}"
            ".chips{display:flex;flex-wrap:wrap;gap:6px;}"
            ".chip{border:1px solid #c8d1dc;padding:4px 6px;background:#fff;}"
            "pre{white-space:pre-wrap;background:#0f1720;color:#eef2f7;padding:10px;}"
            "@media(max-width:1000px){.layout{grid-template-columns:1fr;}.pane{height:auto;}}"
            "</style></head><body>"
            f"<h1>{_html_escape(title)}</h1>{body}</body></html>"
        ),
        encoding="utf-8",
    )


def _lab_data(
    report: dict[str, Any],
    native_scene: dict[str, Any] | None,
) -> dict[str, Any]:
    pages = []
    resources: dict[str, list[str]] = {}
    for scene in (native_scene or {}).get("scenes", []):
        page_number = int(scene.get("page_index", 0)) + 1
        prefix = f"page-{page_number:03d}"
        elements = [_diagnostic_element(item) for item in scene.get("elements", [])]
        for element in elements:
            for resource in element.get("resources", []):
                resources.setdefault(resource, []).append(str(element["element_id"]))
        pages.append(
            {
                "page_id": scene.get("page_id"),
                "page_index": scene.get("page_index"),
                "geometry": scene.get("geometry", {}),
                "original": f"pages/{prefix}-original.png",
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
        },
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
      <label><input type="checkbox" data-kind="text" checked> texto</label><br>
      <label><input type="checkbox" data-kind="image" checked> imagens</label><br>
      <label><input type="checkbox" data-kind="vector" checked> vetores</label><br>
      <label><input type="checkbox" data-kind="interactive" checked> interativos</label><br>
      <label><input type="checkbox" data-kind="clipping" checked> clipping</label><br>
      <label><input type="checkbox" data-kind="other" checked> outros</label><br>
      <label><input id="show-warnings" type="checkbox"> warnings</label><br>
      <label><input id="show-limitations" type="checkbox"> limitacoes</label><br>
      <label>ID <input id="id-filter" placeholder="elemento ou recurso"></label>
    </div>
    <div class="section">
      <div><strong>Elementos visiveis</strong> <span id="visible-count"></span></div>
      <div id="element-list" class="list"></div>
    </div>
  </aside>
  <main class="pane viewer">
    <div class="section">
      <label>Modo
        <select id="view-mode">
          <option value="side">lado a lado</option>
          <option value="original">somente original</option>
          <option value="overlay">somente overlay</option>
          <option value="stack">sobreposicao</option>
        </select>
      </label>
      <label>Zoom <input id="zoom" type="range" min="40" max="200" value="100"></label>
      <label>Opacidade <input id="opacity" type="range" min="0" max="100" value="55"></label>
    </div>
    <div class="views" id="views">
      <div class="view" id="original-view"><div id="original-stage" class="stage"></div></div>
      <div class="view" id="overlay-view"><div id="overlay-stage" class="stage"></div></div>
    </div>
  </main>
  <aside class="pane">
    <div class="section">
      <h2>Inspecao</h2>
      <pre id="element-detail">Selecione um elemento.</pre>
    </div>
    <div class="section">
      <h2>Texto</h2>
      <div id="text-panel" class="list"></div>
    </div>
    <div class="section">
      <h2>Imagens</h2>
      <div id="image-panel" class="list"></div>
    </div>
    <div class="section">
      <h2>Vetores</h2>
      <div id="vector-panel" class="list"></div>
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
let pageIndex = 0;
let selectedId = null;
let visibleElements = [];
const $ = (id) => document.getElementById(id);
const kindChecks = () => [...document.querySelectorAll("[data-kind]")];
const fillSelect = () => {
  $("page-select").innerHTML = data.pages.map((p, i) =>
    `<option value="${i}">Pagina ${i + 1}</option>`).join("");
};
const bboxStyle = (el) => {
  const colors = {text:"#0b66c3", image:"#c75400", vector:"#008f56",
    interactive:"#764abc", clipping:"#52616f", other:"#111827"};
  return colors[el.kind] || colors.other;
};
const currentPage = () => data.pages[pageIndex] || {elements: [], geometry: {}};
const pageSize = (page) => {
  const size = (page.geometry && page.geometry.size) || page.geometry || {};
  return {width: Math.round(size.width || 612), height: Math.round(size.height || 792)};
};
const filterElements = () => {
  const enabled = new Set(kindChecks().filter(c => c.checked).map(c => c.dataset.kind));
  const needle = $("id-filter").value.trim().toLowerCase();
  visibleElements = currentPage().elements.filter(el => {
    if (!enabled.has(el.kind)) return false;
    if (!needle) return true;
    return JSON.stringify(el).toLowerCase().includes(needle);
  });
};
const renderStage = (stageId, imagePath, interactive) => {
  const page = currentPage();
  const size = pageSize(page);
  const zoom = Number($("zoom").value) / 100;
  const stage = $(stageId);
  stage.innerHTML = `<img src="${imagePath}" width="${size.width * zoom}">`;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("width", size.width * zoom);
  svg.setAttribute("height", size.height * zoom);
  svg.setAttribute("viewBox", `0 0 ${size.width} ${size.height}`);
  visibleElements.forEach(el => {
    if (!el.bounding_box) return;
    const b = el.bounding_box;
    const r = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    r.setAttribute("x", b.x_min);
    r.setAttribute("y", b.y_min);
    r.setAttribute("width", Math.max(1, b.x_max - b.x_min));
    r.setAttribute("height", Math.max(1, b.y_max - b.y_min));
    r.setAttribute("fill", selectedId === el.element_id ? "rgba(209,43,43,.18)" : "none");
    r.setAttribute("stroke", selectedId === el.element_id ? "#d12b2b" : bboxStyle(el));
    r.setAttribute("stroke-width", selectedId === el.element_id ? "2" : ".8");
    r.dataset.elementId = el.element_id;
    if (interactive) r.addEventListener("click", () => selectElement(el.element_id));
    svg.appendChild(r);
  });
  stage.appendChild(svg);
};
const renderViews = () => {
  const page = currentPage();
  const mode = $("view-mode").value;
  $("original-view").classList.toggle("hidden", mode === "overlay");
  $("overlay-view").classList.toggle("hidden", mode === "original");
  $("views").style.gridTemplateColumns = mode === "stack" ? "1fr" : "1fr 1fr";
  renderStage("original-stage", page.original, true);
  renderStage("overlay-stage", page.overlay, true);
  $("overlay-view").style.opacity = mode === "stack" ? Number($("opacity").value) / 100 : 1;
};
const renderLists = () => {
  $("visible-count").textContent = `(${visibleElements.length})`;
  $("element-list").innerHTML = visibleElements.slice(0, 800).map(el =>
    `<button data-id="${el.element_id}">` +
    `${el.scene_order ?? "?"} ${el.kind} ${el.element_id}</button>`
  ).join("");
  $("element-list").querySelectorAll("button").forEach(btn =>
    btn.addEventListener("click", () => selectElement(btn.dataset.id)));
  panel("text-panel", "text");
  panel("image-panel", "image");
  panel("vector-panel", "vector");
  renderResources();
  const findings = [...data.warnings, ...data.limitations, ...data.findings];
  $("finding-panel").innerHTML = findings.map((f, i) =>
    `<button data-i="${i}">${f.code || f.message || f}</button>`
  ).join("") || "<span class='muted'>vazio</span>";
};
const panel = (id, kind) => {
  const items = currentPage().elements.filter(el => el.kind === kind).slice(0, 120);
  $(id).innerHTML = items.map(el =>
    `<button data-id="${el.element_id}">${el.element_id}</button>`
  ).join("") || "<span class='muted'>vazio</span>";
  $(id).querySelectorAll("button").forEach(btn =>
    btn.addEventListener("click", () => selectElement(btn.dataset.id)));
};
const renderResources = () => {
  $("resource-panel").innerHTML = Object.entries(data.resources).map(([id, els]) =>
    `<button data-resource="${id}">${id} (${els.length})</button>`
  ).join("") || "<span class='muted'>vazio</span>";
  $("resource-panel").querySelectorAll("button").forEach(btn => {
    btn.addEventListener("click", () => {$("id-filter").value = btn.dataset.resource; render();});
  });
};
const selectElement = (id) => {
  selectedId = id;
  const el = currentPage().elements.find(item => item.element_id === id);
  $("element-detail").textContent = JSON.stringify(fillMissing(el || {}), null, 2);
  renderViews();
  const btn = document.querySelector(`[data-id="${CSS.escape(id)}"]`);
  if (btn) btn.scrollIntoView({block:"nearest"});
};
const fillMissing = (el) => {
  const keys = ["element_id","element_type","page_id","bounding_box","quad","polygon",
    "path","local_transform","effective_transform","paint_order","scene_order",
    "order_method","order_confidence","visibility","opacity","blend_mode",
    "clip_reference","layer_reference","parent_reference","resource_references",
    "source_references","fidelity","editability","warnings","limitations","provenance"];
  const out = {};
  keys.forEach(k => {
    out[k] = el[k] === undefined || el[k] === null ? "not_available" : el[k];
  });
  return out;
};
const historyKey = `eixo.pdf.lab.assessments.${data.report.source_hash}`;
const saveAssessment = () => {
  const entries = JSON.parse(localStorage.getItem(historyKey) || "[]");
  entries.push({
    diagnostic_run_id: data.report.diagnostic_run_id,
    status: $("assessment-status").value,
    notes: $("assessment-notes").value,
    reviewer: $("assessment-reviewer").value,
    selected_element_id: selectedId,
    created_at: new Date().toISOString()
  });
  localStorage.setItem(historyKey, JSON.stringify(entries));
  renderAssessmentHistory();
};
const renderAssessmentHistory = () => {
  $("assessment-history").textContent =
    JSON.stringify(JSON.parse(localStorage.getItem(historyKey) || "[]"), null, 2);
};
const render = () => { filterElements(); renderViews(); renderLists(); };
fillSelect();
["page-select","view-mode","zoom","opacity","id-filter"].forEach(id =>
  $(id).addEventListener("input", () => {
    if (id === "page-select") pageIndex = Number($(id).value);
    render();
  }));
kindChecks().forEach(check => check.addEventListener("change", render));
$("save-assessment").addEventListener("click", saveAssessment);
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
