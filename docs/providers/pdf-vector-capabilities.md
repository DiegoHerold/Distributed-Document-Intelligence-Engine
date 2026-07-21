# PDF Vector Capabilities

Status: Fase 3.8 implementada parcialmente.

## PyMuPDF

| Informacao | Suporte | Origem | Limitacao |
|---|---|---|---|
| caminhos | Provider-derived | `page.get_drawings()` | sem operadores PDF crus |
| linhas | Parcial | items `l` | coordenadas provider-derived |
| retangulos | Parcial | items `re` | sem relacao semantica com tabelas |
| curvas Bezier | Parcial | items `c` | pontos de controle preservados |
| subpaths | Parcial | divisao conservadora por `move_to` | provider nem sempre separa subpaths |
| fill e stroke | Parcial | chaves `fill`, `color`, `type` | estilo efetivo, nao historico de operadores |
| dash, cap, join | Parcial | chaves de desenho | formato varia por versao do provider |
| opacidade | Parcial | `fill_opacity`, `stroke_opacity` | transparencia completa depende de ExtGState |
| blend mode | Parcial | `blendmode` quando disponivel | valores desconhecidos sao preservados |
| clipping | Desconhecido/parcial | `get_drawings()` quando exposto | intersecoes complexas nao materializadas |
| patterns e shadings | Desconhecido | metadados do provider | nao rasterizados nesta fase |
| Form XObjects | Limitado | metadados do provider | definicao e ocorrencia ainda nao separadas |
| ordem de pintura | Provider-derived | `seqno` ou ordem da lista | aproximacao, sem operadores decodificados |

## Regras

- Nenhum `fitz.Path`, `fitz.Rect`, `fitz.Point` ou objeto backend entra no
  artifact publico.
- Vetores nao sao classificados como tabela, celula, grafico, assinatura ou
  campo.
- Caminhos usados apenas como clipping sao preservados com
  `visibility=not_painted`.
