# PDF Technical Inspector

Status: Fase 3.2 implementada.

## Finalidade

O `PDFTechnicalInspector` e o componente oficial de inspecao tecnica de PDFs.
Ele descreve o documento de forma estruturada antes de qualquer decomposicao
visual, parsing granular, OCR ou reconstrucao.

Responsabilidades principais:

- validar se o provider consegue abrir e descrever o PDF;
- registrar versao, paginas, metadados, geometria basica e rotacao;
- identificar criptografia, senha exigida e autenticacao realizada;
- representar permissoes e recursos como estados tecnicos explicitos;
- inventariar sinais leves de texto, imagens, vetores, links, anotacoes e
  formularios;
- calcular cobertura, perfil tecnico, indicadores de fidelidade, editabilidade,
  recomendacoes, evidencias, proveniencia e tempos.

## Contratos Publicos

Os contratos ficam em `eixo.pdf`:

- `PDFTechnicalInspector`;
- `DefaultPDFTechnicalInspector`;
- `PDFInspectionOptions`;
- `PDFTechnicalInspection`;
- `PDFIntegrityInspection`;
- `PDFVersionInspection`;
- `PDFMetadataInspection`;
- `PDFSecurityInspection`;
- `PDFPermissionsInspection`;
- `PDFFeatureInventory`;
- `PDFResourceSummary`;
- `PDFPageInspection`;
- `PDFInspectionCoverage`;
- `PDFTechnicalProfileInspection`;
- `PDFFidelityIndicators`;
- `PDFEditabilityHints`.

Estados tecnicos usam valores explicitos como `present`, `absent`, `unknown`,
`not_inspected`, `not_applicable`, `unsupported`, `partial` e `inconclusive`.
Isso evita booleanos ambiguos quando o provider nao inspecionou ou nao suporta
uma dimensao.

## API Local

`DocumentEngine.local()` cria um `DefaultPDFTechnicalInspector` sobre o mesmo
`PDFProviderRegistry` usado por `engine.pdf_provider`.

```python
from eixo import DocumentEngine, PDFInspectionOptions, PDFProviderSettings
from eixo.providers.pdf.pymupdf import PYMUPDF_PROVIDER_ID, PyMuPDFPDFProvider

engine = DocumentEngine.local(
    pdf_providers=(PyMuPDFPDFProvider(),),
    pdf=PDFProviderSettings(default_provider=PYMUPDF_PROVIDER_ID),
)

inspection = await engine.inspect_pdf(
    "document.pdf",
    options=PDFInspectionOptions(max_pages_to_inspect=5),
)
```

`inspect_pdf()` e especializado e diagnostico. A integracao com `inspect()` /
`parse()` genericos, API REST, CLI e jobs persistentes pertence a fases futuras
do Bloco 3.

## Seguranca

Senhas ficam apenas em opcoes de execucao (`repr=False`) e nao sao retornadas
por `to_dict()`, logs ou proveniencia. A serializacao registra somente
`password_provided`.

O inspector nao persiste documentos, nao grava jobs e nao armazena bytes do
PDF. A proveniencia registra provider, versao, backend, operacao, hash/fonte
quando disponiveis e opcoes seguras.

## Separacao De Responsabilidades

Fase 2.8 responde se e seguro aceitar e armazenar a entrada.

Fase 3.2 responde se um provider PDF consegue abrir e descrever tecnicamente o
documento.

O inspector nao implementa:

- decomposicao visual nativa;
- texto granular, glifos, palavras ou blocos nativos;
- extracao de imagens, vetores, fontes ou content streams;
- cena visual;
- OCR;
- renderer;
- editor;
- exportacao de PDF alterado.

## Provider PyMuPDF

O provider PyMuPDF fornece sinais leves por pagina quando o backend expuser APIs
compatíveis:

- presenca aproximada de texto;
- presenca aproximada de imagens;
- presenca aproximada de vetores;
- links;
- anotacoes;
- formularios.

Esses sinais sao inventario tecnico, nao extracao de conteudo. As capacidades
granulares continuam marcadas como `unsupported` ate as fases especificas do
Bloco 3.

## Testes

A Fase 3.2 possui testes de contrato para modelos, serializacao segura e fluxo
do inspector, alem de teste de integracao com `DocumentEngine.inspect_pdf()` e o
backend falso do provider PyMuPDF.

## Geometria Canonica

A partir da Fase 3.3, `PDFPageInspection` pode carregar `canonical_geometry`
com `PageGeometry`. Essa geometria usa origem no canto superior esquerdo, eixo Y
para baixo e unidade em points, conforme
[canonical-geometry.md](canonical-geometry.md).
