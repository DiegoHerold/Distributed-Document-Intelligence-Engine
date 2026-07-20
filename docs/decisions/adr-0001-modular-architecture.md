# ADR-0001 - Arquitetura modular

## Status

Aceita.

## Contexto

O Eixo precisa processar documentos heterogeneos com diferentes formatos, providers, modelos e modos de execucao.

## Decisao

Adotar uma arquitetura modular com nucleo independente, capabilities intercambiaveis, adapters de infraestrutura e camadas de consumo separadas.

## Consequencias

- O nucleo permanece reutilizavel e testavel.
- Providers podem mudar sem alterar contratos publicos.
- Modulos logicos nao precisam virar servicos fisicos imediatamente.
- Cada nova capability deve ter limites claros.

