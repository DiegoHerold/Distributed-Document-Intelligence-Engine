from __future__ import annotations

import argparse
from pathlib import Path

from tools.pdf_golden import corpus_metrics, discover_corpus_documents, validate_manifest


ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = ROOT / "tests/corpus/pdf"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tests.update_pdf_goldens")
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args(argv)
    manifests = discover_corpus_documents(CORPUS_ROOT)
    errors = [error for path in manifests for error in validate_manifest(path)]
    metrics = corpus_metrics(CORPUS_ROOT)

    if not args.update:
        print("dry-run: pass --update to rewrite golden files intentionally")
    else:
        print("update requested: corpus generator is deterministic; review git diff")
    print(f"documents={metrics['document_count']}")
    print(f"golden={metrics['golden_test_count']}")
    print(f"visual={metrics['visual_test_count']}")
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
