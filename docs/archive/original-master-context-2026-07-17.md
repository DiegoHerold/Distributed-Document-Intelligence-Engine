# Contexto Mestre — Distributed Document Intelligence Engine

> Documento de contexto arquitetural, funcional e estratégico para orientar inteligências artificiais, desenvolvedores, arquitetos, revisores e agentes de código no desenvolvimento de um motor universal de inteligência documental.

---

## 0. Identificação do documento

| Campo | Valor |
|---|---|
| Projeto | Distributed Document Intelligence Engine |
| Tipo | Contexto mestre do produto e da arquitetura |
| Status | Visão arquitetural ideal |
| Versão | 1.0 |
| Idioma | Português |
| Objetivo | Consolidar toda a visão do projeto em uma única fonte de verdade |
| Público-alvo | IAs, arquitetos, desenvolvedores, DevOps, produto, QA e futuros mantenedores |

---

# 1. Propósito deste documento

Este documento existe para que qualquer inteligência artificial ou pessoa que entre no projeto consiga compreender, sem depender de conversas anteriores:

- qual problema o projeto resolve;
- qual é a visão de longo prazo;
- quais princípios arquiteturais são obrigatórios;
- como o motor deve funcionar;
- como o mesmo núcleo será reutilizado como biblioteca, API, CLI, worker ou plataforma distribuída;
- como documentos de diferentes formatos serão transformados em uma representação comum;
- como o sistema decidirá quando utilizar parser nativo, OCR, análise de layout, reconhecimento de tabelas, modelos semânticos ou revisão humana;
- como evitar que o projeto nasça excessivamente complexo;
- como permitir evolução progressiva sem reescrever o núcleo;
- quais decisões não devem ser tomadas sem justificativa;
- quais anti-padrões devem ser evitados;
- como o sistema deve produzir resultados explicáveis, versionados, auditáveis e acompanhados de evidências.

Este arquivo deve ser tratado como uma das principais fontes de verdade do projeto.

Sempre que uma nova fase for desenvolvida, sua implementação deve estar alinhada com os princípios definidos aqui.

---

# 2. Visão do produto

O projeto não deve ser entendido apenas como:

- um extrator de PDF;
- um sistema de OCR;
- um template builder;
- um classificador de documentos;
- uma API de extração;
- um conjunto de workers;
- uma aplicação contábil;
- um wrapper sobre modelos de IA.

O produto deve ser entendido como:

> Uma plataforma modular de inteligência documental, orientada a artefatos e evidências, com processamento adaptativo, capacidades intercambiáveis e execução local ou distribuída.

O objetivo é construir um núcleo reutilizável capaz de:

1. receber documentos de diferentes formatos;
2. inspecionar suas características;
3. criar um plano de processamento adequado;
4. utilizar apenas as capacidades necessárias;
5. converter resultados de múltiplos métodos para um modelo documental canônico;
6. identificar estruturas visuais e semânticas;
7. executar templates, schemas, regras ou instruções;
8. produzir dados estruturados;
9. normalizar e validar os resultados;
10. calcular confiança;
11. reconciliar divergências;
12. preservar evidências;
13. solicitar revisão humana somente quando necessário;
14. funcionar tanto localmente quanto em uma arquitetura distribuída.

---

# 3. Problema que o projeto resolve

Documentos não são uniformes.

Um mesmo arquivo PDF pode conter:

- texto digital;
- páginas escaneadas;
- tabelas incorporadas como imagem;
- assinaturas;
- carimbos;
- gráficos;
- formulários;
- anexos;
- páginas rotacionadas;
- fontes corrompidas;
- colunas;
- listas;
- hierarquias;
- cabeçalhos;
- rodapés;
- campos sem rótulo claro;
- estruturas visuais que não aparecem corretamente na extração textual.

Além disso, o formato físico não define o significado do documento.

Um PDF pode representar:

- balancete;
- contrato;
- extrato bancário;
- nota fiscal;
- relatório;
- currículo;
- laudo;
- formulário;
- declaração;
- demonstrativo;
- documento jurídico;
- documento administrativo;
- documento médico;
- planilha convertida para PDF;
- página digital misturada com imagem.

Soluções tradicionais normalmente cometem um dos seguintes erros:

```text
PDF → extrair texto → aplicar regex
```

ou:

```text
PDF → OCR completo → enviar para IA
```

ou:

```text
PDF → modelo multimodal → retornar JSON
```

Esses caminhos são insuficientes porque:

- desperdiçam recursos;
- perdem informação nativa;
- não preservam estrutura;
- não registram evidências adequadas;
- são difíceis de auditar;
- têm custos elevados;
- não escalam bem;
- tornam o resultado dependente de um único fornecedor;
- não distinguem falha de reconhecimento, estrutura, semântica ou validação;
- não permitem reprocessamento granular;
- não explicam como cada valor foi obtido.

O projeto deve resolver esses problemas com um motor adaptativo, modular e orientado a evidências.

---

# 4. Princípio central do projeto

A arquitetura não deve executar sempre o mesmo pipeline.

O fluxo incorreto seria:

```text
Documento
   ↓
OCR completo
   ↓
IA
   ↓
Resultado
```

O fluxo correto deve ser:

```text
Documento
   ↓
Inspeção de baixo custo
   ↓
Criação de um plano de processamento
   ↓
Execução seletiva das capacidades necessárias
   ↓
Construção do modelo documental canônico
   ↓
Extração orientada por template, schema, regra ou instrução
   ↓
Normalização
   ↓
Validação
   ↓
Avaliação de confiança
   ↓
Escalonamento somente das partes problemáticas
   ↓
Conclusão ou revisão humana
```

A regra geral é:

```text
Cheap first
        ↓
Selective processing
        ↓
Confidence evaluation
        ↓
Escalate only when necessary
        ↓
Human review as final fallback
```

Em português:

```text
primeiro o processamento mais simples;
depois apenas as capacidades necessárias;
avaliação contínua de confiança;
escalonamento somente das partes problemáticas;
revisão humana como último recurso.
```

---

# 5. Objetivos estratégicos

## 5.1. Reutilização

O mesmo núcleo deve funcionar:

- como biblioteca Python;
- como biblioteca para outros runtimes por meio de SDK;
- como API REST;
- como API assíncrona;
- como ferramenta CLI;
- como worker;
- como componente interno de outro produto;
- como plataforma distribuída;
- como serviço multi-tenant;
- como instalação local;
- como solução privada em infraestrutura própria.

## 5.2. Independência de fornecedor

O núcleo não deve depender diretamente de:

- um fornecedor específico de OCR;
- um modelo específico de IA;
- um serviço específico de nuvem;
- uma biblioteca específica de PDF;
- um banco específico para toda a lógica;
- Temporal como requisito obrigatório;
- MinIO como requisito obrigatório;
- Redis como requisito obrigatório;
- OpenAI como requisito obrigatório.

Essas tecnologias podem ser utilizadas por meio de adapters e providers.

## 5.3. Explicabilidade

Cada valor extraído deve responder:

- de onde veio;
- em qual página estava;
- em qual região estava;
- qual método o encontrou;
- qual template ou regra participou;
- quais normalizações foram aplicadas;
- quais validações foram executadas;
- qual foi a confiança;
- se houve divergência;
- se OCR foi usado;
- se modelo semântico foi usado;
- por que o resultado foi aceito ou rejeitado.

## 5.4. Granularidade

O motor deve conseguir processar em diferentes níveis:

- documento;
- página;
- seção;
- bloco;
- tabela;
- linha;
- coluna;
- célula;
- região;
- campo;
- elemento.

## 5.5. Escalabilidade

O sistema deve permitir que recursos sejam escalados independentemente:

- inspeção;
- parsing nativo;
- renderização;
- OCR;
- layout;
- tabelas;
- processamento semântico;
- validação;
- reconciliação;
- revisão.

## 5.6. Evolução progressiva

A arquitetura lógica pode ser completa desde o início, mas a arquitetura física inicial deve ser simples.

