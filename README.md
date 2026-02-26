# Cognitive OS Kernel (MVP)

## Run Demo

```bash
python -m cognitive_os.demo.simple_case
```

## Run HTTP API

```bash
python -c "from cognitive_os.api.http_api import run_http_api; run_http_api()"
```

POST `http://localhost:8000/cognition/run`

```json
{
  "goal": "demo goal",
  "boundary": "global",
  "metadata": {}
}
```
