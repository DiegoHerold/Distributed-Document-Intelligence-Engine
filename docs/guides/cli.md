# CLI do Eixo

A CLI inicial permite usar o Eixo pelo terminal com os mesmos contratos da
biblioteca Python e da API REST.

Fluxo:

```text
CLI
  -> DocumentEngine
  -> Application
  -> Capability Registry
  -> LocalRuntime
```

A CLI nao contem logica documental.

## Instalar e executar

No workspace:

```bash
python -m eixo_cli.main --help
```

Pelo empacotamento Python:

```bash
eixo --help
```

## Comando raiz

```bash
eixo --help
eixo --version
```

## Inspect

```bash
eixo inspect documento.pdf
eixo inspect documento.pdf --format json
eixo inspect documento.pdf --output resultado.json
eixo inspect documento.pdf --output resultado.json --force
```

O comando cria `InspectionRequest` com `LocalPathSource` e chama
`DocumentEngine.inspect()`.

## Parse

```bash
eixo parse documento.pdf
eixo parse documento.pdf --format json --pretty
eixo parse documento.pdf --output parsed.json
```

O comando cria `ParseRequest` e chama `DocumentEngine.parse()`.

## Process

```bash
eixo process documento.pdf
eixo process documento.pdf --profile balanced
eixo process documento.pdf --profile fast
eixo process documento.pdf --profile automatic
eixo process documento.pdf --no-wait
```

Com `--wait`, comportamento padrao, chama `DocumentEngine.process()`.

Com `--no-wait`, chama `DocumentEngine.submit()` e retorna `JobResult`.

## Jobs

```bash
eixo jobs status job_123
eixo jobs result job_123 --format json
eixo jobs result job_123 --output result.json
eixo jobs cancel job_123
```

Os comandos chamam `DocumentEngine.get_job_status()`,
`DocumentEngine.get_job_result()` e `DocumentEngine.cancel_job()`.

Jobs locais sao persistidos no `data_directory` do engine por SQLite. A CLI
continua sem acessar o banco diretamente; ela sempre passa pela fachada publica.

## Formatos de saida

Console:

```bash
eixo inspect documento.pdf
```

JSON:

```bash
eixo inspect documento.pdf --format json > resultado.json
```

`stdout` recebe somente a saida do comando. Erros sao enviados para `stderr`.

## Erros e debug

Sem `--debug`, a CLI mostra mensagens curtas:

```text
Erro: capability necessaria nao encontrada.
```

Com `--debug`, inclui traceback e detalhes tecnicos:

```bash
eixo inspect documento.pdf --debug
```

## Codigos de saida

- `0`: sucesso;
- `1`: erro geral;
- `2`: argumentos invalidos;
- `3`: fonte nao encontrada;
- `4`: formato nao suportado;
- `5`: validacao invalida;
- `6`: capability indisponivel;
- `7`: job nao encontrado;
- `8`: processamento falhou;
- `9`: processamento cancelado;
- `10`: timeout;
- `11`: erro de configuracao.

## Limitacoes

Ainda nao existem capabilities reais de PDF, Excel, OCR, layout, tabelas ou IA
semantica. Jobs e resultados usam persistencia local simples em SQLite, mas
ainda nao ha API remota na CLI nem persistencia distribuida de producao.