```text
Arquitetura lógica: modular e extensível
Arquitetura física inicial: poucos processos e poucos serviços
```

---

# 6. Não objetivos iniciais

O projeto não deve tentar, na primeira versão:

- entender perfeitamente qualquer documento existente;
- suportar todos os formatos de arquivo;
- criar dezenas de microsserviços;
- treinar modelos próprios;
- construir um editor visual completo de templates;
- resolver reconhecimento universal de tabelas;
- eliminar toda revisão humana;
- atingir escala global imediatamente;
- implementar Kubernetes antes de existir necessidade;
- utilizar simultaneamente múltiplos brokers sem justificativa;
- criar um marketplace de plugins;
- implementar billing completo;
- construir todos os SDKs antes do núcleo;
- suportar todos os bancos ou nuvens;
- automatizar aprendizado contínuo sem governança.

O foco inicial deve ser criar um núcleo correto, testável e evolutivo.

---

# 7. Princípios arquiteturais obrigatórios

## 7.1. O motor não depende da API

```text
O motor documental não depende da API.
A API depende do motor documental.
```

## 7.2. Os workers não contêm a inteligência principal

```text
Os workers não implementam a inteligência.
Os workers executam capacidades do motor.
```

## 7.3. Templates não dependem de parsers específicos

```text
Templates não devem conhecer PDFium, PyMuPDF, OCR ou Excel.
Templates operam sobre o modelo documental canônico.
```

## 7.4. Infraestrutura é substituível

```text
A infraestrutura pode mudar.
Os contratos e o núcleo permanecem.
```

## 7.5. Resultado sem evidência é incompleto

Todo campo relevante deve possuir proveniência e evidência.

## 7.6. Revisão humana não é falha

O status `review_required` representa uma conclusão válida do workflow quando a confiança ou consistência não é suficiente.

## 7.7. Processamento deve ser idempotente sempre que possível

Reprocessar a mesma atividade com os mesmos inputs, versões e configurações deve produzir um resultado equivalente ou reutilizar um artefato em cache.

## 7.8. Artefatos intermediários devem ser versionados

OCR, layout, tabelas, renders, extrações e validações não devem ser tratados como dados temporários sem identidade.

## 7.9. Capacidade é diferente de provider

Exemplo:

```text
Capacidade: OCR
Provider: PaddleOCR
Provider: Tesseract
Provider: Azure OCR
Provider: serviço privado
```

## 7.10. Módulo lógico não significa microsserviço

Um módulo deve possuir fronteiras claras, mas pode compartilhar o mesmo processo e deployment inicialmente.

---

# 8. Formas de utilização

## 8.1. Biblioteca local

Uso esperado:

```python
from document_engine import DocumentEngine, ProcessingRequest

engine = DocumentEngine.local()

result = await engine.process(
    ProcessingRequest(
        source="balancete.pdf",
        profile="balanced",
        schema="accounting_trial_balance"
    )
)
```

Nesse modo, o consumidor não deve ser obrigado a instalar:

- API;
- Temporal;
- RabbitMQ;
- Kafka;
- Kubernetes;
- PostgreSQL;
- MinIO;
- Redis.

O processamento pode utilizar:

- armazenamento local;
- cache em memória ou disco;
- execução assíncrona local;
- pool de threads;
- pool de processos;
- GPU local opcional.

## 8.2. API

Exemplo:

```http
POST /v1/extractions
GET  /v1/extractions/{job_id}
GET  /v1/extractions/{job_id}/result
GET  /v1/extractions/{job_id}/events
POST /v1/extractions/{job_id}/cancel
```

A API adiciona:

- autenticação;
- autorização;
- tenants;
- uploads;
- jobs;
- webhooks;
- limites;
- armazenamento;
- auditoria;
- revisão;
- controle de versões;
- gerenciamento de templates e schemas.

## 8.3. Plataforma distribuída

```text
Cliente
   ↓
API
   ↓
Control Plane
   ↓
Orquestrador
   ↓
Execution Runtime
   ↓
Workers CPU / GPU / Semânticos
   ↓
Artifact Store
   ↓
Resultado
```

## 8.4. CLI

Exemplos conceituais:

```bash
document-engine inspect arquivo.pdf
document-engine process arquivo.pdf --profile balanced
document-engine extract arquivo.pdf --schema schema.json
document-engine validate result.json
document-engine benchmark ./corpus
```

---

# 9. Arquitetura de alto nível

```text
┌──────────────────────────────────────────────────────────────┐
│                       CAMADA DE CONSUMO                       │
│                                                              │
│ Python SDK │ TypeScript SDK │ REST API │ CLI │ Webhooks       │
└───────────────────────────────┬──────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────┐
│                        CONTROL PLANE                         │
│                                                              │
│ Jobs │ Tenants │ Templates │ Schemas │ Policies │ Providers   │
│ Versions │ Usage │ Review │ Administration                    │
└───────────────────────────────┬──────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────┐
│                  DOCUMENT INTELLIGENCE KERNEL                │
│                                                              │
│ Document Model │ Inspector │ Router │ Planner │ Pipeline       │
│ Extraction │ Confidence │ Validation │ Evidence │ Provenance   │
└───────────────────────────────┬──────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────┐
│                         CAPABILITIES                         │
│                                                              │
│ Native Parsers │ Rendering │ OCR │ Layout │ Tables            │
│ Classification │ Semantic Models │ Reconciliation             │
│ Normalization │ Domain Rules │ Template Execution             │
└───────────────────────────────┬──────────────────────────────┐
                                │
┌───────────────────────────────▼──────────────────────────────┐
│                       EXECUTION PLANE                        │
│                                                              │
│ Local Runtime │ Temporal Runtime │ CPU Workers │ GPU Workers   │
│ Semantic Workers │ Cache │ Artifact Storage │ Observability   │
└──────────────────────────────────────────────────────────────┘
```

---

# 10. Document Intelligence Kernel

O kernel é o coração do sistema.

Ele deve ser:

- pequeno;
- testável;
- estável;
- independente de infraestrutura;
- independente de providers;
- reutilizável;
- orientado a contratos;
- assíncrono por padrão;
- compatível com execução local e distribuída.

## 10.1. Responsabilidades

O kernel é responsável por:

- representar documentos;
- coordenar o ciclo de processamento;
- criar contexto de execução;
- consultar capacidades registradas;
- solicitar inspeções;
- criar planos;
- executar ou delegar atividades;
- consolidar artefatos;
- construir o documento canônico;
- executar extrações;
- normalizar;
- validar;
- calcular confiança;
- reconciliar candidatos;
- registrar evidências;
- registrar proveniência;
- decidir conclusão ou revisão.

## 10.2. O que não deve existir dentro do kernel

- autenticação;
- cadastro de clientes;
- billing;
- UI;
- FastAPI;
- detalhes de PostgreSQL;
- detalhes de Redis;
- detalhes de MinIO;
- chamadas diretas a fornecedores;
- regras contábeis específicas;
- implementação específica de Temporal;
- gerenciamento de usuários;
- lógica de e-mail.

---

# 11. Modelo Documental Canônico

Para suportar diferentes formatos, o motor precisa converter tudo para uma representação intermediária comum.

Nome conceitual:

```text
Canonical Document Model
```

Evolução possível:

```text
Document Graph
```

## 11.1. Objetivo

Permitir que:

- templates;
- regras;
- normalizadores;
- validadores;
- modelos semânticos;
- mecanismos de busca;
- sistemas de revisão;
- exporters;

trabalhem sobre a mesma estrutura, independentemente da origem.

## 11.2. Estrutura base

```text
Document
├── Metadata
├── Pages
│   ├── TextSpans
│   ├── Words
│   ├── Lines
│   ├── Blocks
│   ├── Paragraphs
│   ├── Headings
│   ├── Images
│   ├── Vectors
│   ├── Tables
│   │   ├── Rows
│   │   ├── Columns
│   │   └── Cells
│   ├── Lists
│   ├── Sections
│   ├── FormFields
│   ├── Regions
│   ├── Headers
│   └── Footers
├── Relationships
├── Artifacts
└── Provenance
```

