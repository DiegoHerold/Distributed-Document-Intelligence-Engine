# CLI de parsing PDF

Fase: 3.12.

Os comandos PDF usam a mesma fachada `DocumentEngine` que a biblioteca e a API.
A CLI nao importa nem chama o provider concreto.

## Inspect

```bash
eixo inspect documento.pdf
eixo inspect documento.pdf --format json
```

## Parse

```bash
eixo parse documento.pdf --profile basic
eixo parse documento.pdf --profile textual
eixo parse documento.pdf --profile visual --pages 1-3
eixo parse documento.pdf --profile full-fidelity --output result.json
```

`--pages` usa paginas publicas 1-based e aceita lista ou intervalo:

```bash
eixo parse documento.pdf --pages 1,3,5
eixo parse documento.pdf --pages 1-3
```

Saida console mostra status, documento, formato, perfil, paginas e referencia do
artefato principal. Saida JSON preserva o contrato `ParseResult`.

## Jobs

```bash
eixo process documento.pdf --profile visual
eixo jobs status job_123
eixo jobs result job_123 --format json
eixo jobs cancel job_123
```

No modo local, jobs e resultados ficam no `PersistentJobStore` SQLite do engine.
Artefatos continuam no `ArtifactStore`; caminhos fisicos nao sao exibidos.

## Seguranca

A CLI nao imprime senha, bytes de imagem, programas de fonte nem artefatos
grandes. Quando o backend opcional de PDF nao esta instalado, o codigo de saida
e `6` e a mensagem informa provider de PDF indisponivel.
