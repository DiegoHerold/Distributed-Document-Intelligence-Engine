# Indice Oficial de Fases

## Bloco 0 - Organizacao e governanca do projeto

Status: concluido.

| Fase | Entrega | Estado |
|---|---|---|
| 0.1 | Organizar arquivos de contexto | Concluida |
| 0.2 | Consolidar contexto mestre | Concluida |
| 0.3 | Criar `AGENTS.md` | Concluida |
| 0.4 | Registrar primeiras ADRs | Concluida |
| 0.5 | Criar indice oficial de fases | Concluida |

## Bloco 1 - Fundacao tecnica reutilizavel

Dependencia: Bloco 0.

| Fase | Entrega | Estado |
|---|---|---|
| 1.1 | Estrutura inicial do monorepo | Planejada |
| 1.2 | Tipos fundamentais | Planejada |
| 1.3 | Contratos de processamento | Planejada |
| 1.4 | Camada de aplicacao | Planejada |
| 1.5 | Capability Registry | Planejada |
| 1.6 | LocalRuntime | Planejada |
| 1.7 | DocumentEngine | Planejada |
| 1.8 | Biblioteca Python publica | Planejada |
| 1.9 | API REST inicial | Planejada |
| 1.10 | CLI inicial | Concluida |
| 1.11 | Testes de paridade | Concluida |

## Blocos futuros

## Bloco 2 - Ingestao e ciclo de vida do documento

Dependencia: Bloco 1.

| Fase | Entrega | Estado |
|---|---|---|
| 2.1 | Criar abstracao `DocumentSource` | Concluida |
| 2.2 | Criar `SourceResolver` | Concluida |
| 2.3 | Detectar formato e MIME real | Concluida |
| 2.4 | Criar hashing e identidade do conteudo | Concluida |
| 2.5 | Criar `LocalArtifactStore` | Planejada |
| 2.6 | Registrar documento recebido | Planejada |
| 2.7 | Criar ciclo de vida local do documento | Planejada |
| 2.8 | Validacoes iniciais de seguranca | Planejada |

| Bloco | Tema | Dependencia principal | Estado |
|---|---|---|---|
| 2 | Ingestao e ciclo de vida do documento | Bloco 1 | Em andamento |
| 3 | Extracao nativa de PDF | Blocos 1 e 2 | Planejado |
| 4 | Extracao nativa de Excel | Blocos 1 e 2 | Planejado |
| 5 | Modelo documental canonico e evidencias | Blocos 3 e 4 | Planejado |
| 6 | Reconstrucao estrutural | Bloco 5 | Planejado |
| 7 | Schemas, templates e extracao | Bloco 6 | Planejado |
| 8 | Normalizacao, validacao e confianca | Bloco 7 | Planejado |
| 9 | Inspector avancado, Router e Processing Plan | Blocos 2 a 8 | Planejado |
| 10 | Renderizacao, imagens e OCR seletivo | Blocos 3, 5 e 9 | Planejado |
| 11 | Semantica e modelos de IA | Blocos 7 a 10 | Planejado |
| 12 | Reconciliacao e revisao humana | Blocos 8 e 11 | Planejado |
| 13 | Persistencia e API de producao | Blocos 1 a 12 | Planejado |
| 14 | Temporal e execucao distribuida | Bloco 13 | Planejado |
| 15 | Observabilidade, seguranca e desempenho | Blocos 13 e 14 | Planejado |
| 16 | Produto e ecossistema | Blocos 13 a 15 | Planejado |

## Ordem recomendada para comecar

1. Fechar Bloco 0.
2. Criar o monorepo minimo.
3. Criar tipos fundamentais.
4. Criar contratos publicos.
5. Expor os contratos pela biblioteca, API e CLI sem duplicacao.
6. Criar testes de paridade.

## Contradicao resolvida

O arquivo de fases revisadas tambem usa o nome "Bloco 0" para contratos, corpus e criterios de qualidade. Nesta documentacao, esse conteudo fica absorvido pelo Bloco 1, principalmente pelas fases de tipos fundamentais, contratos de processamento, testes e estrutura tecnica.
