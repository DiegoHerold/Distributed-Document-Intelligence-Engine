from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True, slots=True)
class CorpusPDFSpec:
    category: str
    slug: str
    title: str
    description: str
    features: tuple[str, ...]
    expected_pages: int = 1
    expected_profile: str = "visual"
    golden_type: str = "golden"
    known_limitations: tuple[str, ...] = ()
    tags: tuple[str, ...] = ("synthetic",)


SPECS = (
    CorpusPDFSpec(
        "basic",
        "simple-text",
        "Simple text",
        "Baseline one-page text document with deterministic coordinates.",
        ("single_font", "native_text", "baseline", "provenance"),
        tags=("synthetic", "golden", "text"),
    ),
    CorpusPDFSpec(
        "text",
        "fragmented-text",
        "Fragmented text",
        "Text painted span by span and character by character.",
        ("fragmented_text", "character_by_character", "glyph_order"),
        tags=("synthetic", "golden", "text"),
    ),
    CorpusPDFSpec(
        "fonts",
        "subset-fonts",
        "Subset fonts",
        "Font-focused document with subset naming and ToUnicode expectations.",
        ("subset_font", "to_unicode_present", "font_resource"),
        tags=("synthetic", "golden", "fonts"),
    ),
    CorpusPDFSpec(
        "images",
        "reused-image",
        "Reused image",
        "Single image resource painted twice to catch duplicate resources.",
        ("image_resource", "image_occurrence", "image_reuse"),
        tags=("synthetic", "golden", "images", "visual_preview"),
    ),
    CorpusPDFSpec(
        "vectors",
        "vector-shapes",
        "Vector shapes",
        "Lines, rectangles and curve-like paths for vector extraction checks.",
        ("line", "rectangle", "bezier_curve", "stroke", "fill"),
        tags=("synthetic", "golden", "vectors", "visual_preview"),
    ),
    CorpusPDFSpec(
        "geometry",
        "rotated-crop",
        "Rotated crop",
        "Page geometry with crop box, rotation hints and transformed text.",
        ("crop_box", "rotated_page", "rotated_text", "transform"),
        tags=("synthetic", "golden", "geometry"),
    ),
    CorpusPDFSpec(
        "clipping",
        "clipped-elements",
        "Clipped elements",
        "Image and vector content associated with a clipping path.",
        ("clipping_path", "partial_clipping", "clip_relation"),
        tags=("synthetic", "golden", "clipping", "visual_preview"),
    ),
    CorpusPDFSpec(
        "interactive",
        "link-and-form",
        "Link and form",
        "External link and checkbox widget without executing actions.",
        ("external_link", "form_widget", "annotation_area"),
        tags=("synthetic", "golden", "interactive"),
    ),
    CorpusPDFSpec(
        "hybrid",
        "raster-plus-text",
        "Raster plus text",
        "Hybrid-like page with image background and native text overlay.",
        ("image_background", "native_text_overlay", "hybrid_pdf"),
        tags=("synthetic", "exploratory", "hybrid"),
        golden_type="exploratory",
        known_limitations=("Renderer-dependent raster comparison is exploratory.",),
    ),
    CorpusPDFSpec(
        "protected",
        "password-required",
        "Password required",
        "Security fixture manifest for encrypted PDFs without storing secrets.",
        ("encrypted", "password_required", "safe_error"),
        tags=("synthetic", "exploratory", "security"),
        golden_type="exploratory",
        known_limitations=("The fixture records intent; no password is stored.",),
    ),
    CorpusPDFSpec(
        "malformed",
        "truncated-recoverable",
        "Truncated recoverable",
        "Malformed fixture for structured error and recovery diagnostics.",
        ("malformed_pdf", "recoverable_parse", "warning"),
        tags=("synthetic", "exploratory", "security"),
        golden_type="exploratory",
        known_limitations=("Provider recovery behavior can vary.",),
    ),
    CorpusPDFSpec(
        "stress",
        "multi-page-small",
        "Multi-page small",
        "Small deterministic multipage document for counting and page selection.",
        ("multiple_pages", "page_selection", "resource_reuse"),
        expected_pages=3,
        tags=("synthetic", "manual", "stress"),
        golden_type="exploratory",
        known_limitations=("Stress expansion is manual and intentionally small here.",),
    ),
)


