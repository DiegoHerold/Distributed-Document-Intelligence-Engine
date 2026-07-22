# Inspecao publica de PDF

Fase: 3.12.

`DocumentEngine.inspect()` agora usa a capability publica generica de PDF quando a
ingestao identifica `pdf` ou `application/pdf`.

Fluxo:

```text
entrada publica
  -> DocumentSource
  -> InspectDocument
  -> Capability Registry
  -> provider PDF nativo
  -> PDFTechnicalInspection
  -> ArtifactStore
  -> InspectionResult resumido
```

Exemplo:

```python
from eixo import DocumentEngine

async with DocumentEngine.local() as engine:
    inspection = await engine.inspect("documento.pdf")

print(inspection.document_id)
print(inspection.metadata["page_count"])
print(inspection.metadata["artifact_reference"]["artifact_id"])
```

A resposta publica nao expoe objetos do provider. O detalhe tecnico completo da
inspecao fica persistido como artefato JSON no `ArtifactStore` local e aparece
na resposta somente por referencia.

Campos resumidos em `InspectionResult.metadata`:

- `artifact_reference`;
- `page_count`;
- `pdf_version`;
- `security`;
- sinais de `text`, `images`, `vectors` e `forms`.

Senhas devem ser passadas por `options["password"]`. Elas sao convertidas para
opcoes em memoria e os contratos PDF serializam apenas `password_provided`.

Sem backend PyMuPDF instalado, a capability existe, mas a execucao retorna erro
publico `pdf.provider_unavailable`.
