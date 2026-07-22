from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable


class GoldenDifferenceCategory(StrEnum):
    CONTENT_CHANGE = "content_change"
    GEOMETRY_CHANGE = "geometry_change"
    STYLE_CHANGE = "style_change"
    RESOURCE_CHANGE = "resource_change"
    RELATION_CHANGE = "relation_change"
    ORDER_CHANGE = "order_change"
    PROVENANCE_CHANGE = "provenance_change"
    FIDELITY_CHANGE = "fidelity_change"
    WARNING_CHANGE = "warning_change"
    MISSING_ELEMENT = "missing_element"
    NEW_ELEMENT = "new_element"


@dataclass(frozen=True, slots=True)
class GoldenToleranceConfig:
    coordinate_tolerance: float = 0.01
    normalized_tolerance: float = 0.0001
    matrix_tolerance: float = 0.000001
    scalar_tolerance: float = 0.0

    def tolerance_for_path(self, path: str) -> float:
        lowered = path.lower()
        if "normalized" in lowered:
            return self.normalized_tolerance
        if "matrix" in lowered or "transform" in lowered:
            return self.matrix_tolerance
        geometry_terms = (
            "bounding_box",
            "bbox",
            "quad",
            "polygon",
            "baseline",
            "media_box",
            "crop_box",
            "width",
            "height",
            ".x",
            ".y",
        )
        if any(term in lowered for term in geometry_terms):
            return self.coordinate_tolerance
        return self.scalar_tolerance


@dataclass(frozen=True, slots=True)
class GoldenDifference:
    path: str
    category: GoldenDifferenceCategory
    expected: Any = None
    actual: Any = None
    tolerance: float | None = None
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "category": self.category.value,
            "expected": self.expected,
            "actual": self.actual,
            "tolerance": self.tolerance,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class GoldenRegressionReport:
    document_id: str
    result: str
    differences: tuple[GoldenDifference, ...] = ()
    affected_pages: tuple[str, ...] = ()
    affected_elements: tuple[str, ...] = ()
    generated_snapshots: tuple[str, ...] = ()
    diagnostic_artifacts: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "result": self.result,
            "difference_count": len(self.differences),
            "differences": [item.to_dict() for item in self.differences],
            "affected_pages": list(self.affected_pages),
            "affected_elements": list(self.affected_elements),
            "generated_snapshots": list(self.generated_snapshots),
            "diagnostic_artifacts": list(self.diagnostic_artifacts),
        }

    def to_markdown(self) -> str:
        lines = [
            f"# PDF golden regression: {self.document_id}",
            "",
            f"Result: {self.result}",
            f"Differences: {len(self.differences)}",
        ]
        if not self.differences:
            return "\n".join(lines)
        lines.append("")
        for diff in self.differences:
            lines.extend(
                [
                    f"## {diff.category.value}: `{diff.path}`",
                    f"- expected: `{diff.expected}`",
                    f"- actual: `{diff.actual}`",
                ]
            )
            if diff.tolerance is not None:
                lines.append(f"- tolerance: `{diff.tolerance}`")
        return "\n".join(lines)


class GoldenArtifactNormalizer:
    unstable_field_names = frozenset(
        {
            "created_at",
            "updated_at",
            "completed_at",
            "started_at",
            "duration_ms",
            "duration_seconds",
            "elapsed_ms",
            "elapsed_seconds",
            "job_id",
            "task_id",
            "correlation_id",
            "request_id",
            "storage_key",
        }
    )

    def normalize(self, value: Any) -> Any:
        if hasattr(value, "to_dict") and callable(value.to_dict):
            value = value.to_dict()
        if isinstance(value, dict):
            normalized: dict[str, Any] = {}
            for key in sorted(value):
                if key in self.unstable_field_names:
                    continue
                normalized[str(key)] = self.normalize(_normalize_path_value(key, value[key]))
            return normalized
        if isinstance(value, tuple):
            return [self.normalize(item) for item in value]
        if isinstance(value, list):
            return [self.normalize(item) for item in value]
        return value


