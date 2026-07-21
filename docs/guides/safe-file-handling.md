# Manuseio Seguro De Arquivos

Use `DocumentEngine.local()` com a politica padrao para desenvolvimento local.

```python
from eixo import DocumentEngine

async with DocumentEngine.local() as engine:
    result = await engine.ingest("documento.pdf")
```

Para alterar limites:

```python
from eixo import DocumentEngine, IngestionLimits, IngestionSecurityPolicy

policy = IngestionSecurityPolicy(
    limits=IngestionLimits(
        max_file_size_bytes=50 * 1024 * 1024,
        read_timeout_seconds=10,
    ),
    require_mime_match=True,
)

async with DocumentEngine.local(security=policy) as engine:
    result = await engine.ingest("documento.pdf")
```

Boas praticas:

- trate filename como metadado;
- nao use filename para criar caminhos internos;
- confie no formato detectado, nao na extensao;
- configure limites menores para ambientes interativos;
- use `--debug` na CLI apenas em diagnostico local;
- nao armazene resultados binarios grandes em jobs SQLite.

Erros tipicos:

```python
from eixo import FileTooLargeError, UnsupportedFormatError

try:
    await engine.ingest("entrada.pdf")
except FileTooLargeError:
    ...
except UnsupportedFormatError:
    ...
```

Itens fora desta fase:

- antivirus;
- sandbox de parser;
- OCR;
- parsing profundo de PDF/Excel;
- isolamento distribuido;
- quotas por usuario.
