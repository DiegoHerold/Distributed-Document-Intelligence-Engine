# PDF Image Capabilities

Status: Fase 3.7 implementada parcialmente.

## PyMuPDF

| Informacao | Suporte | Origem | Limitacao |
|---|---|---|---|
| Image XObject | Provider-derived | `page.get_images(full=True)` | metadados por xref |
| bytes codificados | Parcial | `document.extract_image(xref)` | identidade do stream original depende do provider |
| ocorrencias visuais | Parcial | `page.get_image_info(xrefs=True)` | ordem e geometria sao best effort |
| soft mask | Parcial | `smask` em `get_images(full=True)` | sem composicao alpha completa |
| image mask | Parcial | catalogo de recursos | sem renderizacao da mascara |
| inline images | Desconhecido | `get_image_info(xrefs=True)` | podem nao ter recurso xref estavel |
| clipping | Heuristico | bbox contra pagina | clipping path exato fica para fase posterior |
| Form XObject aninhado | Limitado | metadados do provider | transformacoes aninhadas ainda nao sao completas |

## Regras

- Nunca expor `fitz.Document`, `fitz.Page`, `fitz.Pixmap` ou `fitz.Rect`.
- Nunca serializar bytes grandes dentro do artifact JSON.
- Sempre separar recurso, ocorrencia e mascara.
- Registrar warnings quando uma ocorrencia nao puder ser associada a recurso
  estavel.

## Proxima Evolucao

A Fase 3.8 deve complementar imagens com vetores, estado grafico, clipping,
opacidade e blend mode mais precisos.
