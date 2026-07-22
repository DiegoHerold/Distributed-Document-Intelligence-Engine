# API de parsing PDF

Fase: 3.12.

A API usa endpoints genericos. Nao ha endpoint PDF dedicado.

## Inspect

```http
POST /v1/documents:inspect
Content-Type: multipart/form-data
```

Campos:

- `file`: PDF enviado;
- `options`: JSON opcional;
- `correlation_id`: opcional.

O endpoint cria `InspectionRequest` e chama `DocumentEngine.inspect()`.

## Parse

```http
POST /v1/documents:parse
Content-Type: multipart/form-data
```

Campos:

- `file`: PDF enviado;
- `profile`: `basic`, `textual`, `visual` ou `full_fidelity`;
- `page_selection` ou `pages`: `1-3`, `1,3,5`, `[1,2]` ou `{"pages":[1,2]}`;
- `options`: JSON opcional;
- `correlation_id`: opcional.

Exemplo conceitual:

```json
{
  "profile": "visual",
  "page_selection": {
    "pages": [1, 2]
  }
}
```

Resposta resumida:

```json
{
  "format": "pdf",
  "profile": "visual",
  "status": "success",
  "page_count": 2,
  "artifact_reference": {"artifact_id": "..."},
  "scene_artifact_reference": {"artifact_id": "..."},
  "warnings": [],
  "limitations": []
}
```

## Jobs

```http
POST /v1/extractions
GET /v1/extractions/{job_id}
GET /v1/extractions/{job_id}/result
POST /v1/extractions/{job_id}/cancel
```

`POST /v1/extractions` recebe os mesmos campos `profile`, `page_selection` ou
`pages` e os encaminha para o pipeline generico de processamento.

Erros publicos relevantes:

- `unsupported_format`;
- `pdf.provider_unavailable`;
- `pdf.password_required`;
- `pdf.invalid_password`;
- `pdf.page_out_of_range`;
- `pdf.resource_limit_exceeded`;
- `artifact.storage_failure`;
- `execution.timeout`;
- `execution.cancelled`.
