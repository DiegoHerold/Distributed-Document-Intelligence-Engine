# Contratos E Provider Nativo De PDF

Status: Fase 3.1 implementada. Usado pela Fase 3.2 para inspecao tecnica.

## Finalidade

A Fase 3.1 cria a fronteira oficial entre o Eixo e bibliotecas concretas de
PDF. O nucleo conhece apenas contratos em `eixo.pdf`; PyMuPDF fica isolado no
pacote `eixo-pdf-provider-pymupdf`.

```text
DocumentSource
  -> PDFProvider
  -> PDFProviderRegistry
  -> PyMuPDFPDFProvider
  -> PDFDocumentHandle
  -> PDFPageHandle
```

## Contratos Publicos

Os contratos ficam em `eixo.pdf`:

- `PDFProvider`;
- `PDFDocumentHandle`;
- `PDFPageHandle`;
- `PDFProviderRegistry`;
- `PDFProviderDescriptor`;
- `PDFProviderCapabilities`;
- `PDFProbeOptions`;
- `PDFOpenOptions`;
- `PDFProviderSettings`;
- `PDFProbeResult`;
- `PDFBasicInfo`;
- `PDFPageGeometry`;
- `ProviderLimitation`;
- `PDFProviderProvenance`.

A inspecao tecnica especializada fica em
[pdf-technical-inspector.md](pdf-technical-inspector.md).
O mapeamento interno de objetos, content streams e recursos fica em
[pdf-object-model.md](pdf-object-model.md).
Fontes, tipografia e texto granular ficam em
[pdf-typography.md](pdf-typography.md) e
[pdf-native-text-model.md](pdf-native-text-model.md).

Nenhum contrato publico expoe `fitz.Document`, `fitz.Page`, retangulos,
excecoes ou enums do PyMuPDF.

## Provider PyMuPDF

O primeiro provider concreto e `PyMuPDFPDFProvider`, exposto por:

```python
from eixo.providers.pdf.pymupdf import PyMuPDFPDFProvider
```

O pacote e importavel sem PyMuPDF instalado. Operacoes que precisam do backend
geram `PDFProviderUnavailableError` com instrucao de instalacao.

Dependencia opcional:

```bash
pip install "eixo-document-sdk-python[pdf-pymupdf]"
```

ou, instalando o pacote do provider diretamente:

```bash
pip install "eixo-pdf-provider-pymupdf[backend]"
```

## Registro E Resolucao

`DocumentEngine.local()` possui um registry de providers PDF separado do
`CapabilityRegistry` de processamento. Isso evita executar providers PDF como
capabilities comuns antes de existir uma capability de parsing/inspecao.

Exemplo:

```python
from eixo import DocumentEngine, DocumentSource, PDFOpenOptions, PDFProviderSettings
from eixo.providers.pdf.pymupdf import PYMUPDF_PROVIDER_ID, PyMuPDFPDFProvider

provider = PyMuPDFPDFProvider()
source = DocumentSource.from_path("documento.pdf")

engine = DocumentEngine.local(
    pdf_providers=(provider,),
    pdf=PDFProviderSettings(default_provider=PYMUPDF_PROVIDER_ID),
)

probe = await engine.pdf_provider.probe(source)

async with await engine.pdf_provider.open(
    source,
    PDFOpenOptions(password=None),
) as document:
    info = await document.get_basic_info()
    page = await document.get_page(0)
    geometry = await page.get_basic_geometry()
```

## Capacidades Declaradas

O provider PyMuPDF declara suporte real para:

- abertura de PDF;
- autenticacao por senha;
- acesso incremental a paginas;
- informacoes basicas;
- geometria basica de pagina;
- sinais tecnicos leves de presenca de texto, imagens, vetores, links,
  anotacoes e formularios, usados pelo `PDFTechnicalInspector`;
- mapeamento parcial de objetos, xref, content streams, fontes, imagens,
  mascaras e XObjects para `PDFInternalStructureArtifact`.
- resolucao parcial de catalogo tipografico e extracao textual nativa por
  `rawdict`, preservando glifos, caracteres, palavras, spans, linhas e blocos
  quando disponiveis.

As capacidades de imagens finais, vetores, clipping, anotacoes, formularios,
camadas e renderizacao continuam `unsupported` nesta fase, mesmo que a
biblioteca subjacente tenha APIs relacionadas. Elas serao ativadas apenas quando
o Eixo implementar e testar a fronteira correspondente.

## Ciclo De Vida

`PDFDocumentHandle` controla o documento aberto:

- suporta context manager assincrono;
- `close()` e idempotente;
- uso apos fechamento gera `ClosedPDFDocumentError`;
- falha durante abertura fecha o documento backend e a fonte resolvida;
- indices de pagina invalidos geram `PDFPageOutOfRangeError`.

Operacoes bloqueantes do backend sao executadas com `asyncio.to_thread`.

## Seguranca E Limites

O provider reutiliza `DocumentSource` e `LocalSourceResolver` para fontes locais,
bytes e streams. Limites por operacao ficam em `PDFOpenOptions` e
`PDFProbeOptions`:

- `max_file_size_bytes`;
- `max_pages`;
- `timeout_seconds`;
- `strict_validation`;
- `tolerate_partial_corruption`;
- `trusted_source`.

Senhas ficam em campos `repr=False` e nunca entram na proveniencia. A
proveniencia registra apenas `password_provided`.

## Erros Publicos

Erros PDF derivam de `EixoError`:

- `PDFProviderUnavailableError`;
- `UnsupportedPDFError`;
- `InvalidPDFError`;
- `CorruptedPDFError`;
- `EncryptedPDFError`;
- `PDFPasswordRequiredError`;
- `InvalidPDFPasswordError`;
- `PDFPageOutOfRangeError`;
- `PDFResourceLimitExceededError`;
- `PDFProviderExecutionError`;
- `ClosedPDFDocumentError`.

Excecoes externas do backend nao atravessam a fronteira publica.

## Observabilidade

O provider registra eventos estruturados:

- `pdf.provider.probe.started`;
- `pdf.provider.probe.completed`;
- `pdf.provider.open.started`;
- `pdf.provider.open.completed`;
- `pdf.provider.open.failed`;
- `pdf.provider.page.accessed`;
- `pdf.provider.document.closed`.

Logs nao incluem bytes do documento nem senha.

## Limitacoes Da Fase

- PyMuPDF nao e instalado como dependencia obrigatoria.
- `ArtifactReferenceSource` ainda depende de uma composicao futura com
  `ArtifactStore`.
- Fases 3.1 e 3.2 nao implementam texto granular, extracao de imagens, vetores,
  content streams, cena visual, preview ou renderizacao final.
- A Fase 3.4 preserva content streams e recursos, mas nao decodifica a sequencia
  completa de operadores graficos.
- As Fases 3.5 e 3.6 preservam texto granular via provider, mas glyph id nativo,
  char code, CID, CMaps e `ToUnicode` completos ainda nao sao decodificados.
- Concorrencia no mesmo handle e serializada por lock; documentos diferentes
  podem ser abertos por instancias independentes.
