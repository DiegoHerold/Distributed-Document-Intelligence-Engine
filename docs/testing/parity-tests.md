# Testes de Paridade

Esta documentacao descreve a estrategia da Fase 1.11 para validar que SDK,
API REST e CLI usam a mesma implementacao interna e produzem resultados
semanticamente equivalentes.

## Canais

| Canal | Entrada testada | Caminho |
| --- | --- | --- |
| Biblioteca | `from eixo import DocumentEngine` | `DocumentEngine -> application -> registry -> runtime` |
| API | `TestClient` com requisicao HTTP real | `HTTP -> router -> DocumentEngine -> application -> registry -> runtime` |
| CLI | `eixo_cli.main` com argumentos reais | `args -> CLI adapter -> DocumentEngine -> application -> registry -> runtime` |

A CLI e executada pela entrada publica do pacote. A injecao de engine nos
testes e usada apenas para registrar a mesma capability deterministica nos
tres canais.

## Capability Deterministica

Os testes usam capabilities em `tests/parity/fake_capabilities.py`.

Elas cobrem:

- inspecao;
- parsing;
- processamento;
- warning;
- formato nao suportado;
- falha de execucao;
- timeout;
- validacao de arquivo vazio.

Essas capabilities vivem somente na infraestrutura de teste.

## Normalizacao

`normalize_for_parity()` converte dataclasses, enums, ids e valores
serializaveis para uma estrutura comparavel. O normalizador remove apenas
campos listados em `tests/parity/ignored_fields.py`.

O comparador recursivo informa o caminho exato da primeira divergencia.

## Campos Ignorados

| Caminho | Justificativa |
| --- | --- |
| `correlation_id` | cada transporte cria ou propaga correlation IDs de modo proprio |
| `details.task_id` | task ID e metadado local do runtime |
| `details.timeout` | duracao do timeout e diagnostico local do runtime |
| `execution_metadata` | contem tempo e correlacao de execucao local |
| `metadata.filename` | HTTP e arquivo local podem preservar nomes de formas diferentes |
| `job.job_id` | submit gera job IDs nao deterministas por engine local |
| `job.created_at` | timestamp de criacao do job varia por execucao |
| `status.job_id` | status consulta job IDs locais diferentes por canal |
| `status.created_at` | timestamp de job varia por canal |
| `status.started_at` | timestamp de job varia por canal |
| `status.completed_at` | timestamp de job varia por canal |
| `cancel.job_id` | cancelamento usa job IDs locais diferentes por canal |
| `cancel.created_at` | timestamp de cancelamento varia por canal |
| `cancel.started_at` | timestamp de cancelamento varia por canal |
| `cancel.completed_at` | timestamp de cancelamento varia por canal |

Nao sao ignorados: status, dados, warnings, erros, artefatos, document IDs
deterministicos, capability, provider, versao de contrato e resultado
semanticamente relevante.

## Matriz De Cobertura

| Operacao | Biblioteca | API | CLI | Cenario | Resultado |
| --- | --- | --- | --- | --- | --- |
| inspect | sim | sim | sim | sucesso | obrigatorio |
| parse | sim | sim | sim | sucesso | obrigatorio |
| process | sim | sim | sim | sucesso | obrigatorio |
| process | sim | sim | sim | warning | obrigatorio |
| inspect | sim | sim | sim | arquivo vazio | obrigatorio |
| inspect | sim | sim | sim | capability ausente | obrigatorio |
| process | sim | sim | sim | falha de execucao | obrigatorio |
| inspect | sim | sim | sim | timeout | obrigatorio |
| submit | sim | sim | sim | job aceito | obrigatorio |
| jobs status/result | sim | sim | sim | job concluido | obrigatorio |
| jobs cancel | sim | sim | sim | cancelamento | obrigatorio |
| process | sim | sim | sim | defaults | obrigatorio |
| process | sim | sim | sim | serializacao | obrigatorio |
| process | sim | sim | sim | isolamento | obrigatorio |

## Jobs Na CLI

O runtime local da CLI nao oferece persistencia duravel entre processos do
sistema operacional. Por isso, a paridade de `jobs status` e `jobs result`
usa uma composicao compartilhada em processo de teste. Isso valida os comandos
e o caminho real ate o `DocumentEngine`, mas nao transforma jobs locais em
persistencia de producao.

Persistencia duravel de jobs continua fora do escopo do Bloco 1.

## Comandos

Executar somente paridade:

```bash
python -m pytest tests/parity
```

Executar suite completa do projeto:

```bash
python -m tools.eixo_dev test
```

Neste workspace, use o Python empacotado pelo Codex quando `python` nao estiver
no PATH.
