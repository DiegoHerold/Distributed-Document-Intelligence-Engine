# PDF Native Text Model

Status: Fases 3.5 e 3.6 implementadas parcialmente.

## Finalidade

O modelo textual nativo preserva a camada textual visualmente rastreavel sem
classificacao semantica. Blocos e linhas sao agrupamentos nativos ou derivados
do provider, nao paragrafos, titulos ou tabelas.

Hierarquia principal:

```text
NativeTextBlock
-> NativeTextLine
-> NativeTextSpan
-> NativeGlyph
```

`NativeWord` e `NativeCharacter` se relacionam por IDs. Uma palavra pode cruzar
spans em fases futuras; por isso o modelo nao depende apenas de arrays
aninhados.

## Contratos

- `NativeGlyph`
- `NativeCharacter`
- `NativeWord`
- `NativeTextSpan`
- `PDFTextBaseline`
- `NativeTextLine`
- `NativeTextBlock`
- `PDFNativeTextRelation`
- `PDFPageNativeTextLayer`
- `PDFNativeTextLayer`
- `PDFNativeTextArtifact`
- `PDFNativeTextStatistics`
- `PDFNativeTextExtractionOptions`

## Preservacao

Cada glifo pode carregar pagina, fonte, estilo, Unicode original, Unicode
normalizado, origem, bounding box, quad, baseline, matriz, transformacao,
ordem, visibilidade, metodo de extracao e proveniencia.

Glifos sem Unicode sao preservados. Texto invisivel tambem e preservado com
estado de visibilidade explicito.

## Fora De Escopo

Esta fase nao cria paragrafos, secoes, listas, campos, tabelas, OCR,
reconstrucao de texto vetorizado, edicao ou exportacao de PDF.
