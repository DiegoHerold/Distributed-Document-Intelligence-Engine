# API e Biblioteca

Toda funcionalidade publica deve nascer uma vez no nucleo ou em uma capability e ser exposta por camadas de adaptacao.

## Regra

```text
Contrato
  -> implementacao no nucleo/capability
  -> caso de uso na camada de aplicacao
  -> SDK Python
  -> API REST
  -> CLI quando fizer sentido
```

## Biblioteca

O SDK Python deve expor uma interface ergonomica, mas nao deve duplicar logica de processamento.

Atualmente, o SDK reexporta `DocumentEngine` como fachada publica.

Distribuicao publica atual:

```text
eixo-document-sdk-python
```

Import publico:

```python
from eixo import DocumentEngine, ProcessingRequest
```

O pacote e tipado via `py.typed` e nao inicializa runtime durante import.

## API

A API deve importar contratos compartilhados e chamar casos de uso. Ela nao deve declarar modelos paralelos para requests e responses de dominio.

Na composicao local, a API cria uma unica instancia de `DocumentEngine` por aplicacao e delega startup/shutdown para ela.

A API REST inicial usa FastAPI como adaptador HTTP. A application factory e:

```python
from eixo_api import create_app

app = create_app()
```

`create_app()` nao inicia runtime durante import. O lifespan do framework cria
ou reaproveita o engine, chama `engine.start()` no startup e `engine.shutdown()`
no shutdown.

Endpoints documentais usam `/v1`:

- `POST /v1/documents:inspect`;
- `POST /v1/documents:parse`;
- `POST /v1/extractions`;
- `GET /v1/extractions/{job_id}`;
- `GET /v1/extractions/{job_id}/result`;
- `POST /v1/extractions/{job_id}/cancel`.

Endpoints operacionais permanecem fora de `/v1`:

- `GET /health`;
- `GET /ready`.

Uploads `multipart/form-data` sao convertidos para `BytesSource`. Objetos HTTP,
como arquivos do framework, nao entram no nucleo. O adapter multipart inicial
materializa o arquivo em memoria apos validar limite de tamanho; resolucao,
deteccao de formato e hashing pertencem ao fluxo compartilhado do engine.
Antes de executar capabilities, o engine tambem armazena o original via
`IngestDocument`, `LocalArtifactStore` e `LocalDocumentRepository`.

Erros de dominio sao convertidos para `ErrorResult` com correlation ID.

## CLI

A CLI adapta entrada de terminal para os mesmos contratos e casos de uso. Ela nao deve conter parsers documentais.

A CLI inicial usa `argparse`, preservando a dependencia zero de framework
externo, e expoe o comando empacotado `eixo`.

Comandos documentais:

- `eixo inspect`;
- `eixo parse`;
- `eixo process`;
- `eixo jobs status`;
- `eixo jobs result`;
- `eixo jobs cancel`.

Cada comando converte argumentos de terminal para contratos publicos, como
`InspectionRequest`, `ParseRequest`, `ProcessingRequest` e `JobResult`, e chama
`DocumentEngine.local()`.

Assim como API e SDK, a CLI nao grava artefatos diretamente: o storage local e
acionado pelo engine.

Jobs tambem passam exclusivamente pelo `DocumentEngine`. O modo local usa
`PersistentJobService` e `SQLiteJobStore`; API e CLI nao acessam o banco de
jobs diretamente.

Saidas suportadas:

- `console`;
- `json`;
- arquivo JSON via `--output`.

Comandos de diagnostico da CLI tambem usam a fachada `DocumentEngine`.

## Estado atual

Bloco 1 cria apenas a fundacao:

- `eixo_api.create_app()`;
- API REST v1 inicial;
- `eixo_cli.main()`;
- CLI inicial `eixo`;
- `DocumentEngine.local()`;
- contratos compartilhados;
- casos de uso;
- Capability Registry.

Ainda nao existem capabilities reais de PDF, Excel, OCR, layout, tabelas ou IA
semantica. Jobs e resultados locais sao persistidos em SQLite no
`data_directory` do engine, mas essa ainda nao e a persistencia de producao do
Eixo.
