# ADR-0002 - API e biblioteca desde o inicio

## Status

Aceita.

## Contexto

O motor deve ser usado tanto embarcado em outros projetos quanto por consumidores remotos via API.

## Decisao

Toda funcionalidade publica deve nascer disponivel por biblioteca Python e API REST, usando a mesma camada de aplicacao e os mesmos contratos.

## Consequencias

- Evita duplicacao entre SDK, API, CLI e workers.
- Exige testes de paridade para funcionalidades publicas.
- Permite migrar de motor embarcado para motor remoto com baixo atrito.

