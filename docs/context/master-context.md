# Contexto Mestre

Eixo e uma plataforma modular de inteligencia documental para transformar documentos heterogeneos em dados estruturados, explicaveis e reutilizaveis.

O projeto tambem pode ser descrito como:

> Eixo - Distributed Document Intelligence Engine

Frase de apoio:

> De arquivos complexos a dados estruturados.

## Visao

O Eixo nao deve ser entendido apenas como extrator de PDF, OCR, template builder, API de extracao, classificador ou wrapper de IA.

Ele deve ser entendido como um motor documental modular, orientado a artefatos e evidencias, com processamento adaptativo, capabilities intercambiaveis e execucao local ou distribuida.

## Problema

Documentos reais nao sao uniformes. Um mesmo arquivo pode conter texto digital, paginas escaneadas, tabelas como imagem, formularios, anexos, fontes corrompidas, colunas, assinaturas e estruturas visuais que nao aparecem corretamente em extracoes textuais simples.

O formato fisico tambem nao define o significado. PDFs, planilhas e documentos de texto podem representar balancetes, contratos, extratos, notas fiscais, relatorios, formularios e muitos outros tipos documentais.

## Objetivos estrategicos

- Reutilizar o mesmo nucleo como biblioteca, API, CLI, worker ou plataforma distribuida.
- Manter independencia de fornecedores, OCRs, modelos, bancos e infraestrutura.
- Produzir resultados explicaveis com evidencias e proveniencia.
- Processar por documento, pagina, regiao ou campo quando necessario.
- Escalar de execucao local para execucao distribuida sem reescrever o nucleo.
- Evoluir progressivamente sem antecipar infraestrutura pesada.

## Nao objetivos iniciais

- Criar muitos microsservicos antes do nucleo estar estavel.
- Fazer OCR completo por padrao.
- Acoplar templates a parsers especificos.
- Colocar regras de dominio dentro do core.
- Tratar revisao humana como falha.
- Usar IA para todo documento quando uma rota deterministica for suficiente.

## Principios arquiteturais obrigatorios

- O motor nao depende da API.
- A API depende do motor.
- Workers executam capabilities, mas nao contem a inteligencia principal.
- Templates operam sobre o modelo canonico, nao sobre parsers especificos.
- Providers e infraestrutura sao substituiveis.
- Resultado sem evidencia e incompleto.
- Revisao humana e parte valida do fluxo.
- Artefatos, planos e contratos devem ser versionados.
- Capacidade e diferente de provider.
- Modulo logico nao significa microsservico fisico.

## Formas de uso

- Biblioteca Python embarcada.
- API REST.
- CLI de desenvolvimento e diagnostico.
- Plataforma distribuida com runtime remoto.
- Workers especializados para execucao fisica.

## Arquitetura resumida

```text
Camada de consumo
  -> Control Plane
  -> Document Intelligence Kernel
  -> Capabilities
  -> Execution Plane
```

O diagrama completo esta em [processing-flow.mmd](../architecture/diagrams/processing-flow.mmd).

## Kernel

O kernel coordena o ciclo de processamento, consulta capabilities, cria planos, executa ou delega atividades, consolida artefatos, construi o documento canonico, normaliza, valida, calcula confianca, reconcilia candidatos e registra evidencias.

O kernel nao deve conter autenticacao, billing, UI, FastAPI, detalhes de PostgreSQL, Redis, MinIO, Temporal, regras contabeis especificas ou chamadas diretas a fornecedores.

## Modelo documental canonico

O Canonical Document Model e a representacao intermediaria comum entre formatos e capacidades.

Elementos centrais:

- documento;
- superficies, como paginas e abas;
- elementos, como palavras, celulas, imagens e regioes;
- estruturas, como tabelas, listas, secoes e formularios;
- relacoes espaciais, logicas e hierarquicas;
- evidencias;
- proveniencia;
- artefatos.

## Processamento adaptativo

Todos os documentos passam por inspecao. O sistema deve escolher a rota conforme sinais tecnicos, perfil de processamento, politicas e capabilities disponiveis.

Exemplos:

