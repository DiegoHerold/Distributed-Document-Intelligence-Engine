from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist" / "sdk"
PACKAGE_DIRS = [
    ROOT / "packages/document-core",
    ROOT / "packages/plugins",
    ROOT / "packages/runtime-local",
    ROOT / "packages/document-application",
    ROOT / "packages/document-engine",
    ROOT / "packages/document-sdk-python",
]
SDK_DIR = ROOT / "packages/document-sdk-python"


def build_wheels() -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    for package_dir in PACKAGE_DIRS:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-cache-dir",
                "--no-build-isolation",
                "--no-deps",
                str(package_dir),
                "-w",
                str(DIST),
            ],
            cwd=ROOT,
            check=True,
        )


def build_sdist() -> Path:
    version_ns: dict[str, str] = {}
    exec((SDK_DIR / "src/eixo/version.py").read_text(encoding="utf-8"), version_ns)
    version = version_ns["__version__"]
    sdist_path = DIST / f"eixo_document_sdk_python-{version}.tar.gz"
    root_name = f"eixo_document_sdk_python-{version}"
    with tarfile.open(sdist_path, "w:gz") as archive:
        for relative in [
            "pyproject.toml",
            "README.md",
            "CHANGELOG.md",
        ]:
            archive.add(SDK_DIR / relative, arcname=f"{root_name}/{relative}")
        for path in (SDK_DIR / "src").rglob("*"):
            if path.is_file():
                archive.add(path, arcname=f"{root_name}/{path.relative_to(SDK_DIR)}")
    return sdist_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args(argv)
    if args.clean and DIST.exists():
        shutil.rmtree(DIST)
    build_wheels()
    sdist = build_sdist()
    print(f"built {sdist}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
