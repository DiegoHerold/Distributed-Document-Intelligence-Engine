# PDF Clipping

Status: Fase 3.8 implementada parcialmente.

## Objetivo

Clipping e uma relacao, nao uma alteracao destrutiva da geometria original.

`PDFClippingPath` preserva:

- comandos e subpaths;
- regra de preenchimento;
- transformacao;
- bounding box;
- clipping pai;
- cadeia de clipping;
- bounds efetivos quando seguros;
- content stream e operacoes de origem, quando disponiveis;
- Form XObject pai, quando disponivel;
- metodo e confianca.

## Cadeia

Clippings acumulados usam:

```text
parent_clip_path_id
clip_chain
effective_clip_bounds
```

Intersecoes geometricas complexas nao sao materializadas nesta fase. Quando a
aproximacao depende apenas do provider ou de bounding boxes, `clip_confidence`
deve refletir essa incerteza.

## Elementos

Um `PDFVectorPath` apenas referencia `clip_path_reference`. O caminho original
continua preservado com sua bbox, subpaths, comandos e visibilidade estimada.
