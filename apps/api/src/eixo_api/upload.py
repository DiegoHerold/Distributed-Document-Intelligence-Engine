from __future__ import annotations

from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default
from pathlib import PurePath

from fastapi import Request

from eixo.core import BytesSource, UnsupportedFormatError, ValidationError
from eixo_api.configuration import ApiConfig

CHUNK_SIZE = 1024 * 1024
MULTIPART_OVERHEAD_LIMIT = 1024 * 1024


@dataclass(frozen=True, slots=True)
class HttpUploadedFile:
    filename: str | None
    content_type: str | None
    content: bytes


class HttpDocumentSourceAdapter:
    def __init__(self, config: ApiConfig) -> None:
        self.config = config

    async def to_source(self, file: HttpUploadedFile) -> BytesSource:
        filename = sanitize_filename(file.filename)
        media_type = normalize_declared_media_type(file.content_type)
        if len(file.content) > self.config.max_upload_size:
            raise UploadTooLargeError("Upload exceeds configured maximum size")
        if not file.content:
            raise ValidationError("Uploaded file cannot be empty")
        return BytesSource(
            content=file.content,
            filename=filename,
            declared_media_type=media_type,
            size=len(file.content),
            metadata={"transport": "http-multipart"},
        )


class UploadTooLargeError(ValidationError):
    code = "upload.too_large"


@dataclass(frozen=True, slots=True)
class MultipartDocumentUpload:
    file: HttpUploadedFile
    fields: dict[str, str]


async def read_multipart_document(
    request: Request,
    config: ApiConfig,
) -> MultipartDocumentUpload:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type.lower():
        raise ValidationError("Content-Type must be multipart/form-data")
    body = await read_limited_body(
        request,
        max_size=config.max_upload_size + MULTIPART_OVERHEAD_LIMIT,
    )
    message = BytesParser(policy=default).parsebytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
        + body
    )
    if not message.is_multipart():
        raise ValidationError("Invalid multipart body")
    fields: dict[str, str] = {}
    uploaded_file: HttpUploadedFile | None = None
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if name is None:
            continue
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename is None:
            fields[name] = payload.decode(part.get_content_charset() or "utf-8")
        elif name == "file":
            uploaded_file = HttpUploadedFile(
                filename=filename,
                content_type=part.get_content_type(),
                content=payload,
            )
    if uploaded_file is None:
        raise ValidationError("Multipart field 'file' is required")
    return MultipartDocumentUpload(file=uploaded_file, fields=fields)


async def read_limited_body(request: Request, *, max_size: int) -> bytes:
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > max_size:
            raise UploadTooLargeError("Upload exceeds configured maximum size")
    return bytes(body)


def sanitize_filename(value: str | None) -> str | None:
    if value is None:
        return None
    name = PurePath(value.replace("\\", "/")).name.strip()
    if not name or name in {".", ".."}:
        raise ValidationError("Invalid upload filename")
    if "/" in name or "\\" in name or "\x00" in name:
        raise ValidationError("Invalid upload filename")
    return name


def normalize_declared_media_type(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    media_type = value.split(";", 1)[0].strip().lower()
    if "/" not in media_type:
        raise UnsupportedFormatError("Invalid declared media type")
    return media_type


__all__ = [
    "HttpUploadedFile",
    "HttpDocumentSourceAdapter",
    "MultipartDocumentUpload",
    "UploadTooLargeError",
    "normalize_declared_media_type",
    "read_limited_body",
    "read_multipart_document",
    "sanitize_filename",
]
