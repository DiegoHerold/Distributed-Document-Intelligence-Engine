# PDF Paint Order

Status: Fase 3.4 implementada.

## Politica

Ordem de pintura e best effort e sempre possui nivel de confianca.

`PDFPaintOrder` diferencia:

- `content_stream_index`;
- `operation_index`;
- `local_paint_order`;
- `global_paint_order`;
- `parent_form_order`;
- `confidence`.

`PDFPaintOrderConfidence` pode ser:

- `exact`;
- `high`;
- `partial`;
- `provider_approximation`;
- `unavailable`.

## Regra

A Fase 3.4 nao inventa ordem exata. O provider PyMuPDF atual preserva ordem de
content streams quando `get_contents()` esta disponivel, mas nao decodifica
operadores graficos. Por isso, operacoes ficam `unsupported_by_provider` e a
ordem global detalhada permanece indisponivel ou parcial.

As fases 3.6 a 3.10 poderao refinar essa ordem quando houver operadores,
elementos textuais, imagens, vetores e Form XObjects materializados.
