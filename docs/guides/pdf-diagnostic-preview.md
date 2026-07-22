# Preview Diagnostico PDF

`PDFDiagnosticPreviewGenerator` cria uma visualizacao tecnica de uma
`PDFPageScene`.

Entrada:

- `PDFPageScene`;
- `PDFDiagnosticPreviewConfig`.

Saida:

- `PDFDiagnosticPreviewArtifact`;
- `png_bytes`;
- `png_sha256`;
- metadados JSON via `metadata_dict()`.

## Overlays

A configuracao permite ativar ou ocultar:

- glifos;
- palavras;
- spans;
- linhas;
- blocos;
- imagens;
- vetores;
- clipping;
- links;
- anotacoes;
- widgets;
- IDs;
- ordem de pintura;
- baselines;
- elementos invisiveis.

## IDs e Ordem

O preview desenha marcadores de ID no PNG e registra a legenda completa no JSON.
`paint_order`, `scene_order` e `order_confidence` ficam nos metadados de cada
overlay. Ordem aproximada nao e apresentada como exata.

## Clipping

Elementos com `clip_path_reference` sao destacados nos metadados e desenhados
com o tipo visual do elemento. O preview nao reaplica clipping sobre a imagem;
ele diagnostica a relacao extraida.

## Renderer

Ainda nao existe renderer oficial de pagina PDF. Por isso a pagina-base inicial
e branca e o artefato inclui:

```text
diagnostic_preview.no_official_pdf_renderer
```

Essa dependencia temporaria nao implementa o Bloco 10 e nao deve ser tratada
como viewer ou frontend de producao.
