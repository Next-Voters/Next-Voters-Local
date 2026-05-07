# Operations

This document describes how NV Local is typically run in development and how it is deployed in production-like environments.

## Environments

- Local dev: run `python main.py <city>` from a virtualenv
- Container: build and run `docker/Dockerfile` with `NV_CITY` env var set
- CI/CD: GitHub Actions builds and pushes a container image to Amazon ECR

## Configuration And Secrets

Core runtime secrets:

- `OPENAI_API_KEY`: OpenAI API access
- `TAVILY_API_KEY`: Tavily Search + Extract (web search and content retrieval)
- `SUPABASE_URL`, `SUPABASE_KEY`: City/topic config + report storage
- `TOGETHER_API_KEY`: Dynamic self-information scoring for context compression
- `GLAMA_API_KEY`: MCP for Google Calendar event creation

Container-specific:

- `NV_CITY`: City to run pipeline for (set by Dispatcher Lambda)

Operational guidance:

- Prefer injecting secrets via your environment (shell export, container env vars, or AWS Secrets Manager).
- `main.py` calls `dotenv.load_dotenv()`, so a `.env` file is loaded automatically.

## Deployments

### Container Image Build + Push

GitHub workflow: `/.github/workflows/push-image-to-ecr.yml`

- Trigger: pushes to `main`, or manual `workflow_dispatch`
- Authentication: OIDC via GitHub's `id-token` permission — the workflow assumes an IAM role (`AWS_ROLE_ARN` secret) instead of storing long-lived credentials
- Output: image pushed to Amazon ECR with two tags:
  - `<registry>/<repository>:<git_sha>`
  - `<registry>/<repository>:latest`

Required GitHub configuration:
- **Secret**: `AWS_ROLE_ARN` — ARN of the IAM role the workflow assumes via OIDC
- **Variables**: `AWS_REGION`, `ECR_REPOSITORY` — region and ECR repository name

### Runtime (AWS ECS Fargate)

- EventBridge Scheduler triggers a Dispatcher Lambda weekly
- Dispatcher Lambda launches one ECS Fargate task per supported city
- Each Fargate task runs `main.py` with `NV_CITY` env var set
- Reports are saved to the Supabase `reports` table
- Logs are emitted to stdout/stderr and collected by CloudWatch

## Logging And Monitoring

- Primary logs: stdout/stderr from the container
- In production, logs are collected by CloudWatch via ECS Fargate
- Per-topic pipeline failures are logged to stderr; the container exits 1 if any topic fails

## Data Storage And Backups

- Reports are stored in the Supabase `reports` table (upserted per city/topic).
- Supported cities and topics are read from Supabase (`supported_cities` and related tables).
- Backups, retention, and schema migrations are owned by the Supabase project.

## Runbooks

### Job Fails Immediately

1) Check logs for missing env vars (common: `OPENAI_API_KEY` or `TAVILY_API_KEY`).
2) In container mode, verify `NV_CITY` is set and the city exists in the `supported_cities` table.

### Tavily Search / Extract Errors

Symptoms: empty legislation sources or empty content blocks.

1) Verify `TAVILY_API_KEY` is present in the runtime environment.
2) Tavily Extract can fail on JS-heavy SPAs or access-restricted domains; the pipeline falls back to `markdown.new` but this is not 100% reliable.
3) If failures are widespread, check Tavily service status.

### OpenAI Errors / Rate Limits

1) Verify `OPENAI_API_KEY` and account quota.
2) The agent `recursion_limit` (configured in `config/constants.py`) bounds tool-call loops to prevent runaway API usage.
3) If rate-limited, reduce the number of cities running concurrently by adjusting the Dispatcher Lambda fan-out.
