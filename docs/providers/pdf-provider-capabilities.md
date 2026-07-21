# PDF Provider Capabilities

Status: Fases 3.4 a 3.6 implementadas parcialmente.

## Matriz PyMuPDF

| Recurso | Nivel | Estrategia | Limitacao |
|---|---|---|---|
| objetos indiretos | Parcial | `xref_length()` e `xref_object()` quando disponiveis | resumo seguro, sem bytes grandes |
| xref | Parcial | xref como identificador estavel | geracao assumida como `0` quando nao exposta |
| content streams | Parcial | `page.get_contents()` | sequencia preservada, sem operadores |
| operadores graficos | Nao suportado | adiado para fases posteriores | PyMuPDF nao expoe sequencia bruta neste adapter |
| fontes | Parcial | `page.get_fonts(full=True)` | sem normalizacao tipografica completa |
| imagens | Parcial | `page.get_images(full=True)` | sem extrair bytes nem ocorrencias visuais |
| mascaras | Parcial | `smask` de imagens | mapeamento como recurso tecnico |
| Form XObjects | Parcial | `page.get_xobjects()` quando disponivel | sem decomposicao aninhada completa |
| ExtGState | Nao suportado | registrado como lacuna | fase 3.8 devera aprofundar |
| espacos de cor | Parcial | metadados de imagem quando disponiveis | sem conversao de cor |
| patterns | Nao suportado | preservado como recurso desconhecido se reportado | sem rasterizacao |
| shadings | Nao suportado | preservado como recurso desconhecido se reportado | sem interpretacao |
| camadas opcionais | Nao suportado | registrado como lacuna | sem UI ou toggles |
| ordem de pintura | Parcial | ordem de content streams | sem ordem de operadores |
| tipografia | Parcial | `get_fonts(full=True)` | sem decodificar programas de fonte |
| texto granular | Parcial | `get_text("rawdict")` | sem glyph id, char code ou operador bruto |

## Regra

Nenhum contrato publico expoe `fitz.Document`, `fitz.Page`, `fitz.Rect` ou outro
tipo concreto do provider.