- texto nativo bom usa parser nativo;
- pagina escaneada usa renderizacao e OCR;
- regiao problematica pode ser reprocessada separadamente;
- tabela visual pode usar engine de tabela;
- campos ambiguos podem escalar para modelo semantico;
- conflitos persistentes podem gerar revisao humana.

## Direcao Do Bloco 3

Com a ingestao local, armazenamento, jobs e seguranca do Bloco 2 estabelecidos,
o Bloco 3 passa a ter foco em decomposicao nativa e cena visual de PDF.

O PDF deve ser tratado como uma cena grafica, nao apenas como texto extraido. A
capability de PDF deve preservar objetos nativos, recursos, content streams,
geometria, tipografia, imagens, vetores, clipping, transparencia, ordem de
desenho, relacoes e proveniencia.

O bloco deve produzir duas representacoes complementares:

- `NativePDFParseArtifact`, para preservar a evidencia nativa com o minimo de
  interpretacao;
- `PDFPageScene`, para organizar uma cena visual normalizada, independente do
  provider, apta a preview, selecao, diagnostico e edicao futura.

O marco de conclusao do Bloco 3 e gerar um `NativePDFSceneArtifact` versionado e
reconstruivel. Isso nao implica editor visual, OCR, reconstrucao semantica,
tabelas reconstruidas ou exportacao de PDF alterado; esses temas pertencem a
blocos futuros.

As fases iniciais do Bloco 3 ja estabeleceram contratos de provider PDF e um
`PDFTechnicalInspector` especializado. O inspector descreve validade, versao,
paginas, metadados, seguranca, permissoes, cobertura, recursos e sinais de
fidelidade/editabilidade, sem executar decomposicao visual ou extracao granular.
Tambem ja existe uma geometria canonica compartilhada em `eixo.geometry`, com
origem no canto superior esquerdo, eixo Y para baixo, unidade em points,
matrizes afins e coordenadas normalizadas.
O inventario interno de PDF tambem foi iniciado com grafo de objetos,
referencias, content streams, catalogo de recursos e matriz de suporte do
provider, preparando a Fase 3.5 de fontes e tipografia.
Fontes, tipografia e texto granular ja possuem contratos iniciais: catalogo de
fontes, estilos de ocorrencia, glifos, caracteres, palavras, spans, linhas,
blocos, baselines, relacoes e artefato textual nativo.

Detalhes oficiais do bloco estao em
[block-3-native-pdf-scene.md](../roadmap/block-3-native-pdf-scene.md).

## Capabilities

Capabilities representam capacidades logicas, como parser nativo, renderer, OCR, layout, tabelas, classificacao, templates, schemas, normalizacao, validacao, confianca, reconciliacao e proveniencia.

Providers sao implementacoes concretas dessas capabilities.

## Runtimes

O mesmo contrato deve suportar:

- `LocalRuntime`, para biblioteca, testes e execucao simples;
- `TemporalRuntime`, para execucao distribuida futura.

## Decisoes estabelecidas

As decisoes iniciais foram registradas em ADRs:

- [ADR-0001 - Arquitetura modular](../decisions/adr-0001-modular-architecture.md)
- [ADR-0002 - API e biblioteca desde o inicio](../decisions/adr-0002-api-and-library-from-the-start.md)
- [ADR-0003 - Modelo documental canonico](../decisions/adr-0003-canonical-document-model.md)
- [ADR-0004 - Processamento adaptativo](../decisions/adr-0004-adaptive-processing.md)
- [ADR-0005 - Evidencias obrigatorias](../decisions/adr-0005-required-evidence.md)
- [ADR-0006 - LocalRuntime e TemporalRuntime](../decisions/adr-0006-local-and-temporal-runtimes.md)
- [ADR-0007 - Modulos antes de microsservicos](../decisions/adr-0007-modules-before-microservices.md)

## Questoes abertas

- Linguagem principal final do kernel.
- Biblioteca principal de PDF.
- Primeiro provider de OCR.
- Representacao exata do Document Graph.
- DSL de templates.
- Modelo de schema.
- Calculo final de confianca.
- Politica inicial de cache.
- Estrategia multi-tenant.
- Modelos semanticos locais ou externos.
- Primeira versao da review UI.

## Fontes historicas

Os documentos originais foram preservados em [archive](../archive/README.md).