## 11.3. Elementos comuns

Cada elemento deve possuir, quando aplicável:

```json
{
  "element_id": "el_728",
  "type": "text_span",
  "value": "15.000,00",
  "page": 3,
  "bounding_box": {
    "x": 340,
    "y": 245,
    "width": 90,
    "height": 18
  },
  "source": {
    "method": "native_pdf",
    "provider": "pdf-provider",
    "version": "1.0"
  },
  "confidence": 0.99,
  "attributes": {},
  "relationships": []
}
```

## 11.4. Relações importantes

```text
contains
contained_by
next
previous
aligned_with
label_of
value_of
parent_of
child_of
continuation_of
header_of
footer_of
cell_of
row_of
column_of
belongs_to_section
derived_from
overlaps
references
```

Exemplo:

```text
"CNPJ:" ──label_of──> "12.345.678/0001-90"
```

Exemplo hierárquico:

```text
Conta 1.1
   └── parent_of
       ├── Conta 1.1.01
       └── Conta 1.1.02
```

## 11.5. Geometria

A geometria deve ser padronizada.

Recomenda-se armazenar:

- coordenadas absolutas;
- coordenadas normalizadas;
- unidade;
- rotação;
- página;
- origem do sistema de coordenadas;
- polígonos quando bounding box não for suficiente.

## 11.6. Proveniência

Todo elemento deve saber:

- qual artefato o gerou;
- qual provider;
- qual versão;
- qual configuração;
- qual input;
- qual transformação;
- qual atividade;
- qual job;
- qual timestamp.

---

# 12. Inspector

Todos os documentos passam pelo Inspector.

O Inspector executa apenas operações de baixo custo e produz o perfil técnico inicial.

## 12.1. Sinais do documento

- tipo real do arquivo;
- extensão declarada;
- MIME detectado;
- tamanho;
- hash;
- quantidade de páginas;
- presença de senha;
- corrupção;
- metadados;
- texto interno;
- imagens;
- fontes;
- orientação;
- resolução;
- estrutura interna;
- compressão;
- presença de anexos;
- complexidade estimada.

## 12.2. Sinais por página

- quantidade de caracteres;
- densidade de texto;
- cobertura de texto;
- cobertura de imagem;
- quantidade de vetores;
- presença de glifos inválidos;
- ordem de leitura;
- orientação;
- inclinação;
- presença provável de tabela;
- presença provável de formulário;
- qualidade visual;
- resolução;
- ruído;
- contraste;
- duplicação de texto;
- texto invisível;
- camada OCR anterior.

## 12.3. Exemplo de saída

```json
{
  "document_id": "doc_123",
  "document_type": "pdf",
  "page_count": 12,
  "native_text_available": true,
  "document_profile": "hybrid_pdf",
  "pages": [
    {
      "page": 1,
      "native_text_coverage": 0.92,
      "image_coverage": 0.04,
      "recommended_processing": "native_structural"
    },
    {
      "page": 2,
      "native_text_coverage": 0.00,
      "image_coverage": 0.98,
      "recommended_processing": "full_ocr"
    }
  ]
}
```

O Inspector não extrai variáveis de negócio.

---

# 13. Processing Router

O Processing Router interpreta os sinais e decide a estratégia.

Ele responde:

- quais parsers utilizar;
- quais páginas precisam de OCR;
- quais regiões precisam de OCR;
- quando executar análise estrutural;
- quando executar reconhecimento de tabelas;
- quando usar modelo multimodal;
- quando executar template;
- quando comparar estratégias;
- quando solicitar revisão;
- quando reaproveitar cache.

O Router não executa as tarefas.

---

# 14. Processing Planner

O Planner transforma a estratégia em um plano executável.

Diferença:

```text
Router  → decide o caminho
Planner → descreve as atividades
Executor → executa as atividades
```

## 14.1. Exemplo de plano

```json
{
  "document_id": "doc_123",
  "profile": "balanced",
  "document_tasks": [
    "inspect",
    "classify",
    "merge",
    "extract",
    "validate"
  ],
  "page_tasks": {
    "1": ["native_parse", "layout"],
    "2": ["native_parse", "layout"],
    "3": ["render", "image_preprocessing", "ocr", "layout"],
    "5": ["native_parse", "region_render", "table_ocr"]
  }
}
```

## 14.2. Plano dinâmico

O plano pode ser ajustado.

Exemplo:

```text
native_table retornou apenas 4 de 6 colunas
                    ↓
planner adiciona table_ocr para a região
```

Toda alteração deve ser registrada como escalonamento.

---

# 15. Níveis adaptativos de processamento

Os níveis representam capacidades possíveis, não um pipeline obrigatório.

## Nível 0 — Inspeção e metadados

Objetivos:

- validar;
- identificar formato;
- calcular hash;
- contar páginas;
- detectar corrupção;
- descobrir texto nativo;
- estimar complexidade;
- criar perfil inicial.

Características:

```text
CPU leve
sem OCR
sem GPU
sem IA
```

## Nível 1 — Extração nativa

Aplicável a:

- PDF digital;
- DOCX;
- XLSX;
- CSV;
- HTML;
- XML.

Produz:

- caracteres;
- palavras;
- coordenadas;
- estilos;
- fontes;
- imagens;
- vetores;
- células;
- metadados;
- ordem inicial.

## Nível 2 — Análise estrutural

Responsável por:

- blocos;
- títulos;
- seções;
- colunas;
- listas;
- cabeçalhos;
- rodapés;
- ordem de leitura;
- tabelas;
- relações espaciais;
- hierarquia.

Pode funcionar sem OCR.

## Nível 3 — OCR seletivo

OCR aplicado somente em:

- página específica;
- região;
- imagem;
- tabela;
- campo;
- célula;
- assinatura;
- carimbo.

## Nível 4 — OCR completo e reconstrução

Aplicável a:

- documentos totalmente escaneados;
- fotografias;
- PDFs sem texto;
- texto nativo corrompido;
- imagens multipágina;
- documentos de baixa qualidade.

Produz:

- palavras;
- linhas;
- blocos;
- coordenadas;
- confiança;
- idioma;
- orientação;
- relações.

## Nível 5 — Compreensão semântica

Utilizado para:

- documentos desconhecidos;
- schema complexo;
- campos sem rótulo;
- relações semânticas;
- listas hierárquicas;
- tabelas ambíguas;
- geração assistida de template;
- extração orientada por instrução.

O modelo semântico deve receber:

- melhor texto disponível;
- layout;
- imagem ou recorte necessário;
- schema;
- evidências existentes;
- candidatos;
- campos ausentes;
- contexto do template.

## Nível 6 — Reconciliação avançada

Quando métodos divergem:

```text
Parser nativo: R$ 15.000,00
OCR: R$ 16.000,00
VLM: R$ 15.000,00
```

O sistema deve:

- comparar candidatos;
- validar tipos;
- verificar evidências;
- aplicar regras;
- verificar consistência;
- escolher candidato;
- reprocessar região;
- solicitar revisão se necessário.

## Nível 7 — Revisão humana

Aplicado quando:

- confiança insuficiente;
- campos obrigatórios ausentes;
- divergência persistente;
- validação falha;
- imagem ilegível;
- ambiguidade real.

Status:

```text
review_required
```

---

# 16. Processamento por página, região e campo

O sistema não deve decidir apenas:

```text
este documento precisa de OCR
```

Deve decidir:

```text
quais páginas precisam de OCR;
quais regiões precisam de OCR;
quais tabelas precisam de reconstrução;
quais campos precisam de semântica;
quais candidatos precisam de reconciliação.
```

Exemplo:

```text
Página 1 → parser nativo
Página 2 → parser nativo
Página 3 → OCR completo
Página 4 → OCR apenas no rodapé
Página 5 → parser nativo
Página 6 → OCR da tabela
```

Isso reduz:

- custo;
- latência;
- uso de GPU;
- uso de tokens;
- risco de perda do texto nativo;
- processamento desnecessário.

---

