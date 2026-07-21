# PDF Text Capabilities

Status: Fases 3.5 e 3.6 implementadas parcialmente.

## Matriz PyMuPDF

| Informacao | Suporte | Origem | Precisao | Limitacao |
|---|---|---|---|---|
| nome interno | provider_derived | `get_fonts(full=True)` | provider tuple | parcial |
| familia | heuristic | normalizacao conservadora | baixa/media | nao garante equivalencia tipografica |
| subtype | provider_derived | `get_fonts(full=True)` | provider tuple | parcial |
| encoding | partially_supported | `get_fonts(full=True)` | provider tuple | sem differences completas |
| ToUnicode | unknown | referencias de recurso | desconhecida | mapa nao decodificado |
| CMap | unknown | referencias de recurso | desconhecida | mapa nao decodificado |
| glyph id | unsupported | rawdict | indisponivel | glifo preservado sem id nativo |
| char code | unsupported | rawdict | indisponivel | nao decodificado do stream |
| metricas | partially_supported | rawdict | observada | metricas de fonte nao completas |
| fonte incorporada | partially_supported | referencias | parcial | bytes nao extraidos |
| subset | heuristic | nome da fonte | conservadora | depende do prefixo PDF |
| escrita vertical | heuristic | direcao da linha | aproximada | sem CMap completo |

## Regras

Nenhum tipo `fitz` atravessa a fronteira publica. Bytes de fontes incorporadas
nao sao expostos por API, CLI ou JSON principal nesta fase.
