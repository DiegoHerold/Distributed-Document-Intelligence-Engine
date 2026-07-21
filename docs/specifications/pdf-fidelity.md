# PDF Fidelity

Status: inicial, Fase 3.11.

Fidelidade descreve o quanto a decomposicao preserva a estrutura nativa do PDF.
Ela nao e uma media simples: uma dimensao critica desconhecida pode limitar a
fidelidade geral.

## Niveis

- `native_exact`: informacao recuperada diretamente da estrutura nativa.
- `native_normalized`: informacao nativa convertida para contratos canonicos.
- `provider_reconstructed`: estrutura reconstruida pelo provider.
- `eixo_derived`: informacao calculada pelo Eixo.
- `heuristic`: informacao estimada.
- `raster_only`: conteudo disponivel apenas como imagem.
- `unsupported`: conteudo conhecido, mas nao suportado.
- `unknown`: nao foi possivel determinar.

## Dimensoes

`PDFFidelitySummary` consolida dimensoes como:

- geometria;
- texto;
- fontes;
- imagens;
- vetores;
- interacoes;
- ordem de pintura;
- recursos;
- inspecao.

Cada `PDFFidelityDimension` preserva nivel, metodo, motivos e warnings.

## Contagens

O resumo agrega contagens de elementos por nivel de fidelidade a partir das
cenas, mantendo a explicabilidade por elemento no `PDFVisualElement`.
