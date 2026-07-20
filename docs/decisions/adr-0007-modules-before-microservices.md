# ADR-0007 - Modulos antes de microsservicos

## Status

Aceita.

## Contexto

Separar cedo demais cada capacidade em um microsservico aumenta custo operacional e dificulta a evolucao do nucleo.

## Decisao

Comecar com modulos e pacotes bem definidos em um monorepo. Criar servicos fisicos apenas quando houver necessidade comprovada de escala, isolamento ou operacao.

## Consequencias

- A arquitetura logica pode ser completa sem multiplicar deploys.
- Workers iniciais devem ser poucos e orientados por perfil de execucao.
- O projeto preserva simplicidade enquanto contratos amadurecem.

