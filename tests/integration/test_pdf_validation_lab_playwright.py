from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from eixo import DocumentId, ParseRequest, ParseResult
from eixo.artifacts import LocalArtifactStore
from eixo.core import ArtifactReference, ResultStatus
from eixo.diagnostics.pdf_validation_lab import validate_pdf_batch


def test_pdf_validation_lab_clicks_real_text_with_playwright(tmp_path: Path) -> None:
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is required for the Playwright smoke test.")

    async def run_validation() -> Path:
        source = tmp_path / "sample.pdf"
        source.write_bytes(b"%PDF-1.7\n")
        output = tmp_path / "diagnostics"
        await validate_pdf_batch(
            PlaywrightValidationEngine(tmp_path),
            source,
            output_directory=output,
            profile="visual",
            diagnostic_preview=True,
        )
        runs = output / "documents" / "sample" / "runs"
        return next(runs.iterdir()) / "report.html"

    report = asyncio.run(run_validation())
    script = tmp_path / "click-lab.js"
    script.write_text(_playwright_script(report), encoding="utf-8")
    result = subprocess.run(
        [str(node), str(script)],
        cwd=Path.cwd(),
        env=_node_env(),
        text=True,
        capture_output=True,
        timeout=45,
        check=False,
    )
    if result.returncode != 0 and "Executable doesn't exist" in result.stderr:
        pytest.skip("Playwright browser executable is not installed.")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["value"] == "Reservado Confirmado"
    assert payload["selected_level"] == "composite"
    assert len(payload["selected_ids"]) == 2
    assert payload["candidate_count"] >= 1
    assert payload["preview_quality"] == "ultra"
    assert payload["visible_rects"] > 0
    assert payload["after_filter_value"] == "Reservado"


@dataclass(slots=True)
class PlaywrightValidationEngine:
    base: Path
    artifact_store: LocalArtifactStore = field(init=False)

    def __post_init__(self) -> None:
        self.artifact_store = LocalArtifactStore(self.base / "store")

    async def parse(self, request: ParseRequest) -> ParseResult:
        text_reference = await self._store_json(_text_artifact())
        scene_reference = await self._store_json(_native_scene())
        return ParseResult(
            document_id=DocumentId("doc_playwright"),
            status=ResultStatus.SUCCESS,
            format="pdf",
            profile=request.profile,
            scene_artifact_reference=scene_reference,
            page_count=1,
            statistics={
                "page_count": 1,
                "element_count": 6,
                "text_element_count": 4,
                "image_occurrence_count": 1,
                "vector_element_count": 1,
            },
            artifacts=(text_reference, scene_reference),
        )

    async def _store_json(self, value: dict[str, object]) -> ArtifactReference:
        from io import BytesIO

        from eixo.core import ArtifactType, ArtifactWriteRequest, ContentHash

        payload = json.dumps(value).encode("utf-8")
        digest = ContentHash("sha256", hashlib.sha256(payload).hexdigest())
        return await self.artifact_store.put(
            ArtifactWriteRequest(
                stream=BytesIO(payload),
                artifact_type=ArtifactType.DERIVED,
                content_hash=digest,
                size_bytes=len(payload),
                media_type="application/vnd.eixo+json",
                original_filename="artifact.json",
            )
        )


def _native_scene() -> dict[str, object]:
    elements = [
        _scene_element("text_block", "pdfblock:page-0:block-0", 8, 8, 120, 36, 1),
        _scene_element("text_line", "pdfline:page-0:line-0", 9, 9, 118, 34, 2),
        _scene_element("text_word", "pdfword:page-0:line-0:word-0", 10, 10, 86, 30, 3),
        _scene_element("text_word", "pdfword:page-0:line-0:word-1", 90, 10, 156, 30, 4),
        _scene_element("image", "pdfimageocc:page-0:image-0", 166, 10, 226, 70, 5),
        _scene_element("vector", "pdfvector:page-0:path-0", 10, 48, 86, 56, 6),
    ]
    return {
        "artifact_id": "art_native_pdf_scene_doc_playwright",
        "artifact_type": "native_pdf_scene",
        "inspection": {"page_summary": {"total_pages": 1}},
        "statistics": {
            "page_count": 1,
            "element_count": len(elements),
            "text_element_count": 4,
            "image_occurrence_count": 1,
            "vector_element_count": 1,
        },
        "fidelity_summary": {"overall_level": "native_normalized"},
        "editability_summary": {"overall_status": "partially_editable"},
        "warnings": [],
        "limitations": [],
        "pages": [{"page_id": "pdfpage:0", "page_index": 0, "element_count": len(elements)}],
        "scenes": [
            {
                "page_id": "pdfpage:0",
                "page_index": 0,
                "geometry": {"size": {"width": 240, "height": 120}},
                "elements": elements,
            }
        ],
    }


