# PDF Graphics State

Status: Fase 3.8 implementada parcialmente.

## Objetivo

`PDFEffectiveGraphicsState` representa o estado grafico efetivo usado por um
elemento vetorial.

Campos principais:

- matriz atual;
- largura de contorno;
- line cap;
- line join;
- miter limit;
- dash array e dash phase;
- cor de preenchimento;
- cor de contorno;
- opacidade de fill;
- opacidade de stroke;
- blend mode;
- soft mask;
- clipping ativo;
- operacoes que alteraram o estado.

## Resolver

`PDFGraphicsStateResolver` preserva uma pilha imutavel por operacao:

- `save()` empilha uma copia do estado atual;
- `restore()` desempilha quando possivel;
- underflow gera warning `graphics_state_stack_underflow`;
- `update()` retorna novo resolver, sem compartilhar estado mutavel.

Quando o provider entrega apenas propriedades efetivas, o adapter cria
`PDFEffectiveGraphicsState` com `partially_resolved=True`.

## Cores

`PDFColorValue` preserva o valor original e o espaco de cor declarado. RGB
normalizado pode existir como representacao adicional, mas CMYK, ICCBased,
Separation e DeviceN nao devem ser convertidos silenciosamente para RGB.
