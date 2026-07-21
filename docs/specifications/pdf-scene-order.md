# PDF Scene Order

Status: inicial, Fase 3.10.

A cena distingue ordem de pintura, ordem nativa e ordem de leitura. A
`scene_order` e uma consolidacao visual, nao uma ordem semantica.

## Metodos

- `global_paint_order`: usado quando o artefato de origem preserva uma ordem
  global.
- `local_paint_order`: usado quando existe apenas ordem local.
- `content_stream_order`: usado quando a ordem vem da operacao no content
  stream.
- `element_collection_order`: usado quando so ha ordem nativa do provider ou da
  colecao.
- `interactive_order`: reservado para appearances interativas materializadas.
- `unavailable`: usado quando nao ha base confiavel.

## Confianca

- `exact`;
- `high`;
- `partial`;
- `provider_approximation`;
- `derived`;
- `unavailable`.

## Regras

1. Preservar `global_paint_order` quando disponivel.
2. Preservar elementos sem ordem em suas colecoes especificas.
3. Nao usar posicao vertical como substituto silencioso da ordem de pintura.
4. Nao inserir links logicos no paint order sem appearance visual.
5. Registrar relacoes `painted_before` entre elementos ordenados adjacentes.
