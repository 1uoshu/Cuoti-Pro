# Docker Compose Deployment

The root `compose.yaml` deploys the backend and MySQL only. It deliberately does not build
or modify the frontend.

## Start

1. Copy `.env.compose.example` to `.env` at the repository root.
2. Set `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, JWT, and database passwords.
3. Run:

   ```bash
   docker compose up --build -d
   ```

The backend waits for MySQL, runs `alembic upgrade head`, and starts at
`http://localhost:8000`. OpenAPI documentation is at `http://localhost:8000/docs`.

Check readiness with:

```bash
docker compose ps
docker compose logs -f backend
```

MySQL data and uploaded assignments use named volumes `mysql_data` and `upload_data`.
Stopping containers does not delete them.

## Configuration

The built-in Agent directly reuses the `OPENAI_*` values.

`OPENAI_BASE_URL` is the prefix immediately before `/responses`. For example,
`https://api.mhapi.cn` produces `https://api.mhapi.cn/responses`, while the official
OpenAI-compatible prefix is commonly `https://api.openai.com/v1`.

For a real deployment, replace every demo password, terminate TLS at a reverse proxy,
restrict CORS, back up both volumes, and move sandbox execution to a dedicated isolated
worker before accepting untrusted public traffic.
