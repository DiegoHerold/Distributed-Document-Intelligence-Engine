# eixo-cli

Interface de linha de comando oficial inicial do Eixo.

A CLI e um adaptador sobre `DocumentEngine.local()`. Ela nao implementa parsing,
nao acessa stores diretamente e nao importa bibliotecas concretas de PDF, Excel
ou OCR.

## Execucao

No workspace:

```bash
python -m eixo_cli.main --help
```

Quando instalado pelo pacote `eixo-cli`, o comando exposto e:

```bash
eixo --help
```

## Comandos

```bash
eixo --version
eixo inspect documento.pdf
eixo parse documento.pdf
eixo process documento.pdf
eixo jobs status job_123
eixo jobs result job_123
eixo jobs cancel job_123
```

Comandos auxiliares preservados:

```bash
eixo doctor
eixo runtime info
```

## Opcoes comuns

- `--format console|json`: formato de saida.
- `--output caminho`: grava JSON em arquivo.
- `--pretty`: formata JSON.
- `--quiet`: reduz mensagens auxiliares.
- `--verbose`: reservado para mensagens adicionais reais.
- `--debug`: inclui detalhes tecnicos em erros.
- `--force`: permite sobrescrever arquivo de saida.

## Exemplos

```bash
eixo inspect documento.pdf
eixo inspect documento.pdf --format json
eixo parse documento.pdf --output parsed.json
eixo process documento.pdf --profile balanced
eixo process documento.pdf --no-wait --format json
eixo jobs status job_123
eixo jobs result job_123 --output result.json
```

## Saida

Saida estruturada vai para `stdout`. Mensagens de erro vao para `stderr`.

`--format json` usa a serializacao oficial dos contratos. `--output` sempre
grava JSON UTF-8 e nao sobrescreve arquivos sem `--force`.

## Seguranca de ingestao

A CLI nao valida documentos por conta propria. Ela adapta caminhos locais para
`DocumentSource` e deixa o `DocumentEngine` aplicar a politica central de
ingestao: tamanho, vazio, formato real, MIME, corrupcao basica, XLSX/ZIP,
timeout de leitura, limite de paginas conhecido e nomes perigosos.

Em modo JSON, os erros usam os mesmos codigos publicos da biblioteca e da API,
como `file_too_large`, `empty_file`, `unsupported_format`, `invalid_mime`,
`corrupted_file`, `archive_security_error`, `page_limit_exceeded` e
`read_timeout`.

## Codigos de saida

| Codigo | Significado |
| ---: | --- |
| 0 | sucesso |
| 1 | erro geral |
| 2 | argumentos invalidos |
| 3 | fonte nao encontrada |
| 4 | formato nao suportado |
| 5 | validacao invalida |
| 6 | capability indisponivel |
| 7 | job nao encontrado |
| 8 | processamento falhou |
| 9 | processamento cancelado |
| 10 | timeout |
| 11 | erro de configuracao |

## Jobs

Jobs e resultados estruturados pequenos sao persistidos pelo
`DocumentEngine.local()` em SQLite. A CLI continua sem acessar stores
diretamente: `eixo jobs status`, `eixo jobs result` e `eixo jobs cancel` chamam
a fachada publica.

Esta persistencia e local e adequada para desenvolvimento. Persistencia
distribuida, API remota na CLI e workers de producao continuam fora desta fase.

## Limitacoes atuais

- sem parser real de PDF ou Excel;
- sem OCR;
- sem runtime distribuido;
- sem API remota na CLI;
- sem persistencia distribuida de jobs;
- sem autocomplete avancado.