# 17. Perfis de processamento

## automatic

O motor decide.

```json
{
  "processing_profile": "automatic"
}
```

## fast

Prioriza custo e velocidade.

```text
parser nativo
layout básico
OCR seletivo
sem VLM, salvo falha crítica
```

## balanced

Equilibra custo, precisão e latência.

```text
parser nativo
layout completo
OCR quando necessário
semântica em baixa confiança
validação
```

## maximum_accuracy

Prioriza qualidade.

```text
múltiplas estratégias
OCR de verificação
layout avançado
VLM
reconciliação
validação rigorosa
```

## custom

```json
{
  "processing_profile": "custom",
  "policies": {
    "ocr": "selective",
    "layout_analysis": true,
    "semantic_analysis": "on_low_confidence",
    "minimum_confidence": 0.95,
    "human_review": "on_failure"
  }
}
```

---

# 18. Políticas independentes

O motor não deve depender apenas de níveis fixos.

Exemplo:

```json
{
  "processing_policies": {
    "native_parse": "always",
    "ocr": "auto",
    "layout": "auto",
    "table_recognition": "auto",
    "semantic_extraction": "on_demand",
    "reconciliation": "on_conflict",
    "human_review": "below_threshold"
  }
}
```

Valores possíveis:

```text
never
auto
always
on_demand
on_low_confidence
on_conflict
below_threshold
on_failure
```

---

# 19. Regras iniciais de roteamento

Exemplos conceituais:

```text
Se há texto nativo com boa cobertura:
    usar parser nativo

Se a página contém mais de 90% de imagem
e menos de 20 caracteres válidos:
    executar OCR completo

Se existem caracteres nativos,
mas muitos são inválidos:
    comparar parser nativo com OCR

Se apenas uma região não tem texto:
    executar OCR regional

Se existe estrutura tabular:
    executar análise de tabela

Se o template extrai todos os campos
com confiança acima do limite:
    não chamar VLM

Se campos estão ausentes
ou abaixo da confiança:
    chamar VLM apenas para regiões problemáticas

Se métodos discordarem:
    executar reconciliação

Se a divergência persistir:
    solicitar revisão
```

Os thresholds não devem ser tratados como verdades fixas.

Eles devem ser:

- configuráveis;
- versionados;
- avaliados por benchmark;
- ajustáveis por formato;
- ajustáveis por tipo documental;
- ajustáveis por tenant;
- ajustáveis por perfil.

---

# 20. Escalonamento progressivo

Exemplo:

```text
Tentativa 1 — caminho barato
        ↓
resultado suficiente?
   sim → finalizar
   não
        ↓
Tentativa 2 — capacidade especializada
        ↓
resultado suficiente?
   sim → finalizar
   não
        ↓
Tentativa 3 — modelo semântico
        ↓
resultado suficiente?
   sim → finalizar
   não
        ↓
reconciliação ou revisão
```

O escalonamento deve preservar:

- motivo;
- escopo;
- método anterior;
- método novo;
- custo;
- resultado;
- confiança;
- versão.

---

# 21. Capability Registry

O motor deve trabalhar com capacidades registradas.

Cada capacidade informa:

- identificador;
- versão;
- entradas aceitas;
- saídas produzidas;
- formatos;
- granularidade;
- requisitos;
- classe de recurso;
- custo estimado;
- latência estimada;
- determinismo;
- suporte a regiões;
- idiomas;
- configurações;
- provider.

Exemplo:

```json
{
  "capability": "ocr.paddle",
  "version": "5.x",
  "accepts": ["image/page", "image/region"],
  "produces": ["ocr_document"],
  "resource_class": "gpu_optional",
  "supports_regions": true,
  "deterministic": false,
  "cost_class": "medium"
}
```

O Router consulta o registry para criar o plano.

---

# 22. Plugins e providers

## 22.1. Contratos principais

```text
DocumentParser
DocumentRenderer
OCRProvider
ImagePreprocessor
LayoutAnalyzer
TableRecognizer
ClassificationProvider
SemanticProvider
EmbeddingProvider
TemplateMatcher
SchemaExtractor
Normalizer
Validator
Reconciler
StorageBackend
ArtifactRepository
CacheBackend
ExecutionRuntime
EventPublisher
MetricsProvider
ReviewProvider
```

## 22.2. Exemplo de contrato

```python
class OCRCapability(Protocol):
    async def recognize(
        self,
        artifact: ImageArtifact,
        options: OCROptions
    ) -> OCRResult:
        ...
```

## 22.3. Exemplo de configuração

```python
engine = (
    EngineBuilder()
    .with_parser(PDFParser())
    .with_parser(ExcelParser())
    .with_ocr(PaddleOCRProvider())
    .with_semantic_provider(MySemanticProvider())
    .with_storage(LocalArtifactStorage())
    .build()
)
```

Distribuído:

```python
engine = (
    EngineBuilder()
    .with_storage(S3ArtifactStorage())
    .with_cache(RedisArtifactCache())
    .with_runtime(TemporalExecutionRuntime())
    .build()
)
```

---

# 23. Principais capacidades

## 23.1. Native Parser

Extrai a estrutura interna.

Não extrai variáveis de negócio.

Formatos iniciais sugeridos:

- PDF;
- XLSX;
- CSV;
- imagens.

Formatos futuros:

- DOCX;
- HTML;
- XML;
- e-mail;
- ZIP;
- formatos proprietários.

## 23.2. Renderer

Responsável por:

- renderizar página;
- renderizar região;
- controlar DPI;
- aplicar escala;
- rotação;
- recorte;
- conversão de cor;
- padronização.

## 23.3. Image Preprocessing

Pode aplicar:

- deskew;
- orientação;
- remoção de ruído;
- contraste;
- binarização;
- correção de perspectiva;
- upscale;
- remoção de fundo;
- detecção de sombras.

Cada transformação deve ser versionada.

## 23.4. OCR

Retorna mais do que texto:

- palavra;
- linha;
- bloco;
- coordenadas;
- confiança;
- orientação;
- idioma;
- ordem;
- relações.

## 23.5. Layout Engine

Responsável por:

- títulos;
- parágrafos;
- seções;
- colunas;
- listas;
- cabeçalhos;
- rodapés;
- ordem;
- agrupamentos;
- hierarquia.

## 23.6. Table Engine

Responsável por:

- detectar tabelas;
- identificar linhas;
- identificar colunas;
- reconstruir células;
- células mescladas;
- cabeçalhos;
- tabelas sem bordas;
- tabelas entre páginas;
- hierarquia em linhas;
- colunas implícitas.

## 23.7. Classification Engine

Pode utilizar:

- metadados;
- sinais estruturais;
- palavras-chave;
- templates;
- embeddings;
- modelos semânticos;
- regras;
- classificadores.

A classificação final deve possuir evidência.

## 23.8. Template Engine

Templates devem operar sobre conceitos canônicos:

```text
encontre elemento com texto
encontre valor à direita
encontre valor abaixo
encontre tabela após título
encontre seção
percorra filhos
capture coluna
normalize
validate
```

## 23.9. Schema Extraction Engine

Exemplo:

```json
{
  "company": {
    "cnpj": "string",
    "name": "string"
  },
  "period": {
    "start": "date",
    "end": "date"
  },
  "accounts": [
    {
      "code": "string",
      "description": "string",
      "balance": "decimal"
    }
  ]
}
```

## 23.10. Semantic Engine

Deve ser usado de forma seletiva.

Entrada ideal:

- recorte necessário;
- texto nativo;
- OCR;
- layout;
- schema;
- candidatos;
- campos faltantes;
- evidências;
- instrução;
- regras relevantes.

## 23.11. Normalization Engine

Exemplos:

- datas;
- moedas;
- decimais;
- CNPJ;
- CPF;
- telefones;
- percentuais;
- códigos;
- contas;
- nomes;
- endereços;
- identificadores.

## 23.12. Validation Engine

Tipos de validação:

- tipo;
- formato;
- obrigatório;
- domínio;
- consistência;
- checksum;
- expressão;
- equação;
- total;
- relação;
- referência cruzada;
- duplicidade;
- intervalo.

