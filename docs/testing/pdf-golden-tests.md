# Golden Tests PDF

Os golden tests da Fase 3.13 validam snapshots estruturais pequenos e revisaveis.
Eles nao armazenam dumps completos gigantes dos artefatos.

## Normalizacao

`GoldenArtifactNormalizer` remove somente campos instaveis explicitamente
definidos:

- timestamps;
- IDs de execucao;
- correlacoes de transporte;
- duracoes;
- storage keys locais;
- caminhos temporarios.

Nao sao normalizados para passar no teste:

- texto;
- IDs dos elementos;
- geometria;
- ordem;
- fontes;
- hashes;
- recursos;
- relacoes;
- proveniencia funcional;
- fidelidade.

## Tolerancias

As tolerancias iniciais sao:

| Tipo | Tolerancia |
| --- | --- |
| coordenadas | `0.01` point |
| coordenadas normalizadas | `0.0001` |
| matrizes/transformacoes | `0.000001` |
| outros escalares | `0.0` |

Nao existe tolerancia unica para tudo. Geometria, normalizacao e matrizes usam
limites separados para nao esconder regressao.

## Comparacao

`GoldenArtifactComparator` produz diferencas por caminho, categoria e valor:

- `content_change`
- `geometry_change`
- `style_change`
- `resource_change`
- `relation_change`
- `order_change`
- `provenance_change`
- `fidelity_change`
- `warning_change`
- `missing_element`
- `new_element`

O relatorio pode ser serializado em JSON ou Markdown simples por
`GoldenRegressionReport`.

## Atualizacao

Atualizacao de goldens nunca ocorre durante testes normais.

Comando de revisao:

```bash
python -m tests.update_pdf_goldens
```

Sem `--update`, o comando roda em modo dry-run. Ao usar `--update`, revisar o
`git diff` e registrar o motivo da mudanca.

## CI

Os testes marcados com `golden` fazem parte do conjunto padrao. Casos
exploratorios e stress devem usar marcadores proprios e permanecer fora do
caminho rapido ate ficarem estaveis.
