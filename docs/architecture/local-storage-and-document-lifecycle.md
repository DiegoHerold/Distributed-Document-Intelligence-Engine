# Storage Local e Ciclo de Vida Documental

Este documento descreve a base implementada nas fases 2.5 e 2.6 do Bloco 2.

## Objetivo

O fluxo local recebe o conteudo ja resolvido e identificado, preserva os bytes
originais como artefato imutavel, cria uma entidade documental e registra
transicoes de estado.

```text
DocumentSource
  -> SourceResolver
  -> DocumentIdentity
  -> LocalArtifactStore
  -> LocalDocumentRepository
  -> DocumentRecord(stored)
```

## Conceitos

- `Document`: entidade logica processada pelo Eixo.
- `Artifact`: conteudo imutavel produzido ou consumido.
- `OriginalDocumentArtifact`: bytes originais recebidos.
- `ArtifactReference`: referencia segura, sem caminho absoluto.
- `ArtifactStore`: porta de armazenamento de artefatos.
- `LocalArtifactStore`: adapter local em filesystem.
- `DocumentRecord`: estado atual da entidade documental.
- `DocumentRepository`: porta para registros e historico do documento.

## Layout Local

O diretorio local e configuravel por `LocalEngineConfig.data_directory` ou
`DocumentEngine.local(data_directory=...)`.

Layout inicial:

```text
.eixo/local/
├── artifacts/
│   └── sha256/
│       └── ab/
│           └── cd/
│               └── <digest>/
│                   ├── content
│                   └── metadata.json
├── documents/
│   └── <document_id>/
│       ├── document.json
│       └── transitions.jsonl
├── metadata/
├── temporary/
└── results/
```

`.eixo/` e `.data/` ficam ignorados pelo Git.

## Artifact Store

`LocalArtifactStore`:

- escreve conteudo em chunks;
- usa arquivo temporario antes do destino final;
- valida tamanho e SHA-256;
- deduplica bytes por hash;
- persiste `metadata.json` versionado;
- abre leitores com context manager;
- verifica existencia e integridade;
- permite exclusao explicita.

O `storage_key` e relativo e opaco para consumidores. Caminhos absolutos ficam
dentro do adapter local.

## Politica de Deduplicacao

Bytes iguais reutilizam o mesmo artefato fisico por SHA-256.

Documentos logicos continuam distintos: cada ingestao cria um novo `DocumentId`,
mesmo quando o `ArtifactReference` aponta para conteudo ja armazenado.

## Ciclo de Vida

Estados iniciais:

- `received`;
- `validated`;
- `stored`;
- `processing`;
- `completed`;
- `review_required`;
- `failed`;
- `cancelled`.

Transicoes principais:

```text
received -> validated | failed
validated -> stored | failed
stored -> processing | failed | cancelled
processing -> completed | review_required | failed | cancelled
completed -> processing
review_required -> processing
failed -> processing
```

Cada mudanca gera `DocumentStateTransition` com data, motivo, ator e metadados.

## Integracao

`IngestDocument` executa:

```text
resolver source
identificar conteudo
validar seguranca de ingestao
criar DocumentRecord(received)
transicionar para validated
armazenar OriginalDocumentArtifact
transicionar para stored
persistir document.json e transitions.jsonl
```

`DocumentEngine.ingest(source)` expõe a ingestao pela biblioteca. As operacoes
`inspect`, `parse`, `process` e `submit` usam o mesmo fluxo antes de resolver a
capability.

## Fora do Escopo

Nao foram implementados:

- jobs persistentes;
- filas;
- parsing de PDF ou Excel;
- OCR;
- stores remotos como S3 ou MinIO;
- PostgreSQL;
- retencao avancada;
- protecao completa contra ZIP bomb;
- ciclo de vida distribuido.

Observacao: a Fase 2.8 adicionou protecao inicial contra ZIP bomb, limites,
nomes perigosos e path traversal. Sandbox completo, antivirus e seguranca de
producao continuam fora do escopo.

## Contradicoes e Duvidas

- O documento da tarefa chama a Fase 2.6 de ciclo de vida do documento, enquanto
  o indice anterior descrevia 2.6 como "registrar documento recebido" e 2.7 como
  ciclo de vida local. Para esta entrega, prevaleceu o anexo mais recente:
  2.5 e 2.6 foram implementadas juntas como storage + registro + lifecycle.
