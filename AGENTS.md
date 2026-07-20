# AGENTS.md

Instrucoes oficiais para agentes de codigo que trabalhem no projeto Eixo.

## Ordem obrigatoria de leitura

1. `docs/README.md`
2. `docs/context/master-context.md`
3. `docs/roadmap/README.md`
4. `docs/roadmap/phases/README.md`
5. ADRs em `docs/decisions/`
6. Documentos de arquitetura e especificacao relacionados a tarefa
7. Codigo, testes e contratos existentes no workspace

## Regras arquiteturais

- O motor documental nao depende da API; a API depende do motor.
- API, biblioteca, CLI e workers nao reimplementam logica de extracao.
- Toda capability deve nascer com contrato claro e implementacao unica.
- O modelo documental canonico e a base comum entre formatos, parsers, OCR, templates e IA.
- Todo resultado relevante deve preservar evidencia, proveniencia e versoes.
- OCR e modelos semanticos sao capacidades seletivas, nao pipeline obrigatorio.
- A arquitetura logica pode ser rica, mas a implantacao inicial deve evitar microsservicos desnecessarios.
- Infraestrutura e providers devem ser substituiveis por adapters.

## Padrao de execucao

Antes de alterar codigo ou documentacao estrutural:

1. Ler este arquivo.
2. Inspecionar o workspace real.
3. Identificar documentos e ADRs afetados.
4. Explicitar contradicoes ou suposicoes relevantes.
5. Fazer a menor alteracao coerente com o roadmap.
6. Atualizar links, indices e referencias.
7. Executar validacoes disponiveis.

## Padrao para novas fases

Cada fase deve registrar:

- contexto obrigatorio;
- objetivo;
- escopo;
- fora de escopo;
- dependencias;
- entregas;
- criterios de aceite;
- testes esperados;
- documentos atualizados;
- riscos ou duvidas abertas.

## Testes obrigatorios

Quando houver codigo, a entrega deve incluir testes proporcionais ao risco:

- testes unitarios para comportamento local;
- testes de contrato para modelos publicos;
- testes de integracao quando houver adapters;
- testes de paridade quando a mesma funcionalidade for exposta por biblioteca, API e CLI.

## Resposta final esperada

Ao concluir uma tarefa, informe:

- arquivos criados, movidos ou alterados;
- decisoes tomadas;
- contradicoes encontradas;
- validacoes executadas;
- pendencias ou riscos restantes.

