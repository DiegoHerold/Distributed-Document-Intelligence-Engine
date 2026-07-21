# PDF Provider Capabilities

Status: Fases 3.4 a 3.8 implementadas parcialmente.

## Matriz PyMuPDF

| Recurso | Nivel | Estrategia | Limitacao |
|---|---|---|---|
| objetos indiretos | Parcial | `xref_length()` e `xref_object()` quando disponiveis | resumo seguro, sem bytes grandes |
| xref | Parcial | xref como identificador estavel | geracao assumida como `0` quando nao exposta |
| content streams | Parcial | `page.get_contents()` | sequencia preservada, sem operadores |
| operadores graficos | Parcial | `page.get_drawings()` | desenhos efetivos, sem sequencia bruta de operadores |
| fontes | Parcial | `page.get_fonts(full=True)` | sem normalizacao tipografica completa |
| imagens | Parcial | `page.get_images(full=True)` e `document.extract_image(xref)` | bytes referenciados por hash/tamanho, sem payload no JSON |
| ocorrencias de imagem | Parcial | `page.get_image_info(xrefs=True)` | geometria e ordem best effort |
| mascaras | Parcial | `smask` de imagens | soft masks mapeadas como referencias tecnicas |
| Form XObjects | Parcial | `page.get_xobjects()` quando disponivel | sem decomposicao aninhada completa |
| ExtGState | Parcial | propriedades efetivas em drawings | sem historico completo de save/restore do PDF |
| espacos de cor | Parcial | metadados de imagem quando disponiveis | sem conversao de cor |
| patterns | Nao suportado | preservado como recurso desconhecido se reportado | sem rasterizacao |
| shadings | Nao suportado | preservado como recurso desconhecido se reportado | sem interpretacao |
| camadas opcionais | Nao suportado | registrado como lacuna | sem UI ou toggles |
| ordem de pintura | Parcial | `seqno` ou ordem de drawings | provider approximation |
| tipografia | Parcial | `get_fonts(full=True)` | sem decodificar programas de fonte |
| texto granular | Parcial | `get_text("rawdict")` | sem glyph id, char code ou operador bruto |
| vetores | Parcial | `page.get_drawings()` | sem reconstruir tabelas ou Form XObjects aninhados |
| clipping | Parcial | drawings quando exposto | intersecoes complexas nao materializadas |

## Regra

Nenhum contrato publico expoe `fitz.Document`, `fitz.Page`, `fitz.Rect` ou outro
tipo concreto do provider.
