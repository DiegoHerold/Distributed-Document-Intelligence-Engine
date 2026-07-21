# PDF Font Catalog

Status: Fases 3.5 e 3.6 implementadas parcialmente.

`PDFFontCatalog` consolida fontes, programas, encodings, CMaps, mapeamentos de
glifos, estilos e usos.

Consultas suportadas:

- `font_by_id(font_id)`
- `fonts_for_page(page_index)`
- `usages_for_font(font_id)`
- `styles_for_font(font_id)`
- `fonts_without_unicode()`
- `partially_resolved_fonts()`

## Estados De Suporte

`PDFTypographySupportStatus` diferencia:

- `supported`
- `partially_supported`
- `provider_derived`
- `heuristic`
- `unsupported`
- `unknown`
- `extraction_failed`

## Subset

Nomes como `ABCDEE+Arial-BoldMT` sao separados em:

- `subset_prefix`: `ABCDEE`
- `internal_font_name`: `ABCDEE+Arial-BoldMT`
- `postscript_name`: `Arial-BoldMT`
- `normalized_family`: `Arial`

A normalizacao e conservadora e registra metodo e confianca.