## 23.13. Confidence Engine

A confiança final não deve ser apenas a confiança do OCR.

Exemplo:

```json
{
  "recognition": 0.98,
  "structural": 0.93,
  "semantic": 0.90,
  "validation": 1.0,
  "consensus": 0.95,
  "final": 0.96
}
```

## 23.14. Reconciliation Engine

Compara:

- parser;
- OCR;
- template;
- modelo semântico;
- regras;
- validação;
- histórico;
- consenso.

## 23.15. Provenance Engine

Registra o caminho completo de cada dado.

---

# 24. Processing Plan versionado

Toda extração deve guardar o plano.

```json
{
  "plan_id": "plan_123",
  "plan_version": 1,
  "profile": "balanced",
  "routing_reason": "mixed_digital_and_scanned_pdf",
  "document_steps": [
    "inspect",
    "classify",
    "merge",
    "validate"
  ],
  "page_plans": [],
  "escalations": [
    {
      "page": 5,
      "region_id": "region_table_1",
      "from": "native_table",
      "to": "table_ocr",
      "reason": "missing_columns"
    }
  ]
}
```

Benefícios:

- auditoria;
- reprodução;
- comparação;
- controle de custos;
- explicação;
- benchmark;
- debugging;
- evolução de regras.

---

# 25. Artifact Store

Cada etapa relevante produz artefatos imutáveis ou versionados.

Tipos:

```text
OriginalDocument
DocumentInspectionArtifact
NativeParseArtifact
RenderedPageArtifact
RenderedRegionArtifact
PreprocessedImageArtifact
OCRArtifact
LayoutArtifact
TableArtifact
ClassificationArtifact
CanonicalDocumentArtifact
ExtractionArtifact
NormalizationArtifact
ValidationArtifact
ReconciliationArtifact
ReviewArtifact
ExportArtifact
```

Exemplo:

```json
{
  "artifact_id": "art_982",
  "artifact_type": "ocr.region",
  "content_hash": "sha256:...",
  "producer": {
    "capability": "ocr.paddle",
    "version": "5.x"
  },
  "scope": {
    "document_id": "doc_123",
    "page": 5,
    "region_id": "table_1"
  },
  "inputs": [
    "art_rendered_region_456"
  ]
}
```

---

# 26. Cache por artefato

A chave deve considerar:

```text
hash do input
+
tipo do artefato
+
provider
+
versão
+
configuração
+
idioma
+
pré-processamento
+
escopo
```

Exemplo:

```text
ocr:
sha256-da-regiao:
paddleocr:
provider-version:
pt-br:
preprocessing-v2:
config-v3
```

Cache aplicável a:

- inspeção;
- parsing;
- renderização;
- OCR;
- layout;
- tabelas;
- embeddings;
- inferência;
- normalização;
- validação;
- exportação.

---

# 27. Resultado estruturado

Exemplo:

```json
{
  "field": "company.cnpj",
  "value": "00000000000100",
  "confidence": 0.98,
  "processing": {
    "level": "native_structural",
    "ocr_used": false,
    "semantic_model_used": false,
    "template_used": true,
    "validation_passed": true
  },
  "evidence": [
    {
      "page": 1,
      "element_id": "el_45",
      "method": "native_pdf"
    }
  ]
}
```

Outro campo pode possuir caminho diferente:

```json
{
  "field": "authorized_signature_name",
  "value": "João da Silva",
  "confidence": 0.87,
  "processing": {
    "level": "semantic",
    "ocr_used": true,
    "ocr_scope": "region",
    "semantic_model_used": true,
    "validation_passed": true
  }
}
```

---

# 28. Contrato principal de processamento

## ProcessingRequest

```json
{
  "source": {
    "type": "object_reference",
    "uri": "documents/doc_123/original.pdf"
  },
  "profile": "balanced",
  "template": {
    "id": "trial_balance",
    "version": 4
  },
  "schema": {
    "id": "accounting_document",
    "version": 2
  },
  "policies": {
    "ocr": "auto",
    "layout": "auto",
    "semantic": "on_low_confidence",
    "reconciliation": "on_conflict",
    "review": "below_threshold"
  },
  "minimum_confidence": 0.95
}
```

## ProcessingResult

```json
{
  "document_id": "doc_123",
  "job_id": "job_456",
  "status": "completed",
  "classification": {
    "type": "trial_balance",
    "confidence": 0.99
  },
  "data": {},
  "fields": [],
  "tables": [],
  "warnings": [],
  "processing_summary": {
    "native_pages": 8,
    "ocr_pages": 1,
    "ocr_regions": 2,
    "semantic_calls": 1,
    "review_required": false
  },
  "artifacts": [],
  "versions": {
    "engine": "1.0",
    "processing_plan": 3,
    "template": 4,
    "schema": 2
  }
}
```

---

# 29. Estados

## Estados do job

```text
created
uploaded
queued
inspecting
planning
processing
extracting
normalizing
validating
reconciling
completed
review_required
failed
cancelled
```

## Estados do campo

```text
candidate
extracted
normalized
validated
missing
ambiguous
conflicting
corrected
rejected
review_required
```

## Estados do artefato

```text
created
available
invalid
superseded
expired
deleted
```

---

# 30. Execução local e distribuída

O kernel depende de:

```text
ExecutionRuntime
```

## LocalRuntime

Pode usar:

- asyncio;
- threads;
- processos;
- filas em memória;
- GPU local;
- armazenamento local.

## TemporalRuntime

Pode usar:

- workflows;
- activities;
- task queues;
- retries;
- timeouts;
- cancelamento;
- execução durável;
- child workflows.

Para o kernel:

```python
result = await runtime.execute(task)
```

O contrato deve ser equivalente.

---

# 31. Workflow adaptativo

```text
StartProcessing
      ↓
InspectDocument
      ↓
BuildProcessingPlan
      ↓
ProcessPages
      │
      ├── NativePageWorkflow
      ├── OCRPageWorkflow
      ├── HybridPageWorkflow
      └── TablePageWorkflow
      ↓
MergeCanonicalDocument
      ↓
Classify
      ↓
ExecuteTemplateOrSchema
      ↓
Normalize
      ↓
Validate
      ↓
EvaluateConfidence
      │
      ├── suficiente → PersistResult
      │
      └── insuficiente → EscalateProblemRegions
                                ↓
                         SemanticAnalysis
                                ↓
                         Reconciliation
      ↓
CompleteOrRequestReview
```

O workflow pode mudar durante a execução.

---

# 32. Workers

## Estrutura lógica ideal

```text
workers/
├── inspector-worker/
├── native-parser-worker/
├── render-worker/
├── ocr-worker/
├── layout-worker/
├── table-worker/
├── semantic-worker/
├── reconciliation-worker/
├── validation-worker/
└── review-preparation-worker/
```

## Estrutura física inicial recomendada

```text
cpu-document-worker
├── inspector
├── native-parser
├── render
├── template
├── normalize
└── validation

gpu-document-worker
├── ocr
├── layout
└── table

semantic-worker
├── VLM
├── LLM
├── schema extraction
└── reconciliation
```

No futuro, capacidades podem ser separadas sem mudar o núcleo.

---

# 33. Task Queues

Exemplo:

```text
document.inspect
document.native
document.render
document.ocr
document.layout
document.table
document.semantic
document.reconcile
document.validate
document.review
```

Cada queue escala independentemente.

Não utilizar vários sistemas de mensageria sem necessidade.

Se Temporal for o orquestrador:

```text
Temporal → atividades e task queues
Outbox + event bus opcional → integração externa
```

Kafka, NATS ou RabbitMQ só devem entrar quando houver necessidade real.

---

# 34. Control Plane

Responsabilidades:

- tenants;
- usuários;
- API keys;
- jobs;
- documentos;
- templates;
- schemas;
- políticas;
- providers;
- versões;
- limites;
- revisões;
- webhooks;
- custos;
- uso;
- administração;
- configurações;
- retenção.

