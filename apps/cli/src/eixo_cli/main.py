from __future__ import annotations

import argparse
import asyncio
import sys
from contextlib import redirect_stderr, redirect_stdout
from collections.abc import Awaitable, Callable
from typing import TextIO

from eixo_cli.bootstrap import EngineFactory, create_local_engine
from eixo_cli.commands import (
    run_inspect,
    run_jobs_cancel,
    run_jobs_result,
    run_jobs_status,
    run_parse,
    run_process,
)
from eixo_cli.errors import exit_code_for_error, report_error, report_json_error
from eixo_cli.exit_codes import ExitCode

VERSION = "0.1.0"
CommandHandler = Callable[[argparse.Namespace, object, TextIO], Awaitable[None]]


class EixoArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        raise CliArgumentError(message)


class CliArgumentError(Exception):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = EixoArgumentParser(
        prog="eixo",
        description="Eixo - Distributed Document Intelligence Engine",
        epilog=(
            "Exemplos:\n"
            "  eixo inspect documento.pdf\n"
            "  eixo parse documento.pdf --format json\n"
            "  eixo process documento.pdf --profile balanced\n"
            "  eixo jobs status job_123"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="store_true", help="Show version and exit.")
    subcommands = parser.add_subparsers(dest="command")

    add_document_command(
        subcommands,
        "inspect",
        "Inspeciona tecnicamente um documento.",
        run_inspect,
    )
    add_document_command(
        subcommands,
        "parse",
        "Realiza o parsing nativo de um documento.",
        run_parse,
    )
    parse = subcommands.choices["parse"]
    parse.add_argument(
        "--profile",
        default="visual",
        choices=("basic", "textual", "visual", "full_fidelity", "full-fidelity"),
        help="Perfil publico de parsing.",
    )
    parse.add_argument(
        "--pages",
        help="Paginas 1-based, como 1,3,5 ou 1-3.",
    )
    process = add_document_command(
        subcommands,
        "process",
        "Processa um documento.",
        run_process,
    )
    process.add_argument(
        "--profile",
        default="balanced",
        choices=("automatic", "fast", "balanced"),
        help="Processing profile.",
    )
    wait = process.add_mutually_exclusive_group()
    wait.add_argument("--wait", dest="wait", action="store_true", default=True)
    wait.add_argument("--no-wait", dest="wait", action="store_false")

    jobs = subcommands.add_parser("jobs", help="Consulta e gerencia jobs.")
    job_subcommands = jobs.add_subparsers(dest="job_command")
    add_job_command(job_subcommands, "status", "Consulta o status de um job.", run_jobs_status)
    add_job_command(job_subcommands, "result", "Consulta o resultado de um job.", run_jobs_result)
    add_job_command(job_subcommands, "cancel", "Cancela um job.", run_jobs_cancel)

    runtime = subcommands.add_parser("runtime", help="Inspeciona o LocalRuntime.")
    runtime_subcommands = runtime.add_subparsers(dest="runtime_command")
    runtime_info = runtime_subcommands.add_parser(
        "info",
        help="Exibe configuracao segura do LocalRuntime.",
    )
    runtime_info.set_defaults(handler=run_runtime_info)

    doctor = subcommands.add_parser("doctor", help="Executa um diagnostico minimo.")
    doctor.set_defaults(handler=run_doctor)
    return parser


def add_document_command(
    subcommands: argparse._SubParsersAction,
    name: str,
    help_text: str,
    handler: CommandHandler,
) -> argparse.ArgumentParser:
    command = subcommands.add_parser(name, help=help_text)
    command.add_argument("source", help="Caminho local do documento.")
    add_output_options(command)
    command.set_defaults(handler=handler)
    return command


def add_job_command(
    subcommands: argparse._SubParsersAction,
    name: str,
    help_text: str,
    handler: CommandHandler,
) -> argparse.ArgumentParser:
    command = subcommands.add_parser(name, help=help_text)
    command.add_argument("job_id", help="Identificador do job.")
    add_output_options(command)
    command.set_defaults(handler=handler)
    return command


def add_output_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=("console", "json"), default="console")
    parser.add_argument("--output", help="Grava JSON em arquivo.")
    parser.add_argument("--pretty", action="store_true", help="Formata JSON com indentacao.")
    parser.add_argument("--quiet", action="store_true", help="Reduz mensagens auxiliares.")
    parser.add_argument("--verbose", action="store_true", help="Exibe detalhes adicionais.")
    parser.add_argument("--debug", action="store_true", help="Exibe detalhes tecnicos de erros.")
    parser.add_argument("--force", action="store_true", help="Sobrescreve arquivo de saida.")


async def run_doctor(args: argparse.Namespace, engine: object, stdout: TextIO) -> None:
    stdout.write("eixo cli ok\n")


async def run_runtime_info(args: argparse.Namespace, engine: object, stdout: TextIO) -> None:
    config = engine.runtime.config  # type: ignore[attr-defined]
    stdout.write(f"max_concurrent_tasks={config.max_concurrent_tasks}\n")
    stdout.write(f"max_thread_workers={config.max_thread_workers}\n")
    stdout.write(f"max_process_workers={config.max_process_workers}\n")
    stdout.write(f"default_timeout={config.default_timeout}\n")


def main(
    argv: list[str] | None = None,
    *,
    engine_factory: EngineFactory = create_local_engine,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    out = stdout or sys.stdout
    err = stderr or sys.stderr
    parser = build_parser()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            args = parser.parse_args(argv)
        if args.version:
            out.write(f"eixo {VERSION}\n")
            return int(ExitCode.SUCCESS)
        handler = getattr(args, "handler", None)
        if handler is None:
            parser.print_help(out)
            return int(ExitCode.SUCCESS)
        return int(asyncio.run(run_command(args, handler, engine_factory, out)))
    except CliArgumentError as exc:
        err.write(f"Erro: {exc}\n")
        return int(ExitCode.INVALID_ARGUMENTS)
    except SystemExit as exc:
        return int(exc.code or ExitCode.SUCCESS)
    except Exception as exc:
        parsed_args = locals().get("args", object())
        debug = bool(getattr(parsed_args, "debug", False))
        if getattr(parsed_args, "format", "console") == "json" and not debug:
            report_json_error(exc, err)
        else:
            report_error(exc, err, debug=debug)
        return int(exit_code_for_error(exc))


async def run_command(
    args: argparse.Namespace,
    handler: CommandHandler,
    engine_factory: EngineFactory,
    stdout: TextIO,
) -> ExitCode:
    engine = engine_factory()
    async with engine:
        await handler(args, engine, stdout)
    return ExitCode.SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
