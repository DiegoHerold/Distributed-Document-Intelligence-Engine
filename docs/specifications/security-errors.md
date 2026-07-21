# Erros De Seguranca

Erros publicos de seguranca derivam de `EixoError` e sao convertidos para
`ErrorResult` na API e na CLI.

| Codigo | Excecao | API | CLI |
|---|---|---:|---|
| `file_too_large` | `FileTooLargeError` | 413 | validacao |
| `empty_file` | `EmptyFileError` | 422 | validacao |
| `unsupported_format` | `UnsupportedFormatError` | 415 | formato nao suportado |
| `invalid_mime` | `InvalidMimeError` | 415 | argumentos invalidos |
| `mime_mismatch` | `MimeMismatchError` | 415 | argumentos invalidos |
| `corrupted_file` | `CorruptedFileError` | 422 | validacao |
| `truncated_file` | `TruncatedFileError` | 422 | validacao |
| `invalid_container` | `InvalidContainerError` | 422 | validacao |
| `invalid_document_structure` | `InvalidDocumentStructureError` | 422 | validacao |
| `unsafe_filename` | `UnsafeFilenameError` | 400 | argumentos invalidos |
| `path_traversal_detected` | `PathTraversalError` | 400 | argumentos invalidos |
| `unsafe_storage_key` | `UnsafeStorageKeyError` | 400 | argumentos invalidos |
| `archive_too_many_entries` | `ArchiveTooManyEntriesError` | 422 | validacao |
| `archive_uncompressed_size_exceeded` | `ArchiveUncompressedSizeExceededError` | 422 | validacao |
| `archive_entry_too_large` | `ArchiveEntryTooLargeError` | 422 | validacao |
| `suspicious_compression_ratio` | `SuspiciousCompressionRatioError` | 422 | validacao |
| `zip_bomb_detected` | `ZipBombError` | 422 | validacao |
| `encrypted_archive_not_allowed` | `EncryptedArchiveNotAllowedError` | 422 | validacao |
| `unsafe_archive_entry` | `UnsafeArchiveEntryError` | 422 | validacao |
| `page_limit_exceeded` | `PageLimitExceededError` | 422 | validacao |
| `read_timeout` | `ReadTimeoutError` | 408 | timeout |

Warnings seguros:

| Codigo | Quando ocorre |
|---|---|
| `filename_sanitized` | nome foi normalizado para metadado seguro |
| `declared_mime_mismatch` | MIME declarado diverge do formato real e politica permite |
| `extension_mismatch` | extensao diverge do formato real e politica permite |

Detalhes publicos nunca incluem caminhos internos nem conteudo do documento.