Inicialmente, pode ser um único serviço modular.

---

# 35. Execution Plane

Responsabilidades:

- workflows;
- workers;
- execução;
- modelos;
- cache;
- artifacts;
- CPU;
- GPU;
- filas;
- escalonamento;
- telemetria.

Separação permite:

```text
escalar API sem escalar OCR
escalar OCR sem escalar banco
escalar semântica sem escalar parser
```

---

# 36. Persistência

## PostgreSQL

Dados transacionais:

- documents;
- jobs;
- processing_plans;
- templates;
- schemas;
- extractions;
- fields;
- reviews;
- tenants;
- policies;
- providers;
- versions;
- audit;
- outbox.

## S3 ou MinIO

Artefatos:

- documento original;
- renders;
- recortes;
- imagens tratadas;
- OCR bruto;
- layout;
- tabelas;
- documento canônico;
- resultados intermediários;
- evidências;
- exports.

## Redis

Uso opcional:

- cache curto;
- locks;
- rate limiting;
- sessões;
- estado temporário.

Redis não deve ser a fonte oficial dos resultados.

## Temporal

Uso:

- estado durável do workflow;
- retries;
- atividades;
- cancelamento;
- timeouts;
- child workflows;
- execução assíncrona.

---

# 37. Templates

Templates devem ser:

- versionados;
- testáveis;
- independentes de provider;
- independentes de parser;
- capazes de produzir evidências;
- capazes de declarar campos;
- capazes de declarar tabelas;
- capazes de declarar validações;
- capazes de declarar normalizações;
- capazes de declarar fallback;
- capazes de declarar classificação;
- capazes de operar sobre relações.

## Estrutura conceitual

```text
Template
├── metadata
├── classification signals
├── expected structures
├── fields
├── tables
├── lists
├── relationships
├── normalizers
├── validators
├── confidence rules
└── fallback policies
```

Templates de domínio ficam fora do núcleo.

```text
Engine
└── Template Runtime
    ├── Accounting Templates
    ├── Tax Templates
    ├── Legal Templates
    ├── Banking Templates
    └── Custom Templates
```

---

# 38. Tipos de variáveis e estruturas

O motor deve suportar:

- variável simples;
- rótulo e valor;
- referência;
- grupo;
- objeto;
- lista;
- tabela;
- tabela hierárquica;
- lista hierárquica;
- seção;
- coleção;
- relação;
- campo derivado;
- campo calculado;
- campo composto;
- valor repetido;
- valor multi-página;
- estrutura mista.

Exemplo de balancete:

```text
Dados da empresa → objeto
Dados do período → objeto
Contas → coleção hierárquica de linhas
Totais → campos calculáveis e validáveis
```

---

# 39. Classificação

A classificação pode ocorrer em estágios.

## Classificação técnica

- PDF digital;
- PDF escaneado;
- PDF híbrido;
- planilha;
- imagem;
- documento corrompido.

## Classificação documental

- balancete;
- extrato;
- contrato;
- nota fiscal;
- relatório;
- formulário.

## Matching de template

O sistema pode:

1. filtrar templates por sinais baratos;
2. calcular score;
3. confirmar automaticamente acima do limite;
4. solicitar confirmação em ambiguidade;
5. permitir criação de novo template.

Thresholds devem ser configuráveis e avaliados.

---

# 40. Revisão humana

A revisão é parte do motor.

```text
resultado
   ↓
revisão
   ↓
correção estruturada
   ↓
benchmark
   ↓
melhoria de regras, templates e modelos
```

Exemplo:

```json
{
  "field": "company.cnpj",
  "previous_value": "12345678000199",
  "corrected_value": "12345678000190",
  "reason": "last_digit_incorrect",
  "evidence": {
    "page": 1,
    "region": "..."
  }
}
```

A revisão deve mostrar:

- documento;
- página;
- recorte;
- candidatos;
- métodos;
- confiança;
- validações;
- motivo da revisão;
- campo esperado;
- histórico.

---

# 41. API assíncrona

Padrão:

```http
POST /v1/jobs
```

Resposta:

```json
{
  "job_id": "job_123",
  "status": "queued"
}
```

Acompanhamento:

```http
GET /v1/jobs/job_123
GET /v1/jobs/job_123/events
GET /v1/jobs/job_123/result
```

Pode existir endpoint síncrono limitado:

```http
POST /v1/extract:sync
```

Com limites de:

- tamanho;
- páginas;
- tempo;
- capacidades;
- custo.

---

# 42. Eventos

Eventos importantes:

```text
document.received
document.stored
document.inspected
processing.plan.created
processing.started
page.processing.started
artifact.created
field.candidate.created
field.extracted
field.validated
processing.escalated
validation.failed
reconciliation.started
review.requested
extraction.completed
extraction.failed
```

Exemplo:

```json
{
  "event": "processing.escalated",
  "job_id": "job_123",
  "document_id": "doc_456",
  "scope": {
    "page": 5,
    "region": "table_1"
  },
  "from": "native_table",
  "to": "table_ocr",
  "reason": "missing_columns"
}
```

Eventos alimentam:

- logs;
- métricas;
- auditoria;
- webhooks;
- progresso;
- debug;
- custo;
- tracing.

---

# 43. Observabilidade

Identificadores:

```text
job_id
document_id
tenant_id
correlation_id
plan_id
trace_id
artifact_id
activity_id
```

Métricas:

- tempo por capacidade;
- tempo por página;
- custo por documento;
- páginas com OCR;
- regiões com OCR;
- chamadas semânticas;
- escalonamentos;
- revisão;
- confiança;
- acurácia;
- falhas por provider;
- cache hit;
- CPU;
- memória;
- GPU;
- fila;
- throughput.

Logs devem ser estruturados.

Tracing deve permitir seguir:

```text
requisição
→ job
→ plano
→ atividade
→ artefato
→ campo
→ validação
→ resultado
```

---

# 44. Segurança

Documentos são entradas potencialmente perigosas.

Controles:

- limite de tamanho;
- limite de páginas;
- limite de descompactação;
- MIME real;
- hash;
- detecção de corrupção;
- timeout;
- limite de memória;
- isolamento de parser;
- isolamento de worker;
- antivírus opcional;
- URLs assinadas;
- criptografia;
- tenant isolation;
- retenção;
- exclusão;
- mascaramento;
- auditoria;
- controle de acesso;
- proteção contra path traversal;
- proteção contra ZIP bomb;
- proteção contra parser crash;
- proteção contra prompt injection documental.

Modelos semânticos não devem receber instruções do documento como comandos de sistema.

---

# 45. Distribuição da biblioteca

Pacote principal leve:

```bash
pip install document-engine
```

Extras:

```bash
pip install "document-engine[pdf]"
pip install "document-engine[excel]"
pip install "document-engine[ocr]"
pip install "document-engine[semantic]"
pip install "document-engine[local-full]"
pip install "document-engine[server]"
```

Providers separados:

```text
document-engine-paddle
document-engine-tesseract
document-engine-temporal
document-engine-s3
document-engine-openai
```

Uma aplicação que processa apenas XLSX não deve instalar:

- CUDA;
- OCR;
- modelos;
- Temporal;
- FastAPI;
- bibliotecas pesadas de PDF.

---

# 46. Estrutura ideal do repositório

