# Parsing publico de PDF

Fase: 3.12.

`DocumentEngine.parse()` e a entrada publica recomendada para o parser nativo de
PDF.

```python
from eixo import DocumentEngine

async with DocumentEngine.local() as engine:
    result = await engine.parse(
        "documento.pdf",
        profile="visual",
        pages=[1, 2],
    )

print(result.document_id)
print(result.artifact_reference)
```

O caminho publico reutiliza:

- `ParseDocument`;
- `CapabilityRegistry`;
- provider PDF nativo;
- builders de `PDFPageScenesArtifact` e `NativePDFSceneArtifact`;
- `ArtifactStore`.

O engine coordena a chamada, mas nao abre nem extrai PDF diretamente dentro dos
transportes. API, CLI e jobs chamam os mesmos casos de uso.

Resultado publico:

- `format="pdf"`;
- `profile`;
- `status`;
- `artifact_reference`;
- `scene_artifact_reference`, quando o perfil gera cena final;
- `summary`;
- `page_count`;
- `statistics`;
- `fidelity_summary`;
- `editability_summary`;
- `warnings`;
- `limitations`;
- `provenance`.

Por padrao, artefatos grandes nao sao materializados na resposta publica. Eles
sao gravados no `ArtifactStore` e retornados como `ArtifactReference`.

Jobs persistentes usam `DocumentEngine.submit()` com `ProcessingRequest`. Para
PDF, perfis `basic`, `textual`, `visual` e `full_fidelity` sao roteados para o
mesmo pipeline de parse e o resultado do job persiste em SQLite.
