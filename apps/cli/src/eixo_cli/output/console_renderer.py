from __future__ import annotations

from typing import Any

from eixo import InspectionResult, JobResult, ParseResult, ProcessingResult


def render_console(value: Any, *, quiet: bool = False) -> str:
    if isinstance(value, InspectionResult):
        return render_inspection(value, quiet=quiet)
    if isinstance(value, ParseResult):
        return render_parse(value, quiet=quiet)
    if isinstance(value, ProcessingResult):
        return render_processing(value, quiet=quiet)
    if isinstance(value, JobResult):
        return render_job(value, quiet=quiet)
    if isinstance(value, dict):
        return "\n".join(f"{key}: {item}" for key, item in value.items())
    return str(value)


def render_inspection(value: InspectionResult, *, quiet: bool) -> str:
    lines = [
        f"Status: {value.status.value}",
        f"Documento: {value.document_id or '-'}",
        f"Tipo declarado: {value.declared_media_type or '-'}",
        f"Tipo detectado: {value.detected_media_type or '-'}",
        f"Formato detectado: {value.detected_format or '-'}",
        f"Tamanho: {value.size if value.size is not None else '-'} bytes",
    ]
    if not quiet and value.warnings:
        lines.append(f"Avisos: {len(value.warnings)}")
    return "\n".join(lines)


def render_parse(value: ParseResult, *, quiet: bool) -> str:
    lines = [
        f"Status: {value.status.value}",
        f"Documento: {value.document_id}",
        f"Formato: {value.format or '-'}",
        f"Perfil: {value.profile or '-'}",
        f"Paginas: {value.page_count if value.page_count is not None else '-'}",
        f"Artefato: {value.artifact_reference.artifact_id if value.artifact_reference else '-'}",
        f"Artefatos: {len(value.artifacts)}",
        f"Erros: {len(value.errors)}",
    ]
    if not quiet and value.warnings:
        lines.append(f"Avisos: {len(value.warnings)}")
    return "\n".join(lines)


def render_processing(value: ProcessingResult, *, quiet: bool) -> str:
    lines = [
        f"Job: {value.job_id}",
        f"Status: {value.status.value}",
        f"Documento: {value.document_id or '-'}",
        f"Artefatos: {len(value.artifacts)}",
        f"Erros: {len(value.errors)}",
    ]
    if not quiet and value.warnings:
        lines.append(f"Avisos: {len(value.warnings)}")
    return "\n".join(lines)


def render_job(value: JobResult, *, quiet: bool) -> str:
    lines = [
        f"Job: {value.job_id}",
        f"Status: {value.status.value}",
        f"Progresso: {round(value.progress * 100, 2)}%",
    ]
    if value.created_at:
        lines.append(f"Criado em: {value.created_at}")
    if value.started_at:
        lines.append(f"Iniciado em: {value.started_at}")
    if value.completed_at:
        lines.append(f"Concluido em: {value.completed_at}")
    if value.error is not None:
        lines.append(f"Erro: {value.error.message}")
    if not quiet and value.warnings:
        lines.append(f"Avisos: {len(value.warnings)}")
    return "\n".join(lines)


__all__ = ["render_console"]
