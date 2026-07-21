# PDF Scene Relations

Status: inicial, Fase 3.10.

`PDFSceneRelation` conecta elementos da cena a artefatos, recursos e outros
elementos usando IDs serializaveis.

## Tipos iniciais

- `contains`;
- `contained_by`;
- `uses_resource`;
- `uses_font`;
- `uses_image`;
- `uses_graphics_state`;
- `clipped_by`;
- `belongs_to_layer`;
- `appearance_of`;
- `widget_of`;
- `links_to`;
- `derived_from`;
- `defined_in_form`;
- `occurrence_of`;
- `painted_before`;
- `painted_after`.

## Politica

Relacoes usam IDs, nao objetos aninhados. Recursos grandes permanecem nos
artefatos de origem e sao apenas referenciados pela cena.

O builder cria relacoes derivadas de:

- `source_references`, como `derived_from`;
- `resource_references`, como `uses_font`, `uses_image` ou `uses_resource`;
- `clip_path_reference`, como `clipped_by`;
- `layer_reference`, como `belongs_to_layer`;
- widgets, como `widget_of`;
- links, como `links_to`;
- ordem visual, como `painted_before`.
