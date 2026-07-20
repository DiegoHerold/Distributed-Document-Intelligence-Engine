# Usando a API REST

A API REST inicial do Eixo expoe `DocumentEngine.local()` por HTTP.

Ela reutiliza os contratos publicos do nucleo:

- `InspectionRequest` e `InspectionResult`;
- `ParseRequest` e `ParseResult`;
- `ProcessingRequest` e `ProcessingResult`;
- `JobResult`;
- `ErrorResult`.

## Executar

```bash
uv run uvicorn eixo_api.main:app --reload
```

Alternativa quando `uv` nao estiver disponivel:

```bash
python -m uvicorn eixo_api.main:app --reload
```

## Health

```bash
curl http://localhost:8000/health
```

Resposta:

```json
{
  "status": "ok",
  "service": "eixo-api",
  "version": "0.1.0"
}
```

## Readiness

```bash
curl http://localhost:8000/ready
```

Quando pronta, a API retorna 200. Antes do startup ou durante falha, retorna
503. Readiness nao exige parser real de PDF ou Excel.

## Inspecionar documento

```bash
curl -X POST \
  -F "file=@documento.pdf" \
  -F 'options={"mode":"quick"}' \
  http://localhost:8000/v1/documents:inspect
```

O arquivo e convertido para `BytesSource` e enviado para
`DocumentEngine.inspect()`.

## Parse

```bash
curl -X POST \
  -F "file=@documento.pdf" \
  -F "requested_capability=native" \
  http://localhost:8000/v1/documents:parse
```

O arquivo e convertido para `ParseRequest` e enviado para
`DocumentEngine.parse()`.

## Criar extracao assincrona

```bash
curl -X POST \
  -F "file=@documento.pdf" \
  -F "profile=balanced" \
  http://localhost:8000/v1/extractions
```

Resposta:

```json
{
  "job_id": "job_123",
  "status": "queued",
  "progress": 0.0,
  "created_at": "2026-07-20T12:00:00Z"
}
```

A resposta usa `202 Accepted` e inclui `Location: /v1/extractions/{job_id}`.

## Consultar status

```bash
curl http://localhost:8000/v1/extractions/job_123
```

Retorna `JobResult`.

## Consultar resultado

```bash
curl http://localhost:8000/v1/extractions/job_123/result
```

Se o job ainda nao terminou, a API retorna 409 com `ErrorResult`.

## Cancelar

```bash
curl -X POST \
  http://localhost:8000/v1/extractions/job_123/cancel
```

Cancelamento aceito retorna 202. Job ja cancelado e idempotente. Job concluido
retorna 409.

## Correlation ID

Envie `X-Correlation-ID` quando quiser rastrear uma requisicao:

```bash
curl -H "X-Correlation-ID: corr_123" http://localhost:8000/health
```

A API devolve o mesmo header quando valido ou gera um novo quando ausente.

## Limitacoes atuais

- jobs ficam em memoria;
- resultados ficam em memoria;
- dados sao perdidos ao reiniciar;
- nao ha autenticacao;
- nao ha persistencia de producao;
- nao ha parser real de PDF, Excel, OCR, layout, tabelas ou IA semantica.
