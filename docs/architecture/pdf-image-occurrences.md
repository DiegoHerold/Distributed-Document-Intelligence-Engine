# PDF Image Occurrences

Status: Fase 3.7 implementada parcialmente.

## Objetivo

`PDFImageOccurrence` representa uma pintura concreta de um recurso de imagem em
uma pagina. Ela existe para evitar que atributos visuais sejam gravados no
recurso reutilizavel.

Campos principais:

- `occurrence_id`;
- `image_resource_id`;
- `page_id`;
- `bounding_box`;
- `normalized_bounding_box`;
- `quad`;
- `transform`;
- `paint_order`;
- `clip_status`;
- `visibility`;
- `opacity`;
- `blend_mode`;
- `mask_reference`;
- `soft_mask_reference`;
- `parent_form_xobject_id`;
- `effective_dpi_x` e `effective_dpi_y`;
- `geometry_confidence`.

## Ordem E Geometria

A ordem de pintura e provider-derived nesta fase. Quando o provider so entrega
uma lista de ocorrencias, o Eixo preserva essa sequencia com confianca explicita
de aproximacao.

Bounding boxes e quads usam a geometria canonica do Eixo: origem no canto
superior esquerdo, eixo Y para baixo e unidade em points. Coordenadas
normalizadas so sao emitidas quando o retangulo fica dentro da pagina visivel;
fora disso, a ocorrencia permanece com geometria absoluta e visibilidade
explicita.

## Lacunas Conhecidas

- clipping path exato ainda nao e reconstruido;
- transformacoes aninhadas em Form XObjects ainda sao limitadas;
- ordem de operadores do content stream ainda nao e decodificada;
- inline images sem xref estavel podem ser reportadas como ocorrencias sem
  recurso resolvido em fases futuras.
