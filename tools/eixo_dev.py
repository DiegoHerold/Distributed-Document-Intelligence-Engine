from __future__ import annotations

import argparse
import ast
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_FILES = [
    p
    for base in ("apps", "packages", "tests", "tools")
    for p in (ROOT / base).rglob("*.py")
    if "__pycache__" not in p.parts
]


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def lint() -> int:
    errors: list[str] = []
    for path in PYTHON_FILES:
        text = path.read_text(encoding="utf-8")
        if "\t" in text:
            errors.append(f"{_relative(path)}: contains tab characters")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if len(line) > 100:
                errors.append(f"{_relative(path)}:{lineno}: line longer than 100 chars")
            if line.rstrip() != line:
                errors.append(f"{_relative(path)}:{lineno}: trailing whitespace")
        try:
            ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            errors.append(f"{_relative(path)}:{exc.lineno}: syntax error: {exc.msg}")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"lint ok ({len(PYTHON_FILES)} files)")
    return 0


def format_cmd(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="format")
    parser.add_argument("--check", action="store_true")
    parser.parse_args(argv)
    # Formatting is intentionally conservative until Ruff is introduced.
    return lint()


def typecheck() -> int:
    cmd = [sys.executable, "-m", "compileall", "-q"]
    cmd.extend(str(ROOT / base) for base in ("apps", "packages", "tests", "tools"))
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    if result.returncode == 0:
        print("typecheck ok (compileall)")
    return result.returncode


def test() -> int:
    env = os.environ.copy()
    paths = [
        ROOT / "packages/document-core/src",
        ROOT / "packages/document-model/src",
        ROOT / "packages/plugins/src",
        ROOT / "packages/artifacts/src",
        ROOT / "packages/document-application/src",
        ROOT / "packages/document-engine/src",
        ROOT / "packages/document-sdk-python/src",
        ROOT / "packages/runtime-local/src",
        ROOT / "apps/api/src",
        ROOT / "apps/cli/src",
    ]
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(str(p) for p in paths) + (
        os.pathsep + existing if existing else ""
    )
    result = subprocess.run([sys.executable, "-m", "pytest"], cwd=ROOT, env=env, check=False)
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eixo-dev")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("lint")
    fmt = sub.add_parser("format")
    fmt.add_argument("--check", action="store_true")
    sub.add_parser("typecheck")
    sub.add_parser("test")
    args = parser.parse_args(argv)
    if args.command == "lint":
        return lint()
    if args.command == "format":
        return format_cmd(["--check"] if args.check else [])
    if args.command == "typecheck":
        return typecheck()
    if args.command == "test":
        return test()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
