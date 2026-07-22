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
| 2.5 | Criar `LocalArtifactStore` | Concluida |
| 2.6 | Criar ciclo de vida do documento | Concluida |
| 2.7 | Criar jobs locais persistentes | Concluida |
| 2.8 | Validacoes iniciais de seguranca | Concluida |

## Bloco 3 - Decomposicao nativa e cena visual de PDF

Dependencias: Blocos 1 e 2.

Contexto detalhado: [block-3-native-pdf-scene.md](../block-3-native-pdf-scene.md).

| Fase | Entrega | Estado |
|---|---|---|
| 3.1 | Criar contratos e providers nativos de PDF | Concluida |
| 3.2 | Criar o PDF Inspector tecnico | Concluida |
| 3.3 | Definir geometria e coordenadas canonicas | Concluida |
| 3.4 | Mapear recursos, objetos e content streams | Concluida |
| 3.5 | Criar catalogo de fontes e tipografia | Concluida |
| 3.6 | Extrair texto granular e hierarquia textual nativa | Concluida |
| 3.7 | Extrair imagens, mascaras e ocorrencias | Concluida |
| 3.8 | Extrair vetores e estado grafico | Concluida |
| 3.9 | Extrair links, anotacoes, formularios e camadas | Parcial |
| 3.10 | Montar a cena visual de cada pagina | Concluida |
| 3.11 | Criar o `NativePDFSceneArtifact` | Concluida |
| 3.12 | Integrar parser, armazenamento e canais publicos | Concluida |
| 3.13 | Criar corpus, golden tests e regressao visual | Concluida |
| 3.14 | Laboratorio de validacao com PDFs reais | Concluida |

| Bloco | Tema | Dependencia principal | Estado |
|---|---|---|---|
| 2 | Ingestao e ciclo de vida do documento | Bloco 1 | Concluido |
| 3 | Decomposicao nativa e cena visual de PDF | Blocos 1 e 2 | Em andamento |
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
