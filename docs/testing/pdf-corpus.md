# Corpus PDF

O corpus da Fase 3.13 fica em `tests/corpus/pdf`.

## Organizacao

Cada categoria possui documentos sinteticos e manifestos pareados:

```text
tests/corpus/pdf/<categoria>/
|-- sample.pdf
|-- sample.manifest.json
`-- sample.expected.json
```

Categorias iniciais:

- `basic`
- `text`
- `fonts`
- `images`
- `vectors`
- `geometry`
- `clipping`
- `interactive`
- `protected`
- `malformed`
- `hybrid`
- `stress`

## Manifesto

Cada manifesto registra:

- `document_id`
- `name`
- `description`
- `source`
- `license`
- `generated`
- `category`
- `features`
- `expected_pages`
- `expected_profile`
- `known_limitations`
- `tags`
- `sha256`
- `golden_type`

O hash SHA-256 e obrigatorio para detectar alteracao acidental do fixture.

## Governanca

O corpus inicial usa apenas PDFs sinteticos gerados por
`tests/corpus/pdf/generate.py` com licenca `CC0-1.0 synthetic fixture`.

Nao incluir:

- documentos de clientes;
- dados pessoais reais;
- senhas;
- certificados privados;
- PDFs externos sem licenca clara;
- arquivos que executem acoes incorporadas.

## Golden e Exploratory

`golden_type=golden` identifica documentos deterministicos que podem bloquear CI.

`golden_type=exploratory` identifica casos complexos, dependentes de provider ou
destinados a execucao manual/agendada.

## Metricas

`tools.pdf_golden.corpus_metrics()` calcula:

- quantidade de documentos;
- paginas esperadas;
- cobertura de features;
- cobertura de perfis;
- quantidade de testes golden;
- quantidade de testes visuais;
- limitacoes conhecidas.