def _scene_element(
    element_type: str,
    source_id: str,
    x_min: float,
    y_min: float,
    x_max: float,
    y_max: float,
    order: int,
) -> dict[str, object]:
    return {
        "element_id": f"sceneelement:{element_type}:{source_id}",
        "element_type": element_type,
        "page_id": "pdfpage:0",
        "bounding_box": {
            "x_min": x_min,
            "y_min": y_min,
            "x_max": x_max,
            "y_max": y_max,
        },
        "scene_order": order,
        "visibility": "visible",
        "source_references": [
            {
                "source_artifact_id": "PDFNativeTextArtifact",
                "source_element_id": source_id,
                "source_element_type": element_type,
            }
        ],
        "resource_references": ["pdfimage:0"] if element_type == "image" else [],
    }


def _text_artifact() -> dict[str, object]:
    return {
        "artifact_version": "1.0.0",
        "pages": [
            {
                "page_reference": {"page_id": "pdfpage:0", "page_index": 0},
                "blocks": [
                    {
                        "block_id": "pdfblock:page-0:block-0",
                        "page_id": "pdfpage:0",
                        "line_ids": ["pdfline:page-0:line-0"],
                        "raw_text": "Reservado Confirmado",
                    }
                ],
                "lines": [
                    {
                        "line_id": "pdfline:page-0:line-0",
                        "page_id": "pdfpage:0",
                        "span_ids": ["pdfspan:page-0:block-0:line-0:span-0"],
                        "word_ids": [
                            "pdfword:page-0:line-0:word-0",
                            "pdfword:page-0:line-0:word-1",
                        ],
                        "raw_text": "Reservado Confirmado",
                    }
                ],
                "spans": [
                    {
                        "span_id": "pdfspan:page-0:block-0:line-0:span-0",
                        "page_id": "pdfpage:0",
                        "glyph_ids": ["pdfglyph:page-0:span-0:glyph-0"],
                        "word_ids": [
                            "pdfword:page-0:line-0:word-0",
                            "pdfword:page-0:line-0:word-1",
                        ],
                        "raw_text": "Reservado Confirmado",
                    }
                ],
                "words": [
                    {
                        "word_id": "pdfword:page-0:line-0:word-0",
                        "page_id": "pdfpage:0",
                        "glyph_ids": ["pdfglyph:page-0:span-0:glyph-0"],
                        "text": "Reservado",
                        "normalized_text": "Reservado",
                    },
                    {
                        "word_id": "pdfword:page-0:line-0:word-1",
                        "page_id": "pdfpage:0",
                        "glyph_ids": [],
                        "text": "Confirmado",
                        "normalized_text": "Confirmado",
                    }
                ],
                "glyphs": [
                    {
                        "glyph_id": "pdfglyph:page-0:span-0:glyph-0",
                        "page_id": "pdfpage:0",
                        "unicode_text": "R",
                    }
                ],
            }
        ],
        "text_layer": {"page_text_layers": []},
        "statistics": {"word_count": 2, "span_count": 1, "line_count": 1},
    }


