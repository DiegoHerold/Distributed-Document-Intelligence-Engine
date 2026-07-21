# PDF Vectors

Status: Fase 3.8 implementada parcialmente.

## Finalidade

A camada vetorial nativa preserva desenhos PDF como caminhos, subpaths e
comandos, sem reduzir formas a bounding boxes e sem interpretar semanticamente
tabelas, graficos, assinaturas ou formularios.

```text
PDFInternalStructureArtifact
  -> PDFGraphicsStateResolver
  -> PDFVectorPath
  -> PDFClippingPath
  -> PDFPageVectorLayer
  -> PDFNativeVectorArtifact
```

## Contratos

- `PDFPathCommand`;
- `PDFVectorSubpath`;
- `PDFVectorPath`;
- `PDFFillStyle`;
- `PDFStrokeStyle`;
- `PDFEffectiveGraphicsState`;
- `PDFGraphicsStateResolver`;
- `PDFClippingPath`;
- `PDFPageVectorLayer`;
- `PDFNativeVectorArtifact`.

## Comandos

Comandos iniciais:

- `move_to`;
- `line_to`;
- `curve_to`;
- `rectangle`;
- `close_path`.

Curvas Bezier preservam pontos de controle. Uma aproximacao para preview pode
existir em fase futura, mas nao substitui o comando original.

## Provider PyMuPDF

O adapter usa `page.get_drawings()` e converte os itens retornados para modelos
do Eixo. Estilos de fill/stroke, opacidade, dash, line cap, line join, blend
mode, retangulos, linhas e curvas sao provider-derived.

Ainda nao ha decodificacao dos operadores brutos do content stream. Por isso,
`operation_references` podem permanecer vazias e a ordem de pintura usa `seqno`
ou a ordem retornada pelo provider com confianca de aproximacao.

## Fora De Escopo

- reconstrucao de tabelas;
- links, anotacoes, formularios e camadas;
- renderer definitivo;
- edicao ou exportacao de PDF alterado;
- parser completo da especificacao PDF.
