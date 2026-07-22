# Roadmap

Este roadmap consolida o arquivo historico `original-implementation-roadmap-2026-07-20.txt`.

## Regra obrigatoria

Toda funcionalidade publica deve seguir o fluxo:

```text
Contrato
  -> implementacao no nucleo
  -> caso de uso na camada de aplicacao
  -> biblioteca Python
  -> API REST
  -> CLI, quando util
  -> testes de paridade
  -> documentacao
```

API, biblioteca, workers e CLI nunca devem reimplementar a mesma logica.

## Blocos

| Bloco | Tema | Estado |
|---|---|---|
| 0 | Organizacao e governanca do projeto | Concluido |
| 1 | Fundacao tecnica reutilizavel | Planejado |
| 2 | Ingestao e ciclo de vida do documento | Concluido |
| 3 | Decomposicao nativa e cena visual de PDF | Em andamento |
| 4 | Extracao nativa de Excel | Planejado |
| 5 | Modelo documental canonico e evidencias | Planejado |
| 6 | Reconstrucao estrutural | Planejado |
| 7 | Schemas, templates e extracao | Planejado |
| 8 | Normalizacao, validacao e confianca | Planejado |
| 9 | Inspector avancado, Router e Processing Plan | Planejado |
| 10 | Renderizacao, imagens e OCR seletivo | Planejado |
| 11 | Semantica e modelos de IA | Planejado |
| 12 | Reconciliacao e revisao humana | Planejado |
| 13 | Persistencia e API de producao | Planejado |
| 14 | Temporal e execucao distribuida | Planejado |
| 15 | Observabilidade, seguranca e desempenho | Planejado |
| 16 | Produto e ecossistema | Planejado |

## Marcos principais

| Marco | Entrega esperada |
|---|---|
| 1 | Fundacao reutilizavel |
| 2 | Extracao nativa utilizavel |
| 3 | Extracao estruturada confiavel |
| 4 | Motor adaptativo |
| 5 | Plataforma de producao |
| 6 | Produto completo |

## Proxima fase recomendada

Com as Fases 3.12 e 3.13 concluidas no workspace, a proxima etapa natural e
fechar as pendencias best effort da Fase 3.9 ou avancar para o Bloco 4:
extracao nativa de Excel. A interatividade PDF ainda deve ser tratada como best
effort ate a cobertura detalhada de links, anotacoes e formularios amadurecer.

Veja o contexto detalhado em
[block-3-native-pdf-scene.md](block-3-native-pdf-scene.md).

## Indice detalhado

Veja [phases/README.md](phases/README.md).

## Relatorio de conclusao

Veja [phase-0-completion-report.md](phase-0-completion-report.md).