def _playwright_script(report: Path) -> str:
    report_url = report.resolve().as_uri()
    return f"""
const {{ chromium }} = require("playwright");
(async () => {{
  const browser = await chromium.launch({{ headless: true, channel: "chrome" }});
  const page = await browser.newPage({{ viewport: {{ width: 1280, height: 800 }} }});
  await page.goto({json.dumps(report_url)});
  await page.waitForSelector("#original-stage .hit-layer");
  await page.selectOption("#layer-mode", "clean");
  const viewportCount = await page.locator(".pdf-page-viewport").count();
  const previewCount = await page.locator(".pdf-page-preview").count();
  const overlayStageCount = await page.locator("#overlay-stage").count();
  if (viewportCount !== 1) throw new Error(`expected one viewport, got ${{viewportCount}}`);
  if (previewCount !== 1) throw new Error(`expected one preview, got ${{previewCount}}`);
  if (overlayStageCount !== 0) throw new Error("overlay stage must not exist");
  const cleanRects = await page.locator(".interactive-elements-layer rect").count();
  if (cleanRects !== 0) throw new Error("clean mode should not draw mass geometry");
  await page.selectOption("#text-granularity", "word");
  await page.fill("#search-input", "Reservado");
  await page.waitForFunction(() => document.querySelectorAll("#element-list button").length > 0);
  const target = await page.evaluate(() => {{
    const data = JSON.parse(document.querySelector("#lab-data").textContent);
    const first = data.pages[0].elements.find(item =>
      item.display_text === "Reservado" && item.text_level === "word");
    const second = data.pages[0].elements.find(item =>
      item.display_text === "Confirmado" && item.text_level === "word");
    const size = data.pages[0].geometry.size;
    return {{
      first: first.bounding_box,
      second: second.bounding_box,
      width: size.width,
      height: size.height
    }};
  }});
  const clickBox = async (box, options = {{}}) => {{
    const stage = await page.locator("#original-stage").boundingBox();
    await page.mouse.click(
      stage.x + ((box.x_min + box.x_max) / 2) * stage.width / target.width,
      stage.y + ((box.y_min + box.y_max) / 2) * stage.height / target.height,
      options
    );
  }};
  await clickBox(target.first);
  await page.waitForFunction(() =>
    document.querySelector("#value-panel").textContent === "Reservado");
  await page.locator("#zoom").evaluate(el => {{
    el.value = "170";
    el.dispatchEvent(new Event("input", {{ bubbles: true }}));
  }});
  await page.waitForFunction(() =>
    document.querySelector(".pdf-page-preview").dataset.quality === "ultra");
  await page.evaluate(() => document.querySelector("[data-kind=text]").click());
  const before = await page.textContent("#value-panel");
  await clickBox(target.first);
  const after = await page.textContent("#value-panel");
  await page.evaluate(() => document.querySelector("[data-kind=text]").click());
  await page.selectOption("#text-granularity", "all");
  await page.selectOption("#layer-mode", "light");
  await page.selectOption("#selection-mode", "manual");
  await page.click("#clear-selection");
  await clickBox(target.first, {{ modifiers: ["Control"] }});
  await clickBox(target.second, {{ modifiers: ["Control"] }});
  await page.click("#expand-line");
  const payload = await page.evaluate(() => {{
    const tabJson = JSON.parse(document.querySelector("#tab-json").textContent);
    return {{
      value: document.querySelector("#value-panel").textContent,
      selected_level: tabJson.text_level || tabJson.selection_type,
      candidate_count: document.querySelectorAll("#candidate-panel button").length,
      preview_quality: document.querySelector(".pdf-page-preview").dataset.quality,
      visible_rects: document.querySelectorAll(".interactive-elements-layer rect").length,
      selected_ids: tabJson.selected_element_ids || [],
    }};
  }});
  payload.after_filter_value = after;
  if (before !== after) throw new Error("filtered text captured a click");
  console.log(JSON.stringify(payload));
  await browser.close();
}})().catch(async error => {{
  console.error(error.stack || error.message);
  process.exit(1);
}});
"""


def _node_executable() -> Path | None:
    found = shutil.which("node")
    if found:
        return Path(found)
    bundled = (
        Path.home()
        / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe"
    )
    return bundled if bundled.exists() else None


def _node_env() -> dict[str, str]:
    env = os.environ.copy()
    root = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node"
    paths = [
        root / "node_modules",
        root / "node_modules/.pnpm/node_modules",
    ]
    existing = env.get("NODE_PATH")
    values = [str(item) for item in paths if item.exists()]
    if existing:
        values.append(existing)
    env["NODE_PATH"] = os.pathsep.join(values)
    return env
