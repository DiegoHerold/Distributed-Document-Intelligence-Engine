# Limites De Ingestao

`IngestionSecurityPolicy` configura a seguranca de ingestao por instancia do
engine.

Exemplo:

```python
from eixo import DocumentEngine, IngestionLimits, IngestionSecurityPolicy

engine = DocumentEngine.local(
    security=IngestionSecurityPolicy(
        limits=IngestionLimits(
            max_file_size_bytes=100 * 1024 * 1024,
            max_page_count=500,
            read_timeout_seconds=30,
        )
    )
)
```

## Defaults

| Limite | Valor padrao | Unidade | Comportamento |
|---|---:|---|---|
| `max_file_size_bytes` | `104857600` | bytes | rejeita antes ou durante leitura |
| `max_page_count` | `500` | paginas | aplica quando conhecido |
| `read_timeout_seconds` | `30.0` | segundos | aborta leituras controladas |
| `max_archive_entries` | `1000` | entradas | rejeita ZIP/XLSX grande demais |
| `max_archive_uncompressed_bytes` | `209715200` | bytes | limita total descomprimido declarado |
| `max_archive_entry_size_bytes` | `104857600` | bytes | limita cada entrada |
| `max_compression_ratio` | `100.0` | razao | rejeita compressao suspeita |
| `max_archive_nesting_depth` | `1` | niveis | reservado para validacao recursiva futura |
| `max_filename_length` | `180` | caracteres | corta nomes longos sanitizados |

## Politicas Booleanas

| Opcao | Default | Efeito |
|---|---|---|
| `require_mime_match` | `False` | divergencia de MIME vira warning |
| `allow_extension_mismatch` | `True` | extensao divergente vira warning |
| `reject_empty_files` | `True` | 0 bytes vira `empty_file` |
| `allow_encrypted_archives` | `False` | ZIP criptografado e rejeitado |

## Formatos Permitidos

Default:

- PDF;
- XLSX;
- CSV;
- PNG;
- JPEG;
- TIFF.

Formato real detectado prevalece sobre extensao e MIME declarado.