```text
document-intelligence-engine/
│
├── apps/
│   ├── api/
│   ├── cli/
│   ├── worker-cpu/
│   ├── worker-gpu/
│   ├── worker-semantic/
│   └── review-web/
│
├── packages/
│   ├── document-core/
│   │   ├── models/
│   │   ├── geometry/
│   │   ├── identifiers/
│   │   ├── errors/
│   │   ├── results/
│   │   └── evidence/
│   │
│   ├── document-model/
│   │   ├── document.py
│   │   ├── page.py
│   │   ├── elements.py
│   │   ├── relationships.py
│   │   └── graph.py
│   │
│   ├── engine/
│   │   ├── engine.py
│   │   ├── context.py
│   │   ├── pipeline.py
│   │   ├── executor.py
│   │   └── lifecycle.py
│   │
│   ├── inspector/
│   ├── routing/
│   ├── planning/
│   ├── parsing/
│   ├── rendering/
│   ├── ocr/
│   ├── layout/
│   ├── tables/
│   ├── classification/
│   ├── semantic/
│   ├── templates/
│   ├── schema-extraction/
│   ├── normalization/
│   ├── validation/
│   ├── confidence/
│   ├── reconciliation/
│   ├── provenance/
│   ├── artifacts/
│   ├── plugins/
│   ├── observability/
│   ├── sdk-python/
│   └── sdk-typescript/
│
├── adapters/
│   ├── parsers/
│   │   ├── pdf/
│   │   ├── docx/
│   │   └── excel/
│   ├── ocr/
│   │   ├── paddle/
│   │   └── tesseract/
│   ├── semantic/
│   │   ├── openai/
│   │   └── local-model/
│   ├── storage/
│   │   ├── local/
│   │   └── s3/
│   ├── cache/
│   │   ├── memory/
│   │   └── redis/
│   └── runtime/
│       ├── local/
│       └── temporal/
│
├── contracts/
│   ├── openapi/
│   ├── events/
│   ├── schemas/
│   └── protobuf/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── golden/
│   ├── corpus/
│   ├── benchmark/
│   ├── performance/
│   └── end-to-end/
│
├── deployments/
│   ├── docker/
│   ├── compose/
│   ├── kubernetes/
│   └── helm/
│
├── examples/
│   ├── embedded-python/
│   ├── api-client/
│   ├── custom-ocr-provider/
│   ├── custom-validator/
│   └── custom-template/
│
└── docs/
    ├── architecture/
    ├── concepts/
    ├── plugin-development/
    ├── api/
    ├── sdk/
    └── operations/
```

Essa é a visão ideal, não a obrigação da primeira versão.

---

# 47. Arquitetura física inicial recomendada

```text
1 monorepo
1 biblioteca principal
1 API
1 PostgreSQL
1 MinIO
1 Temporal
3 tipos de workers
```

Opcionalmente:

```text
1 Redis
```

Deploys iniciais:

```text
api
cpu-worker
gpu-worker
semantic-worker
postgres
minio
temporal
```

Não criar serviços separados para cada módulo.

---

# 48. Primeira versão do kernel

A primeira versão deve concentrar-se em poucos pacotes fundamentais.

Sugestão:

```text
packages/
├── document-core/
├── document-model/
├── engine/
├── inspector/
├── parsing/
├── artifacts/
├── routing/
├── planning/
├── validation/
└── plugins/
```

Capacidades iniciais:

- inspeção de PDF;
- parsing nativo;
- renderização;
- OCR provider opcional;
- modelo canônico básico;
- plano simples;
- extração por schema simples;
- evidência;
- validação;
- execução local.

Primeiro objetivo real:

> Processar um PDF digital ou híbrido, decidir corretamente entre texto nativo e OCR, construir uma representação canônica simples e retornar campos estruturados com evidências.

---

# 49. Estratégia de evolução

## Fase A — Fundação do núcleo

- tipos;
- contratos;
- identificadores;
- erros;
- resultados;
- geometria;
- artefatos;
- modelo canônico;
- engine local;
- plugin registry.

## Fase B — Inspeção e parsing

- inspector;
- parser PDF;
- parser XLSX;
- render;
- hashing;
- artifact store local;
- cache local.

## Fase C — Roteamento adaptativo

- router;
- planner;
- perfis;
- políticas;
- regras;
- plano versionado;
- escalonamento.

## Fase D — OCR e estrutura

- OCR provider;
- pré-processamento;
- layout;
- tabelas;
- merge.

## Fase E — Extração

- templates;
- schemas;
- normalização;
- validação;
- confiança;
- evidência.

## Fase F — Semântica e reconciliação

- VLM/LLM;
- extração seletiva;
- múltiplos candidatos;
- consenso;
- revisão.

## Fase G — Plataforma distribuída

- API;
- Temporal;
- workers;
- PostgreSQL;
- MinIO;
- eventos;
- observabilidade.

## Fase H — Produto

- template builder;
- review UI;
- administração;
- SDKs;
- webhooks;
- multi-tenancy.

---

# 50. Qualidade e testes

## Tipos de testes

- unitários;
- integração;
- contrato;
- golden tests;
- snapshot;
- corpus;
- regressão;
- benchmark;
- performance;
- carga;
- caos;
- segurança;
- end-to-end.

## Golden Dataset

Cada documento deve possuir:

- arquivo;
- tipo esperado;
- elementos esperados;
- campos esperados;
- tabelas esperadas;
- evidências esperadas;
- tolerâncias;
- resultado de referência.

## Métricas de qualidade

- precisão de campo;
- recall;
- F1;
- precisão de tabela;
- precisão de estrutura;
- taxa de classificação;
- taxa de revisão;
- taxa de escalonamento;
- custo;
- latência;
- consistência;
- estabilidade entre versões.

## Regra importante

Nenhum threshold deve ser ajustado apenas por intuição.

Alterações devem ser avaliadas em corpus.

---

# 51. Versionamento

Versionar:

- engine;
- modelo canônico;
- contratos;
- templates;
- schemas;
- providers;
- modelos;
- regras;
- políticas;
- normalizadores;
- validadores;
- processamento;
- artefatos;
- API.

Um resultado deve registrar todas as versões relevantes.

---

# 52. Compatibilidade

Ao evoluir contratos:

- preferir campos opcionais;
- evitar renomear sem migração;
- preservar leitura de versões anteriores;
- fornecer adapters;
- documentar breaking changes;
- usar versionamento semântico;
- manter changelog.

---

# 53. Custos

O sistema deve registrar custos estimados e reais:

- CPU;
- GPU;
- armazenamento;
- OCR externo;
- modelo semântico;
- tokens;
- renderização;
- tempo;
- revisão.

O Router poderá futuramente considerar custo como parte da decisão.

---

# 54. Explicação do resultado

Exemplo de explicação ideal:

```text
O campo company.cnpj foi encontrado na página 1.

O parser nativo identificou o rótulo "CNPJ" e o valor localizado à direita.

O template confirmou a relação espacial entre rótulo e valor.

O normalizador removeu pontuação e converteu o valor para 14 dígitos.

O validador de CNPJ confirmou os dígitos verificadores.

A confiança final foi 0,98.

OCR e modelo semântico não foram utilizados.
```

---

# 55. Anti-padrões

Não fazer:

## 55.1. Pipeline fixo para todos

```text
todos os documentos → OCR → IA
```

## 55.2. OCR completo por padrão

Perde texto nativo e aumenta custo.

## 55.3. Regra de negócio dentro do parser

Parser deve produzir estrutura, não campo contábil.

## 55.4. Template preso a coordenada absoluta sem contexto

Coordenadas podem participar, mas não devem ser a única lógica.

## 55.5. Resultado sem evidência

Um JSON sozinho não é suficiente.

## 55.6. Microsserviço por módulo

Módulo lógico pode ser biblioteca interna.

## 55.7. Dependência direta de fornecedor no kernel

Usar provider.

## 55.8. Usar Redis como banco definitivo

Redis é auxiliar.

## 55.9. Misturar task queue e event bus

São responsabilidades diferentes.

## 55.10. Enviar documento inteiro para IA sem necessidade

Enviar apenas escopo relevante.

## 55.11. Confiança única e opaca

Separar dimensões.

## 55.12. Tratar revisão como erro

Revisão é estado válido.

## 55.13. Reprocessar tudo após falha localizada

Escalonar apenas região problemática.

## 55.14. Criar infraestrutura antes do núcleo

O núcleo precisa funcionar localmente.

---

# 56. Decisões arquiteturais já estabelecidas

