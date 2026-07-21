# PDF Visual Elements

Status: inicial, Fase 3.10.

`PDFVisualElement` e o contrato comum para elementos selecionaveis em uma futura
cena visual de PDF.

## Tipos iniciais

- `text_glyph`
- `text_word`
- `text_span`
- `text_line`
- `text_block`
- `image`
- `vector`
- `clipping_path`
- `link`
- `annotation`
- `form_widget`
- `unknown`

## Campos principais

Cada elemento preserva, quando disponivel:

- `element_id`, `element_type`, `page_id`;
- `bounding_box`, `normalized_bounding_box`, `quad`, `polygon` ou
  `path_reference`;
- `local_transform`, `effective_transform`;
- `paint_order`, `native_order`, `scene_order`;
- `order_method`, `order_confidence`;
- `visibility`, `opacity`, `blend_mode`;
- `clip_path_reference`, `clip_chain`;
- `layer_reference`, `layer_membership_reference`;
- `resource_references`;
- `source_references`;
- `fidelity`, `editability_hint`;
- `warnings`, `provenance`.

## Fidelidade

Valores iniciais:

- `native_exact`;
- `native_normalized`;
- `provider_reconstructed`;
- `eixo_derived`;
- `heuristic`;
- `raster_only`;
- `unsupported`;
- `unknown`.

## Editabilidade preliminar

Valores iniciais:

- `native_editable`;
- `partially_editable`;
- `reconstruction_required`;
- `raster_only`;
- `unknown`.

Esses valores sao sinais tecnicos. Eles nao autorizam edicao direta nesta fase.