class GoldenArtifactComparator:
    def __init__(self, tolerances: GoldenToleranceConfig | None = None) -> None:
        self.tolerances = tolerances or GoldenToleranceConfig()

    def compare(self, expected: Any, actual: Any) -> tuple[GoldenDifference, ...]:
        differences: list[GoldenDifference] = []
        self._compare(expected, actual, "$", differences)
        return tuple(differences)

    def report(
        self,
        document_id: str,
        expected: Any,
        actual: Any,
        *,
        diagnostic_artifacts: Iterable[str] = (),
    ) -> GoldenRegressionReport:
        differences = self.compare(expected, actual)
        return GoldenRegressionReport(
            document_id=document_id,
            result="passed" if not differences else "failed",
            differences=differences,
            affected_pages=tuple(sorted(_affected_values(differences, "page"))),
            affected_elements=tuple(sorted(_affected_values(differences, "element"))),
            diagnostic_artifacts=tuple(diagnostic_artifacts),
        )

    def _compare(
        self,
        expected: Any,
        actual: Any,
        path: str,
        differences: list[GoldenDifference],
    ) -> None:
        if isinstance(expected, dict) and isinstance(actual, dict):
            keys = set(expected) | set(actual)
            for key in sorted(keys):
                next_path = f"{path}.{key}"
                if key not in expected:
                    differences.append(
                        GoldenDifference(
                            next_path,
                            GoldenDifferenceCategory.NEW_ELEMENT,
                            actual=actual[key],
                        )
                    )
                elif key not in actual:
                    differences.append(
                        GoldenDifference(
                            next_path,
                            GoldenDifferenceCategory.MISSING_ELEMENT,
                            expected=expected[key],
                        )
                    )
                else:
                    self._compare(expected[key], actual[key], next_path, differences)
            return
        if isinstance(expected, list) and isinstance(actual, list):
            max_len = max(len(expected), len(actual))
            for index in range(max_len):
                next_path = f"{path}[{index}]"
                if index >= len(expected):
                    differences.append(
                        GoldenDifference(
                            next_path,
                            GoldenDifferenceCategory.NEW_ELEMENT,
                            actual=actual[index],
                        )
                    )
                elif index >= len(actual):
                    differences.append(
                        GoldenDifference(
                            next_path,
                            GoldenDifferenceCategory.MISSING_ELEMENT,
                            expected=expected[index],
                        )
                    )
                else:
                    self._compare(expected[index], actual[index], next_path, differences)
            return
        if _is_number(expected) and _is_number(actual):
            tolerance = self.tolerances.tolerance_for_path(path)
            if abs(float(expected) - float(actual)) > tolerance:
                differences.append(
                    GoldenDifference(
                        path,
                        _category_for_path(path),
                        expected=expected,
                        actual=actual,
                        tolerance=tolerance,
                    )
                )
            return
        if expected != actual:
            differences.append(
                GoldenDifference(
                    path,
                    _category_for_path(path),
                    expected=expected,
                    actual=actual,
                )
            )


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_corpus_documents(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.manifest.json")))


def validate_manifest(manifest_path: Path) -> list[str]:
    manifest = load_json(manifest_path)
    errors: list[str] = []
    required = (
        "document_id",
        "name",
        "description",
        "source",
        "license",
        "generated",
        "category",
        "features",
        "expected_pages",
        "expected_profile",
        "known_limitations",
        "tags",
        "sha256",
        "golden_type",
    )
    for key in required:
        if key not in manifest:
            errors.append(f"{manifest_path}: missing {key}")
    pdf_path = manifest_path.with_name(manifest_path.name.replace(".manifest.json", ".pdf"))
    expected_path = manifest_path.with_name(
        manifest_path.name.replace(".manifest.json", ".expected.json")
    )
    if not pdf_path.exists():
        errors.append(f"{manifest_path}: missing PDF {pdf_path.name}")
    elif manifest.get("sha256") != sha256_file(pdf_path):
        errors.append(f"{manifest_path}: sha256 mismatch")
    if not expected_path.exists():
        errors.append(f"{manifest_path}: missing expected {expected_path.name}")
    if manifest.get("license") in {None, "", "unknown"}:
        errors.append(f"{manifest_path}: license must be explicit")
    if not manifest.get("features"):
        errors.append(f"{manifest_path}: features cannot be empty")
    return errors


def corpus_metrics(root: Path) -> dict[str, Any]:
    manifests = [load_json(path) for path in discover_corpus_documents(root)]
    features = sorted({feature for item in manifests for feature in item["features"]})
    return {
        "document_count": len(manifests),
        "page_count": sum(int(item["expected_pages"]) for item in manifests),
        "feature_coverage": features,
        "provider_coverage": sorted(
            {item.get("expected_provider", "provider-independent") for item in manifests}
        ),
        "profile_coverage": sorted({item["expected_profile"] for item in manifests}),
        "golden_test_count": sum(
            1 for item in manifests if item["golden_type"] == "golden"
        ),
        "visual_test_count": sum(
            1 for item in manifests if "visual_preview" in item.get("tags", ())
        ),
        "unsupported_feature_count": sum(
            len(item.get("known_limitations", ())) for item in manifests
        ),
        "known_limitation_count": sum(
            len(item.get("known_limitations", ())) for item in manifests
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pdf-golden")
    parser.add_argument("corpus_root", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args(argv)

    if args.update:
        print("Golden update requested explicitly; no automatic snapshot rewrite is run.")
    errors = [
        error
        for manifest in discover_corpus_documents(args.corpus_root)
        for error in validate_manifest(manifest)
    ]
    metrics = corpus_metrics(args.corpus_root)
    if args.report:
        write_json(args.report, {"metrics": metrics, "errors": errors})
    print(json.dumps({"metrics": metrics, "errors": errors}, indent=2, sort_keys=True))
    return 1 if errors else 0


def _normalize_path_value(key: str, value: Any) -> Any:
    if not isinstance(value, str):
        return value
    lowered_key = key.lower()
    lowered_value = value.lower()
    if ("path" in lowered_key or lowered_key.endswith("_file")) and (
        "\\tmp" in lowered_value
        or "/tmp" in lowered_value
        or "\\temp" in lowered_value
    ):
        return "<temporary-path>"
    return value


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _category_for_path(path: str) -> GoldenDifferenceCategory:
    lowered = path.lower()
    if any(term in lowered for term in ("raw_text", "unicode", "glyph", "word")):
        return GoldenDifferenceCategory.CONTENT_CHANGE
    if any(
        term in lowered
        for term in ("geometry", "bounding_box", "bbox", "quad", "matrix", "transform")
    ):
        return GoldenDifferenceCategory.GEOMETRY_CHANGE
    if any(term in lowered for term in ("font", "style", "color", "opacity")):
        return GoldenDifferenceCategory.STYLE_CHANGE
    if any(term in lowered for term in ("resource", "hash", "image")):
        return GoldenDifferenceCategory.RESOURCE_CHANGE
    if "relation" in lowered:
        return GoldenDifferenceCategory.RELATION_CHANGE
    if "order" in lowered:
        return GoldenDifferenceCategory.ORDER_CHANGE
    if "provenance" in lowered or "source_reference" in lowered:
        return GoldenDifferenceCategory.PROVENANCE_CHANGE
    if "fidelity" in lowered or "editability" in lowered:
        return GoldenDifferenceCategory.FIDELITY_CHANGE
    if "warning" in lowered or "limitation" in lowered:
        return GoldenDifferenceCategory.WARNING_CHANGE
    return GoldenDifferenceCategory.CONTENT_CHANGE


def _affected_values(differences: Iterable[GoldenDifference], kind: str) -> set[str]:
    values: set[str] = set()
    needle = f"{kind}_id"
    for diff in differences:
        for value in (diff.expected, diff.actual):
            if isinstance(value, dict) and isinstance(value.get(needle), str):
                values.add(value[needle])
    return values


__all__ = [
    "GoldenArtifactComparator",
    "GoldenArtifactNormalizer",
    "GoldenDifference",
    "GoldenDifferenceCategory",
    "GoldenRegressionReport",
    "GoldenToleranceConfig",
    "corpus_metrics",
    "discover_corpus_documents",
    "load_json",
    "sha256_file",
    "validate_manifest",
    "write_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
