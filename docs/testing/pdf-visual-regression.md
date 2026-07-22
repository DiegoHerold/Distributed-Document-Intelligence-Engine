# Regressao Visual PDF

A regressao visual inicial valida o preview de diagnostico, nao um renderer de
producao.

## Escopo

O teste visual reduzido confirma:

- PNG gerado;
- hash deterministico do preview;
- contagens de overlays;
- IDs de elementos;
- clipping associado;
- ordem declarada;
- limitacoes do renderer diagnostico.

## Separacao de Causas

Uma diferenca visual pode vir de:

- renderizacao da pagina-base;
- desenho do overlay;
- geometria extraida;
- ordem visual;
- clipping;
- diferenca do provider.

Como ainda nao ha renderer oficial no Bloco 3, o preview registra a limitacao
`diagnostic_preview.no_official_pdf_renderer`.

## Tolerancias

O conjunto inicial usa PNG deterministico com pagina-base branca. Para esse
caso, o hash deve ser estavel.

Quando um renderer real for integrado, a comparacao deve migrar para metricas
por pixel com tolerancias separadas para antialiasing e rasterizacao de fontes.

Metricas iniciais disponiveis nos testes:

- diferenca de bytes entre previews deterministicos;
- razao de diferenca igual a zero para cenas identicas;
- hash SHA-256 do PNG.

## Execucao

Testes visuais reduzidos usam `pytest.mark.visual` e rodam no CI padrao.

Conjuntos visuais maiores devem ficar em execucao manual ou agendada, junto com
corpus exploratorio e stress.
