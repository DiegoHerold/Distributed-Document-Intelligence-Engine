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

Nesta fase, jobs e resultados ficam em memoria no `DocumentEngine.local()`.
Como cada invocacao da CLI inicia um novo processo, jobs criados por
`eixo process --no-wait` nao sao duraveis entre chamadas. Os comandos `jobs`
ja existem para o contrato oficial e para testes, mas persistencia real fica
para fases futuras.

## Limitacoes atuais

- sem parser real de PDF ou Excel;
- sem OCR;
- sem runtime distribuido;
- sem API remota na CLI;
- sem persistencia duravel de jobs;
- sem autocomplete avancado.
