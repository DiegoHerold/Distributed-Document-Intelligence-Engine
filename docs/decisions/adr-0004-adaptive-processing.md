# ADR-0004 - Processamento adaptativo

## Status

Aceita.

## Contexto

Documentos variam em qualidade, estrutura, formato, cobertura de texto nativo e necessidade de OCR ou IA.

## Decisao

Todo documento deve passar por inspecao e receber uma rota de processamento adaptativa. O plano pode variar por documento, pagina, regiao ou campo.

## Consequencias

- OCR completo nao e o caminho padrao.
- O sistema pode reprocessar apenas regioes problematicas.
- Router, Planner e Processing Plan tornam-se componentes centrais.
- Custos e latencia podem ser controlados por perfil e politica.