def main() -> int:
    for category in (
        "basic",
        "text",
        "fonts",
        "images",
        "vectors",
        "geometry",
        "clipping",
        "interactive",
        "protected",
        "malformed",
        "hybrid",
        "stress",
    ):
        (ROOT / category).mkdir(parents=True, exist_ok=True)
    for spec in SPECS:
        write_spec(spec)
    return 0


def write_spec(spec: CorpusPDFSpec) -> None:
    directory = ROOT / spec.category
    pdf_path = directory / f"{spec.slug}.pdf"
    expected_path = directory / f"{spec.slug}.expected.json"
    manifest_path = directory / f"{spec.slug}.manifest.json"
    pdf_bytes = build_pdf_bytes(spec)
    pdf_path.write_bytes(pdf_bytes)
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    manifest = {
        "document_id": f"pdf-corpus-{spec.category}-{spec.slug}",
        "name": spec.title,
        "description": spec.description,
        "source": "generated by tests/corpus/pdf/generate.py",
        "license": "CC0-1.0 synthetic fixture",
        "generated": True,
        "category": spec.category,
        "features": list(spec.features),
        "expected_pages": spec.expected_pages,
        "expected_profile": spec.expected_profile,
        "expected_provider": "provider-independent",
        "known_limitations": list(spec.known_limitations),
        "tags": sorted(spec.tags),
        "sha256": digest,
        "golden_type": spec.golden_type,
        "reason": spec.description,
    }
    expected = {
        "schema_version": "pdf-corpus-expected/v1",
        "document_id": manifest["document_id"],
        "expected": {
            "page_count": spec.expected_pages,
            "features": list(spec.features),
            "profile": spec.expected_profile,
            "golden_type": spec.golden_type,
            "security": {
                "stores_password": False,
                "executes_actions": False,
            },
            "metrics": expected_metrics(spec),
        },
    }
    write_json(manifest_path, manifest)
    write_json(expected_path, expected)


def build_pdf_bytes(spec: CorpusPDFSpec) -> bytes:
    stream_lines = [
        "BT",
        "/F1 12 Tf",
        "72 720 Td",
        f"({spec.title}) Tj",
        "0 -18 Td",
        f"({','.join(spec.features)}) Tj",
        "ET",
    ]
    if "rectangle" in spec.features or "crop_box" in spec.features:
        stream_lines.append("72 620 120 40 re S")
    if "image_resource" in spec.features or "image_background" in spec.features:
        stream_lines.append("q 60 0 0 40 72 560 cm /Im1 Do Q")
    if "external_link" in spec.features:
        stream_lines.append("% link annotation fixture metadata lives in manifest")
    content = "\n".join(stream_lines).encode("ascii")
    pages = [
        (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        )
    ]
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{' '.join(f'{3 + i} 0 R' for i in range(spec.expected_pages))}] "
        f"/Count {spec.expected_pages} >>",
    ]
    objects.extend(pages * spec.expected_pages)
    objects.append(f"<< /Length {len(content)} >>\nstream\n{content.decode('ascii')}\nendstream")
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    return assemble_pdf(objects)


def assemble_pdf(objects: list[str]) -> bytes:
    chunks = [b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"]
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(sum(len(chunk) for chunk in chunks))
        chunks.append(f"{index} 0 obj\n{body}\nendobj\n".encode("latin-1"))
    xref_offset = sum(len(chunk) for chunk in chunks)
    xref = ["xref", f"0 {len(objects) + 1}", "0000000000 65535 f "]
    xref.extend(f"{offset:010d} 00000 n " for offset in offsets[1:])
    trailer = [
        *xref,
        "trailer",
        f"<< /Size {len(objects) + 1} /Root 1 0 R >>",
        "startxref",
        str(xref_offset),
        "%%EOF",
        "",
    ]
    chunks.append("\n".join(trailer).encode("ascii"))
    return b"".join(chunks)


def expected_metrics(spec: CorpusPDFSpec) -> dict[str, int]:
    has_text = "native_text" in spec.features or "fragmented_text" in spec.features
    has_image = any("image" in feature for feature in spec.features)
    return {
        "text_elements": 1 if has_text else 0,
        "image_resources": 1 if has_image else 0,
        "image_occurrences": 2 if "image_reuse" in spec.features else 1
        if has_image
        else 0,
        "vector_paths": 1 if any(
            feature in spec.features
            for feature in ("line", "rectangle", "bezier_curve", "clipping_path")
        )
        else 0,
        "unresolved_fonts": 0,
        "unsupported_operations": len(spec.known_limitations),
        "elements_without_geometry": 0,
        "elements_without_source_reference": 0,
    }


def write_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