1. O motor deve ser reutilizável como biblioteca e API.
2. O núcleo deve ser independente de infraestrutura.
3. O processamento deve ser adaptativo.
4. Todos os documentos passam pelo Inspector.
5. OCR deve ser seletivo sempre que possível.
6. O processamento pode ocorrer por página, região ou campo.
7. O resultado deve possuir evidência.
8. O modelo canônico é a base de integração entre capacidades.
9. Templates operam sobre o modelo canônico.
10. Providers são intercambiáveis.
11. O mesmo kernel suporta LocalRuntime e TemporalRuntime.
12. A arquitetura lógica será mais completa que o deployment inicial.
13. O projeto não deve começar com muitos microsserviços.
14. Artefatos e planos devem ser versionados.
15. Confiança deve ser explicável.
16. Revisão humana é fallback válido.
17. Cache deve ser por artefato e configuração.
18. Regras e templates de domínio ficam fora do núcleo.
19. Temporal pode cuidar de task queues.
20. Event bus externo será adicionado apenas quando necessário.

---

# 57. Questões ainda abertas

Estas decisões devem ser discutidas futuramente:

- nome final do produto;
- linguagem principal do kernel;
- biblioteca principal de PDF;
- primeiro provider de OCR;
- representação exata do Document Graph;
- formato de serialização;
- mecanismo de plugins;
- DSL de templates;
- modelo de schema;
- cálculo final de confiança;
- política inicial de cache;
- banco do artifact metadata;
- formato de eventos;
- limite entre packages;
- suporte a streaming;
- estratégia de sandbox;
- primeira interface pública estável;
- primeiro corpus de benchmark;
- estratégia de licenciamento;
- estratégia multi-tenant;
- modelos semânticos locais ou externos;
- suporte inicial a DOCX;
- primeira versão da review UI.

Nenhuma questão aberta invalida os princípios centrais.

---

# 58. Glossário

## Artefato

Resultado intermediário ou final produzido por uma capacidade.

## Capability

Função lógica disponível ao motor, como OCR ou layout.

## Provider

Implementação concreta de uma capability.

## Documento canônico

Representação normalizada de um documento.

## Document Graph

Modelo canônico com relações entre elementos.

## Evidence

Informação que liga um resultado ao documento original.

## Provenance

Histórico completo de produção de um dado.

## Processing Plan

Plano versionado de atividades.

## Router

Componente que decide a estratégia.

## Planner

Componente que cria o plano executável.

## Runtime

Ambiente que executa tarefas local ou remotamente.

## Escalonamento

Aumento seletivo de processamento.

## Reconciliation

Resolução de divergência entre candidatos.

## Review

Revisão humana estruturada.

## Template

Definição reutilizável de como identificar e extrair informações.

## Schema

Descrição da estrutura de saída esperada.

## Normalização

Conversão de valor para formato consistente.

## Validação

Verificação de regras e consistência.

## Confidence

Medida composta de confiabilidade.

---

# 59. Instruções para inteligências artificiais

Qualquer IA que trabalhe neste projeto deve:

1. ler este documento antes de propor mudanças estruturais;
2. diferenciar visão ideal de implementação inicial;
3. não criar microsserviços sem necessidade comprovada;
4. preservar a independência do kernel;
5. criar contratos antes de providers específicos;
6. manter o modelo canônico como ponto central;
7. preservar evidências e proveniência;
8. não executar OCR indiscriminadamente;
9. considerar processamento granular;
10. evitar duplicar mensageria;
11. manter APIs assíncronas quando apropriado;
12. criar testes junto com módulos;
13. documentar decisões;
14. indicar claramente suposições;
15. não inventar funcionalidades já existentes sem inspecionar o código;
16. não quebrar contratos estáveis sem migração;
17. não acoplar templates a bibliotecas específicas;
18. não colocar regras de domínio no core;
19. tratar revisão humana como parte do fluxo;
20. manter a solução simples fisicamente no início.

Antes de modificar código, a IA deve:

```text
1. Ler AGENTS.md, se existir.
2. Ler este contexto mestre.
3. Ler os ADRs relacionados.
4. Inspecionar o workspace real.
5. Identificar módulos existentes.
6. Identificar contratos.
7. Identificar testes.
8. Explicar impactos.
9. Implementar o menor conjunto coerente.
10. Validar.
```

---

# 60. Regra de escopo para novas fases

Cada fase futura deve definir:

- contexto obrigatório;
- estado atual;
- objetivo;
- escopo obrigatório;
- fora do escopo;
- regras arquiteturais;
- contratos;
- modo de execução;
- critérios de aceite;
- testes;
- resposta final esperada.

A fase não deve implementar itens futuros apenas porque aparecem neste contexto.

---

# 61. Exemplo de fluxo completo

```text
1. Cliente envia um PDF.

2. O sistema calcula hash e armazena o original.

3. O Inspector detecta:
   - 10 páginas;
   - 8 digitais;
   - 1 escaneada;
   - 1 tabela em imagem.

4. O Router define:
   - parser nativo nas páginas digitais;
   - OCR completo na página escaneada;
   - OCR regional na tabela;
   - análise estrutural em todas as páginas relevantes.

5. O Planner cria e versiona o plano.

6. O Runtime executa as atividades.

7. Cada atividade produz artefatos.

8. O sistema consolida o Canonical Document.

9. O classificador identifica o tipo documental.

10. O Template Engine executa o template compatível.

11. O Schema Extraction Engine monta os objetos.

12. O Normalization Engine converte datas, valores e documentos.

13. O Validation Engine confirma formatos e totais.

14. O Confidence Engine calcula a confiança.

15. Um campo abaixo do limite é escalonado.

16. O Semantic Engine recebe apenas a região problemática.

17. O Reconciliation Engine compara candidatos.

18. O sistema aceita o valor ou solicita revisão.

19. O resultado final é persistido com evidências.

20. Eventos, métricas e auditoria são registrados.
```

---

# 62. Visão final

O projeto deve evoluir para um motor no qual o consumidor possa dizer:

```text
Aqui está um documento.
Aqui está um schema, template ou instrução.
Processe com este perfil.
Retorne dados, estruturas, confiança e evidências.
```

E o sistema deve decidir:

- qual parser;
- qual OCR;
- qual layout;
- qual análise de tabela;
- qual modelo semântico;
- qual validação;
- qual fallback;
- qual nível de revisão;
- qual custo;
- qual rota.

Sem que o consumidor precise conhecer os detalhes internos.

---

# 63. Definição oficial resumida

> O Distributed Document Intelligence Engine é um motor modular e extensível para inspeção, compreensão, extração, normalização, validação e reconciliação de documentos heterogêneos. Ele utiliza processamento adaptativo, modelo documental canônico, capabilities intercambiáveis, evidências, artefatos versionados e execução local ou distribuída para produzir resultados estruturados, explicáveis e reutilizáveis.

---

# 64. Regra arquitetural final

```text
O motor documental não depende da API.

A API depende do motor documental.

Os workers não implementam a inteligência.

Os workers executam capacidades do motor.

Os templates não dependem do parser.

Os templates operam sobre o modelo canônico.

Todos os documentos passam pelo Inspector.

Cada documento recebe seu próprio plano.

Cada página pode seguir uma rota diferente.

Cada região pode escalar separadamente.

Cada resultado deve manter evidência.

A infraestrutura pode mudar.

Os contratos e o núcleo permanecem.
```

---

# 65. Próxima decisão recomendada

Após a aprovação deste contexto mestre, a próxima etapa deve ser:

> Definir a versão inicial do kernel, seus primeiros pacotes, contratos públicos, modelos principais e limites de escopo.

Essa próxima etapa deve produzir:

- estrutura inicial real do monorepo;
- dependências entre packages;
- contratos principais;
- modelo documental mínimo;
- modelo de artefato;
- interface de capability;
- interface de provider;
- interface de runtime;
- primeiro fluxo local;
- critérios de aceite;
- roadmap técnico incremental.

---

## Encerramento

Este documento representa a visão ideal do sistema.

Ele não exige que tudo seja implementado imediatamente.

A orientação central é:

```text
Pensar grande.
Projetar com fronteiras corretas.
Começar pequeno.
Validar com documentos reais.
Evoluir sem reescrever o núcleo.
```
