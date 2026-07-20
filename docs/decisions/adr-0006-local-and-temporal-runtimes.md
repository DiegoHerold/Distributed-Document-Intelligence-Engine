# ADR-0006 - LocalRuntime e TemporalRuntime

## Status

Aceita.

## Contexto

O Eixo deve funcionar localmente no inicio e evoluir para execucao distribuida sem reescrever a inteligencia principal.

## Decisao

Definir contratos de runtime que permitam `LocalRuntime` para execucao embarcada e `TemporalRuntime` para execucao distribuida futura.

## Consequencias

- Biblioteca e testes podem usar runtime local.
- API distribuida futura pode usar Temporal.
- O mesmo teste funcional deve poder validar runtimes diferentes quando ambos existirem.

