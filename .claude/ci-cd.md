# CI/CD Triggers & Local Mocks

## 1. Local Mocks (for development)

### JIRA Mock: `twin-jira`

Full JIRA Cloud REST API replica with CRUD and JQL support.

```yaml
# docker-compose.yml
services:
  jira-mock:
    image: node:20-alpine
    command: npx @volter/twin-jira serve --port 8080
    ports:
      - "8080:8080"
    environment:
      - JIRA_TWIN_ROOT=/data
    volumes:
      - ./test-data/jira:/data
```

### Confluence Mock: `mock-mock`

Auto-generates mocks from Confluence API documentation.

```yaml
# docker-compose.yml
services:
  confluence-mock:
    image: node:20-alpine
    command: npx @mhmdalimansour/mock-mock --url file:///app/confluence-docs.html --port 8081
    ports:
      - "8081:8081"
    volumes:
      - ./test-data/confluence:/app
```

### Point the Agent to Mocks

```yaml
environment:
  JIRA_URL: http://jira-mock:8080
  CONFLUENCE_URL: http://confluence-mock:8081
```

---

## 2. GitHub Actions Trigger

File: `.github/workflows/agent-triage.yml`

### Triggers

- `issues`: When a new issue is opened or labeled.
- `pull_request`: When a new PR is opened or updated.
- `issue_comment`: When someone comments (e.g., `/agent review`).

### Workflow

```yaml
name: AI Agent Triage

on:
  issues:
    types: [opened, labeled]
  pull_request:
    types: [opened, synchronize]
  issue_comment:
    types: [created]

jobs:
  run-agent:
    if: contains(github.event.comment.body, '@agent') || github.event_name != 'issue_comment'
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Run Agent Container
        env:
          TASK: ${{ github.event.issue.title || github.event.pull_request.title }}
          GITHUB_ISSUE_NUMBER: ${{ github.event.issue.number || github.event.pull_request.number }}
          GITHUB_REPO: ${{ github.repository }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          docker run --rm \
            -e TASK="$TASK" \
            -e GITHUB_ISSUE_NUMBER="$GITHUB_ISSUE_NUMBER" \
            -e GITHUB_REPO="$GITHUB_REPO" \
            -e GITHUB_TOKEN="$GITHUB_TOKEN" \
            -e ANTHROPIC_API_KEY="${{ secrets.ANTHROPIC_API_KEY }}" \
            -v ${{ github.workspace }}:/workspace \
            gcr.io/${{ secrets.GCP_PROJECT }}/langchain-sldc-deep-agents:latest \
            python -m app.cli

      - name: Post Results as Comment
        if: github.event_name == 'pull_request' || github.event_name == 'issue_comment'
        uses: actions/github-script@v6
        with:
          script: |
            const fs = require('fs');
            const output = JSON.parse(fs.readFileSync('./output.json', 'utf8'));
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `## 🤖 AI Agent Analysis\n\n**Summary:** ${output.summary}\n**Score:** ${output.review_score}/100\n**Files Changed:** ${output.files_changed.join(', ')}`
            });
```

---

## 3. Bitbucket Pipelines Trigger

File: `bitbucket-pipelines.yml`

### Custom Trigger (Manual)

```yaml
image: atlassian/default-image:3

pipelines:
  custom:
    agent-trigger:
      - variables:
          - name: TASK
            default: 'Analyze this work'
          - name: JIRA_KEY
      - step:
          name: Run AI Agent
          script:
            - docker pull gcr.io/$GCP_PROJECT/langchain-sldc-deep-agents:latest
            - docker run --rm
                -e TASK="$TASK"
                -e JIRA_KEY="$JIRA_KEY"
                -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY"
                -v $(pwd):/workspace
                gcr.io/$GCP_PROJECT/langchain-sldc-deep-agents:latest
                python -m app.cli
```

### PR Trigger (Automatic)

```yaml
  pull-requests:
    '**':
      - step:
          name: AI Code Review
          script:
            - export TASK="Review PR #$BITBUCKET_PR_ID"
            - export JIRA_KEY=$(git log -1 --pretty=%s | grep -oP 'PROJ-\d+' || echo "")
            - docker run --rm
                -e TASK="$TASK"
                -e JIRA_KEY="$JIRA_KEY"
                -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY"
                -v $(pwd):/workspace
                gcr.io/$GCP_PROJECT/langchain-sldc-deep-agents:latest
                python -m app.cli
```

---

## 4. The Headless CLI Entrypoint

Run the agent without an HTTP server—ideal for CI/CD.

### Basic Usage

```bash
docker run --rm \
  -e TASK="Fix login bug PROJ-123" \
  -e JIRA_KEY="PROJ-123" \
  -e GITHUB_TOKEN="ghp_xxxxx" \
  -e ANTHROPIC_API_KEY="sk-..." \
  -e POSTGRES_DSN="sqlite:///memory.db" \
  -v $(pwd):/workspace \
  gcr.io/PROJECT/langchain-sldc-deep-agents:latest \
  python -m app.cli
```

### Local Testing

```bash
# Build locally
docker build -t langchain-sldc-deep-agents:local .

# Run with environment variables
docker run --rm \
  -e TASK="Implement login feature" \
  -e POSTGRES_DSN="sqlite:///memory.db" \
  -v $(pwd):/workspace \
  langchain-sldc-deep-agents:local \
  python -m app.cli
```

### Exit Codes

- `0`: Success (review score >= 60)
- `1`: Failure (review score < 60 or error)

### Output (JSON)

```json
{
  "status": "success",
  "summary": "Implemented OAuth2 login with JWT tokens. Added 3 unit tests.",
  "files_changed": ["src/auth.py", "tests/test_auth.py"],
  "review_score": 85,
  "security_report": "No critical vulnerabilities found."
}
```

---

## 5. Cloud Scheduler (GCP)

For scheduled agent runs (e.g., nightly tech debt scans):

```yaml
apiVersion: cloud.google.com/v1
kind: CloudSchedulerJob
metadata:
  name: nightly-code-review
spec:
  schedule: "0 2 * * *"  # 2 AM daily
  httpTarget:
    uri: https://YOUR_CLOUD_RUN_URL/schedule/nightly-review
    httpMethod: POST
    headers:
      Content-Type: application/json
    oidcToken:
      serviceAccountEmail: YOUR_SA@project.iam.gserviceaccount.com
```

---

## 6. CI/CD Pipeline (GitHub Actions)

File: `.github/workflows/ci.yaml`

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install poetry && poetry install
      - run: poetry run ruff check .        # Linting
      - run: poetry run mypy app/           # Type checking
      - run: poetry run pytest tests/ --cov=app/   # Unit + Eval tests
      - run: docker compose -f docker-compose.yml up -d
      - run: poetry run pytest tests/integration/ # Integration tests
      - run: docker compose down
```

File: `.github/workflows/cd.yaml`

```yaml
name: CD

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: gcr.io/${{ secrets.GCP_PROJECT }}/langchain-sldc-deep-agents:latest
      - name: Deploy to Cloud Run
        run: |
          gcloud run deploy langchain-sldc-deep-agents \
            --image gcr.io/${{ secrets.GCP_PROJECT }}/langchain-sldc-deep-agents:latest \
            --platform managed \
            --region us-central1 \
            --memory 4Gi \
            --cpu 2 \
            --timeout 3600 \
            --set-env-vars "ENVIRONMENT=production"
```