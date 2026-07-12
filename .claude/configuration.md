# Configuration Guide: langchain-sldc-deep-agents

## `agents.yaml` Schema

### 1. `mcp_servers` (Tool Sources)

Define external tool providers. They are run as subprocesses (stdio transport).

```yaml
mcp_servers:
  github:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-github"]
    env_mapping:
      GITHUB_PERSONAL_ACCESS_TOKEN: ${GITHUB_TOKEN}
  
  jira:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-jira"]
    env_mapping:
      JIRA_API_TOKEN: ${JIRA_API_TOKEN}
      JIRA_URL: ${JIRA_URL}
  
  confluence:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-confluence"]
    env_mapping:
      CONFLUENCE_API_TOKEN: ${CONFLUENCE_API_TOKEN}
      CONFLUENCE_URL: ${CONFLUENCE_URL}
  
  filesystem:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"]
```

### 2. `graph.nodes` (Agent Definitions)

Add a new agent here; requires `id`, `type`, `model_preset`, `tools`, and `prompt_file`.

```yaml
nodes:
  - id: context_loader
    type: llm_node
    description: "Fetches requirements from GitHub/JIRA/Confluence."
    model_preset: default
    tools:
      - get_issue
      - search_issues
      - fetch_jira_issue
      - search_confluence
    prompt_file: prompts/context_loader/system.jinja2
    output_key: external_context

  - id: planner
    type: llm_node
    description: "Breaks down the ticket/requirements into a technical plan."
    model_preset: default
    tools:
      - read_file
      - list_directory
    prompt_file: prompts/planner/system.jinja2
    output_key: plan

  - id: coder
    type: llm_node
    description: "Implements code based on the plan and requirements."
    model_preset: coding
    tools:
      - write_file
      - run_shell_command
      - git_commit
    prompt_file: prompts/coder/system.jinja2
    output_key: code

  - id: reviewer
    type: llm_node
    description: "Performs static analysis, security, and logic checks."
    model_preset: reasoning
    tools:
      - git_diff
      - run_linter
    prompt_file: prompts/reviewer/system.jinja2
    output_key: review_report

  - id: human_approval
    type: interrupt_node
    description: "Pauses the workflow for human sign-off."
    output_key: human_decision

  - id: summarizer
    type: llm_node
    description: "Compresses long contexts and generates final reports."
    model_preset: default
    tools: []
    prompt_file: prompts/summarizer/system.jinja2
    output_key: final_summary
```

### 3. `graph.edges` & `conditional_edges`

Define the workflow flow.

```yaml
edges:
  - from: context_loader
    to: planner
  - from: planner
    to: coder
  - from: coder
    to: reviewer
  - from: summarizer
    to: END

conditional_edges:
  - from: reviewer
    condition: quality_threshold
    branches:
      approved: summarizer
      needs_work: coder
      reject: human_approval

  - from: human_approval
    condition: check_approval
    branches:
      approved: summarizer
      rejected: END
```

### 4. `graph.model_presets`

Map logical names to specific cloud/local models.

```yaml
model_presets:
  default:
    provider: ollama
    model: llama3.2
    temperature: 0.3
  
  coding:
    provider: anthropic
    model: claude-3-5-sonnet-20241022
    temperature: 0.2
  
  reasoning:
    provider: openai
    model: gpt-4o
    temperature: 0.4
```

---

## Environment Variables (Local vs Cloud)

| Env Var | Local (Docker Compose) | Cloud (GCP Cloud Run) |
| :--- | :--- | :--- |
| `POSTGRES_DSN` | `postgresql://agent:secret@postgres:5432/agentforge` | `postgresql://user:pass@10.x.x.x:5432/agentforge` |
| `REDIS_URL` | `redis://redis:6379` | `redis://10.x.x.x:6379` (Memorystore) |
| `VECTOR_DB_URL` | `http://qdrant:6333` | `https://your-qdrant-cloud.com:6333` |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | `http://ollama-vm.internal:11434` (GCE VM) |
| `CONTEXT_SOURCE` | `github` (for testing) | `jira` (for enterprise) |
| `DEFAULT_PROVIDER` | `ollama` | `anthropic` |
| `FALLBACK_PROVIDER` | (none) | `openai` |
| `JIRA_URL` | `http://jira-mock:8080` | `https://company.atlassian.net` |
| `CONFLUENCE_URL` | `http://confluence-mock:8081` | `https://company.atlassian.net/wiki` |
| `GITHUB_TOKEN` | `ghp_xxxxx` (personal) | `${{ secrets.GITHUB_TOKEN }}` (injected) |
| `ANTHROPIC_API_KEY` | (optional) | `${{ secrets.ANTHROPIC_API_KEY }}` |
| `OPENAI_API_KEY` | (optional) | `${{ secrets.OPENAI_API_KEY }}` |
| `GCP_PROJECT` | (not used) | `my-project-id` |
| `GCP_LOCATION` | (not used) | `us-central1` |
| `TASK_QUEUE` | (not used) | `agent-tasks` |
| `CLOUD_RUN_URL` | (not used) | `agentforge-xyz-uc.a.run.app` |
| `TASK_SA_EMAIL` | (not used) | `task-sa@project.iam.gserviceaccount.com` |

---

## Environment Selection Matrix

| Environment | Database | Cache | Vector DB | LLM Provider | Work Source |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Local (Dev)** | Postgres (container) | Redis (container) | Qdrant (container) | Ollama (container) | Mocks (JIRA/Confluence) |
| **CI (GitHub Actions)** | SQLite (in-memory) | Disabled | Disabled | Anthropic (API) | GitHub Issues + Mocks |
| **CI (Bitbucket Pipelines)** | SQLite (in-memory) | Disabled | Disabled | Anthropic (API) | JIRA Mocks |
| **Staging** | Cloud SQL (small) | Memorystore | Qdrant Cloud | Ollama + Anthropic fallback | JIRA/Confluence (test) |
| **Production** | Cloud SQL (scaled) | Memorystore | Qdrant Cloud | Anthropic/OpenAI | JIRA/Confluence (prod) |

---

## Adding a New Node (Zero Code Changes)

1.  **Add node definition** to `agents.yaml` under `nodes`.
2.  **Create prompt file** in `prompts/{node_id}/system.jinja2`.
3.  **Add edges** to connect the node in the workflow.
4.  **Restart the application.**

Example: Adding a "Documentation Generator":

```yaml
nodes:
  - id: docs_generator
    type: llm_node
    description: "Generates API documentation from code."
    model_preset: default
    tools:
      - read_file
      - write_file
    prompt_file: prompts/docs_generator/system.jinja2
    output_key: documentation
```

```yaml
edges:
  - from: summarizer
    to: docs_generator
  - from: docs_generator
    to: END
```