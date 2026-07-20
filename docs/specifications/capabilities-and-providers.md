# Capabilities e Providers

## Capability

Uma capability representa uma funcao logica do motor, como:

- `document.inspect`;
- `document.parse.pdf`;
- `document.parse.excel`;
- `document.render`;
- `document.ocr`.

Ela possui um `CapabilityDescriptor` e executa de forma assincrona:

```python
await capability.execute(request, context)
```

## Provider

Um provider representa uma implementacao concreta de uma ou mais capabilities.

Exemplos futuros:

- Tesseract para OCR;
- PaddleOCR para OCR;
- um parser PDF especifico;
- um provider semantico.

## Registry

O `CapabilityRegistry` permite:

- registrar providers;
- registrar capabilities;
- buscar por identificador;
- buscar por formato;
- buscar por contrato de entrada e saida;
- resolver uma capability compativel;
- rejeitar duplicidades;
- detectar capability ausente.

O descriptor inicial tambem declara caracteristicas operacionais:

- `resource_class`;
- `deterministic`;
- `supports_cancellation`;
- `supports_progress`;
- prioridade;
- status;
- metadata extensivel.

Formatos e MIME vazios representam compatibilidade generica naquele eixo. Quando
preenchidos, a resolucao exige correspondencia normalizada.

## Como adicionar uma capability futuramente

1. Defina o contrato de entrada e saida.
2. Crie um `CapabilityDescriptor`.
3. Registre o provider.
4. Registre a capability.
5. Adicione testes de compatibilidade e execucao.

## Limitacoes atuais

O registry nao faz roteamento, custo, latencia ou execucao distribuida. Essas responsabilidades ficam para fases futuras.
