# PDF Text Order

Status: Fases 3.5 e 3.6 implementadas parcialmente.

O Eixo diferencia:

- ordem no content stream;
- ordem de operacao;
- ordem do provider;
- ordem aproximada de pintura;
- ordem nativa de leitura;
- ordem semantica futura.

Estas ordens nao sao equivalentes.

Na implementacao PyMuPDF atual, glifos e spans recebem ordem derivada de
`page.get_text("rawdict")`. A ordem de operadores textuais brutos ainda nao e
decodificada.

`PDFPaintOrder` continua carregando confianca, normalmente
`provider_approximation` nesta fase.
